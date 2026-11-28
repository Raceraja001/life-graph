"""063 — decisions.superseded_at: when a decision was superseded.

ADR docs/design/adr-m8-ingestion-structure.md §5.5. The decision lifecycle
(§5.4) needs one timestamp. Its siblings ``decided_at`` and ``reviewed_at`` are
columns on the same table, and change detection compares it to a time window,
so it is a typed column rather than a key in ``properties``.

- Nullable, no default, no server default.
- No index: decisions are read by id or by (tenant_id, status), which
  ``ix_decisions_tenant_status`` already covers.
- No backfill: a row that is already superseded keeps NULL, which means
  "time unknown". We never invent a time.

The table is schema-qualified (``life_graph.decisions``) because of the
``"$user"`` search_path issue (D30).

Downgrade drops the column. ``status`` and ``superseded_by`` stay, so only the
time is lost.

Revision ID: 063
Revises: 062
Create Date: 2026-11-28
"""

import sqlalchemy as sa

from alembic import op

revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        schema="life_graph",
    )


def downgrade() -> None:
    op.drop_column("decisions", "superseded_at", schema="life_graph")
