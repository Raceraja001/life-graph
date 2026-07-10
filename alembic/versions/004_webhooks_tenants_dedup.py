"""Add webhook, tenant config, and dedup support.

Revision ID: 004
Revises: 003

New tables: tenant_configs, tenant_webhooks
New column: memories.content_hash (SHA-256 for dedup)
New index: ix_memories_content_hash (tenant_id, content_hash)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New column: memories.content_hash for dedup ────────
    op.add_column(
        "memories",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_memories_content_hash",
        "memories",
        ["tenant_id", "content_hash"],
    )

    # ── New table: tenant_configs ──────────────────────────
    op.create_table(
        "tenant_configs",
        sa.Column("tenant_id", sa.String(64), primary_key=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "provisioned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenant_configs_status", "tenant_configs", ["status"])

    # ── New table: tenant_webhooks ─────────────────────────
    op.create_table(
        "tenant_webhooks",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("secret", sa.String(256), nullable=False),
        sa.Column("events", sa.String(500), nullable=False, server_default="*"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_tenant_webhooks_tenant", "tenant_webhooks", ["tenant_id"])
    op.create_index(
        "ix_tenant_webhooks_active",
        "tenant_webhooks",
        ["tenant_id", "active"],
    )


def downgrade() -> None:
    # ── Drop tenant_webhooks ──────────────────────────────
    op.drop_index("ix_tenant_webhooks_active", table_name="tenant_webhooks")
    op.drop_index("ix_tenant_webhooks_tenant", table_name="tenant_webhooks")
    op.drop_table("tenant_webhooks")

    # ── Drop tenant_configs ───────────────────────────────
    op.drop_index("ix_tenant_configs_status", table_name="tenant_configs")
    op.drop_table("tenant_configs")

    # ── Drop content_hash ─────────────────────────────────
    op.drop_index("ix_memories_content_hash", table_name="memories")
    op.drop_column("memories", "content_hash")
