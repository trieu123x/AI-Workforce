from datetime import date
from typing import Any


def is_authorized_chunk(
    chunk: dict[str, Any],
    *,
    tenant_id: str,
    role: str,
    department: str,
    as_of: date | None = None,
) -> bool:
    if str(chunk.get("tenant_id")) != str(tenant_id):
        return False
    today = as_of or date.today()
    if chunk.get("status", "active") != "active":
        return False
    effective = chunk.get("effective_date")
    expiration = chunk.get("expiration_date")
    if effective and date.fromisoformat(str(effective)) > today:
        return False
    if expiration and date.fromisoformat(str(expiration)) < today:
        return False
    if chunk.get("department", chunk.get("department_access", "ALL")) not in {"ALL", department}:
        return False
    allowed = {str(item).lower() for item in chunk.get("allowed_roles", [])}
    principals = {role.lower(), department.lower()}
    if allowed and not principals.intersection(allowed):
        return False
    return chunk.get("confidentiality") != "restricted" or bool(allowed)
