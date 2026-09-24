"""043 — relabel assistant closing messages onto their own surface.

``Stop``/``SubagentStop`` captures used to land on ``tool_exhaust``. That
surface is now an activity trail the capture spine does not extract, so a
conclusion left there would never become a memory again. The hook writes
``assistant_message`` from this release on; this moves the rows already
stored, which are identifiable by the ``kind`` property the hook has always
set.

Both surfaces are ``TrustTier.VERIFIED``, so no row changes trust tier and
nothing that was fenced becomes unfenced.

Revision ID: 043
Revises: 042
Create Date: 2026-09-24
"""

from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None

_PREDICATE = """
    surface = '{from_surface}'
    AND properties->>'kind' = 'assistant_message'
"""


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE capture_events
        SET surface = 'assistant_message'
        WHERE {_PREDICATE.format(from_surface="tool_exhaust")}
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE capture_events
        SET surface = 'tool_exhaust'
        WHERE {_PREDICATE.format(from_surface="assistant_message")}
        """
    )
