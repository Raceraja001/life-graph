"""040 — contacts in the connector index (docs/specs/connector-contacts.md).

``connector_items`` gains ``emails``: the addresses of the people an item
involves (a contact's addresses, an event's attendees, a mail's sender and
recipients — never the user's own), GIN-indexed so meeting prep and name
resolution can look people up by exact address. The kind check now allows
``contact``.

Revision ID: 040
Revises: 039
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connector_items",
        sa.Column("emails", ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index(
        "ix_connector_items_emails", "connector_items", ["emails"], postgresql_using="gin"
    )
    op.drop_constraint("ck_connector_items_kind", "connector_items", type_="check")
    op.create_check_constraint(
        "ck_connector_items_kind", "connector_items", "kind IN ('event', 'email', 'contact')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM connector_items WHERE kind = 'contact'")
    op.drop_constraint("ck_connector_items_kind", "connector_items", type_="check")
    op.create_check_constraint(
        "ck_connector_items_kind", "connector_items", "kind IN ('event', 'email')"
    )
    op.drop_index("ix_connector_items_emails", table_name="connector_items")
    op.drop_column("connector_items", "emails")
