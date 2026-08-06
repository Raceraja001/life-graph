"""031 — Autonomy actions: kind/instruction columns; action_command nullable.

Adds a ``kind`` discriminator ('command' | 'agent_task') and a nullable
``instruction`` column to ``auto_actions`` and ``approval_queue``, and
relaxes ``action_command`` to nullable on both tables (agent_task actions
carry a natural-language ``instruction`` instead of a shell command).

Revision ID: 031
Revises: 030
Create Date: 2026-08-06
"""

import sqlalchemy as sa

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("auto_actions", "approval_queue"):
        op.add_column(
            table,
            sa.Column("kind", sa.Text(), nullable=False, server_default="command"),
        )
        op.add_column(
            table,
            sa.Column("instruction", sa.Text(), nullable=True),
        )
        op.alter_column(
            table,
            "action_command",
            existing_type=sa.Text(),
            nullable=True,
        )


def downgrade() -> None:
    for table in ("auto_actions", "approval_queue"):
        op.alter_column(
            table,
            "action_command",
            existing_type=sa.Text(),
            nullable=False,
        )
        op.drop_column(table, "instruction")
        op.drop_column(table, "kind")
