"""
Tests for AI Agents Catalog endpoints.
"""

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
    assert "system_prompt" in agent


def test_toggle_agent_status(client, ceo_token_headers):
    """Test CEO toggling an agent's active status."""
    response = client.patch("/api/v1/agents/HR/toggle", headers=ceo_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role_code"] == "HR"
    assert "is_active" in data

    # Toggle back to active
    client.patch("/api/v1/agents/HR/toggle", headers=ceo_token_headers)
