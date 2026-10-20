"""050 — llm offers: free LLM models, tiers and credits found, and their evaluation.

docs/specs/free-llm-offers.md (Job 1 of docs/design/11_persona_roster_plan.md):
``llm_offers`` holds what was found (per tenant) with its terms, status and
benchmark result; ``llm_catalog_snapshots`` holds yesterday's free-model ids
per provider, so the daily catalog diff is a plain comparison. Snapshots are a
public catalog, not tenant data, so they carry no tenant.

No schema qualifier, matching every migration since 023.

Revision ID: 050
Revises: 049
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_offers",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("dedup_key", sa.String(500), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(300), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("terms", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("evaluation", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("uq_llm_offers_key", "llm_offers", ["tenant_id", "dedup_key"], unique=True)
    op.create_index("ix_llm_offers_tenant_status", "llm_offers", ["tenant_id", "status"])
    op.create_table(
        "llm_catalog_snapshots",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column(
            "taken_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("model_ids", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_llm_catalog_snapshots_provider", "llm_catalog_snapshots", ["provider", "taken_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_catalog_snapshots_provider", table_name="llm_catalog_snapshots")
    op.drop_table("llm_catalog_snapshots")
    op.drop_index("ix_llm_offers_tenant_status", table_name="llm_offers")
    op.drop_index("uq_llm_offers_key", table_name="llm_offers")
    op.drop_table("llm_offers")
