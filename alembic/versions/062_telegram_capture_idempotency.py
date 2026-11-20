"""062 — one capture per Telegram message; memory foreign keys that match the models.

1. Telegram replay idempotency (audit M9). The poller replays an update after a
   crash or a lease handover, and the capture spine's only dedup was a content
   hash inside a 10-minute window. A partial unique index on
   (tenant_id, surface, chat_id, message_id) for ``surface = 'telegram'`` makes
   the database the judge: CaptureService.ingest turns the conflict into the
   usual duplicate view.

   Rows that would already violate it are not deleted. Every row but the
   earliest of a (tenant, chat, message) group has its ``message_id`` key
   renamed to ``replayed_message_id`` (plus ``replay_of`` = the kept row's id),
   which takes it out of the index predicate and keeps it readable. Downgrade
   renames the keys back. The table is locked against writes for the few
   statements this takes, so no duplicate can slip in between the rename and
   the index build. (Production has no Telegram bot configured, so the rename
   is expected to touch nothing there.)

2. ON DELETE for five self/cross references to memories and sessions. The
   models have always declared ``ondelete="SET NULL"``; the migrations that
   created these columns (001, intentions, knowledge_gaps) declared no action,
   so deleting a memory another memory superseded, or one an intention or a
   knowledge gap points at, failed with a foreign-key violation instead of
   clearing the reference. Found by the model/schema drift check
   (scripts/schema_drift.py). Re-created NOT VALID and then validated, so the
   check runs without blocking writes for its whole length.

Revision ID: 062
Revises: 061
Create Date: 2026-11-20
"""

from alembic import op

revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None

_INDEX = "uq_ce_telegram_message"

# (table, column, constraint, referred table)
_FKS = (
    ("memories", "supersedes", "memories_supersedes_fkey", "memories"),
    ("memories", "superseded_by", "memories_superseded_by_fkey", "memories"),
    ("intentions", "source_memory", "intentions_source_memory_fkey", "memories"),
    ("intentions", "source_session", "intentions_source_session_fkey", "sessions"),
    ("knowledge_gaps", "resolved_by", "knowledge_gaps_resolved_by_fkey", "memories"),
)


def _recreate_fks(ondelete: str) -> None:
    for table, column, name, referred in _FKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({column}) "
            f"REFERENCES {referred} (id) ON DELETE {ondelete} NOT VALID"
        )
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")


def upgrade() -> None:
    # capture_events lives in the life_graph schema (see models/memory.py).
    op.execute("LOCK TABLE life_graph.capture_events IN SHARE ROW EXCLUSIVE MODE")
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER w AS keep_id,
                   row_number() OVER w AS rn
            FROM life_graph.capture_events
            WHERE surface = 'telegram'
              AND (properties ->> 'chat_id') IS NOT NULL
              AND (properties ->> 'message_id') IS NOT NULL
            WINDOW w AS (
                PARTITION BY tenant_id, properties ->> 'chat_id', properties ->> 'message_id'
                ORDER BY created_at, id
            )
        )
        UPDATE life_graph.capture_events ce
           SET properties = (ce.properties - 'message_id')
               || jsonb_build_object(
                    'replayed_message_id', ce.properties -> 'message_id',
                    'replay_of', ranked.keep_id::text)
          FROM ranked
         WHERE ce.id = ranked.id AND ranked.rn > 1
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX {_INDEX} ON life_graph.capture_events
            (tenant_id, surface, (properties ->> 'chat_id'), (properties ->> 'message_id'))
        WHERE surface = 'telegram'
          AND (properties ->> 'chat_id') IS NOT NULL
          AND (properties ->> 'message_id') IS NOT NULL
        """
    )
    _recreate_fks("SET NULL")


def downgrade() -> None:
    _recreate_fks("NO ACTION")
    op.execute(f"DROP INDEX IF EXISTS life_graph.{_INDEX}")
    op.execute(
        """
        UPDATE life_graph.capture_events
           SET properties = (properties - 'replayed_message_id' - 'replay_of')
               || jsonb_build_object('message_id', properties -> 'replayed_message_id')
         WHERE surface = 'telegram' AND properties ? 'replayed_message_id'
        """
    )
