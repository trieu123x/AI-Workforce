"""add user profiles

Revision ID: a75c1e9b4d20
Revises: f64b2c8d1e30
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a75c1e9b4d20"
down_revision: Union[str, None] = "f64b2c8d1e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("user_profiles"):
        return
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(30)),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("gender", sa.String(30)),
        sa.Column("bio", sa.Text()),
        sa.Column("emergency_contact_name", sa.String(255)),
        sa.Column("emergency_contact_phone", sa.String(30)),
        sa.Column("preferences", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("job_title", sa.String(150)),
        sa.Column("employee_code", sa.String(50)),
        sa.Column("hire_date", sa.Date()),
        sa.Column("monthly_salary", sa.Numeric(18, 2)),
        sa.Column("salary_currency", sa.String(3), nullable=False, server_default="VND"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_user_profile_user"),
    )
    op.create_index("idx_user_profiles_tenant", "user_profiles", ["tenant_id"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("user_profiles"):
        op.drop_index("idx_user_profiles_tenant", table_name="user_profiles")
        op.drop_table("user_profiles")
