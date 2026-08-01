"""add structured HR operations v1

Revision ID: e28a6b7c4d10
Revises: c19e4f2a7b31
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e28a6b7c4d10"
down_revision: Union[str, None] = "c19e4f2a7b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "manager_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_users_manager", "users", ["manager_id"])

    for column in (
        sa.Column("employment_type", sa.String(30), nullable=False, server_default="FULL_TIME"),
        sa.Column("employment_status", sa.String(30), nullable=False, server_default="OFFICIAL"),
        sa.Column("skills", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("certifications", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("experience_summary", sa.Text(), nullable=True),
        sa.Column("employment_history", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    ):
        op.add_column("user_profiles", column)

    op.create_table(
        "leave_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("allocated_days", sa.Numeric(6, 2), nullable=False, server_default="12.00"),
        sa.Column("carried_over_days", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("used_days", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("reserved_days", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "allocated_days >= 0 AND carried_over_days >= 0 AND used_days >= 0 AND reserved_days >= 0",
            name="ck_leave_balance_non_negative",
        ),
        sa.UniqueConstraint("user_id", "year", name="uq_leave_balance_user_year"),
    )
    op.create_index("idx_leave_balance_tenant_year", "leave_balances", ["tenant_id", "year"])

    op.create_table(
        "leave_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_approvals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("leave_type", sa.String(30), nullable=False, server_default="ANNUAL"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("part_of_day", sa.String(20), nullable=False, server_default="FULL_DAY"),
        sa.Column("requested_days", sa.Numeric(6, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="WAITING"),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("requested_days > 0", name="ck_leave_request_days_positive"),
    )
    op.create_index("idx_leave_requests_employee_status", "leave_requests", ["employee_id", "status"])
    op.create_index("idx_leave_requests_tenant_dates", "leave_requests", ["tenant_id", "start_date", "end_date"])

    op.create_table(
        "leave_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_balances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("amount_days", sa.Numeric(6, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(6, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("leave_request_id", "entry_type", name="uq_leave_ledger_request_type"),
    )
    op.create_index("idx_leave_ledger_balance_created", "leave_ledger", ["balance_id", "created_at"])

    op.create_table(
        "hr_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("external_provider", sa.String(50), nullable=True),
        sa.Column("external_event_id", sa.String(255), nullable=True),
        sa.Column("sync_status", sa.String(30), nullable=False, server_default="INTERNAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_type", "source_id", name="uq_hr_calendar_source"),
    )
    op.create_index("idx_hr_calendar_tenant_dates", "hr_calendar_events", ["tenant_id", "start_at", "end_at"])

    op.create_table(
        "employment_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contract_number", sa.String(100), nullable=False),
        sa.Column("contract_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("probation_end_date", sa.Date(), nullable=True),
        sa.Column("signed_by_employee", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signed_by_company", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("document_name", sa.String(255), nullable=True),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "contract_number", name="uq_contract_tenant_number"),
    )
    op.create_index("idx_contract_tenant_expiry", "employment_contracts", ["tenant_id", "end_date", "status"])

    op.create_table(
        "onboarding_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mentor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("probation_end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_onboarding_tenant_status", "onboarding_cases", ["tenant_id", "status"])

    op.create_table(
        "onboarding_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("onboarding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("onboarding_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("owner_department", sa.String(50), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("onboarding_id", "step_key", name="uq_onboarding_step_key"),
    )
    op.create_index("idx_onboarding_step_status", "onboarding_steps", ["onboarding_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_onboarding_step_status", table_name="onboarding_steps")
    op.drop_table("onboarding_steps")
    op.drop_index("idx_onboarding_tenant_status", table_name="onboarding_cases")
    op.drop_table("onboarding_cases")
    op.drop_index("idx_contract_tenant_expiry", table_name="employment_contracts")
    op.drop_table("employment_contracts")
    op.drop_index("idx_hr_calendar_tenant_dates", table_name="hr_calendar_events")
    op.drop_table("hr_calendar_events")
    op.drop_index("idx_leave_ledger_balance_created", table_name="leave_ledger")
    op.drop_table("leave_ledger")
    op.drop_index("idx_leave_requests_tenant_dates", table_name="leave_requests")
    op.drop_index("idx_leave_requests_employee_status", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("idx_leave_balance_tenant_year", table_name="leave_balances")
    op.drop_table("leave_balances")
    for column in (
        "employment_history",
        "experience_summary",
        "certifications",
        "skills",
        "employment_status",
        "employment_type",
    ):
        op.drop_column("user_profiles", column)
    op.drop_index("idx_users_manager", table_name="users")
    op.drop_column("users", "manager_id")
