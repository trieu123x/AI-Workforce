"""harden_llm_cost_metering

Revision ID: 8f3a1c7d9b20
Revises: 4c9f845c3e2b
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op


revision: str = "8f3a1c7d9b20"
down_revision: Union[str, None] = "4c9f845c3e2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows were produced by hard-coded estimates. Keep them for audit
    # history but explicitly exclude them from provider-metered reports.
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "ADD COLUMN IF NOT EXISTS cached_prompt_tokens INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "ADD COLUMN IF NOT EXISTS usage_source VARCHAR(30) NOT NULL "
        "DEFAULT 'LEGACY_ESTIMATE'"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "ADD COLUMN IF NOT EXISTS pricing_version VARCHAR(30) NOT NULL "
        "DEFAULT 'legacy'"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "ALTER COLUMN estimated_cost_usd TYPE NUMERIC(18, 9)"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs ALTER COLUMN usage_source SET DEFAULT 'PROVIDER'"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "ALTER COLUMN pricing_version SET DEFAULT '2026-07-31'"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_prompt_tokens"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_prompt_tokens "
        "CHECK (prompt_tokens >= 0)"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "DROP CONSTRAINT IF EXISTS ck_llm_cost_completion_tokens"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_completion_tokens "
        "CHECK (completion_tokens >= 0)"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_cached_tokens"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_cached_tokens "
        "CHECK (cached_prompt_tokens >= 0 "
        "AND cached_prompt_tokens <= prompt_tokens)"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_usage_source"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_usage_source "
        "CHECK (usage_source IN "
        "('PROVIDER', 'MANUAL_IMPORT', 'LEGACY_ESTIMATE'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_cost_tenant_created "
        "ON llm_cost_logs (tenant_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_llm_cost_tenant_created")
    op.execute(
        "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_usage_source"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_cached_tokens"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "DROP CONSTRAINT IF EXISTS ck_llm_cost_completion_tokens"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_prompt_tokens"
    )
    op.execute(
        "ALTER TABLE llm_cost_logs "
        "ALTER COLUMN estimated_cost_usd TYPE NUMERIC(10, 6)"
    )
    op.execute("ALTER TABLE llm_cost_logs DROP COLUMN IF EXISTS pricing_version")
    op.execute("ALTER TABLE llm_cost_logs DROP COLUMN IF EXISTS usage_source")
    op.execute(
        "ALTER TABLE llm_cost_logs DROP COLUMN IF EXISTS cached_prompt_tokens"
    )
