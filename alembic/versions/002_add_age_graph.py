"""Add Apache AGE graph layer

Revision ID: 002
Revises: 001
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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


def upgrade() -> None:
    # -- Load Apache AGE extension --
    op.execute("CREATE EXTENSION IF NOT EXISTS age")
    op.execute("LOAD 'age'")
    op.execute(
        "SET search_path = ag_catalog, \"$user\", public"
    )

    # -- Create the graph --
    op.execute("SELECT create_graph('life_graph')")
    op.execute("SET search_path = public, ag_catalog")

    # -- Create vertex labels --
    for label in VERTEX_LABELS:
        op.execute(
            f"SELECT create_vlabel('life_graph', '{label}')"
        )

    # -- Create edge labels --
    for label in EDGE_LABELS:
        op.execute(
            f"SELECT create_elabel('life_graph', '{label}')"
        )


def downgrade() -> None:
    op.execute("LOAD 'age'")
    op.execute(
        "SET search_path = ag_catalog, \"$user\", public"
    )
    op.execute("SELECT drop_graph('life_graph', true)")
    op.execute("DROP EXTENSION IF EXISTS age CASCADE")
