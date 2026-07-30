"""
Tests for Hybrid RAG Engine, document ingestion, vector search, and Knowledge Agent inline citations.
"""

def test_list_documents(client, ceo_token_headers):
    """Test listing documents in Knowledge Base."""
    response = client.get("/api/v1/documents/", headers=ceo_token_headers)
    assert response.status_code == 200
    docs = response.json()
    assert isinstance(docs, list)
    assert len(docs) > 0
    doc_names = [d["document_name"] for d in docs]
    assert "Chinh_sach_Nghi_phep_2025.md" in doc_names


def test_ingest_text_document(client, ceo_token_headers):
    """Test ingesting new markdown document text into RAG store."""
    payload = {
        "document_name": "Quy_dinh_Bao_mat_2025.md",
        "content": "# Quy Định Bảo Mật Thông Tin\n1. Tất cả nhân viên không được chia sẻ mật khẩu tài khoản.\n2. Thiết bị công ty phải đặt mật khẩu khóa màn hình sau 5 phút.",
        "department_access": "ALL",
    }
    response = client.post("/api/v1/documents/ingest-text", data=payload, headers=ceo_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["chunks_created"] > 0


def test_hybrid_rag_search(client, ceo_token_headers):
    """Test Hybrid RAG search returning top scored chunks."""
    payload = {
        "query": "nghỉ phép bao nhiêu ngày",
        "top_k": 3,
    }
    response = client.post("/api/v1/documents/search", json=payload, headers=ceo_token_headers)
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) > 0
    assert "citation_tag" in results[0]
    assert results[0]["score"] > 0.0


def test_knowledge_agent_chat_citations(client, employee_token_headers):
    """Test Knowledge Agent generating response with inline citation tags."""
    payload = {
        "agent_role": "KNOWLEDGE",
        "message": "Chi phí di chuyển công tác phí tối đa là bao nhiêu?",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "KNOWLEDGE"
    assert len(data["citations"]) > 0
    assert "[Citation:" in data["reply"]
