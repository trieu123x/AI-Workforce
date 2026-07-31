"""
SQLAlchemy ORM Models for AI Workforce Platform.
All tables defined per enterprise specification (Multi-tenant, Tasks, Agents, Workflows, Approvals, RAG Collections).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ============================================================
# 1. TENANTS — Multi-tenant organization isolation
# ============================================================
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Asia/Ho_Chi_Minh"
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="vi")
    data_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365
    )
    default_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gpt-4o"
    )
    notification_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    security_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    departments: Mapped[list["Department"]] = relationship(
        "Department", back_populates="tenant", cascade="all, delete-orphan"
    )
    ai_agents: Mapped[list["AIAgent"]] = relationship("AIAgent", back_populates="tenant", cascade="all, delete-orphan")
    document_chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="tenant", cascade="all, delete-orphan")
    workflows: Mapped[list["AgentWorkflow"]] = relationship("AgentWorkflow", back_populates="tenant")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="tenant", cascade="all, delete-orphan")


# ============================================================
# 2. USERS — Employees with RBAC roles
# ============================================================
class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_department_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="departments")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('Owner', 'Admin', 'Manager', 'Employee', 'CEO', 'Guest')",
            name="ck_users_role",
        ),
        Index("idx_users_tenant_dept", "tenant_id", "department"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="Employee")
    department: Mapped[str] = mapped_column(String(50), nullable=False, default="ALL")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    workflows: Mapped[list["AgentWorkflow"]] = relationship("AgentWorkflow", back_populates="initiator")
    approvals: Mapped[list["WorkflowApproval"]] = relationship("WorkflowApproval", back_populates="approver")
    memories: Mapped[list["UserMemory"]] = relationship("UserMemory", back_populates="user", cascade="all, delete-orphan")


# ============================================================
# 3. AI_AGENTS — AI Employee configuration catalog
# ============================================================
class AIAgent(Base):
    __tablename__ = "ai_agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_code: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CEO, HR, LEGAL, IT, FINANCE, SALES, KNOWLEDGE
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="gpt-4o")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tools_access: Mapped[dict] = mapped_column(JSONB, default=list)
    allowed_actions: Mapped[dict] = mapped_column(JSONB, default=list)
    disallowed_actions: Mapped[dict] = mapped_column(JSONB, default=list)
    knowledge_access: Mapped[dict] = mapped_column(JSONB, default=list)
    avatar_emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="ai_agents")


# ============================================================
# 4. TASKS — Enterprise Task Management
# ============================================================
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    ai_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, URGENT
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="DRAFT"
    )  # DRAFT, PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, OVERDUE
    attachments: Mapped[dict] = mapped_column(JSONB, default=list)
    output_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="tasks")
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id])
    assignee: Mapped["User | None"] = relationship("User", foreign_keys=[assignee_id])
    ai_agent: Mapped["AIAgent | None"] = relationship("AIAgent")
    comments: Mapped[list["TaskComment"]] = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="comments")
    user: Mapped["User"] = relationship("User")


# ============================================================
# 5. AGENT_WORKFLOWS — Multi-agent task execution sessions
# ============================================================
class AgentWorkflow(Base):
    __tablename__ = "agent_workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    initiator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING, IN_PROGRESS, AWAITING_APPROVAL, COMPLETED, FAILED
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    dag_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="workflows")
    initiator: Mapped["User"] = relationship("User", back_populates="workflows")
    approvals: Mapped[list["WorkflowApproval"]] = relationship("WorkflowApproval", back_populates="workflow", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="workflow")
    llm_cost_logs: Mapped[list["LLMCostLog"]] = relationship("LLMCostLog", back_populates="workflow")
    step_executions: Mapped[list["WorkflowStepExecution"]] = relationship(
        "WorkflowStepExecution", back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowStepExecution(Base):
    """Durable, idempotent checkpoint for one workflow step."""

    __tablename__ = "workflow_step_executions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_key", name="uq_workflow_step_key"),
        Index("idx_workflow_steps_status", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workflow: Mapped["AgentWorkflow"] = relationship(
        "AgentWorkflow", back_populates="step_executions"
    )


class CustomerSupportCase(Base):
    __tablename__ = "customer_support_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_support_case_idempotency"),
        Index("idx_support_cases_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    inbound_body: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)
    draft_reply: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[dict] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="QUEUED")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"
    __table_args__ = (
        UniqueConstraint("support_case_id", "idempotency_key", name="uq_outbound_case_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    support_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_support_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ============================================================
# 6. WORKFLOW_APPROVALS — Human-in-the-loop gate
# ============================================================
class WorkflowApproval(Base):
    __tablename__ = "workflow_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_workflows.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="WAITING")
    # WAITING, APPROVED, REJECTED, EXPIRED
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workflow: Mapped["AgentWorkflow"] = relationship("AgentWorkflow", back_populates="approvals")
    approver: Mapped["User | None"] = relationship("User", back_populates="approvals")


# ============================================================
# 7. USER_MEMORIES — Long-term personalization memory
# ============================================================
class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = (
        Index("idx_user_memories", "user_id", "memory_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    memory_category: Mapped[str] = mapped_column(String(50), nullable=False)
    memory_key: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memories")


# ============================================================
# 8. LLM_COST_LOGS — Token usage & cost metering
# ============================================================
class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("idx_chat_conversation_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ai_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User")
    ai_agent: Mapped["AIAgent"] = relationship("AIAgent")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("sender IN ('USER', 'ASSISTANT')", name="ck_chat_message_sender"),
        Index("idx_chat_message_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[dict] = mapped_column(JSONB, default=list)
    tools_executed: Mapped[dict] = mapped_column(JSONB, default=list)
    attachments: Mapped[dict] = mapped_column(JSONB, default=list)
    feedback_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["ChatConversation"] = relationship(
        "ChatConversation", back_populates="messages"
    )


class LLMCostLog(Base):
    __tablename__ = "llm_cost_logs"
    __table_args__ = (
        CheckConstraint("prompt_tokens >= 0", name="ck_llm_cost_prompt_tokens"),
        CheckConstraint(
            "completion_tokens >= 0", name="ck_llm_cost_completion_tokens"
        ),
        CheckConstraint(
            "cached_prompt_tokens >= 0 AND cached_prompt_tokens <= prompt_tokens",
            name="ck_llm_cost_cached_tokens",
        ),
        CheckConstraint(
            "usage_source IN ('PROVIDER', 'MANUAL_IMPORT', 'LEGACY_ESTIMATE')",
            name="ck_llm_cost_usage_source",
        ),
        Index("idx_llm_cost_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_workflows.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    department: Mapped[str | None] = mapped_column(String(50), nullable=True)
    agent_role: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(18, 9), nullable=False)
    usage_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PROVIDER", server_default="PROVIDER"
    )
    pricing_version: Mapped[str] = mapped_column(
        String(30), nullable=False, default="2026-07-31", server_default="2026-07-31"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    workflow: Mapped["AgentWorkflow | None"] = relationship("AgentWorkflow", back_populates="llm_cost_logs")
    user: Mapped["User | None"] = relationship("User")


class CostBudget(Base):
    __tablename__ = "cost_budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False, default="TENANT")  # TENANT, DEPARTMENT, AGENT, USER
    scope_id: Mapped[str] = mapped_column(String(100), nullable=False, default="ALL")  # e.g., "HR", "ALL", user_id
    monthly_budget_usd: Mapped[float] = mapped_column(Float, nullable=False, default=500.0)
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ModelRoutingRule(Base):
    __tablename__ = "model_routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "HR_FAQ", "LEGAL_CONTRACT", "IT_TICKET", "GENERAL_CHAT"
    agent_role: Mapped[str] = mapped_column(String(50), nullable=False, default="ALL")
    preferred_model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-3.5-turbo")
    fallback_model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4o")
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    cost_saving_strategy: Mapped[str] = mapped_column(String(50), default="BALANCED")  # LOW_COST, BALANCED, HIGH_PERFORMANCE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )



# ============================================================
# 9. DOCUMENT_CHUNKS & COLLECTIONS — pgvector knowledge store
# ============================================================
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    collection_name: Mapped[str] = mapped_column(String(100), default="General Knowledge")
    department_access: Mapped[str] = mapped_column(String(50), default="ALL")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    dense_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="document_chunks")


# ============================================================
# 10. AUDIT_LOGS — Full agent action trail
# ============================================================
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_workflow", "workflow_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SYSTEM"
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_workflows.id"), nullable=True
    )
    agent_role: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str | None] = mapped_column(String(150), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    before_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SUCCESS"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    workflow: Mapped["AgentWorkflow | None"] = relationship("AgentWorkflow", back_populates="audit_logs")
    actor_user: Mapped["User | None"] = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user_created", "user_id", "created_at"),
        Index("idx_notifications_user_unread", "user_id", "is_read"),
        UniqueConstraint(
            "tenant_id", "user_id", "dedup_key", name="uq_notification_dedup"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="INFO"
    )
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(
        String(30), nullable=False, default="IN_APP"
    )
    delivery_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DELIVERED"
    )
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    enabled_event_types: Mapped[dict] = mapped_column(JSONB, default=list)
    enabled_channels: Mapped[dict] = mapped_column(JSONB, default=list)
    quiet_hours: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User")


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "display_name", name="uq_integration_name"
        ),
        Index("idx_integrations_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False)
    credential_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONB, default=list)
    allowed_resources: Mapped[dict] = mapped_column(JSONB, default=list)
    allowed_agent_roles: Mapped[dict] = mapped_column(JSONB, default=list)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="CONFIGURED"
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    created_by: Mapped["User"] = relationship("User")
    usage_logs: Mapped[list["IntegrationUsageLog"]] = relationship(
        "IntegrationUsageLog",
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class IntegrationUsageLog(Base):
    __tablename__ = "integration_usage_logs"
    __table_args__ = (
        Index("idx_integration_usage_created", "connection_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    connection: Mapped["IntegrationConnection"] = relationship(
        "IntegrationConnection", back_populates="usage_logs"
    )
    actor_user: Mapped["User | None"] = relationship("User")
