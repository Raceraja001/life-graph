"""Add memory_links table for bidirectional Zettelkasten-style links.

Revision ID: 009
Revises: 008

Creates the memory_links table for typed relationships between memories:
- BECAUSE — causal link
- EVIDENCED_BY — supporting evidence
- RELATED_TO — semantic similarity
- CONTRADICTS — conflicting information
- SUPERSEDES — updated version
- LEADS_TO — temporal sequence
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE memory_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            target_memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            link_type VARCHAR(30) NOT NULL,
            strength FLOAT NOT NULL DEFAULT 0.5,
            properties JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'legacy',
            UNIQUE(source_memory_id, target_memory_id, link_type)
        )
    """)
    op.execute("CREATE INDEX ix_memory_links_source ON memory_links(source_memory_id)")
    op.execute("CREATE INDEX ix_memory_links_target ON memory_links(target_memory_id)")
    op.execute("CREATE INDEX ix_memory_links_type ON memory_links(link_type)")
    op.execute("CREATE INDEX ix_memory_links_tenant ON memory_links(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memory_links")
