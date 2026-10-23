"""053 — entities: the people, projects and things the owner's memories mention.

The Apache AGE graph did not serve retrieval (2026-10-22 review): entity
search needed the whole question to be a substring of a name, neighbour
expansion used a label nothing was written under, and no vertex carried a
tenant. This is a plain, tenant-scoped index instead: one row per thing
(``key`` is the normalised name, ``name`` how it is usually written) and one
link row per memory that mentions it. services/entities.py fills and reads it.

No schema qualifier, matching every migration since 023.

Revision ID: 053
Revises: 052
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("mentions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("uq_entities_tenant_key", "entities", ["tenant_id", "key"], unique=True)
    op.create_table(
        "memory_entities",
        sa.Column(
            "memory_id",
            UUID(),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            UUID(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
    )
    op.create_index("ix_memory_entities_entity", "memory_entities", ["entity_id"])


def downgrade() -> None:
    op.drop_table("memory_entities")
    op.drop_table("entities")
