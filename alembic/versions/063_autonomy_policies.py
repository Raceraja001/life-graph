"""063 — autonomy_policies: the owner's auto-approval conditions, review stages, fix rounds.

docs/specs/agent-drivers.md, "Autonomy policy" (2026-11-27, owner decision D2).
One row per (tenant, scope): ``scope`` is ``global`` or a project's UUID as
text. ``policy`` is JSONB validated by services/dev/autonomy_policy.py. No
row = today's behaviour (conditions only ever narrow change_policy.auto_gate;
fix rounds default to 0, which is the one-bounce rule unchanged).

Per-task review-stage results and the risk report live in the task's existing
``agent_tasks.properties`` JSONB, and fix rounds in ``verification_runs``
(attempt 3, 4, ...): no schema change for those.

No schema qualifier, matching every migration since 023.

Revision ID: 063
Revises: 062
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autonomy_policies",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("policy", JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "scope", name="uq_autonomy_policies_tenant_scope"),
    )


def downgrade() -> None:
    op.drop_table("autonomy_policies")
