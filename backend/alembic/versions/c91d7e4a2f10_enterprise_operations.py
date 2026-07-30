"""enterprise operations analytics, settings, notifications and integrations

Revision ID: c91d7e4a2f10
Revises: b72e4f910c31
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c91d7e4a2f10"
down_revision: Union[str, None] = "b72e4f910c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _accept_complete_create_all_schema() -> bool:
    """Adopt a complete schema created by the legacy runtime create_all hook.

    Older application versions created model tables before Alembic could record
    this revision. We only adopt that state when every required table and
    column is present; a partial schema is rejected instead of being silently
    stamped as healthy.
    """

    inspector = sa.inspect(op.get_bind())
    required_columns = {
        "tenants": {
            "logo_url",
            "timezone",
            "language",
            "data_retention_days",
            "default_model",
            "notification_settings",
            "security_settings",
            "billing_email",
        },
        "audit_logs": {
            "actor_user_id",
            "actor_type",
            "action",
            "resource_type",
            "resource_id",
            "before_data",
            "after_data",
            "ip_address",
            "user_agent",
            "status",
            "error_message",
        },
        "notifications": {
            "id",
            "tenant_id",
            "user_id",
            "event_type",
            "title",
            "message",
            "severity",
            "entity_type",
            "entity_id",
            "channel",
            "delivery_status",
            "payload",
            "dedup_key",
            "is_read",
            "read_at",
            "created_at",
        },
        "notification_preferences": {
            "id",
            "tenant_id",
            "user_id",
            "enabled_event_types",
            "enabled_channels",
            "quiet_hours",
            "updated_at",
        },
        "integration_connections": {
            "id",
            "tenant_id",
            "provider",
            "display_name",
            "auth_type",
            "credential_reference",
            "permissions",
            "allowed_resources",
            "allowed_agent_roles",
            "configuration",
            "status",
            "created_by_id",
            "connected_at",
            "last_checked_at",
            "last_error",
            "created_at",
            "updated_at",
        },
        "integration_usage_logs": {
            "id",
            "tenant_id",
            "connection_id",
            "actor_user_id",
            "agent_role",
            "operation",
            "resource",
            "status",
            "execution_time_ms",
            "metadata",
            "error_message",
            "created_at",
        },
    }
    table_names = set(inspector.get_table_names())
    tenant_columns = {
        column["name"] for column in inspector.get_columns("tenants")
    }
    drift_detected = any(
        table in table_names
        for table in required_columns
        if table not in {"tenants", "audit_logs"}
    ) or bool(required_columns["tenants"] & tenant_columns)
    if not drift_detected:
        return False

    missing: list[str] = []
    missing_columns: dict[str, set[str]] = {}
    for table, expected in required_columns.items():
        if table not in table_names:
            missing.append(f"table {table}")
            continue
        actual = {column["name"] for column in inspector.get_columns(table)}
        missing_columns[table] = expected - actual
        missing.extend(
            f"column {table}.{name}" for name in sorted(missing_columns[table])
        )

    tenant_column_definitions = {
        "logo_url": sa.Column("logo_url", sa.Text(), nullable=True),
        "timezone": sa.Column(
            "timezone",
            sa.String(100),
            nullable=False,
            server_default="Asia/Ho_Chi_Minh",
        ),
        "language": sa.Column(
            "language", sa.String(10), nullable=False, server_default="vi"
        ),
        "data_retention_days": sa.Column(
            "data_retention_days",
            sa.Integer(),
            nullable=False,
            server_default="365",
        ),
        "default_model": sa.Column(
            "default_model",
            sa.String(100),
            nullable=False,
            server_default="gpt-4o",
        ),
        "notification_settings": sa.Column(
            "notification_settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        "security_settings": sa.Column(
            "security_settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        "billing_email": sa.Column(
            "billing_email", sa.String(255), nullable=True
        ),
    }
    audit_column_definitions = {
        "actor_user_id": sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        "actor_type": sa.Column(
            "actor_type", sa.String(20), nullable=False, server_default="SYSTEM"
        ),
        "action": sa.Column("action", sa.String(150), nullable=True),
        "resource_type": sa.Column(
            "resource_type", sa.String(100), nullable=True
        ),
        "resource_id": sa.Column(
            "resource_id", sa.String(255), nullable=True
        ),
        "before_data": sa.Column(
            "before_data", postgresql.JSONB(), nullable=True
        ),
        "after_data": sa.Column(
            "after_data", postgresql.JSONB(), nullable=True
        ),
        "ip_address": sa.Column(
            "ip_address", sa.String(64), nullable=True
        ),
        "user_agent": sa.Column("user_agent", sa.Text(), nullable=True),
        "status": sa.Column(
            "status", sa.String(20), nullable=False, server_default="SUCCESS"
        ),
        "error_message": sa.Column("error_message", sa.Text(), nullable=True),
    }
    reconcilable = {
        f"column tenants.{name}" for name in tenant_column_definitions
    } | {
        f"column audit_logs.{name}" for name in audit_column_definitions
    }
    unreconciled = [item for item in missing if item not in reconcilable]
    if unreconciled:
        raise RuntimeError(
            "Partial legacy create_all schema detected. Resolve these objects before "
            f"retrying the migration: {', '.join(unreconciled)}"
        )

    for name in sorted(missing_columns.get("tenants", set())):
        op.add_column("tenants", tenant_column_definitions[name])
    for name in sorted(missing_columns.get("audit_logs", set())):
        op.add_column("audit_logs", audit_column_definitions[name])

    op.execute("UPDATE audit_logs SET action = tool_name WHERE action IS NULL")
    indexes = {
        table: {index["name"] for index in inspector.get_indexes(table)}
        for table in (
            "audit_logs",
            "notifications",
            "integration_connections",
            "integration_usage_logs",
        )
    }
    for name, table, columns in (
        ("idx_audit_tenant_created", "audit_logs", ["tenant_id", "created_at"]),
        ("idx_audit_actor", "audit_logs", ["actor_user_id"]),
        (
            "idx_notifications_user_created",
            "notifications",
            ["user_id", "created_at"],
        ),
        (
            "idx_notifications_user_unread",
            "notifications",
            ["user_id", "is_read"],
        ),
        (
            "idx_integrations_tenant_status",
            "integration_connections",
            ["tenant_id", "status"],
        ),
        (
            "idx_integration_usage_created",
            "integration_usage_logs",
            ["connection_id", "created_at"],
        ),
    ):
        if name not in indexes[table]:
            op.create_index(name, table, columns)
    return True


def upgrade() -> None:
    if _accept_complete_create_all_schema():
        return

    op.add_column("tenants", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "timezone",
            sa.String(100),
            nullable=False,
            server_default="Asia/Ho_Chi_Minh",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("language", sa.String(10), nullable=False, server_default="vi"),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "data_retention_days", sa.Integer(), nullable=False, server_default="365"
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "default_model",
            sa.String(100),
            nullable=False,
            server_default="gpt-4o",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "notification_settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "security_settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "tenants", sa.Column("billing_email", sa.String(255), nullable=True)
    )

    op.add_column(
        "audit_logs",
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "audit_logs",
        sa.Column(
            "actor_type", sa.String(20), nullable=False, server_default="SYSTEM"
        ),
    )
    op.add_column("audit_logs", sa.Column("action", sa.String(150), nullable=True))
    op.add_column(
        "audit_logs", sa.Column("resource_type", sa.String(100), nullable=True)
    )
    op.add_column(
        "audit_logs", sa.Column("resource_id", sa.String(255), nullable=True)
    )
    op.add_column(
        "audit_logs", sa.Column("before_data", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "audit_logs", sa.Column("after_data", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "audit_logs", sa.Column("ip_address", sa.String(64), nullable=True)
    )
    op.add_column("audit_logs", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("status", sa.String(20), nullable=False, server_default="SUCCESS"),
    )
    op.add_column("audit_logs", sa.Column("error_message", sa.Text(), nullable=True))
    op.execute("UPDATE audit_logs SET action = tool_name WHERE action IS NULL")
    op.create_index(
        "idx_audit_tenant_created", "audit_logs", ["tenant_id", "created_at"]
    )
    op.create_index("idx_audit_actor", "audit_logs", ["actor_user_id"])

    op.create_table(
        "notifications",
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
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="INFO"),
        sa.Column("entity_type", sa.String(80), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("channel", sa.String(30), nullable=False, server_default="IN_APP"),
        sa.Column(
            "delivery_status",
            sa.String(30),
            nullable=False,
            server_default="DELIVERED",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("dedup_key", sa.String(255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "dedup_key", name="uq_notification_dedup"
        ),
    )
    op.create_index(
        "idx_notifications_user_created", "notifications", ["user_id", "created_at"]
    )
    op.create_index(
        "idx_notifications_user_unread", "notifications", ["user_id", "is_read"]
    )

    op.create_table(
        "notification_preferences",
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
            "enabled_event_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "enabled_channels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"IN_APP\"]'::jsonb"),
        ),
        sa.Column(
            "quiet_hours",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )

    op.create_table(
        "integration_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("auth_type", sa.String(50), nullable=False),
        sa.Column("credential_reference", sa.String(255), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "allowed_resources",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "allowed_agent_roles",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status", sa.String(30), nullable=False, server_default="CONFIGURED"
        ),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "provider", "display_name", name="uq_integration_name"
        ),
    )
    op.create_index(
        "idx_integrations_tenant_status",
        "integration_connections",
        ["tenant_id", "status"],
    )

    op.create_table(
        "integration_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_role", sa.String(50), nullable=True),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_integration_usage_created",
        "integration_usage_logs",
        ["connection_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_integration_usage_created", table_name="integration_usage_logs"
    )
    op.drop_table("integration_usage_logs")
    op.drop_index(
        "idx_integrations_tenant_status", table_name="integration_connections"
    )
    op.drop_table("integration_connections")
    op.drop_table("notification_preferences")
    op.drop_index(
        "idx_notifications_user_unread", table_name="notifications"
    )
    op.drop_index(
        "idx_notifications_user_created", table_name="notifications"
    )
    op.drop_table("notifications")

    op.drop_index("idx_audit_actor", table_name="audit_logs")
    op.drop_index("idx_audit_tenant_created", table_name="audit_logs")
    for column in (
        "error_message",
        "status",
        "user_agent",
        "ip_address",
        "after_data",
        "before_data",
        "resource_id",
        "resource_type",
        "action",
        "actor_type",
        "actor_user_id",
    ):
        op.drop_column("audit_logs", column)

    for column in (
        "billing_email",
        "security_settings",
        "notification_settings",
        "default_model",
        "data_retention_days",
        "language",
        "timezone",
        "logo_url",
    ):
        op.drop_column("tenants", column)
