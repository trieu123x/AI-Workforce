"""expand document chunk section titles

Revision ID: i64e1f8a9b53
Revises: h53d0e7f8a42
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "i64e1f8a9b53"
down_revision: Union[str, None] = "h53d0e7f8a42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "document_chunks",
        "section_title",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Truncate only during an explicit downgrade so converting back to
    # VARCHAR(500) cannot fail on titles accepted by the upgraded schema.
    op.execute(
        "UPDATE document_chunks SET section_title = LEFT(section_title, 500) "
        "WHERE LENGTH(section_title) > 500"
    )
    op.alter_column(
        "document_chunks",
        "section_title",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
