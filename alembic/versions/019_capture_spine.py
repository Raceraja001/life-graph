"""019 — Capture Spine: capture_events, corrections, interview_questions,
and ALTER memories to add capture_event_id.

Revision ID: 019
Revises: 018
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── capture_events ────────────────────────────────────────
    op.create_table(
        "capture_events",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("yield_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("properties", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_ce_tenant_occurred", "capture_events",
        ["tenant_id", sa.text("occurred_at DESC")],
        schema="life_graph",
    )
    op.create_index(
        "ix_ce_tenant_surface", "capture_events",
        ["tenant_id", "surface"],
        schema="life_graph",
    )
    op.create_index(
        "ix_ce_tenant_hash", "capture_events",
        ["tenant_id", "content_hash"],
        schema="life_graph",
    )

    # ── corrections ───────────────────────────────────────────
    op.create_table(
        "corrections",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column(
            "capture_event_id", sa.dialects.postgresql.UUID(),
            sa.ForeignKey("life_graph.capture_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("original", sa.Text(), nullable=True),
        sa.Column("corrected", sa.Text(), nullable=True),
        sa.Column("diff_summary", sa.Text(), nullable=True),
        sa.Column("context", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "domain_tags", ARRAY(sa.Text()),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_cor_tenant_created", "corrections",
        ["tenant_id", sa.text("created_at DESC")],
        schema="life_graph",
    )
    op.create_index(
        "ix_cor_tenant_kind", "corrections",
        ["tenant_id", "kind"],
        schema="life_graph",
    )

    # ── interview_questions ───────────────────────────────────
    op.create_table(
        "interview_questions",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("origin_ref", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "priority", sa.Float(),
            nullable=False, server_default="0.5",
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column(
            "answer_capture_id", sa.dialects.postgresql.UUID(),
            sa.ForeignKey("life_graph.capture_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asked_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_iq_tenant_status_priority", "interview_questions",
        ["tenant_id", "status", sa.text("priority DESC")],
        schema="life_graph",
    )

    # ── ALTER memories: add capture_event_id ──────────────────
    # memories lives in 'public' schema, not 'life_graph'
    op.add_column(
        "memories",
        sa.Column(
            "capture_event_id", sa.dialects.postgresql.UUID(),
            nullable=True,
        ),
        schema="public",
    )


def downgrade() -> None:
    # ── memories: drop capture_event_id ───────────────────────
    op.drop_column("memories", "capture_event_id", schema="public")

    # ── interview_questions ───────────────────────────────────
    op.drop_index("ix_iq_tenant_status_priority", schema="life_graph")
    op.drop_table("interview_questions", schema="life_graph")

    # ── corrections ───────────────────────────────────────────
    op.drop_index("ix_cor_tenant_kind", schema="life_graph")
    op.drop_index("ix_cor_tenant_created", schema="life_graph")
    op.drop_table("corrections", schema="life_graph")

    # ── capture_events ────────────────────────────────────────
    op.drop_index("ix_ce_tenant_hash", schema="life_graph")
    op.drop_index("ix_ce_tenant_surface", schema="life_graph")
    op.drop_index("ix_ce_tenant_occurred", schema="life_graph")
    op.drop_table("capture_events", schema="life_graph")
