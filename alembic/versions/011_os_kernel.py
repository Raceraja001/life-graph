"""Add OS Kernel tables: agent_sessions, agent_personas, agent_tasks.

Revision ID: 011
Revises: 010

Adds three tables for the OS Kernel process manager:
- agent_sessions: tracks routing decisions and conversation chains
- agent_personas: database-driven agent configurations
- agent_tasks: tracks every agent execution like OS processes
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Agent Sessions ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'legacy',
            user_message TEXT NOT NULL,
            classified_intent VARCHAR(30),
            classification_conf FLOAT DEFAULT 0.0,
            routed_to VARCHAR(100),
            handoff_chain JSONB NOT NULL DEFAULT '[]',
            total_duration_ms INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            total_cost_usd NUMERIC(10, 6) DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            context JSONB NOT NULL DEFAULT '{}',
            memory_session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS ix_agent_sessions_tenant
            ON agent_sessions(tenant_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_agent_sessions_intent
            ON agent_sessions(tenant_id, classified_intent);
    """)

    # ── Agent Personas ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_personas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'legacy',
            name VARCHAR(100) NOT NULL,
            display_name VARCHAR(200),
            description TEXT,
            system_prompt TEXT NOT NULL,
            model VARCHAR(100) NOT NULL DEFAULT 'gemini/gemini-2.5-flash',
            temperature FLOAT NOT NULL DEFAULT 0.7,
            max_tokens INTEGER NOT NULL DEFAULT 4096,
            allowed_tools TEXT[] DEFAULT '{}',
            intent_tags TEXT[] DEFAULT '{}',
            icon VARCHAR(10),
            is_builtin BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            properties JSONB NOT NULL DEFAULT '{}',
            use_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_personas_name
            ON agent_personas(tenant_id, name);
        CREATE INDEX IF NOT EXISTS ix_agent_personas_tenant
            ON agent_personas(tenant_id, is_active);
        CREATE INDEX IF NOT EXISTS ix_agent_personas_intent
            ON agent_personas USING gin(intent_tags);
    """)

    # ── Agent Tasks ───────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'legacy',
            task_name TEXT,
            agent_name VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            priority VARCHAR(10) NOT NULL DEFAULT 'normal',
            input JSONB NOT NULL DEFAULT '{}',
            result JSONB NOT NULL DEFAULT '{}',
            error TEXT,
            logs JSONB NOT NULL DEFAULT '[]',
            token_usage JSONB NOT NULL DEFAULT '{}',
            model_used VARCHAR(100),
            timeout_seconds INTEGER NOT NULL DEFAULT 300,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 2,
            parent_task_id UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
            session_id UUID REFERENCES agent_sessions(id) ON DELETE SET NULL,
            project_id UUID,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS ix_agent_tasks_tenant_status
            ON agent_tasks(tenant_id, status);
        CREATE INDEX IF NOT EXISTS ix_agent_tasks_tenant_created
            ON agent_tasks(tenant_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_agent_tasks_agent
            ON agent_tasks(tenant_id, agent_name);
        CREATE INDEX IF NOT EXISTS ix_agent_tasks_session
            ON agent_tasks(session_id);
        CREATE INDEX IF NOT EXISTS ix_agent_tasks_parent
            ON agent_tasks(parent_task_id);
        CREATE INDEX IF NOT EXISTS ix_agent_tasks_queued
            ON agent_tasks(status, priority, created_at)
            WHERE status = 'queued';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_tasks CASCADE;")
    op.execute("DROP TABLE IF EXISTS agent_personas CASCADE;")
    op.execute("DROP TABLE IF EXISTS agent_sessions CASCADE;")
