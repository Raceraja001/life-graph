"""012 — Add scheduled_jobs table.

Revision ID: 012
Revises: 011
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
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
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "cron_expression",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "agent_name", sa.String(100), nullable=False,
        ),
        sa.Column(
            "input", JSONB, nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "run_count", sa.Integer, nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "consecutive_failures",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_run_status",
            sa.String(20),
            nullable=True,
        ),
        sa.Column(
            "last_run_task_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "agent_tasks.id", ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "max_retries", sa.Integer, nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "timeout_seconds", sa.Integer, nullable=False,
            server_default=sa.text("600"),
        ),
        sa.Column(
            "properties", JSONB, nullable=False,
            server_default="{}",
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
        "ix_scheduled_jobs_name",
        "scheduled_jobs",
        ["tenant_id", "name"],
        unique=True,
    )
    op.create_index(
        "ix_scheduled_jobs_tenant",
        "scheduled_jobs",
        ["tenant_id", "is_active"],
    )
    op.create_index(
        "ix_scheduled_jobs_next_run",
        "scheduled_jobs",
        ["next_run_at"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_jobs_next_run")
    op.drop_index("ix_scheduled_jobs_tenant")
    op.drop_index("ix_scheduled_jobs_name")
    op.drop_table("scheduled_jobs")
