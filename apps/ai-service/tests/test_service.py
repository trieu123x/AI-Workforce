import math

from fastapi.testclient import TestClient

from app.main import app
from app.rag.embedding.factory import get_embedding_provider
from app.rag.evaluation.reranking_metrics import ndcg_at_k, reciprocal_rank
from app.rag.ingestion.chunker import chunk_document
from app.rag.reranking.base import BaseReranker
from app.rag.reranking.reranker import RerankPipeline


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "ai-service"


def test_accelerator_health_contract() -> None:
    response = client.get("/health/accelerator")
    assert response.status_code == 200
    payload = response.json()
    assert "cuda_available" in payload
    assert "torch_version" in payload


def test_business_boundary_chunking() -> None:
    chunks = chunk_document(
        "# Chính sách nghỉ phép\n"
        "Điều 1. Phạm vi\nÁp dụng toàn công ty.\n"
        "Khoản 1. Điều kiện\nNhân viên còn ngày phép.\n"
        "Bước 1: Gửi yêu cầu\nNhân viên tạo đơn."
    )
    assert [chunk["section_type"] for chunk in chunks] == [
        "heading", "article", "clause", "step"
    ]


def test_chunk_endpoint_contract() -> None:
    response = client.post("/v1/rag/chunk", json={"content": "## Quy trình\nNội dung."})
    assert response.status_code == 200
    chunk = response.json()["chunks"][0]
    assert chunk["section_title"] == "Quy trình"
    assert chunk["token_count"] == 5


def test_deterministic_embedding_contract() -> None:
    provider = get_embedding_provider()
    vectors = provider.embed(["same text", "same text"])
    assert vectors[0] == vectors[1]
    assert len(vectors[0]) == provider.dimension
    assert math.isclose(sum(value * value for value in vectors[0]), 1.0, rel_tol=1e-6)


def test_agent_route_contract() -> None:
    response = client.post("/v1/agents/route", json={"message": "Kiểm tra ngân sách tháng"})
    assert response.status_code == 200
    assert response.json()["role"] == "FINANCE"


class _FixedBGEReranker(BaseReranker):
    backend = "bge"
    model_name = "BAAI/bge-reranker-v2-m3"

    def score(self, query, documents, candidates):
        return [0.95, 0.30]


class _FailingReranker(BaseReranker):
    backend = "bge"
    model_name = "unavailable-bge"

    def score(self, query, documents, candidates):
        raise RuntimeError("model unavailable")


def _rerank_candidates() -> list[dict]:
    return [
        {
            "id": "leave",
            "document_title": "Chính sách nghỉ phép",
            "section_title": "Số ngày phép",
            "content": "Nhân viên có 12 ngày nghỉ phép mỗi năm.",
            "_dense_score": 0.80,
            "_sparse_score": 1.0,
            "_rrf_score": 1.0,
        },
        {
            "id": "travel",
            "content": "Quy định thanh toán công tác phí.",
            "_dense_score": 0.40,
            "_sparse_score": 0.1,
            "_rrf_score": 0.5,
        },
        {
            "id": "leave",
            "content": "Bản trùng không được rerank lần hai.",
        },
    ]



def test_bge_rerank_pipeline_contract() -> None:
    outcome = RerankPipeline(provider=_FixedBGEReranker()).run(
        "Tôi có bao nhiêu ngày nghỉ phép?",
        _rerank_candidates(),
        top_k=2,
    )
    assert outcome.candidates_scored == 2
    assert outcome.fallback_used is False
    assert outcome.model == "BAAI/bge-reranker-v2-m3"
    assert [item["id"] for item in outcome.results] == ["leave", "travel"]
    assert outcome.results[0]["rerank_model_score"] == 0.95



def test_rerank_pipeline_falls_back_to_lexical() -> None:
    outcome = RerankPipeline(provider=_FailingReranker()).run(
        "nghỉ phép 12 ngày",
        _rerank_candidates(),
        top_k=1,
    )
    assert outcome.fallback_used is True
    assert outcome.backend == "lexical"
    assert outcome.results[0]["id"] == "leave"


def test_rerank_endpoint_observability_contract() -> None:
    response = client.post("/v1/rag/rerank", json={
        "query": "nghỉ phép 12 ngày",
        "candidates": _rerank_candidates(),
        "top_k": 1,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] in {"bge", "lexical"}
    assert payload["candidates_scored"] == 2
    assert payload["fallback_used"] is False


def test_reranking_metrics() -> None:
    assert reciprocal_rank(["wrong", "right"], {"right"}) == 0.5
    assert math.isclose(
        ndcg_at_k(["a", "b"], {"a": 3.0, "b": 1.0}, 2),
        1.0,
    )
