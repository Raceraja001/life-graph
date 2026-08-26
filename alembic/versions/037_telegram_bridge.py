"""037 — Telegram bridge: telegram_bindings, telegram_pairing_codes.

Two tables backing the phone-to-Life-Graph chat bridge.

``telegram_bindings`` answers the only question that matters for safety: which
tenant does this chat write to? The Bot API hands us a ``chat_id`` and nothing
else — no auth header, no tenant. Everything downstream (capture, recall,
approvals) reads the tenant from this table, so an unbound chat has no tenant
and its messages are dropped rather than defaulted.

``telegram_pairing_codes`` is the one-time handshake that creates a binding.
Codes are short, single-use, and expire, because the code is the only secret
standing between someone who guesses it and a write into another tenant's
memory.

The ``getUpdates`` offset is deliberately *not* here. It is one integer with no
tenant scope and no audit value; it lives in Redis. Losing it replays at most
24 hours of updates, which the capture spine's content-hash dedup absorbs.

No schema qualifier, matching every migration since 023 — these land in
``public`` alongside approvals, notification_channels and push_subscriptions.

Revision ID: 037
Revises: 036
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_bindings",
        sa.Column(
            "id",
            UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        # BigInteger, not Integer: Telegram chat ids for supergroups are large
        # negative numbers that do not fit in int4.
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_type", sa.String(16), nullable=False, server_default="private"),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "bound_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default="{}"),
    )

    # One tenant per chat, enforced in the database rather than only in code:
    # this is the boundary that decides whose memory a message may write to,
    # and application-level checks race under concurrent pairing.
    #
    # Partial on `active` so a revoked binding stays on disk as an audit record
    # and the same chat can later be bound again.
    op.create_index(
        "ix_telegram_bindings_chat",
        "telegram_bindings",
        ["chat_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_index(
        "ix_telegram_bindings_tenant",
        "telegram_bindings",
        ["tenant_id"],
    )

    op.create_table(
        "telegram_pairing_codes",
        # The code is the primary key: it must be unique, and a second row with
        # the same code is the one thing that would break the handshake.
        sa.Column("code", sa.String(16), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    # Supports the sweep that deletes expired codes.
    op.create_index(
        "ix_telegram_pairing_expires",
        "telegram_pairing_codes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_pairing_expires", table_name="telegram_pairing_codes")
    op.drop_table("telegram_pairing_codes")
    op.drop_index("ix_telegram_bindings_tenant", table_name="telegram_bindings")
    op.drop_index("ix_telegram_bindings_chat", table_name="telegram_bindings")
    op.drop_table("telegram_bindings")
