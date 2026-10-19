"""045 — documents: the user's identity and ownership documents.

Passports, licences, policies, warranties: kind, title, issuer, the last four
characters of the number only, issue and expiry dates, and which expiry
reminders were already sent (docs/specs/assistant-capabilities.md, Phase B).

No schema qualifier, matching every migration since 023.

Revision ID: 045
Revises: 044
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="other"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(200), nullable=True),
        sa.Column("number_last4", sa.String(8), nullable=True),
        sa.Column("holder", sa.String(120), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("reminders_sent", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_documents_tenant_expiry", "documents", ["tenant_id", "expires_on"])


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_expiry", table_name="documents")
    op.drop_table("documents")
