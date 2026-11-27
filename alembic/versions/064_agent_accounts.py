"""064 — agent_accounts and agent_account_limits: named logins per coding CLI.

Spec docs/specs/agent-drivers.md, "Phase 3b (2026-11-27): accounts, pool,
limits, resume". ``agent_accounts`` holds one row per named login a driver
CLI can run on (a subscription login in a life-graph-managed home directory,
an API key, a Vertex project); no credential is ever in it: ``secret_ref`` is
the id of a ``vault_secrets`` row and the identity is stored masked and as a
keyed hash only. ``agent_account_limits`` keeps the latest reading of each
plan-limit window per account (from a run, or the opt-in Codex probe).

Numbered 064 because race/autonomy-policy claims 063. On this branch it
revises 062; when both branches are merged, set ``down_revision = "063"``
here (whichever lands second), so the chain stays a single head.

No schema qualifier, matching every migration since 023.

Revision ID: 064
Revises: 062
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "064"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("driver", sa.String(32), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("home_dir", sa.String(512), nullable=True),
        sa.Column("secret_ref", UUID(as_uuid=True), nullable=True),
        sa.Column("secret_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("identity_masked", sa.String(120), nullable=True),
        sa.Column("identity_hash", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(200), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "driver", "name", name="uq_agent_accounts_name"),
    )
    op.create_index("ix_agent_accounts_pool", "agent_accounts", ["tenant_id", "driver", "priority"])
    op.create_index(
        "uq_agent_accounts_identity",
        "agent_accounts",
        ["tenant_id", "driver", "identity_hash"],
        unique=True,
        postgresql_where=sa.text("identity_hash IS NOT NULL"),
    )

    op.create_table(
        "agent_account_limits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window", sa.String(32), nullable=False),
        sa.Column("used_percent", sa.Float(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=True),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="run"),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("account_id", "window", name="uq_agent_account_limits_window"),
    )
    op.create_index(
        "ix_agent_account_limits_tenant", "agent_account_limits", ["tenant_id", "account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_account_limits_tenant", table_name="agent_account_limits")
    op.drop_table("agent_account_limits")
    op.drop_index("uq_agent_accounts_identity", table_name="agent_accounts")
    op.drop_index("ix_agent_accounts_pool", table_name="agent_accounts")
    op.drop_table("agent_accounts")
