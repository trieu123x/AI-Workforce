"""Operational management analytics, separate from the existing CEO dashboard."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.models import (
    AIAgent,
    AgentWorkflow,
    AuditLog,
    ChatConversation,
    ChatMessage,
    LLMCostLog,
    Task,
    User,
    WorkflowApproval,
)

router = APIRouter(prefix="/management", tags=["Management Analytics"])
MANAGEMENT_ROLES = {"Owner", "Admin", "CEO", "Manager"}


def _percentage(numerator: int | float, denominator: int | float) -> float:
    return round((numerator / denominator * 100) if denominator else 0.0, 1)


@router.get("/dashboard", summary="Get actionable management analytics")
def get_management_dashboard(
    period: Literal["7d", "30d", "90d"] = Query("30d"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    if current_user.role not in MANAGEMENT_ROLES:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Management analytics access denied")

    days = {"7d": 7, "30d": 30, "90d": 90}[period]
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    tenant_id = current_user.tenant_id

    task_query = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.updated_at >= start,
    )
    visible_user_ids = None
    if current_user.role == "Manager":
        visible_user_ids = db.query(User.id).filter(
            User.tenant_id == tenant_id,
            User.department == current_user.department,
        )
        task_query = task_query.filter(
            or_(
                Task.creator_id.in_(visible_user_ids),
                Task.assignee_id.in_(visible_user_ids),
            )
        )
    tasks = task_query.all()
    completed = [task for task in tasks if task.status == "COMPLETED"]
    failed = [task for task in tasks if task.status == "FAILED"]
    overdue = [
        task
        for task in tasks
        if task.due_date
        and task.due_date < now
        and task.status not in {"COMPLETED", "CANCELLED", "FAILED"}
    ]
    at_risk = [
        task
        for task in tasks
        if task.due_date
        and now <= task.due_date <= now + timedelta(hours=48)
        and task.status not in {"COMPLETED", "CANCELLED", "FAILED"}
    ]

    workflow_query = db.query(AgentWorkflow).filter(
        AgentWorkflow.tenant_id == tenant_id,
        AgentWorkflow.created_at >= start,
    )
    if visible_user_ids is not None:
        workflow_query = workflow_query.filter(
            AgentWorkflow.initiator_id.in_(visible_user_ids)
        )
    workflows = workflow_query.all()
    failed_workflows = [workflow for workflow in workflows if workflow.status == "FAILED"]

    approval_query = db.query(WorkflowApproval).join(AgentWorkflow).filter(
        AgentWorkflow.tenant_id == tenant_id,
        WorkflowApproval.updated_at >= start,
    )
    if visible_user_ids is not None:
        approval_query = approval_query.filter(
            AgentWorkflow.initiator_id.in_(visible_user_ids)
        )
    approvals = approval_query.all()
    approved_count = sum(item.status == "APPROVED" for item in approvals)
    rejected_count = sum(item.status == "REJECTED" for item in approvals)
    pending_count = sum(item.status == "WAITING" for item in approvals)

    cost_query = db.query(LLMCostLog).filter(
        LLMCostLog.tenant_id == tenant_id,
        LLMCostLog.created_at >= start,
        LLMCostLog.usage_source.in_(("PROVIDER", "MANUAL_IMPORT")),
    )
    if current_user.role == "Manager":
        cost_query = cost_query.filter(
            LLMCostLog.department == current_user.department
        )
    cost_logs = cost_query.all()
    token_usage = sum(
        row.prompt_tokens + row.completion_tokens for row in cost_logs
    )
    estimated_cost = round(sum(float(row.estimated_cost_usd) for row in cost_logs), 6)

    audit_query = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.created_at >= start,
    )
    if current_user.role == "Manager":
        audit_query = audit_query.filter(
            AuditLog.agent_role.in_((current_user.department, "TASK", "APPROVAL"))
        )
    audit_rows = audit_query.all()
    measured_execution = [
        row.execution_time_ms
        for row in audit_rows
        if row.execution_time_ms is not None and row.execution_time_ms >= 0
    ]
    average_execution_seconds = round(
        (sum(measured_execution) / len(measured_execution) / 1000)
        if measured_execution
        else 0.0,
        2,
    )

    agent_query = db.query(AIAgent).filter(
        AIAgent.tenant_id == tenant_id,
        AIAgent.is_active.is_(True),
    )
    if current_user.role == "Manager":
        agent_query = agent_query.filter(
            AIAgent.role_code.in_((current_user.department, "KNOWLEDGE"))
        )
    active_agents = agent_query.all()

    agent_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"executions": 0, "failures": 0, "execution_time_ms": 0}
    )
    for row in audit_rows:
        role = row.agent_role or "SYSTEM"
        if role in {"TASK", "APPROVAL", "SYSTEM"}:
            continue
        stats = agent_stats[role]
        stats["executions"] += 1
        stats["failures"] += int((row.status or "SUCCESS") == "FAILED")
        stats["execution_time_ms"] += row.execution_time_ms or 0
    agent_name_map = {agent.role_code: agent.name for agent in active_agents}
    agent_performance = []
    for role, stats in agent_stats.items():
        successes = stats["executions"] - stats["failures"]
        agent_performance.append(
            {
                "role": role,
                "name": agent_name_map.get(role, f"{role} Agent"),
                "executions": stats["executions"],
                "failures": stats["failures"],
                "success_rate": _percentage(successes, stats["executions"]),
                "average_execution_seconds": round(
                    stats["execution_time_ms"] / max(stats["executions"], 1) / 1000,
                    2,
                ),
            }
        )
    agent_performance.sort(
        key=lambda item: (-item["success_rate"], -item["executions"], item["role"])
    )

    workflow_failure_counts: dict[str, int] = defaultdict(int)
    for workflow in failed_workflows:
        workflow_failure_counts[workflow.title] += 1

    feedback_query = (
        db.query(ChatMessage.feedback_rating)
        .join(ChatConversation)
        .filter(
            ChatConversation.tenant_id == tenant_id,
            ChatMessage.sender == "ASSISTANT",
            ChatMessage.feedback_rating.isnot(None),
            ChatMessage.created_at >= start,
        )
    )
    if visible_user_ids is not None:
        feedback_query = feedback_query.filter(
            ChatConversation.user_id.in_(visible_user_ids)
        )
    ratings = [value for (value,) in feedback_query.all()]
    positive_ratings = sum(value > 0 for value in ratings)

    baseline_hours_per_completed_task = 1.5
    measured_ai_hours = sum(measured_execution) / 3_600_000
    hours_saved = round(
        max(len(completed) * baseline_hours_per_completed_task - measured_ai_hours, 0),
        1,
    )

    return {
        "period": {
            "key": period,
            "from": start.isoformat(),
            "to": now.isoformat(),
            "department_scope": (
                current_user.department if current_user.role == "Manager" else "ALL"
            ),
        },
        "kpis": {
            "tasks_completed": len(completed),
            "success_rate": _percentage(len(completed), len(completed) + len(failed)),
            "average_execution_seconds": average_execution_seconds,
            "human_approval_rate": _percentage(
                approved_count, approved_count + rejected_count
            ),
            "pending_approvals": pending_count,
            "failed_workflows": len(failed_workflows),
            "token_usage": token_usage,
            "estimated_cost_usd": estimated_cost,
            "hours_saved": hours_saved,
            "active_agents": len(active_agents),
            "user_satisfaction": _percentage(positive_ratings, len(ratings)),
        },
        "task_health": {
            "total": len(tasks),
            "failed": len(failed),
            "overdue": len(overdue),
            "at_risk": len(at_risk),
            "attention": [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "status": "OVERDUE" if task in overdue else task.status,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "assignee": task.assignee.full_name if task.assignee else None,
                }
                for task in sorted(
                    overdue + at_risk,
                    key=lambda item: item.due_date or now,
                )[:10]
            ],
        },
        "agent_performance": agent_performance[:10],
        "workflow_failures": [
            {"workflow": title, "failures": count}
            for title, count in sorted(
                workflow_failure_counts.items(), key=lambda item: -item[1]
            )[:10]
        ],
        "methodology": {
            "hours_saved": (
                f"{baseline_hours_per_completed_task} baseline hours per completed "
                "task minus measured AI execution time."
            ),
            "user_satisfaction": "Percentage of positive rated assistant messages.",
            "cost": "Provider and approved manual-import usage snapshots only.",
        },
    }
