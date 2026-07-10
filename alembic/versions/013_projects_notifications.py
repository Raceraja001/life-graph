"""013 — Add projects and notifications tables.

Revision ID: 013
Revises: 012
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Projects table ──────────────────────────────────
    op.create_table(
        "projects",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", sa.String(64), nullable=False,
        ),
        sa.Column(
            "name", sa.String(200), nullable=False,
        ),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("git_url", sa.Text, nullable=True),
        sa.Column(
            "git_branch", sa.String(200), nullable=True,
        ),
        sa.Column(
            "language", sa.String(50), nullable=True,
        ),
        sa.Column(
            "framework", sa.String(100), nullable=True,
        ),
        sa.Column(
            "dependency_file", sa.Text, nullable=True,
        ),
        sa.Column(
            "dependency_count", sa.Integer,
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "file_count", sa.Integer,
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "recent_commits", JSONB,
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "scan_metadata", JSONB,
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "last_scanned_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False,
            server_default=sa.text("true"),
        ),
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
    )

    op.create_index(
        "ix_projects_name", "projects",
        ["tenant_id", "name"], unique=True,
    )
    op.create_index(
        "ix_projects_tenant", "projects",
        ["tenant_id", "is_active"],
    )
    op.create_index(
        "ix_projects_language", "projects",
        ["tenant_id", "language"],
    )

    # ── Notifications table ─────────────────────────────
    op.create_table(
        "notifications",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", sa.String(64), nullable=False,
        ),
        sa.Column(
            "priority", sa.String(10), nullable=False,
            server_default="info",
        ),
        sa.Column(
            "channel", sa.String(20), nullable=False,
            server_default="terminal",
        ),
        sa.Column(
            "title", sa.String(500), nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column(
            "metadata", JSONB, nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "is_read", sa.Boolean, nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_delivered", sa.Boolean, nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "delivery_error", sa.Text, nullable=True,
        ),
        sa.Column(
            "source_type", sa.String(50), nullable=True,
        ),
        sa.Column(
            "source_id", UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_notifications_tenant", "notifications",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_unread", "notifications",
        ["tenant_id", "is_read", "created_at"],
    )
    op.create_index(
        "ix_notifications_priority", "notifications",
        ["tenant_id", "priority", "created_at"],
    )
    op.create_index(
        "ix_notifications_pending", "notifications",
        ["is_delivered", "priority", "created_at"],
        postgresql_where=sa.text(
            "is_delivered = false"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_pending")
    op.drop_index("ix_notifications_priority")
    op.drop_index("ix_notifications_unread")
    op.drop_index("ix_notifications_tenant")
    op.drop_table("notifications")

    op.drop_index("ix_projects_language")
    op.drop_index("ix_projects_tenant")
    op.drop_index("ix_projects_name")
    op.drop_table("projects")
