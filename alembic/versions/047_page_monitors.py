"""047 — page_monitors: pages the user asked the assistant to watch.

docs/specs/assistant-capabilities.md, Phase D: a URL, an optional part of
the page, a mode (change, price_below, contains) and the last observation,
checked by the page_monitor watcher.

No schema qualifier, matching every migration since 023.

Revision ID: 047
Revises: 046
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_monitors",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False, server_default="change"),
        sa.Column("selector", sa.Text(), nullable=True),
        sa.Column("threshold", sa.Numeric(14, 2), nullable=True),
        sa.Column("pattern", sa.String(200), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_hash", sa.String(64), nullable=True),
        sa.Column("last_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("last_excerpt", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_page_monitors_tenant", "page_monitors", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_page_monitors_tenant", table_name="page_monitors")
    op.drop_table("page_monitors")
