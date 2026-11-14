"""059 — capabilities and standing_rules: the owner's authority, written down.

Until now a capability (``autonomy/approvals/capability.py``) lived in one
process's memory. That failed closed across a restart — the owner re-approves
— but it also meant the worker that issued a mandate had to be the worker that
executed it, and "one use" was only one use *per process*. Two ARQ workers
racing on the same approved click could each have had their own copy.

So the record moves into a table, and the one-use check becomes a conditional
``UPDATE … WHERE consumed_at IS NULL … RETURNING``: Postgres decides who wins,
once, for the whole deployment.

What is bound here is the whole of the approval. ``tenant_id``, ``task_id``,
``errand_id``, ``approval_id``, ``step_index``, ``action_types``,
``target_origins``, ``target_selector`` and ``parameters_hash`` are all
re-tested at execution time, so an approval authorises the one action the
owner was shown and not a later plan that ends in a similar-looking click.

``parameters_hash`` is a SHA-256 over the canonicalised action
(``services.browser_errand.canonical_parameters_hash``) and never the value
itself: no password, PIN or form content is stored in this table. Neither is
anything the owner typed — the digest is written, compared and discarded.

``standing_rules`` is the other half: the owner's lasting "always / never",
which was also in memory and therefore not shared. Model output can never
reach either table — only owner-authenticated code calls the stores that
write them.

No schema qualifier, matching every migration since 023.

Revision ID: 059
Revises: 058
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capabilities",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("capability_id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("errand_id", sa.String(64), nullable=True),
        sa.Column("approval_id", sa.String(64), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("action_types", ARRAY(sa.String()), nullable=False, server_default="{}"),
        # NULL, not '{}': an empty array would read as "no origin authorised"
        # and a NULL as "any origin", which are opposite meanings. The store
        # refuses to issue the empty case, so only NULL ever lands here.
        sa.Column("target_origins", ARRAY(sa.String()), nullable=True),
        sa.Column("target_selector", sa.String(255), nullable=True),
        sa.Column("parameters_hash", sa.String(64), nullable=True),
        sa.Column("one_use", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actor", sa.String(120), nullable=False, server_default="owner"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("max_amount", sa.Numeric(18, 4), nullable=True),
    )
    # Unique across tenants, like a vault handle: the id is 24 random bytes,
    # and a collision would let one tenant's handle name another tenant's row.
    # It is also what makes the consuming UPDATE touch exactly one row.
    op.create_index("uq_capabilities_capability_id", "capabilities", ["capability_id"], unique=True)
    op.create_index("ix_capabilities_tenant", "capabilities", ["tenant_id"])
    # The revoke-all path and the errand resume path, which are both
    # tenant-scoped by construction.
    op.create_index("ix_capabilities_tenant_errand", "capabilities", ["tenant_id", "errand_id"])
    op.create_index("ix_capabilities_tenant_task", "capabilities", ["tenant_id", "task_id"])
    # Retention: the nightly purge deletes by expiry, and an expired row is
    # already refused by the check, so this index only makes the sweep cheap.
    op.create_index("ix_capabilities_expires_at", "capabilities", ["expires_at"])

    op.create_table(
        "standing_rules",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("effect", sa.String(32), nullable=False),
        sa.Column("target_origin", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_standing_rules_tenant", "standing_rules", ["tenant_id"])
    # One row per (tenant, action, origin): setting a tenant's rules replaces
    # the set, and a duplicate would make "which effect applies" depend on row
    # order. NULL origin means "anywhere", and NULLs are distinct in a unique
    # index, so the partial index below covers that case explicitly.
    op.create_index(
        "uq_standing_rules_scope",
        "standing_rules",
        ["tenant_id", "action_type", "target_origin"],
        unique=True,
        postgresql_where=sa.text("target_origin IS NOT NULL"),
    )
    op.create_index(
        "uq_standing_rules_scope_any_origin",
        "standing_rules",
        ["tenant_id", "action_type"],
        unique=True,
        postgresql_where=sa.text("target_origin IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_standing_rules_scope_any_origin", table_name="standing_rules")
    op.drop_index("uq_standing_rules_scope", table_name="standing_rules")
    op.drop_index("ix_standing_rules_tenant", table_name="standing_rules")
    op.drop_table("standing_rules")
    op.drop_index("ix_capabilities_expires_at", table_name="capabilities")
    op.drop_index("ix_capabilities_tenant_task", table_name="capabilities")
    op.drop_index("ix_capabilities_tenant_errand", table_name="capabilities")
    op.drop_index("ix_capabilities_tenant", table_name="capabilities")
    op.drop_index("uq_capabilities_capability_id", table_name="capabilities")
    op.drop_table("capabilities")
