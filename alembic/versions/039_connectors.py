"""039 — connector_accounts and connector_items (docs/specs/connectors.md).

Calendar and email reading, built as connector plugins. ``connector_accounts``
holds one row per configured mailbox or calendar (no credentials — those live
in 0600 files outside the DB). ``connector_items`` is a bounded local index of
events and messages: subjects, senders, times and a locally written summary;
mail bodies are never stored. Retention (90 days of mail, events from 90 days
back to a year ahead) is enforced nightly, which also bounds what the normal
backups contain.

No schema qualifier, matching every migration since 023.

Revision ID: 039
Revises: 038
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op
from life_graph.config import settings

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_accounts",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("connector", sa.String(64), nullable=False),
        sa.Column("account_key", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("auth_method", sa.String(16), nullable=False),
        sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("exposure", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_interval_min", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("cursor", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(16), nullable=False, server_default="never_synced"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "connector", "account_key", name="uq_connector_account_key"
        ),
        sa.CheckConstraint(
            "exposure IN ('standard', 'local_only')", name="ck_connector_accounts_exposure"
        ),
    )

    op.create_table(
        "connector_items",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "account_id",
            UUID(),
            sa.ForeignKey("connector_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(512), nullable=False),
        sa.Column("thread_key", sa.String(512), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("sender_name", sa.Text(), nullable=True),
        sa.Column("sender_addr", sa.Text(), nullable=True),
        sa.Column("to_me", sa.Boolean(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("attendees", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(16), nullable=True),
        sa.Column("summary_state", sa.String(16), nullable=False, server_default="none"),
        sa.Column("flags", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("local_detail", sa.Text(), nullable=True),
        sa.Column("trust_tier", sa.String(24), nullable=False),
        sa.Column("embedding", Vector(settings.embedding_dimension), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("account_id", "external_id", name="uq_connector_item_external"),
        sa.CheckConstraint("kind IN ('event', 'email')", name="ck_connector_items_kind"),
    )
    op.create_index(
        "ix_connector_items_tenant_kind_occurred",
        "connector_items",
        ["tenant_id", "kind", "occurred_at"],
    )
    op.create_index(
        "ix_connector_items_tenant_kind_starts",
        "connector_items",
        ["tenant_id", "kind", "starts_at"],
    )
    op.create_index("ix_connector_items_thread", "connector_items", ["account_id", "thread_key"])


def downgrade() -> None:
    op.drop_index("ix_connector_items_thread", table_name="connector_items")
    op.drop_index("ix_connector_items_tenant_kind_starts", table_name="connector_items")
    op.drop_index("ix_connector_items_tenant_kind_occurred", table_name="connector_items")
    op.drop_table("connector_items")
    op.drop_table("connector_accounts")
