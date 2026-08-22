"""Add notification_channels.name

The API has always accepted a ``name`` on channel creation — it is declared
and documented on ``NotificationChannelCreate`` — but there was nowhere to put
it, so ``create_notification_channel`` silently dropped it and
``NotificationChannelResponse.name`` reported null for every channel.

Revision ID: 034
Revises: 033
"""

from alembic import op
import sqlalchemy as sa

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_channels",
        sa.Column("name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_channels", "name")
