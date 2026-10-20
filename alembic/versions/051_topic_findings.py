"""051 — topic findings: what the tech watch found new on the owner's topics.

docs/specs/research-and-tech-watch.md (Job 10 of
docs/design/11_persona_roster_plan.md): one row per item per source page per
topic per tenant; ``sent_at`` marks it as sent in the Monday digest.

No schema qualifier, matching every migration since 023.

Revision ID: 051
Revises: 050
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_findings",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("dedup_key", sa.String(500), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column(
            "found_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_topic_findings_key", "topic_findings", ["tenant_id", "topic", "dedup_key"], unique=True
    )
    op.create_index("ix_topic_findings_tenant_found", "topic_findings", ["tenant_id", "found_at"])


def downgrade() -> None:
    op.drop_index("ix_topic_findings_tenant_found", table_name="topic_findings")
    op.drop_index("uq_topic_findings_key", table_name="topic_findings")
    op.drop_table("topic_findings")
