"""enable HR notification events for existing preferences

Revision ID: f31b8c9d5e20
Revises: e28a6b7c4d10
Create Date: 2026-08-01
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f31b8c9d5e20"
down_revision: Union[str, None] = "e28a6b7c4d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVENT_TYPES = (
    "LEAVE_APPROVAL_REQUIRED",
    "ONBOARDING_TASK_CREATED",
    "CONTRACT_EXPIRING",
    "PROBATION_ENDING",
)


def upgrade() -> None:
    for event_type in EVENT_TYPES:
        op.execute(
            f"""
            UPDATE notification_preferences
            SET enabled_event_types = enabled_event_types || '["{event_type}"]'::jsonb
            WHERE NOT enabled_event_types @> '["{event_type}"]'::jsonb
            """
        )


def downgrade() -> None:
    # Preference choices are user data; a downgrade must not rewrite them.
    pass
