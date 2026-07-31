"""deduplicate document chunks and enforce one row per chunk index

Revision ID: b86d2f9e1a40
Revises: a75c1e9b4d20
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b86d2f9e1a40"
down_revision: Union[str, None] = "a75c1e9b4d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINT_NAME = "uq_document_chunks_document_index"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("document_chunks"):
        return

    # Keep the newest row for every logical chunk. Rows without a parent
    # knowledge_document_id are legacy data and are intentionally untouched.
    op.execute(
        """
        WITH ranked_chunks AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY knowledge_document_id, chunk_index
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS duplicate_rank
            FROM document_chunks
            WHERE knowledge_document_id IS NOT NULL
        )
        DELETE FROM document_chunks AS chunks
        USING ranked_chunks AS ranked
        WHERE chunks.id = ranked.id
          AND ranked.duplicate_rank > 1
        """
    )

    # Repair denormalized counters after removing duplicate rows.
    op.execute(
        """
        UPDATE knowledge_documents AS documents
        SET chunk_count = (
            SELECT COUNT(*)
            FROM document_chunks AS chunks
            WHERE chunks.knowledge_document_id = documents.id
        )
        """
    )

    constraint_names = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints("document_chunks")
    }
    if CONSTRAINT_NAME not in constraint_names:
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            "document_chunks",
            ["knowledge_document_id", "chunk_index"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("document_chunks"):
        return
    constraint_names = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints("document_chunks")
    }
    if CONSTRAINT_NAME in constraint_names:
        op.drop_constraint(CONSTRAINT_NAME, "document_chunks", type_="unique")
