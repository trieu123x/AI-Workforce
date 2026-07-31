"""add versioned document and embedding pipeline

Revision ID: f64b2c8d1e30
Revises: e53f1a9c7d20
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "f64b2c8d1e30"
down_revision: Union[str, None] = "e53f1a9c7d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("knowledge_documents"):
        op.create_table(
            "knowledge_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", sa.String(100), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("document_title", sa.String(255), nullable=False),
            sa.Column("department", sa.String(50), nullable=False, server_default="ALL"),
            sa.Column("document_type", sa.String(50), nullable=False, server_default="knowledge"),
            sa.Column("version", sa.String(50), nullable=False, server_default="1.0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("processing_status", sa.String(20), nullable=False, server_default="uploaded"),
            sa.Column("confidentiality", sa.String(30), nullable=False, server_default="internal"),
            sa.Column("allowed_roles", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("effective_date", sa.Date()),
            sa.Column("expiration_date", sa.Date()),
            sa.Column("storage_key", sa.Text()),
            sa.Column("source_url", sa.Text()),
            sa.Column("source_hash", sa.String(64)),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding_model", sa.String(255)),
            sa.Column("embedding_version", sa.String(100)),
            sa.Column("error_message", sa.Text()),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint(
                "tenant_id", "document_id", "version", name="uq_knowledge_document_version"
            ),
            sa.CheckConstraint(
                "processing_status IN ('uploaded', 'parsing', 'chunking', 'embedding', 'indexing', 'ready', 'failed')",
                name="ck_knowledge_documents_processing_status",
            ),
        )

    knowledge_indexes = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("knowledge_documents")
    }
    if "idx_knowledge_documents_tenant_status" not in knowledge_indexes:
        op.create_index(
            "idx_knowledge_documents_tenant_status",
            "knowledge_documents",
            ["tenant_id", "status"],
        )

    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("document_chunks")
    }
    columns = (
        sa.Column("knowledge_document_id", postgresql.UUID(as_uuid=True)),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("embedding_text", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("embedding_model", sa.String(255)),
        sa.Column("embedding_version", sa.String(100)),
        sa.Column(
            "embedding_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("embedding", Vector(1024)),
    )
    for column in columns:
        if column.name not in existing_columns:
            op.add_column("document_chunks", column)

    foreign_key_names = {
        foreign_key["name"]
        for foreign_key in sa.inspect(bind).get_foreign_keys("document_chunks")
    }
    if "fk_document_chunks_knowledge_document" not in foreign_key_names:
        op.create_foreign_key(
            "fk_document_chunks_knowledge_document",
            "document_chunks",
            "knowledge_documents",
            ["knowledge_document_id"],
            ["id"],
            ondelete="CASCADE",
        )

    document_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("document_chunks")
    }
    if "idx_doc_chunks_content_hash" not in document_indexes:
        op.create_index(
            "idx_doc_chunks_content_hash",
            "document_chunks",
            ["tenant_id", "document_id", "content_hash"],
        )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_content_fts
        ON document_chunks USING gin (to_tsvector('simple', content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_doc_chunks_content_fts")
    op.execute("DROP INDEX IF EXISTS idx_doc_chunks_embedding_hnsw")
    op.drop_index("idx_doc_chunks_content_hash", table_name="document_chunks")
    op.drop_constraint(
        "fk_document_chunks_knowledge_document", "document_chunks", type_="foreignkey"
    )
    for column_name in (
        "embedding",
        "embedding_status",
        "embedding_version",
        "embedding_model",
        "content_hash",
        "embedding_text",
        "page_end",
        "page_start",
        "knowledge_document_id",
    ):
        op.drop_column("document_chunks", column_name)
    op.drop_index(
        "idx_knowledge_documents_tenant_status", table_name="knowledge_documents"
    )
    op.drop_table("knowledge_documents")
