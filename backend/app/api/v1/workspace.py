"""Workspace settings and dynamic department management."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.models import Department, Tenant, User

router = APIRouter(prefix="/workspace", tags=["Workspace Management"])
ADMIN_ROLES = {"Owner", "Admin", "CEO"}


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)


class DepartmentCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern="^[A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


def _require_admin(current_user: User) -> None:
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Only Owner/Admin can manage the workspace")


def _serialize_department(department: Department, member_count: int = 0) -> dict:
    return {
        "id": str(department.id),
        "code": department.code,
        "name": department.name,
        "description": department.description,
        "is_active": department.is_active,
        "member_count": member_count,
        "created_at": department.created_at.isoformat() if department.created_at else None,
    }


@router.get("", summary="Get current workspace")
def get_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "domain": tenant.domain,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "current_user_role": current_user.role,
    }


@router.patch("", summary="Update current workspace")
def update_workspace(
    req: WorkspaceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if req.name is not None:
        tenant.name = req.name.strip()
    db.commit()
    return {"message": "Workspace updated successfully", "name": tenant.name}


@router.get("/departments", summary="List workspace departments")
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    departments = db.query(Department).filter(
        Department.tenant_id == current_user.tenant_id
    ).order_by(Department.name).all()
    counts = {
        department.code: db.query(User).filter(
            User.tenant_id == current_user.tenant_id,
            User.department == department.code,
        ).count()
        for department in departments
    }
    return [
        _serialize_department(department, counts[department.code])
        for department in departments
    ]


@router.post("/departments", status_code=201, summary="Create a department")
def create_department(
    req: DepartmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    if db.query(Department).filter(
        Department.tenant_id == current_user.tenant_id,
        Department.code == req.code,
    ).first():
        raise HTTPException(status_code=409, detail="Department code already exists")
    department = Department(
        tenant_id=current_user.tenant_id,
        code=req.code,
        name=req.name.strip(),
        description=req.description,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return _serialize_department(department)


@router.patch("/departments/{department_id}", summary="Update a department")
def update_department(
    department_id: UUID,
    req: DepartmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    department = db.query(Department).filter(
        Department.id == department_id,
        Department.tenant_id == current_user.tenant_id,
    ).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    for field_name, value in req.model_dump(exclude_unset=True).items():
        setattr(department, field_name, value)
    db.commit()
    return _serialize_department(department)


@router.delete("/departments/{department_id}", summary="Delete an unused department")
def delete_department(
    department_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    department = db.query(Department).filter(
        Department.id == department_id,
        Department.tenant_id == current_user.tenant_id,
    ).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    in_use = db.query(User).filter(
        User.tenant_id == current_user.tenant_id,
        User.department == department.code,
    ).count()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Department still has {in_use} member(s); reassign them first",
        )
    db.delete(department)
    db.commit()
    return {"message": "Department deleted successfully"}
