"""Add BM25 full-text search column and GIN index.

Revision ID: 007
Revises: 006

Adds a tsvector column with GIN index for PostgreSQL full-text search (BM25).
This enables hybrid search: vector similarity + keyword matching + graph proximity.

The tsvector column is a GENERATED ALWAYS STORED column — PostgreSQL
automatically keeps it in sync with the content column.
"""

from alembic import op

# revision identifiers
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tsvector column generated from content (auto-updated by Postgres)
    op.execute("""
        ALTER TABLE memories
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
    """)

    # GIN index for fast full-text search
    op.execute("""
        CREATE INDEX ix_memories_content_tsv
        ON memories USING GIN(content_tsv);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_content_tsv;")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS content_tsv;")
