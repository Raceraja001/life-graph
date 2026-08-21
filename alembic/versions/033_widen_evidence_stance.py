"""033 — Widen evidence.stance so "contradicts" fits.

``stance`` was VARCHAR(10). The three values the code writes are
"supports" (8), "neutral" (7) and "contradicts" — which is **11**. Every
attempt to store contradicting evidence failed with
StringDataRightTruncationError, so the evidence system could only ever
record agreement.

That is the opposite of what it is for: the preference engine exists to
challenge a stored preference with evidence, and the contradicting half
could never be persisted.

Revision ID: 033
Revises: 032
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "evidence",
        "stance",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Rows holding "contradicts" would be truncated by a narrower column, so
    # clear them to the neutral value before shrinking it back.
    op.execute("UPDATE evidence SET stance = 'neutral' WHERE length(stance) > 10")
    op.alter_column(
        "evidence",
        "stance",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
