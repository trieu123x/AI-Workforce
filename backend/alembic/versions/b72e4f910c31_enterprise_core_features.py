"""enterprise core features

Revision ID: b72e4f910c31
Revises: 8f3a1c7d9b20
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b72e4f910c31"
down_revision: Union[str, None] = "8f3a1c7d9b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_department")
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "departments" not in existing_tables:
        op.create_table(
            "departments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
            ),
            sa.UniqueConstraint("tenant_id", "code", name="uq_department_tenant_code"),
        )
    if "chat_conversations" not in existing_tables:
        op.create_table(
            "chat_conversations",
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
            sa.Column(
                "ai_agent_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ai_agents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("thread_id", sa.String(255), nullable=True),
            sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
            ),
        )
        op.create_index(
            "idx_chat_conversation_user_updated",
            "chat_conversations",
            ["user_id", "updated_at"],
        )
    if "chat_messages" not in existing_tables:
        op.create_table(
            "chat_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "conversation_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sender", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "citations", postgresql.JSONB(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "tools_executed", postgresql.JSONB(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "attachments", postgresql.JSONB(), nullable=False, server_default="[]"
            ),
            sa.Column("feedback_rating", sa.Integer(), nullable=True),
            sa.Column("feedback_comment", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
            ),
            sa.CheckConstraint(
                "sender IN ('USER', 'ASSISTANT')", name="ck_chat_message_sender"
            ),
        )
        op.create_index(
            "idx_chat_message_conversation_created",
            "chat_messages",
            ["conversation_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index(
        "idx_chat_message_conversation_created", table_name="chat_messages"
    )
    op.drop_table("chat_messages")
    op.drop_index(
        "idx_chat_conversation_user_updated", table_name="chat_conversations"
    )
    op.drop_table("chat_conversations")
    op.drop_table("departments")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_department "
        "CHECK (department IN "
        "('BOARD', 'HR', 'LEGAL', 'IT', 'FINANCE', 'SALES', 'ALL'))"
    )
