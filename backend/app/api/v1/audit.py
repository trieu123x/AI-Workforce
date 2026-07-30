"""
API Endpoints for Audit Logging and LLM Token Cost Metering.
"""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user, RoleRequired
from app.models.models import User
from app.schemas.costs import CostSummaryResponse
from app.services.audit_service import get_audit_logs, get_llm_cost_summary

router = APIRouter(prefix="/audit", tags=["Audit & Billing"])


@router.get(
    "/logs",
    summary="Query audit trail of agent tool executions (Manager & CEO only)",
    dependencies=[Depends(RoleRequired("Manager", "CEO"))],
)
def fetch_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    return get_audit_logs(db, current_user.tenant_id, limit=limit)


@router.get(
    "/costs",
    response_model=CostSummaryResponse,
    summary="Query LLM token usage and cost metering report (CEO only)",
    dependencies=[Depends(RoleRequired("CEO"))],
)
def fetch_cost_summary(
    month: str | None = Query(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CostSummaryResponse:
    return get_llm_cost_summary(db, current_user.tenant_id, month)
