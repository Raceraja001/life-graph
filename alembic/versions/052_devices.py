"""052 — devices: phones paired with Jarvis, and their one-time pairing codes.

docs/design/12_android_app_plan.md (Phase 1). A device holds a long-lived
token; only its SHA-256 is stored (``token_hash``), so the table cannot be
used to sign in. Revoking sets ``revoked_at``; the row stays, like
telegram_bindings. A pairing code is six digits, lives ten minutes and is
spent once (``used_at``).

No schema qualifier, matching every migration since 023.

Revision ID: 052
Revises: 051
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_devices_token_hash", "devices", ["token_hash"], unique=True)
    op.create_index("ix_devices_tenant", "devices", ["tenant_id"])
    op.create_table(
        "device_pairing_codes",
        sa.Column("code", sa.String(16), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_device_pairing_codes_expires", "device_pairing_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_device_pairing_codes_expires", table_name="device_pairing_codes")
    op.drop_table("device_pairing_codes")
    op.drop_index("ix_devices_tenant", table_name="devices")
    op.drop_index("uq_devices_token_hash", table_name="devices")
    op.drop_table("devices")
