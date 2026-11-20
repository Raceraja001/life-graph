"""042 — tasks in the connector index (docs/specs/connector-tasks.md).

Only the kind check changes: ``task`` joins ``event``, ``email``, ``contact``
and ``code``.

Revision ID: 042
Revises: 041
Create Date: 2026-09-19
"""

from alembic import op

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_connector_items_kind", "connector_items", type_="check")
    op.create_check_constraint(
        "ck_connector_items_kind",
        "connector_items",
        "kind IN ('event', 'email', 'contact', 'code', 'task')",
    )


# DATA-DESTROYING DOWNGRADE (audit M18, 2026-11-20): this deletes
# every task item in connector_items.
# Nothing brings it back on a later upgrade. CI runs it only on an empty
# throwaway database; on a real one take a backup first.
def downgrade() -> None:
    op.execute("DELETE FROM connector_items WHERE kind = 'task'")
    op.drop_constraint("ck_connector_items_kind", "connector_items", type_="check")
    op.create_check_constraint(
        "ck_connector_items_kind",
        "connector_items",
        "kind IN ('event', 'email', 'contact', 'code')",
    )
