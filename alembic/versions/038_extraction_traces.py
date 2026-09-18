"""038 — extraction_traces, and the fact_set_f1 eval scoring type.

The self-improvement loop needs labelled examples, and the only task with a
natural label today is capture extraction: every fact the LLM extracts becomes
a pending memory the user approves, rejects or edits anyway. But nothing kept
the model's input and output, so there was nothing to learn from. This table
records each local extraction call; memories link back to it through
``properties.extraction_trace_id`` / ``extraction_fact_index``, and the label is
read from those memories at suite-build time (approved = keep, edited = keep
the edited text, rejected = drop).

``input_text`` is the full capture text — personal data, tenant-scoped like
everything else, and covered by the normal backups.

``fact_set_f1`` joins the eval scoring types: an extraction is a *set* of
facts, compared by embedding similarity, which none of the existing
string-level scorers can express.

No schema qualifier, matching every migration since 023.

Revision ID: 038
Revises: 037
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None

_SCORING_TYPES_OLD = "'exact_match','contains','regex','semantic_similarity','llm_judge'"
_SCORING_TYPES_NEW = _SCORING_TYPES_OLD + ",'fact_set_f1'"


def upgrade() -> None:
    op.create_table(
        "extraction_traces",
        sa.Column(
            "id",
            UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False, server_default="capture_extraction"),
        # "default" when the built-in prompt was used, else prompt_versions.id.
        sa.Column("prompt_version_id", sa.Text(), nullable=False, server_default="default"),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=True),
        # Parsed facts in extraction order: [{content, fact_type, confidence}].
        sa.Column("facts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_extraction_traces_tenant_task_created",
        "extraction_traces",
        ["tenant_id", "task_type", "created_at"],
    )
    # Labels are read by joining memories on this property.
    op.create_index(
        "ix_memories_extraction_trace_id",
        "memories",
        [sa.text("(properties->>'extraction_trace_id')")],
        postgresql_where=sa.text("properties ? 'extraction_trace_id'"),
    )

    op.drop_constraint("ck_eval_cases_scoring_type", "eval_cases", type_="check")
    op.create_check_constraint(
        "ck_eval_cases_scoring_type", "eval_cases", f"scoring_type IN ({_SCORING_TYPES_NEW})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM eval_cases WHERE scoring_type = 'fact_set_f1'")
    op.drop_constraint("ck_eval_cases_scoring_type", "eval_cases", type_="check")
    op.create_check_constraint(
        "ck_eval_cases_scoring_type", "eval_cases", f"scoring_type IN ({_SCORING_TYPES_OLD})"
    )
    op.drop_index("ix_memories_extraction_trace_id", table_name="memories")
    op.drop_index("ix_extraction_traces_tenant_task_created", table_name="extraction_traces")
    op.drop_table("extraction_traces")
