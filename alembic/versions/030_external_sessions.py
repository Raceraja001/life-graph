"""external_sessions table

Revision ID: 030
Revises: 029
Create Date: 2026-08-04

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="legacy"),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("raw_key", sa.Text(), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_turn_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_distilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "tool", "external_id", name="uq_external_session"),
    )
    op.create_index("ix_external_sessions_tenant_tool", "external_sessions", ["tenant_id", "tool"])


def downgrade() -> None:
    op.drop_index("ix_external_sessions_tenant_tool", table_name="external_sessions")
    op.drop_table("external_sessions")
