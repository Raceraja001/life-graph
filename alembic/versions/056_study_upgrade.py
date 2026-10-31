"""056 — study upgrade: card status, lapses, sources and a review log.

docs/research/study-helper-spec-2026-10.html. ``review_cards`` gains a status
(draft cards wait for the owner before they are scheduled), a lapse count,
the day it was last reviewed and where it came from. ``study_reviews`` keeps
every answer, for streaks, accuracy per deck and a later FSRS fit.

Existing cards become ``active`` through the server default: nothing changes
for them. Additive and reversible.

Revision ID: 056
Revises: 055
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_cards",
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
    )
    op.add_column(
        "review_cards", sa.Column("lapses", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("review_cards", sa.Column("last_reviewed_on", sa.Date(), nullable=True))
    op.add_column("review_cards", sa.Column("source_kind", sa.String(16), nullable=True))
    op.add_column("review_cards", sa.Column("source_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_review_cards_status", "review_cards", ["tenant_id", "status"])

    op.create_table(
        "study_reviews",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("card_id", UUID(), nullable=True),
        sa.Column("deck", sa.String(80), nullable=False, server_default="general"),
        sa.Column("grade", sa.String(8), nullable=False),
        sa.Column("reviewed_on", sa.Date(), nullable=False),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("interval_before", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ease_after", sa.Float(), nullable=False, server_default="2.5"),
    )
    op.create_index("ix_study_reviews_day", "study_reviews", ["tenant_id", "reviewed_on"])
    op.create_index("ix_study_reviews_deck", "study_reviews", ["tenant_id", "deck"])


def downgrade() -> None:
    op.drop_index("ix_study_reviews_deck", table_name="study_reviews")
    op.drop_index("ix_study_reviews_day", table_name="study_reviews")
    op.drop_table("study_reviews")
    op.drop_index("ix_review_cards_status", table_name="review_cards")
    op.drop_column("review_cards", "source_id")
    op.drop_column("review_cards", "source_kind")
    op.drop_column("review_cards", "last_reviewed_on")
    op.drop_column("review_cards", "lapses")
    op.drop_column("review_cards", "status")
