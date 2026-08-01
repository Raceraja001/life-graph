"""028 — Web Push subscriptions.

Revision ID: 028
Revises: 027
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="legacy"),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_push_sub_endpoint", "push_subscriptions", ["endpoint"], unique=True)
    op.create_index("ix_push_sub_tenant", "push_subscriptions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_push_sub_tenant", table_name="push_subscriptions")
    op.drop_index("uq_push_sub_endpoint", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
