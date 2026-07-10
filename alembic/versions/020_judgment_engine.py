"""020 — Judgment Engine: decisions, predictions, calibration_snapshots, challenges.

Revision ID: 020
Revises: 019
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── decisions ─────────────────────────────────────────────
    op.create_table(
        "decisions",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("options", JSONB(), nullable=False, server_default="[]"),
        sa.Column("chosen_option", sa.String(200), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="candidate"),
        sa.Column("source", sa.String(16), nullable=True),
        sa.Column(
            "domain_tags", ARRAY(sa.Text()),
            nullable=False, server_default="{}",
        ),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("capture_event_id", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("challenge_id", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column(
            "superseded_by", sa.dialects.postgresql.UUID(),
            sa.ForeignKey("life_graph.decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_decisions_tenant_created", "decisions",
        ["tenant_id", sa.text("created_at DESC")],
        schema="life_graph",
    )
    op.create_index(
        "ix_decisions_tenant_status", "decisions",
        ["tenant_id", "status"],
        schema="life_graph",
    )
    # ivfflat index on embedding (raw SQL for vector_cosine_ops)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_decisions_embedding "
        "ON life_graph.decisions USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 10)"
    )

    # ── predictions ───────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column(
            "decision_id", sa.dialects.postgresql.UUID(),
            sa.ForeignKey("life_graph.decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "domain_tags", ARRAY(sa.Text()),
            nullable=False, server_default="{}",
        ),
        sa.Column("resolve_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_criteria", JSONB(), nullable=False, server_default="{}"),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_source", sa.String(32), nullable=True),
        sa.Column("resolution_evidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("actual_vs_predicted", sa.Float(), nullable=True),
        sa.Column("capture_event_id", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_predictions_tenant_outcome", "predictions",
        ["tenant_id", "outcome"],
        schema="life_graph",
    )
    op.create_index(
        "ix_predictions_tenant_resolve_by", "predictions",
        ["tenant_id", "resolve_by"],
        schema="life_graph",
    )

    # ── calibration_snapshots ─────────────────────────────────
    op.create_table(
        "calibration_snapshots",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("domain", sa.String(64), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("resolved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ambiguous_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brier_score", sa.Float(), nullable=True),
        sa.Column("buckets", JSONB(), nullable=False, server_default="[]"),
        sa.Column("estimate_multiplier", sa.Float(), nullable=True),
        sa.Column("bias_findings", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_cal_tenant_domain_computed", "calibration_snapshots",
        ["tenant_id", "domain", sa.text("computed_at DESC")],
        schema="life_graph",
    )

    # ── challenges ────────────────────────────────────────────
    op.create_table(
        "challenges",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("proposal", sa.Text(), nullable=False),
        sa.Column("report", JSONB(), nullable=False, server_default="{}"),
        sa.Column("verdict", sa.String(32), nullable=True),
        sa.Column("action_taken", sa.String(16), nullable=True),
        sa.Column(
            "outcome_prediction_id", sa.dialects.postgresql.UUID(),
            sa.ForeignKey("life_graph.predictions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "total_cost_usd", sa.Float(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_challenges_tenant_created", "challenges",
        ["tenant_id", sa.text("created_at DESC")],
        schema="life_graph",
    )


def downgrade() -> None:
    # Drop in reverse order of creation (challenges, calibration, predictions, decisions)
    op.drop_index("ix_challenges_tenant_created", schema="life_graph")
    op.drop_table("challenges", schema="life_graph")

    op.drop_index("ix_cal_tenant_domain_computed", schema="life_graph")
    op.drop_table("calibration_snapshots", schema="life_graph")

    op.drop_index("ix_predictions_tenant_resolve_by", schema="life_graph")
    op.drop_index("ix_predictions_tenant_outcome", schema="life_graph")
    op.drop_table("predictions", schema="life_graph")

    op.execute("DROP INDEX IF EXISTS life_graph.ix_decisions_embedding")
    op.drop_index("ix_decisions_tenant_status", schema="life_graph")
    op.drop_index("ix_decisions_tenant_created", schema="life_graph")
    op.drop_table("decisions", schema="life_graph")
