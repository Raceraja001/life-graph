"""036 — backfill memories.trust_tier from source_type (downgrade-only).

Migration 022 added ``memories.trust_tier`` with a blanket ``'verified'`` and
grandfathered every existing row, on the reasoning that the corpus predated
untrusted surfaces. What it did not cover is the window *after* 022: writes
through ``POST /api/v1/memories`` took the store's ``'verified'`` default
regardless of who sent them, so third-party content could be filed as trusted.
That write path now derives the tier from ``source_type`` via
``core/trust.py::classify_surface``; this migration applies the same policy to
the rows already on disk.

**Downgrade-only.** A row is rewritten only when the derived tier is *stricter*
than what is stored. Two reasons:

1. A caller may have set a tier explicitly and deliberately — recomputing from
   ``source_type`` could silently promote such a row back to trusted, which is
   the exact failure this is meant to close.
2. Promotions would buy nothing anyway. The only consumer of the column,
   ``drivers/context.py``, branches at ``>= external``, so ``self`` and
   ``verified`` are indistinguishable in behaviour today.

That also makes the migration idempotent: a second run finds nothing left to
lower.

Revision ID: 036
Revises: 035
Create Date: 2026-08-26
"""

from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


# Mirrors life_graph/core/trust.py::_SURFACE_TIER. Kept as literal SQL rather
# than importing the app, so the migration keeps working if that module moves —
# the same choice migration 022 made. tests/unit/test_trust_tier_backfill.py
# asserts the two stay in agreement, which is what makes the duplication safe.
_SELF = (
    "cli",
    "dashboard",
    "voice",
    "image",
    "interview_answer",
    "orchestrator",
    "manual",
    "chat",
    "explicit",
)
_VERIFIED = (
    "tool_exhaust",
    "agent_task",
    "inferred",
    "project_scan",
    "kernel_task",
    "consolidation",
    "cold_start",
    "brief",
    "belief_challenge",
    "reinforcement",
    "autonomous_action",
    "ops",
    "bulk_import",
    "transcript",
    "uzhavu_sync",
)
_HOSTILE = ("whatsapp",)

# Least → most dangerous. array_position gives the ordinal, so "stricter than"
# is a plain integer comparison in SQL.
_ORDER_SQL = "ARRAY['self','verified','external','hostile_possible']"


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE memories
        SET trust_tier = derived.tier
        FROM (
            SELECT
                id,
                CASE
                    WHEN source_type IN ({_in(_SELF)}) THEN 'self'
                    WHEN source_type IN ({_in(_VERIFIED)}) THEN 'verified'
                    WHEN source_type IN ({_in(_HOSTILE)}) THEN 'hostile_possible'
                    ELSE 'external'  -- default-deny, matching classify_surface
                END AS tier
            FROM memories
        ) AS derived
        WHERE memories.id = derived.id
          AND array_position({_ORDER_SQL}, derived.tier)
              > COALESCE(array_position({_ORDER_SQL}, memories.trust_tier), 0)
        """
    )
    # COALESCE(..., 0) on the stored side: a value that is not a recognised
    # tier at all ranks as most-trusted, so any derived tier beats it and the
    # corrupt row gets repaired rather than skipped.


def downgrade() -> None:
    """No-op — the previous tiers are not recoverable.

    This migration overwrites values without recording what they were. The
    honest reverse is to leave the corrected tiers in place; restoring a blanket
    'verified' would re-open the hole 022 left, which is not what a downgrade
    should do.
    """
