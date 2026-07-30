"""
Tests for Sprint 3 Specialized AI Employees: Legal Agent, IT Agent, Finance Agent, and Sales Agent.
"""

def test_legal_agent_contract_audit(client, employee_token_headers):
    """Test Legal Agent auditing contract text and returning high-risk findings + docx redline link."""
    payload = {
        "agent_role": "LEGAL",
        "message": "Hợp đồng dịch vụ với mức phạt vi phạm 30% và đơn phương chấm dứt hợp đồng ngay lập tức.",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "LEGAL"
    assert data["legal_risk_card"] is not None
    card = data["legal_risk_card"]
    assert card["total_risks_found"] > 0
    assert "docx_download_url" in card
    assert len(data["tools_executed"]) > 0
    assert data["tools_executed"][0]["tool_name"] == "audit_contract_risk"


def test_it_agent_jira_ticket(client, employee_token_headers):
    """Test IT Agent handling technical error report and creating Jira Ticket card."""
    payload = {
        "agent_role": "IT",
        "message": "VPN bị đứt kết nối khẩn cấp không thể kết nối mạng công ty",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "IT"
    assert data["jira_card"] is not None
    card = data["jira_card"]
    assert "IT-" in card["ticket_key"]
    assert card["priority"] == "HIGH"
    assert card["status"] == "OPEN"
    assert len(data["tools_executed"]) > 0


def test_finance_agent_invoice_audit(client, employee_token_headers):
    """Test Finance Agent auditing invoice text and reconciling PO database."""
    payload = {
        "agent_role": "FINANCE",
        "message": "Hóa đơn PO-2025-098 tổng tiền 15.000.000 VNĐ từ Công ty TNHH Thiết Bị Số",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "FINANCE"
    assert data["invoice_card"] is not None
    card = data["invoice_card"]
    assert card["po_number"] == "PO-2025-098"
    assert len(card["anomalies"]) > 0
    assert card["status"] == "DISCREPANCY_FLAGGED"


def test_sales_agent_quotation(client, employee_token_headers):
    """Test Sales Agent generating product quotation payload and PDF card."""
    payload = {
        "agent_role": "SALES",
        "message": "Tôi muốn xin báo giá 20 camera AI IP Security",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "SALES"
    assert data["quote_card"] is not None
    card = data["quote_card"]
    assert "Camera AI" in card["items"][0]["name"]
    assert card["items"][0]["quantity"] == 20
    assert "pdf_url" in card
