"""055 — feature ideas: how much an idea is worth, and duplicates.

The first assessment (2026-10-27) offered virtual try-on for clothes as an idea
for a personal assistant, and the same feature twice from two sites. Each
assessed finding now says whether it is worth it for Life Graph (high /
medium / low, with why) and, when it is the same feature as an earlier one,
which (``duplicate_of``) — shown once, with both sources.

Revision ID: 055
Revises: 054
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # high, medium or low
    op.add_column("topic_findings", sa.Column("worth", sa.String(8), nullable=True))
    op.add_column("topic_findings", sa.Column("worth_why", sa.Text(), nullable=True))
    op.add_column("topic_findings", sa.Column("duplicate_of", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    for col in ("duplicate_of", "worth_why", "worth"):
        op.drop_column("topic_findings", col)
