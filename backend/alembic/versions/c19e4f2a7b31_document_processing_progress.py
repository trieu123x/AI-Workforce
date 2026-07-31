"""add per-stage document processing progress

Revision ID: c19e4f2a7b31
Revises: b86d2f9e1a40
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c19e4f2a7b31"
down_revision: Union[str, None] = "b86d2f9e1a40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_documents"):
        return

    columns = {column["name"] for column in inspector.get_columns("knowledge_documents")}
    if "processing_progress" not in columns:
        op.add_column(
            "knowledge_documents",
            sa.Column(
                "processing_progress",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints("knowledge_documents")
    }
    if "ck_knowledge_documents_processing_progress" not in constraints:
        op.create_check_constraint(
            "ck_knowledge_documents_processing_progress",
            "knowledge_documents",
            "processing_progress >= 0 AND processing_progress <= 100",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_documents"):
        return

    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("knowledge_documents")
    }
    if "ck_knowledge_documents_processing_progress" in constraints:
        op.drop_constraint(
            "ck_knowledge_documents_processing_progress",
            "knowledge_documents",
            type_="check",
        )
    columns = {column["name"] for column in sa.inspect(bind).get_columns("knowledge_documents")}
    if "processing_progress" in columns:
        op.drop_column("knowledge_documents", "processing_progress")
