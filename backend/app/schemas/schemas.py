"""Pydantic schemas for User and AIAgent endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "Employee"
    department: str = "ALL"
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    tenant_id: UUID


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AI Agent schemas
# ---------------------------------------------------------------------------
class AIAgentBase(BaseModel):
    name: str
    role_code: str
    system_prompt: str
    model_name: str = "gpt-4o"
    is_active: bool = True
    tools_access: list = Field(default_factory=list)
    allowed_actions: list = Field(default_factory=list)
    disallowed_actions: list = Field(default_factory=list)
    knowledge_access: list = Field(default_factory=list)
    avatar_emoji: Optional[str] = None
    description: Optional[str] = None


class AIAgentCreate(AIAgentBase):
    tenant_id: UUID


class AIAgentResponse(AIAgentBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Workflow schemas
# ---------------------------------------------------------------------------
class WorkflowResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    initiator_id: UUID
    title: str
    status: str
    current_step: int
    dag_plan: Optional[dict] = None
    thread_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    comments: Optional[str] = None
