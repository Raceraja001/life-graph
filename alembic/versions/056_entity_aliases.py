"""056 — entity aliases: one person, many names (services/entities.py, core/aliases.py).

The owner calls one person "Mahalakshmi", "Maha" and "my wife"; each name was
its own entity, so a question using one name missed what was said with another.
An alias entity now points at the entity it is another name for
(``canonical_id``); ``role`` keeps the person's relationship to the owner
(spouse, mother, owner, …); ``alias_via`` / ``alias_evidence`` say why the link
was made, so it can be checked and undone (clearing ``canonical_id``).

Additive: every existing row keeps null in all four columns, which is today's
behaviour (each name its own entity). No schema qualifier, matching 023+.

Revision ID: 056
Revises: 055
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column(
            "canonical_id",
            UUID(),
            sa.ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("entities", sa.Column("role", sa.String(40), nullable=True))
    op.add_column("entities", sa.Column("alias_via", sa.String(16), nullable=True))
    op.add_column("entities", sa.Column("alias_evidence", sa.Text(), nullable=True))
    op.create_index("ix_entities_canonical", "entities", ["canonical_id"])
    op.create_index("ix_entities_tenant_role", "entities", ["tenant_id", "role"])


def downgrade() -> None:
    op.drop_index("ix_entities_tenant_role", table_name="entities")
    op.drop_index("ix_entities_canonical", table_name="entities")
    op.drop_column("entities", "alias_evidence")
    op.drop_column("entities", "alias_via")
    op.drop_column("entities", "role")
    op.drop_column("entities", "canonical_id")
