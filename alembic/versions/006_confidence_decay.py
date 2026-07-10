"""Add confidence decay columns to memories.

Revision ID: 006
Revises: 005

Adds columns for confidence decay and reinforcement tracking:
- last_reinforced: When was this memory last confirmed by the user?
- reinforced_count: How many times has it been reinforced?
- extraction_tier: Which pipeline tier extracted this memory (regex/spacy/llm)?
- extraction_confidence: Confidence from the extraction pipeline.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Confidence Decay ──────────────────────────────────────
    op.add_column(
        "memories",
        sa.Column(
            "last_reinforced",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last time user confirmed this memory is still accurate",
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "reinforced_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Number of times user confirmed this memory",
        ),
    )

    # ── Extraction Provenance ─────────────────────────────────
    op.add_column(
        "memories",
        sa.Column(
            "extraction_tier",
            sa.String(20),
            nullable=True,
            comment="Which extraction tier created this: regex, spacy, llm, manual",
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "extraction_confidence",
            sa.Float,
            nullable=True,
            comment="Confidence score from the extraction pipeline (0.0-1.0)",
        ),
    )


def downgrade() -> None:
    op.drop_column("memories", "extraction_confidence")
    op.drop_column("memories", "extraction_tier")
    op.drop_column("memories", "reinforced_count")
    op.drop_column("memories", "last_reinforced")
