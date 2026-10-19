"""046 — money: transactions, category rules and monthly budgets.

docs/specs/assistant-capabilities.md, Phase C. Transactions come from
statement CSVs and bank alert texts; a per-tenant hash makes re-imports
idempotent. Category rules are learned from the user's corrections.

No schema qualifier, matching every migration since 023.

Revision ID: 046
Revises: 045
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "money_transactions",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("merchant", sa.String(120), nullable=True),
        sa.Column("category", sa.String(40), nullable=False, server_default="uncategorised"),
        sa.Column("category_source", sa.String(16), nullable=False, server_default="rule"),
        sa.Column("account_last4", sa.String(4), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="csv"),
        sa.Column("dedup_hash", sa.String(64), nullable=False),
        _created(),
    )
    op.create_index(
        "uq_money_transactions_dedup",
        "money_transactions",
        ["tenant_id", "dedup_hash"],
        unique=True,
    )
    op.create_index(
        "ix_money_transactions_tenant_day", "money_transactions", ["tenant_id", "occurred_on"]
    )

    op.create_table(
        "money_category_rules",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("pattern", sa.String(120), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        _created(),
    )
    op.create_index(
        "uq_money_rules_pattern", "money_category_rules", ["tenant_id", "pattern"], unique=True
    )

    op.create_table(
        "money_budgets",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("alerts_sent", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _created(),
    )
    op.create_index(
        "uq_money_budgets_category", "money_budgets", ["tenant_id", "category"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_money_budgets_category", table_name="money_budgets")
    op.drop_table("money_budgets")
    op.drop_index("uq_money_rules_pattern", table_name="money_category_rules")
    op.drop_table("money_category_rules")
    op.drop_index("ix_money_transactions_tenant_day", table_name="money_transactions")
    op.drop_index("uq_money_transactions_dedup", table_name="money_transactions")
    op.drop_table("money_transactions")
