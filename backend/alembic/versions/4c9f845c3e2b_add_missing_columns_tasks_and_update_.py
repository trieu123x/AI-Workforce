"""add_missing_columns_tasks_and_update_constraints

Revision ID: 4c9f845c3e2b
Revises: da0273f16c30
Create Date: 2026-07-30 13:59:58.883314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4c9f845c3e2b'
down_revision: Union[str, None] = 'da0273f16c30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add missing columns with IF NOT EXISTS
    op.execute("ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS allowed_actions JSONB DEFAULT '[]'::jsonb;")
    op.execute("ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS disallowed_actions JSONB DEFAULT '[]'::jsonb;")
    op.execute("ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS knowledge_access JSONB DEFAULT '[]'::jsonb;")

    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS document_id VARCHAR(100);")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS collection_name VARCHAR(100) DEFAULT 'General Knowledge';")

    op.execute("ALTER TABLE workflow_approvals ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'MEDIUM';")
    op.execute("ALTER TABLE workflow_approvals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;")
    op.execute("ALTER TABLE workflow_approvals ADD COLUMN IF NOT EXISTS comments TEXT;")

    op.execute("ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS title VARCHAR(255) DEFAULT 'Workflow Execution';")
    op.execute("ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS dag_plan JSONB;")
    op.execute("ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS thread_id VARCHAR(255);")
    op.execute("ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;")

    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS tool_name VARCHAR(100) DEFAULT 'general';")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS input_parameters JSONB;")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER;")

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(50) DEFAULT 'ALL';")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;")

    # 2. Update Check Constraints
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('Owner', 'Admin', 'Manager', 'Employee', 'CEO', 'Guest'));")
    
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_department;")
    op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_department CHECK (department IN ('BOARD', 'HR', 'LEGAL', 'IT', 'FINANCE', 'SALES', 'ALL'));")

    # 3. Create missing tables (tasks and task_comments) if not existing
    op.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id UUID PRIMARY KEY,
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        creator_id UUID NOT NULL REFERENCES users(id),
        assignee_id UUID REFERENCES users(id),
        ai_agent_id UUID REFERENCES ai_agents(id),
        priority VARCHAR(20) DEFAULT 'MEDIUM',
        due_date TIMESTAMP WITH TIME ZONE,
        status VARCHAR(50) DEFAULT 'DRAFT',
        attachments JSONB DEFAULT '[]'::jsonb,
        output_result JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS task_comments (
        id UUID PRIMARY KEY,
        task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id),
        content TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_comments;")
    op.execute("DROP TABLE IF EXISTS tasks;")
