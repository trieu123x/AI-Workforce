"""User management API routes (sync)."""

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user, RoleRequired
from app.models.models import User
from app.schemas.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
def get_my_profile(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse, summary="Update own profile")
def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.add(current_user)
    return UserResponse.model_validate(current_user)


@router.get(
    "/",
    response_model=List[UserResponse],
    summary="List all users",
    dependencies=[Depends(RoleRequired("Owner", "Admin", "CEO", "Manager"))],
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[UserResponse]:
    query = db.query(User).filter(User.tenant_id == current_user.tenant_id)
    if current_user.role == "Manager":
        query = query.filter(User.department == current_user.department)
    users = query.all()
    return [UserResponse.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role == "Manager" and user.department != current_user.department:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role in {"Employee", "Guest"} and user.id != current_user.id:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)
