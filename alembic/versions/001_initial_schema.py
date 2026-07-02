"""Initial schema: memories, sessions, intentions, knowledge_gaps

Revision ID: 001
Revises: None
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Enable extensions --
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # -- Memories table --
    op.create_table(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("tags", ARRAY(sa.String()), server_default="{}"),
        sa.Column("properties", JSONB(), server_default="{}"),
        sa.Column("importance", sa.Float(), server_default="0.5"),
        sa.Column("importance_tier", sa.String(), server_default="'normal'"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("source_type", sa.String(), server_default="'inferred'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), server_default="0"),
        sa.Column("last_accessed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decay_rate", sa.Float(), server_default="0.1"),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("trust_score", sa.Float(), server_default="0.5"),
        sa.Column("supersedes", UUID(as_uuid=True), sa.ForeignKey("memories.id"), nullable=True),
        sa.Column("superseded_by", UUID(as_uuid=True), sa.ForeignKey("memories.id"), nullable=True),
        sa.Column("status", sa.String(), server_default="'active'"),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("embedding_model", sa.String(), server_default="'all-mpnet-base-v2'"),
        sa.Column("owner", sa.String(), server_default="'default'"),
    )

    # -- Sessions table --
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context", JSONB(), server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("memories_created", sa.Integer(), server_default="0"),
        sa.Column("memories_accessed", sa.Integer(), server_default="0"),
        sa.Column("embedding", Vector(768), nullable=True),
    )

    # -- Intentions table --
    op.create_table(
        "intentions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.String(), server_default="'event'"),
        sa.Column("trigger_condition", sa.Text(), nullable=True),
        sa.Column("trigger_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_match", JSONB(), server_default="{}"),
        sa.Column("priority", sa.String(), server_default="'normal'"),
        sa.Column("status", sa.String(), server_default="'pending'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_session", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("source_memory", UUID(as_uuid=True), sa.ForeignKey("memories.id"), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
    )

    # -- Knowledge Gaps table --
    op.create_table(
        "knowledge_gaps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("query_count", sa.Integer(), server_default="1"),
        sa.Column("first_asked", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("last_asked", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_by", UUID(as_uuid=True), sa.ForeignKey("memories.id"), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
    )

    # -- Memory Sessions junction --
    op.create_table(
        "memory_sessions",
        sa.Column("memory_id", UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # -- Indexes --

    # pgvector HNSW indexes (cosine distance)
    op.execute("""
        CREATE INDEX idx_memories_embedding ON memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_sessions_embedding ON sessions
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_intentions_embedding ON intentions
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # GIN indexes for array/JSONB
    op.create_index("idx_memories_tags", "memories", ["tags"], postgresql_using="gin")
    op.execute("CREATE INDEX idx_memories_properties ON memories USING GIN(properties jsonb_path_ops)")

    # BTREE indexes for common queries
    op.create_index("idx_memories_created_at", "memories", [sa.text("created_at DESC")])
    op.create_index("idx_memories_status", "memories", ["status"])
    op.create_index("idx_memories_importance", "memories", [sa.text("importance DESC")])
    op.create_index("idx_memories_last_accessed", "memories", ["last_accessed"])

    # Intentions indexes
    op.create_index("idx_intentions_status", "intentions", ["status"])
    op.create_index("idx_intentions_trigger_time", "intentions", ["trigger_time"])

    # Sessions
    op.create_index("idx_sessions_started", "sessions", [sa.text("started_at DESC")])

    # Touch function (helper for updating access metadata)
    op.execute("""
        CREATE OR REPLACE FUNCTION touch_memory(mem_id UUID)
        RETURNS VOID AS $$
        BEGIN
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed = NOW(),
                updated_at = NOW()
            WHERE id = mem_id;
        END;
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS touch_memory(UUID)")
    op.drop_table("memory_sessions")
    op.drop_table("knowledge_gaps")
    op.drop_table("intentions")
    op.drop_table("sessions")
    op.drop_table("memories")
