"""Workspace employee management with tenant-safe RBAC."""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user, get_password_hash
from app.models.models import Department, User

router = APIRouter(prefix="/users-mgmt", tags=["User & Department Management"])

UserRole = Literal["Owner", "Admin", "Manager", "Employee"]
UserRoleFilter = Literal["Owner", "Admin", "Manager", "Employee", "CEO", "Guest"]
MANAGEMENT_ROLES = {"Owner", "Admin", "CEO"}


class CreateEmployeeRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "Employee"
    department: str = Field(default="ALL", min_length=2, max_length=50, pattern="^[A-Z0-9_-]+$")


class UpdateUserStatusRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    department: Optional[str] = Field(None, min_length=2, max_length=50, pattern="^[A-Z0-9_-]+$")


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "department": user.department,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _department_exists(db: Session, tenant_id, code: str) -> bool:
    return code == "ALL" or db.query(Department).filter(
        Department.tenant_id == tenant_id,
        Department.code == code,
        Department.is_active.is_(True),
    ).first() is not None


@router.get("", summary="List employees visible to the current management role")
def get_organization_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=100),
    department: Optional[str] = Query(
        None, min_length=2, max_length=50, pattern="^[A-Z0-9_-]+$"
    ),
    role: Optional[UserRoleFilter] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role not in MANAGEMENT_ROLES | {"Manager"}:
        raise HTTPException(status_code=403, detail="Insufficient permission to list employees")

    query = db.query(User).filter(User.tenant_id == current_user.tenant_id)
    if current_user.role == "Manager":
        query = query.filter(User.department == current_user.department)
    if department:
        query = query.filter(User.department == department)
    if role:
        query = query.filter(User.role == role)
    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(or_(
            User.full_name.ilike(search),
            User.email.ilike(search),
        ))

    total = query.count()
    users = query.order_by(User.created_at.desc(), User.id.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [_serialize_user(user) for user in users],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.post("", status_code=201, summary="Add an employee to the workspace")
def add_employee(
    req: CreateEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only Owner/Admin can add employees")
    if req.role == "Owner" and current_user.role not in {"Owner", "CEO"}:
        raise HTTPException(status_code=403, detail="Only Owner can grant the Owner role")
    if not _department_exists(db, current_user.tenant_id, req.department):
        raise HTTPException(status_code=422, detail="Department does not exist or is inactive")

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email is already in use")

    new_user = User(
        tenant_id=current_user.tenant_id,
        email=req.email,
        full_name=req.full_name,
        password_hash=get_password_hash(req.password),
        role=req.role,
        department=req.department,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {
        "message": "Employee created successfully",
        "user_id": str(new_user.id),
        "user": _serialize_user(new_user),
    }


@router.patch("/{user_id}/status", summary="Update an employee account")
def update_employee_status(
    user_id: UUID,
    req: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only Owner/Admin can update employees")

    target_user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id,
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Employee not found")
    if current_user.role == "Admin" and target_user.role in {"Owner", "CEO"}:
        raise HTTPException(status_code=403, detail="Admin cannot modify an Owner account")
    if req.role == "Owner" and current_user.role not in {"Owner", "CEO"}:
        raise HTTPException(status_code=403, detail="Only Owner can grant the Owner role")
    if req.department and not _department_exists(
        db, current_user.tenant_id, req.department
    ):
        raise HTTPException(status_code=422, detail="Department does not exist or is inactive")
    if target_user.id == current_user.id and req.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot lock your own account")

    removes_owner = target_user.role in {"Owner", "CEO"} and (
        req.is_active is False or (req.role is not None and req.role != "Owner")
    )
    if removes_owner:
        active_owner_count = db.query(User).filter(
            User.tenant_id == current_user.tenant_id,
            User.role.in_(("Owner", "CEO")),
            User.is_active.is_(True),
        ).count()
        if active_owner_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="The workspace must keep at least one active Owner",
            )

    if req.is_active is not None:
        target_user.is_active = req.is_active
    if req.role is not None:
        target_user.role = req.role
    if req.department is not None:
        target_user.department = req.department

    db.commit()
    return {
        "message": "Employee updated successfully",
        "user": _serialize_user(target_user),
    }
