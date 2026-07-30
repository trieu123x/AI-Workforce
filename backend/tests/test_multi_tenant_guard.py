"""
Tests for RBAC Role Guards, Department Access Restrictions, and Multi-Tenant Isolation.
"""

def test_rbac_ceo_only_cost_summary(client, employee_token_headers):
    """Test Employee role getting 403 Forbidden when trying to access CEO-only cost summary."""
    response = client.get("/api/v1/audit/costs", headers=employee_token_headers)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"] or "role" in response.json()["detail"].lower()


def test_rbac_toggle_agent_forbidden_for_employee(client, employee_token_headers):
    """Test Employee role getting 403 Forbidden when trying to toggle agent status."""
    response = client.patch("/api/v1/agents/HR/toggle", headers=employee_token_headers)
    assert response.status_code == 403


def test_empty_message_validation(client, employee_token_headers):
    """Test 400 Bad Request error on empty chat message."""
    response = client.post("/api/v1/agent/chat", json={"agent_role": "HR", "message": "   "}, headers=employee_token_headers)
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()
