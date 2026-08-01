"""
Tests for AI Agents Catalog endpoints.
"""

from app.models.models import User


def _login(client, email: str):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_list_agents(client, ceo_token_headers):
    """Test listing all AI Agents for current organization."""
    response = client.get("/api/v1/agents/", headers=ceo_token_headers)
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) >= 7
    roles = [a["role_code"] for a in agents]
    assert "CEO" in roles
    assert "HR" in roles
    assert "KNOWLEDGE" in roles


def test_get_agent_by_role(client, ceo_token_headers):
    """Test fetching details of a specific AI Agent."""
    response = client.get("/api/v1/agents/HR", headers=ceo_token_headers)
    assert response.status_code == 200
    agent = response.json()
    assert agent["role_code"] == "HR"
    assert agent["avatar_emoji"] == "🧑‍💼"
    assert agent["system_prompt"] == "Managed by workspace administrators."
    assert agent["tools_access"] == []


def test_only_admin_or_owner_can_configure_agent(
    client,
    ceo_token_headers,
    transactional_db_session,
):
    """Business CEO can use HR data, while Admin/Owner control AI configuration."""
    forbidden = client.patch("/api/v1/agents/HR/toggle", headers=ceo_token_headers)
    assert forbidden.status_code == 403

    admin = transactional_db_session.query(User).filter(
        User.email == "legal.counsel@company.com"
    ).one()
    admin.role = "Admin"
    transactional_db_session.commit()
    admin_headers = _login(client, admin.email)

    options = client.get(
        "/api/v1/agents/HR/configuration-options",
        headers=admin_headers,
    )
    assert options.status_code == 200, options.text
    option_data = options.json()
    assert any(item["name"] == "get_employee_basic_profile" for item in option_data["tools"])
    assert not any(item["name"] == "get_employee_profile" for item in option_data["tools"])

    response = client.patch("/api/v1/agents/HR/toggle", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role_code"] == "HR"
    assert "is_active" in data

    # Toggle back to active
    client.patch("/api/v1/agents/HR/toggle", headers=admin_headers)

    document_selector = "*"
    if option_data["documents"]:
        document_selector = f"document:{option_data['documents'][0]['document_id']}"
    configured = client.patch(
        "/api/v1/agents/HR",
        headers=admin_headers,
        json={
            "tools_access": ["get_employee_basic_profile", "hybrid_rag_search"],
            "allowed_actions": ["get_employee_basic_profile", "hybrid_rag_search"],
            "disallowed_actions": [],
            "knowledge_access": [document_selector],
        },
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["knowledge_access"] == [document_selector]
