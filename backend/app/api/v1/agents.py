"""Tenant-safe AI Employee configuration and operational statistics."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import RoleRequired, get_current_active_user
from app.models.models import AIAgent, AgentWorkflow, AuditLog, LLMCostLog, User
from app.schemas.schemas import AIAgentResponse
from app.services.auth_service import ensure_tenant_default_agents

router = APIRouter(prefix="/agents", tags=["AI Agents"])


class AIAgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=4000)
    system_prompt: Optional[str] = Field(None, min_length=10)
    model_name: Optional[str] = Field(None, min_length=2, max_length=100)
    tools_access: Optional[list[str]] = None
    allowed_actions: Optional[list[str]] = None
    disallowed_actions: Optional[list[str]] = None
    knowledge_access: Optional[list[str]] = None
    is_active: Optional[bool] = None


def _get_tenant_agent(db: Session, tenant_id, role_code: str) -> AIAgent:
    agent = db.query(AIAgent).filter(
        AIAgent.tenant_id == tenant_id,
        AIAgent.role_code == role_code.upper(),
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{role_code}' not found")
    return agent


@router.get("/", response_model=List[AIAgentResponse], summary="List tenant AI Employees")
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AIAgentResponse]:
    agents = ensure_tenant_default_agents(db, current_user.tenant_id)
    return [AIAgentResponse.model_validate(agent) for agent in agents]


@router.get("/{role_code}/stats", summary="Get AI Employee history, cost and success rate")
def get_agent_stats(
    role_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    agent = _get_tenant_agent(db, current_user.tenant_id, role_code)
    agent_workflows = [
        workflow
        for workflow in db.query(AgentWorkflow).filter(
            AgentWorkflow.tenant_id == current_user.tenant_id
        ).all()
        if (workflow.dag_plan or {}).get("agent_role") == agent.role_code
    ]
    workflow_total = len(agent_workflows)
    successful = sum(workflow.status == "COMPLETED" for workflow in agent_workflows)
    audit_query = db.query(AuditLog).filter(
        AuditLog.tenant_id == current_user.tenant_id,
        AuditLog.agent_role == agent.role_code,
    )
    total_cost = db.query(func.coalesce(func.sum(LLMCostLog.estimated_cost_usd), 0)).filter(
        LLMCostLog.tenant_id == current_user.tenant_id,
        LLMCostLog.agent_role == agent.role_code,
        LLMCostLog.usage_source.in_(("PROVIDER", "MANUAL_IMPORT")),
    ).scalar()
    history = [
        {
            "id": str(item.id),
            "tool_name": item.tool_name,
            "input_parameters": item.input_parameters,
            "output_result": item.output_result,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in audit_query.order_by(AuditLog.created_at.desc()).limit(20).all()
    ]
    executions = audit_query.count()
    denominator = workflow_total or executions
    success_rate = round(successful / denominator * 100, 1) if denominator else 0.0
    return {
        "role_code": agent.role_code,
        "executions": executions,
        "workflow_total": workflow_total,
        "successful_workflows": successful,
        "success_rate": success_rate,
        "cost_usd": round(float(total_cost or 0), 6),
        "history": history,
    }


@router.get("/{role_code}", response_model=AIAgentResponse, summary="Get an AI Employee")
def get_agent(
    role_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AIAgentResponse:
    return AIAgentResponse.model_validate(
        _get_tenant_agent(db, current_user.tenant_id, role_code)
    )


@router.patch(
    "/{role_code}",
    response_model=AIAgentResponse,
    summary="Configure an AI Employee",
    dependencies=[Depends(RoleRequired("Owner", "Admin", "CEO"))],
)
def update_agent(
    role_code: str,
    req: AIAgentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AIAgentResponse:
    agent = _get_tenant_agent(db, current_user.tenant_id, role_code)
    data = req.model_dump(exclude_unset=True)
    if "allowed_actions" in data and "disallowed_actions" in data:
        overlap = set(data["allowed_actions"]) & set(data["disallowed_actions"])
        if overlap:
            raise HTTPException(
                status_code=422,
                detail=f"Actions cannot be both allowed and disallowed: {', '.join(sorted(overlap))}",
            )
    for field_name, value in data.items():
        setattr(agent, field_name, value)
    db.commit()
    db.refresh(agent)
    return AIAgentResponse.model_validate(agent)


@router.patch(
    "/{role_code}/toggle",
    summary="Toggle AI Employee active status",
    dependencies=[Depends(RoleRequired("Owner", "Admin", "CEO"))],
)
def toggle_agent(
    role_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    agent = _get_tenant_agent(db, current_user.tenant_id, role_code)
    agent.is_active = not agent.is_active
    db.commit()
    return {"role_code": agent.role_code, "is_active": agent.is_active}
