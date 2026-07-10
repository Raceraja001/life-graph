"""Add impact scoring columns.

Revision ID: 008
Revises: 007

Adds columns for impact scoring feedback loop:
- memories.impact_score: Learned usefulness from session outcomes
- memories.impact_confidence: Data quality for impact score
- sessions.outcome: Session result (success/failure/neutral)
- memory_sessions.role: Whether memory was created or recalled
- memory_sessions.was_useful: Per-memory feedback (v2)
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Memory impact scoring ─────────────────────────────────
    op.add_column(
        "memories",
        sa.Column(
            "impact_score",
            sa.Float,
            nullable=False,
            server_default="0.5",
            comment="Learned usefulness from session outcome feedback (0.0-1.0)",
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "impact_confidence",
            sa.Float,
            nullable=False,
            server_default="0.0",
            comment="Confidence in impact_score (grows with more data points)",
        ),
    )

    # ── Session outcome ───────────────────────────────────────
    op.add_column(
        "sessions",
        sa.Column(
            "outcome",
            sa.String(20),
            nullable=True,
            comment="Session result: success, failure, or neutral",
        ),
    )

    # ── Memory-Session role tracking ──────────────────────────
    op.add_column(
        "memory_sessions",
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            server_default="created",
            comment="Whether memory was created or recalled in this session",
        ),
    )
    op.add_column(
        "memory_sessions",
        sa.Column(
            "was_useful",
            sa.Boolean,
            nullable=True,
            comment="Per-memory usefulness feedback (v2)",
        ),
    )


def downgrade() -> None:
    op.drop_column("memory_sessions", "was_useful")
    op.drop_column("memory_sessions", "role")
    op.drop_column("sessions", "outcome")
    op.drop_column("memories", "impact_confidence")
    op.drop_column("memories", "impact_score")
