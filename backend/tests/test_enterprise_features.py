"""Regression tests for enterprise RBAC, task scopes and core workflow features."""

import uuid
from io import BytesIO

from app.models.models import AIAgent, User
from reportlab.pdfgen import canvas


def test_public_registration_always_creates_owner_workspace(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"owner-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Workspace Owner",
            "password": "Password123!",
            "tenant_name": "Isolated Workspace",
            "role": "CEO",
            "department": "ALL",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "Owner"
    assert response.json()["user"]["department"] == "BOARD"


def test_locked_account_token_is_rejected(
    client, employee_token_headers, transactional_db_session
):
    employee = transactional_db_session.query(User).filter(
        User.email == "employee@company.com"
    ).first()
    employee.is_active = False
    transactional_db_session.commit()
    try:
        response = client.get("/api/v1/users/me", headers=employee_token_headers)
        assert response.status_code == 403
    finally:
        employee.is_active = True
        transactional_db_session.commit()


def test_employee_cannot_list_organization(client, employee_token_headers):
    response = client.get("/api/v1/users-mgmt", headers=employee_token_headers)
    assert response.status_code == 403


def test_employee_task_scope(client, ceo_token_headers, employee_token_headers):
    employee = client.get("/api/v1/users/", headers=ceo_token_headers).json()
    employee_id = next(item["id"] for item in employee if item["email"] == "employee@company.com")
    private_task = client.post(
        "/api/v1/tasks",
        headers=ceo_token_headers,
        json={"title": "Board-only task", "status": "DRAFT"},
    )
    assigned_task = client.post(
        "/api/v1/tasks",
        headers=ceo_token_headers,
        json={
            "title": "Assigned employee task",
            "assignee_id": employee_id,
            "status": "PENDING",
        },
    )
    assert private_task.status_code == 201
    assert assigned_task.status_code == 201

    visible = client.get("/api/v1/tasks", headers=employee_token_headers)
    assert visible.status_code == 200
    titles = {item["title"] for item in visible.json()}
    assert "Assigned employee task" in titles
    assert "Board-only task" not in titles


def test_agent_tool_policy_is_enforced(
    client, employee_token_headers, transactional_db_session
):
    agent = transactional_db_session.query(AIAgent).filter(
        AIAgent.role_code == "HR"
    ).first()
    original_denied = list(agent.disallowed_actions or [])
    agent.disallowed_actions = ["query_leave_balance"]
    transactional_db_session.commit()
    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers=employee_token_headers,
            json={"agent_role": "HR", "message": "Tôi còn bao nhiêu ngày phép?"},
        )
        assert response.status_code == 403
    finally:
        agent.disallowed_actions = original_denied
        transactional_db_session.commit()


def test_workspace_departments_and_workflow_run(client, ceo_token_headers):
    code = f"QA_{uuid.uuid4().hex[:6].upper()}"
    department = client.post(
        "/api/v1/workspace/departments",
        headers=ceo_token_headers,
        json={"code": code, "name": "Quality Assurance"},
    )
    assert department.status_code == 201
    departments = client.get(
        "/api/v1/workspace/departments", headers=ceo_token_headers
    )
    assert code in {item["code"] for item in departments.json()}

    workflow = client.post(
        "/api/v1/workflows",
        headers=ceo_token_headers,
        json={
            "title": "Approval workflow",
            "trigger_type": "MANUAL",
            "nodes": [
                {
                    "id": "trigger",
                    "type": "TRIGGER",
                    "name": "Manual start",
                    "next": ["approval"],
                },
                {
                    "id": "approval",
                    "type": "HUMAN_APPROVAL",
                    "name": "Manager approval",
                    "config": {"risk_level": "HIGH"},
                },
            ],
        },
    )
    assert workflow.status_code == 201
    run = client.post(
        f"/api/v1/workflows/{workflow.json()['id']}/run",
        headers=ceo_token_headers,
    )
    assert run.status_code == 201
    assert run.json()["status"] == "AWAITING_APPROVAL"
    pending = client.get("/api/v1/approvals/pending", headers=ceo_token_headers)
    assert any(item["workflow_id"] == run.json()["id"] for item in pending.json())


def test_chat_history_feedback_and_task_conversion(client, employee_token_headers):
    chat = client.post(
        "/api/v1/agent/chat",
        headers=employee_token_headers,
        json={"agent_role": "KNOWLEDGE", "message": "Quy định công tác phí là gì?"},
    )
    assert chat.status_code == 200
    data = chat.json()
    conversation = client.get(
        f"/api/v1/agent/conversations/{data['conversation_id']}",
        headers=employee_token_headers,
    )
    assert conversation.status_code == 200
    assert len(conversation.json()["messages"]) >= 2
    feedback = client.post(
        f"/api/v1/agent/messages/{data['message_id']}/feedback",
        headers=employee_token_headers,
        json={"rating": 1, "comment": "Useful"},
    )
    assert feedback.status_code == 200
    task = client.post(
        f"/api/v1/agent/conversations/{data['conversation_id']}/task",
        headers=employee_token_headers,
        json={"title": "Follow up on travel policy"},
    )
    assert task.status_code == 201


def test_pdf_upload_is_extracted_and_indexed(client, ceo_token_headers):
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(72, 760, "Internal warranty policy: twelve months.")
    document.save()
    response = client.post(
        "/api/v1/documents/upload",
        headers=ceo_token_headers,
        data={"collection_name": "Product Policies", "department_access": "ALL"},
        files={"file": ("warranty-policy.pdf", buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "INDEXED"
    assert response.json()["chunks_created"] >= 1


def test_website_import_blocks_private_networks(client, ceo_token_headers):
    response = client.post(
        "/api/v1/documents/import-website",
        headers=ceo_token_headers,
        json={"url": "http://127.0.0.1:8000/docs", "department_access": "ALL"},
    )
    assert response.status_code == 422
    assert "Private or reserved" in response.json()["detail"]
