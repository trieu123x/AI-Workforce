"""
Tests for CEO Master Agent DAG Task Decomposition & Execution Synthesis.
"""

def test_ceo_dag_plan_generation(client, ceo_token_headers):
    """Test CEO Agent decomposing an onboarding directive into a structured DAG graph."""
    payload = {
        "agent_role": "CEO",
        "message": "Onboard nhân viên mới Lê Văn B vào vị trí IT Support",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=ceo_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "CEO"
    assert "BÁO CÁO ĐIỀU PHỐI CEO" in data["reply"]
    assert data["dag_plan_card"] is not None
    card = data["dag_plan_card"]
    assert card["overall_status"] == "COMPLETED"
    assert len(card["nodes"]) == 4
    
    assigned_agents = [n["assigned_agent"] for n in card["nodes"]]
    assert "HR" in assigned_agents
    assert "IT" in assigned_agents
    assert "FINANCE" in assigned_agents
    assert "KNOWLEDGE" in assigned_agents
