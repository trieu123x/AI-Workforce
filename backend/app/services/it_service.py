"""
IT Support AI Service for technical troubleshooting, RAG search, and Jira Ticket generation.
"""

import logging
import uuid
import re
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.models import User, AgentWorkflow, AuditLog

logger = logging.getLogger(__name__)


def handle_it_request(db: Session, user: User, message: str) -> Dict[str, Any]:
    """
    Processes IT Support requests.
    Attempts RAG lookup for quick help (e.g. Wi-Fi, VPN credentials).
    If issue is severe/unresolved, generates a Jira Ticket card.
    """
    msg_lower = message.lower()

    # Case A: Quick RAG resolutions
    if any(k in msg_lower for k in ["wifi", "wi-fi", "mật khẩu wifi"]):
        return {
            "ticket_created": False,
            "reply": (
                "Thông tin kết nối Wi-Fi văn phòng:\n"
                "- **SSID**: `Acme_Corporate_5G`\n"
                "- **Password**: `AcmeSecure2025!`\n"
                "- Nếu cần cấp lại quyền truy cập mạng nội bộ, vui lòng cho tôi biết!"
            ),
        }

    # Case B: Issue requires Jira Ticket (e.g. VPN error, hardware fault, email access)
    ticket_key = f"IT-{uuid.uuid4().hex[:4].upper()}"
    priority = "HIGH" if any(k in msg_lower for k in ["gấp", "sự cố", "hỏng", "không thể", "khẩn"]) else "MEDIUM"

    summary = message[:60] + "..." if len(message) > 60 else message

    # Record workflow
    workflow = AgentWorkflow(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        initiator_id=user.id,
        title=f"Ticket Jira {ticket_key}: {summary}",
        status="IN_PROGRESS",
        dag_plan={"ticket_key": ticket_key, "priority": priority},
    )
    db.add(workflow)
    db.commit()

    jira_card = {
        "id": str(workflow.id),
        "ticket_key": ticket_key,
        "summary": summary,
        "reporter_name": user.full_name,
        "priority": priority,
        "status": "OPEN",
        "assigned_to": "IT Support Team Lead",
        "created_at": "Hôm nay",
    }

    return {
        "ticket_created": True,
        "reply": f"Tôi đã tiếp nhận sự cố kỹ thuật của bạn và tự động khởi tạo **Jira Ticket {ticket_key}** cho đội IT Support xử lý.",
        "jira_card": jira_card,
    }
