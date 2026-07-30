"""Human-in-the-loop approval gates with tenant and approver enforcement."""

import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.models import AgentWorkflow, AuditLog, User, UserMemory, WorkflowApproval

router = APIRouter(prefix="/approvals", tags=["Workflow Approvals"])
APPROVER_ROLES = {"Owner", "Admin", "CEO", "Manager"}


class ApprovalActionRequest(BaseModel):
    action: Literal["APPROVE", "REJECT", "EDIT_AND_APPROVE"]
    comments: Optional[str] = None
    edited_payload: Optional[dict[str, Any]] = None


def _can_approve(current_user: User, approval: WorkflowApproval) -> bool:
    if current_user.role not in APPROVER_ROLES:
        return approval.approver_id == current_user.id
    if approval.approver_id and approval.approver_id != current_user.id:
        return current_user.role in {"Owner", "Admin", "CEO"}
    return True


@router.get("/pending", summary="List pending approvals visible to the current approver")
def get_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    approvals = db.query(WorkflowApproval).join(AgentWorkflow).filter(
        AgentWorkflow.tenant_id == current_user.tenant_id,
        WorkflowApproval.status == "WAITING",
    ).order_by(WorkflowApproval.updated_at.desc()).all()
    return [
        {
            "id": str(approval.id),
            "workflow_id": str(approval.workflow_id),
            "workflow_title": approval.workflow.title,
            "action_type": approval.action_type,
            "risk_level": approval.risk_level,
            "payload": approval.payload,
            "reason": (approval.payload or {}).get("reason"),
            "requester": (approval.payload or {}).get("requester_name"),
            "data_sources": (approval.payload or {}).get("data_sources", []),
            "status": approval.status,
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
            "comments": approval.comments,
        }
        for approval in approvals
        if _can_approve(current_user, approval)
    ]


@router.post("/{approval_id}/action", summary="Approve, reject or edit-and-approve")
def process_approval_action(
    approval_id: UUID,
    req: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    approval = db.query(WorkflowApproval).join(AgentWorkflow).filter(
        WorkflowApproval.id == approval_id,
        AgentWorkflow.tenant_id == current_user.tenant_id,
    ).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if not _can_approve(current_user, approval):
        raise HTTPException(status_code=403, detail="You are not an eligible approver")
    if approval.status != "WAITING":
        raise HTTPException(status_code=409, detail=f"Approval is already {approval.status}")
    if approval.expires_at and approval.expires_at < datetime.now(timezone.utc):
        approval.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=410, detail="Approval request has expired")
    if req.action == "EDIT_AND_APPROVE" and req.edited_payload is None:
        raise HTTPException(status_code=422, detail="edited_payload is required")

    original_payload = approval.payload
    if req.action == "EDIT_AND_APPROVE":
        approval.payload = req.edited_payload
    approved = req.action in {"APPROVE", "EDIT_AND_APPROVE"}
    approval.status = "APPROVED" if approved else "REJECTED"
    approval.comments = req.comments
    approval.approver_id = current_user.id
    approval.workflow.status = "COMPLETED" if approved else "FAILED"
    approval.workflow.completed_at = datetime.now(timezone.utc)

    if approved and approval.action_type in {"XIN_NGHI_PHEP", "XIN NGHỈ PHÉP"}:
        request_payload = approval.payload or {}
        requester_id = request_payload.get("requester_id")
        days_requested = request_payload.get("days_requested", 1)
        if requester_id:
            memory = db.query(UserMemory).filter(
                UserMemory.tenant_id == current_user.tenant_id,
                UserMemory.user_id == requester_id,
                UserMemory.memory_key == "leave_balance",
            ).first()
            if memory and memory.memory_value:
                try:
                    data = json.loads(memory.memory_value)
                    data["used_days"] = data.get("used_days", 0) + days_requested
                    data["remaining_days"] = max(
                        0, data.get("total_days", 12) - data["used_days"]
                    )
                    memory.memory_value = json.dumps(data)
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass

    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        workflow_id=approval.workflow_id,
        agent_role="APPROVAL",
        tool_name=req.action.lower(),
        input_parameters={
            "approval_id": str(approval.id),
            "approver_id": str(current_user.id),
            "original_payload": original_payload,
        },
        output_result={"status": approval.status, "payload": approval.payload},
        execution_time_ms=0,
    ))
    db.commit()
    return {
        "id": str(approval.id),
        "status": approval.status,
        "action_taken": req.action,
        "payload": approval.payload,
        "message": f"Approval moved to {approval.status}.",
    }
