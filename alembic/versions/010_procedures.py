"""Add procedures table for procedural/strategy memory.

Revision ID: 010
Revises: 008

Adds the `procedures` table for storing learned behavioral patterns
and strategies extracted from recurring session workflows.
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS procedures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trigger TEXT NOT NULL,
            steps JSONB NOT NULL DEFAULT '[]',
            description TEXT,
            confidence FLOAT NOT NULL DEFAULT 0.5,
            learned_from JSONB NOT NULL DEFAULT '[]',
            times_applied INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            tags TEXT[] DEFAULT '{}',
            properties JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'legacy'
        );

        CREATE INDEX IF NOT EXISTS ix_procedures_status
            ON procedures(status);
        CREATE INDEX IF NOT EXISTS ix_procedures_tenant
            ON procedures(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_procedures_confidence
            ON procedures(confidence DESC);
        CREATE INDEX IF NOT EXISTS ix_procedures_tags
            ON procedures USING gin(tags);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS procedures CASCADE;")
