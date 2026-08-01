"""
Tests for Human-in-the-loop (HITL) Workflow Approvals.
"""

from datetime import date, timedelta

def test_pending_approvals_list(client, ceo_token_headers):
    """Test fetching pending workflow approval cards."""
    response = client.get("/api/v1/approvals/pending", headers=ceo_token_headers)
    assert response.status_code == 200
    approvals = response.json()
    assert isinstance(approvals, list)


def test_approve_workflow_card(client, employee_token_headers, ceo_token_headers):
    """Test submitting leave request and CEO approving the generated card."""
    start = date.today() + timedelta(days=60)
    while start.weekday() >= 5:
        start += timedelta(days=1)
    end = start
    # 1. Employee submits leave request via HR Agent
    req_res = client.post(
        "/api/v1/agent/chat",
        json={
            "agent_role": "HR",
            "message": (
                f"Tôi muốn xin nghỉ phép từ {start.isoformat()} đến {end.isoformat()} "
                "vì có việc gia đình"
            ),
        },
        headers=employee_token_headers,
    )
    assert req_res.status_code == 200
    card = req_res.json()["approval_card"]
    assert card is not None
    approval_id = card["id"]

    # 2. CEO approves the pending workflow card
    app_res = client.post(
        f"/api/v1/approvals/{approval_id}/action",
        json={"action": "APPROVE", "comments": "Đồng ý cho nghỉ phép."},
        headers=ceo_token_headers,
    )
    assert app_res.status_code == 200
    data = app_res.json()
    assert data["status"] == "APPROVED"
    assert data["action_taken"] == "APPROVE"
