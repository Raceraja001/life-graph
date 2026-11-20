"""041 — code items (pull requests, issues) in the connector index
(docs/specs/connector-github.md).

Only the kind check changes: ``code`` joins ``event``, ``email`` and ``contact``.

Revision ID: 041
Revises: 040
Create Date: 2026-09-19
"""

from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_connector_items_kind", "connector_items", type_="check")
    op.create_check_constraint(
        "ck_connector_items_kind",
        "connector_items",
        "kind IN ('event', 'email', 'contact', 'code')",
    )


# DATA-DESTROYING DOWNGRADE (audit M18, 2026-11-20): this deletes
# every code item (pull requests, issues) in connector_items.
# Nothing brings it back on a later upgrade. CI runs it only on an empty
# throwaway database; on a real one take a backup first.
def downgrade() -> None:
    op.execute("DELETE FROM connector_items WHERE kind = 'code'")
    op.drop_constraint("ck_connector_items_kind", "connector_items", type_="check")
    op.create_check_constraint(
        "ck_connector_items_kind", "connector_items", "kind IN ('event', 'email', 'contact')"
    )
