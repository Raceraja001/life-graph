"""048 — review_cards: spaced-repetition study cards.

docs/specs/assistant-capabilities.md, Phase G: front, back, deck, the SM-2
scheduling fields (ease, interval, repetitions, due date) and a per-tenant
dedup key over the normalised front.

No schema qualifier, matching every migration since 023.

Revision ID: 048
Revises: 047
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_cards",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("deck", sa.String(80), nullable=False, server_default="general"),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("source_memory_id", UUID(), nullable=True),
        sa.Column("ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("last_grade", sa.String(8), nullable=True),
        sa.Column("reviews", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_review_cards_dedup", "review_cards", ["tenant_id", "dedup_key"], unique=True
    )
    op.create_index("ix_review_cards_due", "review_cards", ["tenant_id", "due_on"])


def downgrade() -> None:
    op.drop_index("ix_review_cards_due", table_name="review_cards")
    op.drop_index("uq_review_cards_dedup", table_name="review_cards")
    op.drop_table("review_cards")
