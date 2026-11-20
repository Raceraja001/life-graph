"""061 — approval_queue.requested_by: who asked for the work an entry gates.

Audit follow-up (quality phase 2, batch 2a). The autonomy queue recorded who
*decided* an entry (``resolved_by``, server-derived since #295) but not who
*asked* for it, so a caller could queue a host command through
``POST /autonomy/auto-actions`` and approve it itself. ``requested_by`` is set
server-side (api/approval_identity.py ``resolver``) when an entry comes from an
API request, and the resolve routes refuse a non-owner caller deciding its own
request (``refuse_self_approval``). NULL — every existing row, and entries an
in-process producer files — means "not recorded": nothing is refused for it.

No schema qualifier, matching every migration since 023.

Revision ID: 061
Revises: 060
Create Date: 2026-11-20
"""

import sqlalchemy as sa

from alembic import op

revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("approval_queue", sa.Column("requested_by", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("approval_queue", "requested_by")
