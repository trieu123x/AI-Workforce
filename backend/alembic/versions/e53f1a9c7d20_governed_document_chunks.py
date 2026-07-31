"""add governed document chunk metadata

Revision ID: e53f1a9c7d20
Revises: d42a7f8c1b90
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e53f1a9c7d20"
down_revision: Union[str, None] = "d42a7f8c1b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("document_chunks")
    }
    columns = (
        sa.Column("document_title", sa.String(255)),
        sa.Column(
            "document_type",
            sa.String(50),
            nullable=False,
            server_default="knowledge",
        ),
        sa.Column(
            "version", sa.String(50), nullable=False, server_default="1.0"
        ),
        sa.Column("effective_date", sa.Date()),
        sa.Column("expiration_date", sa.Date()),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="active"
        ),
        sa.Column(
            "confidentiality",
            sa.String(30),
            nullable=False,
            server_default="internal",
        ),
        sa.Column(
            "allowed_roles",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("source_file", sa.String(255)),
        sa.Column("section_title", sa.String(500)),
        sa.Column("page", sa.Integer()),
    )
    for column in columns:
        if column.name not in existing_columns:
            op.add_column("document_chunks", column)

    op.execute(
        """
        UPDATE document_chunks
        SET document_title = document_name,
            source_file = document_name,
            section_title = COALESCE(metadata->>'section_title', 'Chunk ' || chunk_index)
        """
    )
    inspector = sa.inspect(bind)
    constraint_names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("document_chunks")
    }
    if "ck_doc_chunks_status" not in constraint_names:
        op.create_check_constraint(
            "ck_doc_chunks_status",
            "document_chunks",
            "status IN ('draft', 'active', 'inactive', 'archived')",
        )
    if "ck_doc_chunks_confidentiality" not in constraint_names:
        op.create_check_constraint(
            "ck_doc_chunks_confidentiality",
            "document_chunks",
            "confidentiality IN ('public', 'internal', 'confidential', 'restricted')",
        )

    index_names = {
        index["name"] for index in sa.inspect(bind).get_indexes("document_chunks")
    }
    if "idx_doc_chunks_governance" not in index_names:
        op.create_index(
            "idx_doc_chunks_governance",
            "document_chunks",
            ["tenant_id", "status", "department_access", "effective_date"],
        )
    if "idx_doc_chunks_document" not in index_names:
        op.create_index(
            "idx_doc_chunks_document",
            "document_chunks",
            ["tenant_id", "document_id"],
        )


def downgrade() -> None:
    op.drop_index("idx_doc_chunks_document", table_name="document_chunks")
    op.drop_index("idx_doc_chunks_governance", table_name="document_chunks")
    op.drop_constraint("ck_doc_chunks_confidentiality", "document_chunks", type_="check")
    op.drop_constraint("ck_doc_chunks_status", "document_chunks", type_="check")
    for column_name in (
        "page",
        "section_title",
        "source_file",
        "allowed_roles",
        "confidentiality",
        "status",
        "expiration_date",
        "effective_date",
        "version",
        "document_type",
        "document_title",
    ):
        op.drop_column("document_chunks", column_name)
