"""
HR Service providing employee tools for checking leave balances, submitting leave requests,
and querying HR data.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.models import User, UserMemory, AgentWorkflow, WorkflowApproval

logger = logging.getLogger(__name__)


def query_leave_balance(db: Session, user: User) -> dict:
    """Retrieves leave balance for a given user from user_memories or defaults."""
    memory = db.query(UserMemory).filter(
        UserMemory.user_id == user.id,
        UserMemory.memory_key == "leave_balance"
    ).first()

    if memory and memory.memory_value:
        try:
            balance_data = json.loads(memory.memory_value)
            return {
                "user_id": str(user.id),
                "user_name": user.full_name,
                "total_days": balance_data.get("total_days", 12),
                "used_days": balance_data.get("used_days", 0),
                "remaining_days": balance_data.get("remaining_days", 12),
            }
        except Exception:
            pass

    # Default fallback
    return {
        "user_id": str(user.id),
        "user_name": user.full_name,
        "total_days": 12,
        "used_days": 2,
        "remaining_days": 10,
    }


def request_leave(db: Session, user: User, days: int, reason: str, start_date: str = "Tới đây") -> dict:
    """
    Validates leave balance and creates a pending leave request workflow + WorkflowApproval card.
    """
    balance = query_leave_balance(db, user)
    remaining = balance["remaining_days"]

    if days > remaining:
        return {
            "success": False,
            "message": f"Không thể gửi đơn xin nghỉ phép. Bạn xin nghỉ {days} ngày nhưng chỉ còn {remaining} ngày phép chưa sử dụng.",
            "remaining_days": remaining,
        }

    # Create AgentWorkflow record
    workflow = AgentWorkflow(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        initiator_id=user.id,
        title=f"Đơn xin nghỉ phép {days} ngày — {user.full_name}",
        status="AWAITING_APPROVAL",
        dag_plan={
            "task": "Nghỉ phép",
            "days": days,
            "reason": reason,
            "start_date": start_date,
        },
    )
    db.add(workflow)
    db.flush()

    # Find Manager in tenant
    manager = db.query(User).filter(
        User.tenant_id == user.tenant_id,
        User.role.in_(["Manager", "CEO"])
    ).first()

    # Create WorkflowApproval card
    approval = WorkflowApproval(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        approver_id=manager.id if manager else None,
        action_type="XIN_NGHI_PHEP",
        payload={
            "requester_id": str(user.id),
            "requester_name": user.full_name,
            "requester_email": user.email,
            "days_requested": days,
            "remaining_days": remaining,
            "reason": reason,
            "start_date": start_date,
        },
        status="WAITING",
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db.add(approval)
    db.commit()

    return {
        "success": True,
        "message": f"Đã khởi tạo đơn xin nghỉ {days} ngày ({reason}). Đơn đã được chuyển tới Quản lý để phê duyệt.",
        "workflow_id": str(workflow.id),
        "approval_id": str(approval.id),
        "approval_card": {
            "id": str(approval.id),
            "action_type": "XIN NGHỈ PHÉP",
            "requester_name": user.full_name,
            "details": f"Xin nghỉ {days} ngày ({start_date}). Lý do: {reason}. Quỹ phép còn lại: {remaining} ngày.",
            "status": "WAITING",
        },
    }
