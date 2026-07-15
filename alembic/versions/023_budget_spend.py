"""023 — The Governor: budget_spend ledger.

Month-to-date spend per tenant per category, so the Governor can authorize
spend against a monthly cap. See
docs/superpowers/specs/2026-07-15-governor-budget-kernel-design.md.

Revision ID: 023
Revises: 022
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_spend",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("spent_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "period_month", "category", name="uq_budget_spend_key"
        ),
    )
    op.create_index(
        "ix_budget_spend_lookup", "budget_spend", ["tenant_id", "period_month"]
    )


def downgrade() -> None:
    op.drop_index("ix_budget_spend_lookup", table_name="budget_spend")
    op.drop_table("budget_spend")
