"""028 — Conversations: last_distilled_at marker column.

Revision ID: 028
Revises: 027
Create Date: 2026-07-31
"""

import sqlalchemy as sa

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("last_distilled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "last_distilled_at")
