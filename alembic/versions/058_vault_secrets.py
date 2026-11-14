"""058 — vault_secrets: the owner's secrets, encrypted, reachable only by handle.

The browser agent needs a bank password to fill a login, but nothing that
reads this database should see one. A row therefore holds only ciphertext
(``encrypted_value``, AES-256-GCM with the tenant and handle as additional
authenticated data — services/vault.py), and everything else refers to the
secret as ``vault://<handle>``.

``allowed_origins`` lists the sites a handle may be resolved for, so a leaked
handle is worthless anywhere else; ``one_use`` with ``used_at`` spends an OTP
exactly once. ``revoked_at`` set means the secret is gone — revoking also
blanks ``encrypted_value``.

No schema qualifier, matching every migration since 023.

Revision ID: 058
Revises: 057
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vault_secrets",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("handle", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("secret_type", sa.String(32), nullable=False, server_default="generic"),
        sa.Column("allowed_origins", ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("one_use", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_origin", sa.String(255), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Unique across tenants: a handle is random, and a collision would let one
    # tenant's handle name another tenant's row.
    op.create_index("uq_vault_secrets_handle", "vault_secrets", ["handle"], unique=True)
    op.create_index("ix_vault_secrets_tenant", "vault_secrets", ["tenant_id"])
    op.create_index("ix_vault_secrets_tenant_label", "vault_secrets", ["tenant_id", "label"])


def downgrade() -> None:
    op.drop_index("ix_vault_secrets_tenant_label", table_name="vault_secrets")
    op.drop_index("ix_vault_secrets_tenant", table_name="vault_secrets")
    op.drop_index("uq_vault_secrets_handle", table_name="vault_secrets")
    op.drop_table("vault_secrets")
