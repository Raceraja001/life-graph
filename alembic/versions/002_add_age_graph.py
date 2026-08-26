"""Add Apache AGE graph layer

Apache AGE is a *compiled* Postgres extension. It is not present on managed
Postgres (Supabase, Neon, RDS) and not present in the stock
``pgvector/pgvector:pg16`` image, so this migration must be optional: it is the
2nd of 35 revisions, and raising here blocks 003..035 and leaves the database
with nothing but the tables from 001.

``CREATE EXTENSION IF NOT EXISTS age`` does *not* make it optional — IF NOT
EXISTS suppresses "already exists", not "extension is not available" — so the
availability probe below is the real guard. When AGE is missing the migration
logs and returns; graph search then degrades to vector+BM25 (see
``LIFE_GRAPH_GRAPH_ENABLED``).

One thing still has to happen on the AGE-less path: the ``life_graph``
**schema**. AGE creates it as a side effect of ``create_graph('life_graph')``,
and migrations 019 and 021 put nine ordinary application tables in it
(capture_events, corrections, driver_stats, verification_runs, ...) — so
skipping this migration outright merely moved the failure to 019 with
``schema "life_graph" does not exist``. Without AGE we create the schema
ourselves; it is a namespace the application owns, not a graph artifact.

Revision ID: 002
Revises: 001
Create Date: 2026-07-03
"""

import logging
from collections.abc import Sequence

from alembic import context, op

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRAPH_NAME = "life_graph"

# Vertex labels for the knowledge graph
VERTEX_LABELS = [
    "Entity",
    "Person",
    "Project",
    "Technology",
    "Decision",
    "Concept",
    "Domain",
]

# Edge labels for relationships between vertices
EDGE_LABELS = [
    "prefers",
    "uses",
    "decided",
    "related_to",
    "supersedes",
    "knows",
    "part_of",
    "conflicts_with",
]

_MISSING = (
    "Apache AGE is not available on this PostgreSQL server. Skipping the "
    "knowledge-graph migration — the remaining migrations will run normally and "
    "the application degrades graph search to vector+BM25. Set "
    "LIFE_GRAPH_GRAPH_ENABLED=false to silence the runtime probe as well."
)


def _probe(sql: str) -> bool:
    """Run a one-row existence probe on its **own** connection.

    The probe must never run on the migration connection. A query there opens
    an implicit transaction, alembic's ``context.begin_transaction()`` then
    finds one already in progress and becomes a no-op, and every migration in
    the run is silently rolled back while ``alembic upgrade head`` still exits
    0. ``alembic/env.py`` loads the AGE label list on its own connection for
    exactly this reason.
    """
    engine = op.get_bind().engine
    with engine.connect() as probe:
        return probe.exec_driver_sql(sql).first() is not None


def _age_available() -> bool:
    """True when this server can ``CREATE EXTENSION age``."""
    return _probe("SELECT 1 FROM pg_available_extensions WHERE name = 'age'")


def _age_installed() -> bool:
    """True when the AGE extension is actually created in this database."""
    return _probe("SELECT 1 FROM pg_extension WHERE extname = 'age'")


def upgrade() -> None:
    # Offline mode emits SQL without a live connection, so there is nothing to
    # probe — emit the full script and let the operator decide.
    if not context.is_offline_mode() and not _age_available():
        logger.warning(_MISSING)
        # 019 and 021 create tables in this schema; AGE would have made it.
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {GRAPH_NAME}")
        # Pin the search_path exactly as the AGE branch does below. The
        # database role is also called "life_graph", so the default
        # `"$user", public` would resolve `"$user"` to the schema we just
        # created and silently divert every unqualified CREATE TABLE in
        # revisions 003..035 into it.
        op.execute("SET search_path = public")
        return

    # -- Load Apache AGE extension --
    op.execute("CREATE EXTENSION IF NOT EXISTS age")
    op.execute("LOAD 'age'")
    op.execute('SET search_path = ag_catalog, "$user", public')

    # -- Create the graph (re-run safe: AGE has no CREATE GRAPH IF NOT EXISTS) --
    op.execute(
        f"SELECT create_graph('{GRAPH_NAME}') "
        f"WHERE NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = '{GRAPH_NAME}')"
    )
    op.execute("SET search_path = public, ag_catalog")

    # -- Create vertex labels --
    for label in VERTEX_LABELS:
        op.execute(_create_label_sql("create_vlabel", label))

    # -- Create edge labels --
    for label in EDGE_LABELS:
        op.execute(_create_label_sql("create_elabel", label))


def _create_label_sql(fn: str, label: str) -> str:
    """Label creation that is a no-op when the label already exists."""
    return (
        f"SELECT {fn}('{GRAPH_NAME}', '{label}') WHERE NOT EXISTS ("
        f"SELECT 1 FROM ag_catalog.ag_label l "
        f"JOIN ag_catalog.ag_graph g ON l.graph = g.graphid "
        f"WHERE g.name = '{GRAPH_NAME}' AND l.name = '{label}')"
    )


def downgrade() -> None:
    if not context.is_offline_mode() and not _age_installed():
        logger.warning("Apache AGE is not installed in this database — dropping the schema only.")
        # Mirrors drop_graph(..., true) on the AGE path. By the time 002
        # downgrades, 019 and 021 have already dropped their tables.
        op.execute(f"DROP SCHEMA IF EXISTS {GRAPH_NAME} CASCADE")
        return

    op.execute("LOAD 'age'")
    op.execute('SET search_path = ag_catalog, "$user", public')
    op.execute(
        f"SELECT drop_graph('{GRAPH_NAME}', true) "
        f"WHERE EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = '{GRAPH_NAME}')"
    )
    op.execute("SET search_path = public")
    op.execute("DROP EXTENSION IF EXISTS age CASCADE")
