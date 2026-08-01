"""version AI Employee tool and knowledge configuration

Revision ID: g42c9d0e6f31
Revises: f31b8c9d5e20
"""

from alembic import op
import sqlalchemy as sa


revision = "g42c9d0e6f31"
down_revision = "f31b8c9d5e20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_agents",
        sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("ai_agents", "configuration_version")
