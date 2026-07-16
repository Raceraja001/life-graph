"""025 — Embedding modernization: config-driven vector dimension (null-and-rebuild).

Alters the pgvector ``embedding`` column on all 8 embedded tables to
``settings.embedding_dimension`` (bge-m3 = 1024), clearing old vectors first.
Vector indexes are dropped before and recreated after the type change. Run the
versioned re-embed job immediately after (``life-graph reembed``) — search is
degraded until embeddings are regenerated.

See docs/superpowers/specs/2026-07-15-embedding-modernization-design.md.

Revision ID: 025
Revises: 024
Create Date: 2026-07-15
"""

from alembic import op
from life_graph.config import settings

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None

_DIM = settings.embedding_dimension

# (schema, table, has_embedding_model_column)
_EMBED_TABLES = [
    (None, "memories", True),
    (None, "sessions", False),
    (None, "intentions", False),
    (None, "knowledge_gaps", False),
    (None, "preferences", True),
    (None, "evidence", True),
    (None, "shared_context", False),
    ("life_graph", "decisions", False),
]

# (index_name, schema, table, create_sql_template) — recreated at the new dim.
_HNSW = "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
_VECTOR_INDEXES = [
    ("idx_memories_embedding", None, "memories", _HNSW),
    ("idx_sessions_embedding", None, "sessions", _HNSW),
    ("idx_intentions_embedding", None, "intentions", _HNSW),
    ("ix_decisions_embedding", "life_graph", "decisions",
     "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"),
]


def _qualified(schema: str | None, table: str) -> str:
    return f"{schema}.{table}" if schema else table


def _drop_indexes() -> None:
    for name, schema, _table, _sql in _VECTOR_INDEXES:
        qname = f"{schema}.{name}" if schema else name
        op.execute(f"DROP INDEX IF EXISTS {qname}")


def _create_indexes() -> None:
    for name, schema, table, sql in _VECTOR_INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {_qualified(schema, table)} {sql}"
        )


def _alter_dim(dim: int) -> None:
    for schema, table, has_model in _EMBED_TABLES:
        qt = _qualified(schema, table)
        # Clear incompatible vectors first so the type change always succeeds.
        reset_cols = "embedding = NULL" + (", embedding_model = NULL" if has_model else "")
        op.execute(f"UPDATE {qt} SET {reset_cols}")
        op.execute(f"ALTER TABLE {qt} ALTER COLUMN embedding TYPE vector({dim})")


def upgrade() -> None:
    _drop_indexes()
    _alter_dim(_DIM)
    _create_indexes()


def downgrade() -> None:
    _drop_indexes()
    _alter_dim(768)
    _create_indexes()
