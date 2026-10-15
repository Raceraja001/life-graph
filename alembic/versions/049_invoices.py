"""049 — invoices: what the user bills their clients.

docs/specs/assistant-capabilities.md, Phase H: per-tenant numbering, line
items, stored totals, status (draft, sent, paid, void) and the dates the
overdue reminder needs.

No schema qualifier, matching every migration since 023.

Revision ID: 049
Revises: 048
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("number", sa.String(32), nullable=False),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("client_email", sa.String(200), nullable=True),
        sa.Column("client_details", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("items", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(8), nullable=False, server_default="draft"),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("sent_on", sa.Date(), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_reminded_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("uq_invoices_number", "invoices", ["tenant_id", "number"], unique=True)
    op.create_index("ix_invoices_tenant_status", "invoices", ["tenant_id", "status", "due_on"])


def downgrade() -> None:
    op.drop_index("ix_invoices_tenant_status", table_name="invoices")
    op.drop_index("uq_invoices_number", table_name="invoices")
    op.drop_table("invoices")
