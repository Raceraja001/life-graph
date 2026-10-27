"""054 — feature ideas: tech-watch findings become decisions the owner makes.

The feature watch (2026-10-27) reports what the big assistant apps shipped.
Each finding now carries how far its source can be trusted, whether it is a
feature at all, how it fits Life Graph (have / part / new) with one
suggestion, and the owner's decision on it (services/feature_ideas.py).

No schema qualifier, matching every migration since 023.

Revision ID: 054
Revises: 053
Create Date: 2026-10-27
"""

import sqlalchemy as sa

from alembic import op

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # new | considering | not_for_us | dismissed
    op.add_column(
        "topic_findings", sa.Column("status", sa.String(16), nullable=False, server_default="new")
    )
    # official | unknown | suspicious; null until checked
    op.add_column("topic_findings", sa.Column("trust", sa.String(16), nullable=True))
    # null until assessed; false = not a feature (pricing, payments, news)
    op.add_column("topic_findings", sa.Column("is_feature", sa.Boolean(), nullable=True))
    op.add_column("topic_findings", sa.Column("app", sa.String(80), nullable=True))
    # have | part | new
    op.add_column("topic_findings", sa.Column("fit", sa.String(8), nullable=True))
    op.add_column("topic_findings", sa.Column("suggestion", sa.Text(), nullable=True))
    op.add_column(
        "topic_findings", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    for col in ("decided_at", "suggestion", "fit", "app", "is_feature", "trust", "status"):
        op.drop_column("topic_findings", col)
