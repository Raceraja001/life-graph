"""022 — Immune System: trust_tier on capture_events and memories.

Adds provenance trust tiers (self|verified|external|hostile_possible) so the
driver boundary can fence/exclude untrusted content. See
docs/superpowers/specs/2026-07-15-immune-system-trust-tiers-design.md.

Revision ID: 022
Revises: 021
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── capture_events.trust_tier (schema: life_graph) ────────
    # Default-deny at the raw ingress: new rows default to 'external'.
    op.add_column(
        "capture_events",
        sa.Column(
            "trust_tier", sa.String(16),
            nullable=False, server_default="external",
        ),
        schema="life_graph",
    )

    # Backfill existing capture events from their known surface, mirroring
    # core/trust.py::classify_surface (kept in SQL to avoid an app import here).
    op.execute(
        """
        UPDATE life_graph.capture_events SET trust_tier = CASE
            WHEN surface IN ('cli','dashboard','voice','image','interview_answer','orchestrator')
                THEN 'self'
            WHEN surface IN ('tool_exhaust','project_scan','kernel_task')
                THEN 'verified'
            WHEN surface IN ('api','mcp','watcher')
                THEN 'external'
            WHEN surface = 'whatsapp'
                THEN 'hostile_possible'
            ELSE 'external'  -- default-deny
        END
        """
    )

    # ── memories.trust_tier (default schema: public) ──────────
    # System-produced by default: 'verified'. Untrusted origin is set
    # explicitly by the ingesting caller going forward. Historical rows are
    # grandfathered to 'verified' (they predate untrusted surfaces and were
    # already fed to drivers without incident); blanket-fencing the whole
    # corpus would degrade prompt quality for no security gain.
    op.add_column(
        "memories",
        sa.Column(
            "trust_tier", sa.String(16),
            nullable=False, server_default="verified",
        ),
    )


def downgrade() -> None:
    op.drop_column("memories", "trust_tier")
    op.drop_column("capture_events", "trust_tier", schema="life_graph")
