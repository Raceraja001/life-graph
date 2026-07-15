"""024 — Shadow Mode: shadow_enrollments + shadow_runs.

New autonomous actors run in dry-run and record 'would-have-done' reports until
graded and graduated. See
docs/superpowers/specs/2026-07-15-shadow-mode-design.md.

Revision ID: 024
Revises: 023
Create Date: 2026-07-15
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_enrollments",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="shadow"),
        sa.Column("graded_good", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("graded_bad", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "enrolled_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column("graduated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "agent_id", name="uq_se_tenant_agent"),
    )
    op.create_index("ix_se_tenant_status", "shadow_enrollments", ["tenant_id", "status"])

    op.create_table(
        "shadow_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column(
            "enrollment_id", sa.Text(),
            sa.ForeignKey("shadow_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("would_have_routed", sa.String(32), nullable=False),
        sa.Column("rationale", JSONB(), nullable=False, server_default="{}"),
        sa.Column("grade", sa.String(8), nullable=True),
        sa.Column("graded_by", sa.Text(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sr_tenant_agent", "shadow_runs", ["tenant_id", "agent_id"])
    op.create_index("ix_sr_tenant_grade", "shadow_runs", ["tenant_id", "grade"])
    op.create_index("ix_sr_enrollment", "shadow_runs", ["enrollment_id"])


def downgrade() -> None:
    op.drop_index("ix_sr_enrollment", table_name="shadow_runs")
    op.drop_index("ix_sr_tenant_grade", table_name="shadow_runs")
    op.drop_index("ix_sr_tenant_agent", table_name="shadow_runs")
    op.drop_table("shadow_runs")
    op.drop_index("ix_se_tenant_status", table_name="shadow_enrollments")
    op.drop_table("shadow_enrollments")
