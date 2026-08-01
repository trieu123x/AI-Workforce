"""Central policy engine for tenant-safe, purpose-limited AI HR access."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.models import User
from app.services.hr_service import authorized_employee_ids

HR_DATA_SECTIONS = {
    "BASIC",
    "PRIVATE",
    "CONTRACT",
    "COMPENSATION",
    "LEAVE",
    "PERFORMANCE",
    "DISCIPLINE",
    "HR_NOTES",
    "DOCUMENTS",
}

SECTION_PERMISSIONS = {
    "BASIC": "employee.basic.read",
    "PRIVATE": "employee.private.read",
    "CONTRACT": "employee.contract.read",
    "COMPENSATION": "employee.compensation.read",
    "LEAVE": "employee.leave.read",
    "PERFORMANCE": "employee.performance.read",
    "DISCIPLINE": "employee.discipline.read",
    "HR_NOTES": "employee.hr_notes.read",
    "DOCUMENTS": "employee.documents.read",
}

PURPOSE_SECTIONS = {
    "SELF_SERVICE": {"BASIC", "PRIVATE", "CONTRACT", "COMPENSATION", "LEAVE"},
    "DIRECTORY_LOOKUP": {"BASIC"},
    "LEAVE_MANAGEMENT": {"BASIC", "LEAVE"},
    "CONTRACT_RENEWAL": {"BASIC", "CONTRACT"},
    "CONTRACT_STATUS_MONITORING": {"BASIC", "CONTRACT"},
    "ONBOARDING": {"BASIC", "PRIVATE", "CONTRACT", "DOCUMENTS"},
    "PERFORMANCE_REVIEW": {"BASIC", "PERFORMANCE"},
    "PAYROLL_PROCESSING": {"BASIC", "COMPENSATION"},
    "HR_OPERATIONS": {"BASIC", "PRIVATE", "CONTRACT", "LEAVE", "DOCUMENTS"},
    "LEGAL_REVIEW": {"BASIC", "CONTRACT", "DISCIPLINE", "DOCUMENTS"},
    "EMPLOYEE_SUPPORT": {"BASIC", "PRIVATE", "LEAVE"},
    "EXECUTIVE_REVIEW": {
        "BASIC",
        "CONTRACT",
        "COMPENSATION",
        "LEAVE",
        "PERFORMANCE",
    },
}


@dataclass(frozen=True)
class EmployeeAccessDecision:
    allowed: bool
    scope: str
    purpose: str
    allowed_sections: tuple[str, ...] = ()
    denied_sections: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    denial_reasons: dict[str, str] = field(default_factory=dict)


def normalize_sections(sections: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(section).strip().upper() for section in sections if section))


def _scope_for_employee(db: Session, actor: User, target: User) -> tuple[bool, str, str | None]:
    if actor.tenant_id != target.tenant_id:
        return False, "NONE", "CROSS_TENANT"
    if actor.id == target.id:
        return True, "SELF", None
    if actor.role in {"Owner", "CEO"}:
        return True, "COMPANY", None
    if target.id in authorized_employee_ids(db, actor):
        return True, "REPORTING_TREE", None
    return False, "NONE", "OUTSIDE_SCOPE"


def _role_sections(actor: User, target: User) -> set[str]:
    if actor.id == target.id:
        return {"BASIC", "PRIVATE", "CONTRACT", "COMPENSATION", "LEAVE"}
    if actor.role in {"Owner", "CEO"}:
        return set(HR_DATA_SECTIONS)
    if actor.role == "Admin" and actor.department == "HR":
        return set(HR_DATA_SECTIONS)
    if actor.department == "HR" and actor.role == "Manager":
        return {"BASIC", "PRIVATE", "CONTRACT", "LEAVE", "PERFORMANCE", "DOCUMENTS"}
    if actor.department == "FINANCE" and actor.role in {"Admin", "Manager"}:
        return {"BASIC", "COMPENSATION"}
    if actor.role in {"Admin", "Manager"}:
        return {"BASIC", "CONTRACT", "LEAVE", "PERFORMANCE"}
    return set()


def authorize_employee_access(
    db: Session,
    *,
    actor: User,
    target: User,
    requested_sections: Iterable[str],
    purpose: str,
) -> EmployeeAccessDecision:
    """Apply tenant, scope, RBAC, field and purpose checks in one place."""
    requested = normalize_sections(requested_sections)
    normalized_purpose = str(purpose or "").strip().upper()
    if normalized_purpose not in PURPOSE_SECTIONS:
        return EmployeeAccessDecision(
            allowed=False,
            scope="NONE",
            purpose=normalized_purpose or "UNSPECIFIED",
            denied_sections=requested,
            denial_reasons={section: "INVALID_PURPOSE" for section in requested},
        )

    in_scope, scope, scope_denial = _scope_for_employee(db, actor, target)
    if not in_scope:
        return EmployeeAccessDecision(
            allowed=False,
            scope=scope,
            purpose=normalized_purpose,
            denied_sections=requested,
            denial_reasons={section: scope_denial or "OUTSIDE_SCOPE" for section in requested},
        )

    role_sections = _role_sections(actor, target)
    purpose_sections = PURPOSE_SECTIONS[normalized_purpose]
    allowed_sections: list[str] = []
    denied_sections: list[str] = []
    denial_reasons: dict[str, str] = {}
    for section in requested:
        if section not in HR_DATA_SECTIONS:
            denied_sections.append(section)
            denial_reasons[section] = "UNSUPPORTED_SECTION"
        elif section not in role_sections:
            denied_sections.append(section)
            denial_reasons[section] = "MISSING_PERMISSION"
        elif section not in purpose_sections:
            denied_sections.append(section)
            denial_reasons[section] = "PURPOSE_LIMITATION"
        else:
            allowed_sections.append(section)
    return EmployeeAccessDecision(
        allowed=bool(allowed_sections),
        scope=scope,
        purpose=normalized_purpose,
        allowed_sections=tuple(allowed_sections),
        denied_sections=tuple(denied_sections),
        permissions=tuple(SECTION_PERMISSIONS[section] for section in allowed_sections),
        denial_reasons=denial_reasons,
    )
