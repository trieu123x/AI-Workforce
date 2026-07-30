"""
Tests for Audit Logging & LLM Token Cost Metering endpoints.
"""

def test_fetch_audit_logs(client, ceo_token_headers):
    """Test fetching audit trail of tool executions."""
    # 1. Trigger an agent chat to generate audit records
    client.post(
        "/api/v1/agent/chat",
        json={"agent_role": "HR", "message": "Tôi còn bao nhiêu ngày phép?"},
        headers=ceo_token_headers,
    )

    # 2. Fetch audit logs
    response = client.get("/api/v1/audit/logs", headers=ceo_token_headers)
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert "agent_role" in logs[0]
    assert "tool_name" in logs[0]


def test_fetch_llm_cost_summary(client, ceo_token_headers):
    """Test fetching LLM token usage and cost metering report."""
    response = client.get("/api/v1/audit/costs", headers=ceo_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "total_tokens" in data
    assert "total_estimated_cost_usd" in data
    assert "legacy_records_excluded" in data
    assert data["total_requests"] >= 0
    assert data["total_estimated_cost_usd"] >= 0


def test_deterministic_agent_does_not_claim_provider_usage(
    client, ceo_token_headers
):
    before = client.get(
        "/api/v1/costs/summary", headers=ceo_token_headers
    ).json()["total_requests"]
    response = client.post(
        "/api/v1/agent/chat",
        json={"agent_role": "HR", "message": "Tôi còn bao nhiêu ngày phép?"},
        headers=ceo_token_headers,
    )
    assert response.status_code == 200
    after = client.get(
        "/api/v1/costs/summary", headers=ceo_token_headers
    ).json()["total_requests"]
    assert after == before


def test_cost_month_validation(client, ceo_token_headers):
    response = client.get(
        "/api/v1/costs/summary?month=2026-13",
        headers=ceo_token_headers,
    )
    assert response.status_code == 422
