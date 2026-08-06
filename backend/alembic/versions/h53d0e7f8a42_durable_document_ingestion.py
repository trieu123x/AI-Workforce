"""add durable document ingestion state

Revision ID: h53d0e7f8a42
Revises: g42c9d0e6f31
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "h53d0e7f8a42"
down_revision: Union[str, None] = "g42c9d0e6f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("knowledge_documents")
    }
    if "collection_name" not in columns:
        op.add_column(
            "knowledge_documents",
            sa.Column(
                "collection_name",
                sa.String(length=100),
                nullable=False,
                server_default="General Knowledge",
            ),
        )
    if "processing_attempts" not in columns:
        op.add_column(
            "knowledge_documents",
            sa.Column(
                "processing_attempts", sa.Integer(), nullable=False, server_default="0"
            ),
        )
    if "processing_checkpoint" not in columns:
        op.add_column(
            "knowledge_documents",
            sa.Column(
                "processing_checkpoint",
                sa.String(length=20),
                nullable=False,
                server_default="uploaded",
            ),
        )
    if "parsed_text" not in columns:
        op.add_column(
            "knowledge_documents",
            sa.Column("parsed_text", sa.Text(), nullable=True),
        )
    op.execute(
        "UPDATE knowledge_documents SET processing_checkpoint = 'ready' "
        "WHERE processing_status = 'ready' AND processing_checkpoint = 'uploaded'"
    )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("knowledge_documents")
    }
    if "parsed_text" in columns:
        op.drop_column("knowledge_documents", "parsed_text")
    if "processing_checkpoint" in columns:
        op.drop_column("knowledge_documents", "processing_checkpoint")
    if "processing_attempts" in columns:
        op.drop_column("knowledge_documents", "processing_attempts")
    if "collection_name" in columns:
        op.drop_column("knowledge_documents", "collection_name")
