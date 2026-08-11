"""032 — Autonomy kill-switch: autonomy_paused/autonomy_paused_at on tenant_configs.

Adds a per-tenant kill-switch flag so autonomous action execution
(``AutoFixService._run_action``) can be halted immediately without
affecting the tenant's general read/write access (that's what
``TenantConfig.status`` already does — a separate, narrower concern).

Revision ID: 032
Revises: 031
Create Date: 2026-08-11
"""

import sqlalchemy as sa

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_configs",
        sa.Column("autonomy_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tenant_configs",
        sa.Column("autonomy_paused_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_configs", "autonomy_paused_at")
    op.drop_column("tenant_configs", "autonomy_paused")
