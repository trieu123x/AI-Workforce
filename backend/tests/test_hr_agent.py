"""
Tests for HR Agent intent handling, tool execution, leave balances, and Approval Cards.
"""

import json
from datetime import date, timedelta

from app.core.database import SyncSessionLocal
from app.models.models import AIAgent, User, UserMemory
from app.services.agents.agent_executor import _repair_hr_agent_capabilities


def test_stale_hr_agent_capabilities_are_split_into_narrow_profile_tools(
    client,
    employee_token_headers,
    transactional_db_session,
):
    agent = transactional_db_session.query(AIAgent).filter(
        AIAgent.role_code == "HR"
    ).first()
    agent.tools_access = [
        "query_leave_balance",
        "request_leave",
        "hybrid_rag_search",
        "get_employee_profile",
    ]
    agent.allowed_actions = list(agent.tools_access)
    agent.disallowed_actions = []
    agent.configuration_version = 1
    _repair_hr_agent_capabilities(agent)
    transactional_db_session.commit()

    assert "get_employee_profile" not in agent.tools_access
    assert "get_employee_basic_profile" in agent.tools_access
    assert "get_employee_full_profile" in agent.tools_access
    assert "query_company_users_sql" in agent.tools_access
    assert agent.configuration_version == 4

    response = client.post(
        "/api/v1/agent/chat",
        json={"agent_role": "HR", "message": "Hồ sơ của tôi"},
        headers=employee_token_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["hr_card"]["type"] == "EMPLOYEE_PROFILE"


def test_hr_company_user_sql_tool_respects_chat_actor_scope(
    client,
    employee_token_headers,
    ceo_token_headers,
):
    employee_response = client.post(
        "/api/v1/agent/chat",
        json={"agent_role": "HR", "message": "Danh sách nhân viên"},
        headers=employee_token_headers,
    )
    assert employee_response.status_code == 200, employee_response.text
    employee_data = employee_response.json()
    assert employee_data["tools_executed"][0]["tool_name"] == "query_company_users_sql"
    assert employee_data["hr_card"]["scope"] == "SELF"
    assert len(employee_data["hr_card"]["items"]) == 1
    assert employee_data["hr_card"]["items"][0]["employee"]["email"] == "employee@company.com"

    ceo_response = client.post(
        "/api/v1/agent/chat",
        json={"agent_role": "HR", "message": "Danh sách nhân viên"},
        headers=ceo_token_headers,
    )
    assert ceo_response.status_code == 200, ceo_response.text
    ceo_data = ceo_response.json()
    assert ceo_data["tools_executed"][0]["tool_name"] == "query_company_users_sql"
    assert ceo_data["hr_card"]["scope"] == "COMPANY"
    assert len(ceo_data["hr_card"]["items"]) > 1


def test_hr_leave_balance_query(client, employee_token_headers):
    """Test HR Agent handling leave balance inquiry."""
    payload = {
        "agent_role": "HR",
        "message": "Tôi còn bao nhiêu ngày phép?",
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "HR"
    assert "ngày phép" in data["reply"].lower()
    assert len(data["tools_executed"]) > 0
    assert data["tools_executed"][0]["tool_name"] == "query_leave_balance"
    assert data["hr_card"]["type"] == "LEAVE_BALANCE"

    conversation = client.get(
        f"/api/v1/agent/conversations/{data['conversation_id']}",
        headers=employee_token_headers,
    )
    assert conversation.status_code == 200
    assistant = conversation.json()["messages"][-1]
    assert assistant["attachments"][0]["type"] == "HR_CARD"
    assert assistant["attachments"][0]["payload"]["type"] == "LEAVE_BALANCE"


def test_hr_leave_request_creates_approval_card(client, employee_token_headers):
    """Test HR Agent handling leave submission and generating an Approval Card."""
    # Reset leave balance memory for employee to ensure deterministic quota
    db = SyncSessionLocal()
    try:
        user = db.query(User).filter(User.email == "employee@company.com").first()
        if user:
            mem = db.query(UserMemory).filter(
                UserMemory.user_id == user.id,
                UserMemory.memory_key == "leave_balance",
            ).first()
            if mem:
                mem.memory_value = json.dumps({"total_days": 12, "used_days": 2, "remaining_days": 10})
                db.commit()
    finally:
        db.close()

    start = date.today() + timedelta(days=30)
    while start.weekday() >= 5:
        start += timedelta(days=1)
    end = start + timedelta(days=1)
    while end.weekday() >= 5:
        end += timedelta(days=1)
    payload = {
        "agent_role": "HR",
        "message": (
            f"Tôi muốn xin nghỉ phép từ {start.isoformat()} đến {end.isoformat()} "
            "vì lý do gia đình"
        ),
    }
    response = client.post("/api/v1/agent/chat", json=payload, headers=employee_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_role"] == "HR"
    assert data["approval_card"] is not None
    card = data["approval_card"]
    assert card["action_type"] == "XIN NGHỈ PHÉP"
    assert card["status"] == "WAITING"
    assert "id" in card
