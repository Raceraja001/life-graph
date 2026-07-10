"""014 — Era 4: Personal AI — preferences, evidence, advisor, research.

Revision ID: 014
Revises: 013
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Preferences table ────────────────────────────────────
    op.create_table(
        "preferences",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", sa.String(64), nullable=False,
        ),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("choice", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column(
            "confidence", sa.Float(),
            nullable=False, server_default="0.5",
        ),
        sa.Column(
            "confidence_history", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "source", sa.String(20),
            server_default="'explicit'",
        ),
        sa.Column("source_detail", sa.Text(), nullable=True),
        sa.Column(
            "tags", ARRAY(sa.String()),
            server_default="{}",
        ),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column(
            "properties", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "last_validated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "validated_count", sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "last_challenged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "embedding_model", sa.String(50),
            server_default="'all-mpnet-base-v2'",
        ),
        sa.Column(
            "status", sa.String(20),
            server_default="'active'",
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
        "ix_pref_tenant_status", "preferences",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_pref_tenant_topic", "preferences",
        ["tenant_id", "topic"],
    )
    op.create_index(
        "ix_pref_tenant_category", "preferences",
        ["tenant_id", "category"],
    )
    op.create_index(
        "ix_pref_confidence", "preferences",
        ["confidence"],
    )
    op.create_index(
        "ix_pref_last_validated", "preferences",
        ["last_validated_at"],
    )
    op.create_index(
        "ix_pref_tags", "preferences",
        ["tags"], postgresql_using="gin",
    )
    op.create_index(
        "ix_pref_properties", "preferences",
        ["properties"], postgresql_using="gin",
    )
    op.create_index(
        "ix_pref_source", "preferences",
        ["source"],
    )

    # ── Evidence table ───────────────────────────────────────
    op.create_table(
        "evidence",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", sa.String(64), nullable=False,
        ),
        sa.Column(
            "preference_id", UUID(as_uuid=True),
            sa.ForeignKey("preferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_type", sa.String(30), nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=True),
        sa.Column(
            "stance", sa.String(10),
            nullable=False, server_default="'supports'",
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column(
            "credibility", sa.Float(),
            nullable=False, server_default="1.0",
        ),
        sa.Column(
            "weight", sa.Float(),
            nullable=False, server_default="1.0",
        ),
        sa.Column(
            "properties", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "embedding_model", sa.String(50),
            server_default="'all-mpnet-base-v2'",
        ),
        sa.Column(
            "status", sa.String(20),
            server_default="'active'",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_evidence_pref_stance", "evidence",
        ["preference_id", "stance"],
    )
    op.create_index(
        "ix_evidence_tenant_status", "evidence",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_evidence_source_type", "evidence",
        ["source_type"],
    )
    op.create_index(
        "ix_evidence_stance", "evidence",
        ["stance"],
    )
    op.create_index(
        "uq_evidence_source_url", "evidence",
        ["preference_id", "source_url"],
        unique=True,
        postgresql_where=sa.text("source_url IS NOT NULL"),
    )

    # ── Advisor sessions table ───────────────────────────────
    op.create_table(
        "advisor_sessions",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", sa.String(64), nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "sources_used", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "preferences_cited", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "confidence", sa.Float(),
            server_default="0.5",
        ),
        sa.Column(
            "consensus_score", sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(20),
            server_default="'pending'",
        ),
        sa.Column(
            "properties", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_advisor_tenant_created", "advisor_sessions",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_advisor_consensus", "advisor_sessions",
        ["consensus_score"],
    )
    op.create_index(
        "ix_advisor_tenant_status", "advisor_sessions",
        ["tenant_id", "status"],
    )

    # ── Research runs table ──────────────────────────────────
    op.create_table(
        "research_runs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id", sa.String(64), nullable=False,
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "sources_searched", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "evidence_found", sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "evidence_added", sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "preferences_affected", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "status", sa.String(20),
            server_default="'pending'",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "properties", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_research_tenant_started", "research_runs",
        ["tenant_id", "started_at"],
    )
    op.create_index(
        "ix_research_tenant_status", "research_runs",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_tenant_status")
    op.drop_index("ix_research_tenant_started")
    op.drop_table("research_runs")

    op.drop_index("ix_advisor_tenant_status")
    op.drop_index("ix_advisor_consensus")
    op.drop_index("ix_advisor_tenant_created")
    op.drop_table("advisor_sessions")

    op.drop_index("uq_evidence_source_url")
    op.drop_index("ix_evidence_stance")
    op.drop_index("ix_evidence_source_type")
    op.drop_index("ix_evidence_tenant_status")
    op.drop_index("ix_evidence_pref_stance")
    op.drop_table("evidence")

    op.drop_index("ix_pref_source")
    op.drop_index("ix_pref_properties")
    op.drop_index("ix_pref_tags")
    op.drop_index("ix_pref_last_validated")
    op.drop_index("ix_pref_confidence")
    op.drop_index("ix_pref_tenant_category")
    op.drop_index("ix_pref_tenant_topic")
    op.drop_index("ix_pref_tenant_status")
    op.drop_table("preferences")
