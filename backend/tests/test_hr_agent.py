"""
Tests for HR Agent intent handling, tool execution, leave balances, and Approval Cards.
"""

import json
from app.core.database import SyncSessionLocal
from app.models.models import User, UserMemory


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

    payload = {
        "agent_role": "HR",
        "message": "Tôi muốn xin nghỉ phép 2 ngày vào tuần tới vì lý do gia đình",
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
