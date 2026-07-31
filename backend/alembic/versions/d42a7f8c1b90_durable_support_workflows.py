"""durable customer support workflows

Revision ID: d42a7f8c1b90
Revises: c91d7e4a2f10
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d42a7f8c1b90"
down_revision: Union[str, None] = "c91d7e4a2f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_step_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("input_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["agent_workflows.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workflow_id", "step_key", name="uq_workflow_step_key"),
    )
    op.create_index(
        "idx_workflow_steps_status",
        "workflow_step_executions",
        ["status", "updated_at"],
    )
    op.create_table(
        "customer_support_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=False),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("inbound_body", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("draft_reply", sa.Text()),
        sa.Column("citations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(40), nullable=False, server_default="QUEUED"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["agent_workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_support_case_idempotency"),
    )
    op.create_index(
        "idx_support_cases_tenant_status",
        "customer_support_cases",
        ["tenant_id", "status"],
    )
    op.create_table(
        "outbound_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("support_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("delivery_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["support_case_id"], ["customer_support_cases.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "support_case_id", "idempotency_key", name="uq_outbound_case_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("outbound_messages")
    op.drop_index("idx_support_cases_tenant_status", table_name="customer_support_cases")
    op.drop_table("customer_support_cases")
    op.drop_index("idx_workflow_steps_status", table_name="workflow_step_executions")
    op.drop_table("workflow_step_executions")
