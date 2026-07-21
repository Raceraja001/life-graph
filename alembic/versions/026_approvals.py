"""026 — Approvals: unified human-in-the-loop queue.

Creates the polymorphic ``approvals`` table backing the mobile Approvals tab.
Any subsystem can enqueue an item awaiting an approve/reject decision; the
resolution triggers the source's real side-effect. Distinct from the Era-8
autonomy ``approval_queue`` (shell-command HITL), which is unchanged.

See docs/specs/approvals-feed.md.

Revision ID: 026
Revises: 025
Create Date: 2026-07-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="legacy"),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(128), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_by", sa.String(128), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_approvals_status",
        ),
    )
    op.create_index("ix_approvals_tenant_status", "approvals", ["tenant_id", "status"])
    op.create_index(
        "uq_approvals_source_ref",
        "approvals",
        ["tenant_id", "source", "source_ref"],
        unique=True,
        postgresql_where=sa.text("source_ref IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_approvals_source_ref", table_name="approvals")
    op.drop_index("ix_approvals_tenant_status", table_name="approvals")
    op.drop_table("approvals")
