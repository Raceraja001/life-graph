"""Move the archive-proposal horizon from ~40 days to ~6 months.

Revision ID: 035
Revises: 034
Create Date: 2026-08-22

``memories.decay_rate`` is the lambda in the proposal curve

    effective_importance = importance * exp(-decay_rate * days_since_activity)

A memory becomes a candidate for a *removal proposal* once that value falls
below ``settings.decay_archive_threshold`` (0.01). At the old rate of 0.1 that
happened 39 days after last activity for importance 0.5 -- far too eager now
that decay proposes rather than archives. At 0.0217 the horizon is ~180 days
for importance 0.5 and ~212 for importance 1.0.

This rate does not affect recall ordering: ``scoring/ranking.py`` demotes
stale memories with its own recency curve, independent of this column.

Only rows still carrying the old default are rewritten, so a per-memory
override set by hand survives the migration.
"""

import sqlalchemy as sa

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None

_OLD_RATE = "0.1"
_NEW_RATE = "0.0217"


def upgrade() -> None:
    op.alter_column(
        "memories",
        "decay_rate",
        existing_type=sa.Float(),
        server_default=_NEW_RATE,
        existing_nullable=False,
    )
    op.execute(
        sa.text("UPDATE memories SET decay_rate = :new WHERE decay_rate = :old").bindparams(
            new=float(_NEW_RATE), old=float(_OLD_RATE)
        )
    )


def downgrade() -> None:
    op.alter_column(
        "memories",
        "decay_rate",
        existing_type=sa.Float(),
        server_default=_OLD_RATE,
        existing_nullable=False,
    )
    op.execute(
        sa.text("UPDATE memories SET decay_rate = :old WHERE decay_rate = :new").bindparams(
            new=float(_NEW_RATE), old=float(_OLD_RATE)
        )
    )
