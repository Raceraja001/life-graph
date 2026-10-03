#!/usr/bin/env python3
"""Clear a pending-memory backlog: delete the mechanical noise, approve the rest.

Why this exists
---------------
Proactive recall reads ``status='active'`` only. On an instance where nothing
has ever been approved, every memory sits at ``pending`` and recall returns
empty buckets — the capture side works, extraction works, ranking works, and
the payoff event delivers nothing. That was the state here: 601 memories, 601
pending, and a SessionStart hook that had never surfaced a single one.

So the backlog is not a tidiness problem, it is the feature being closed. This
script opens it in one pass and leaves an auditable record of what it judged.

What counts as noise
--------------------
Facts about the *mechanics* of a session rather than its content: shell command
transcripts, task ids, exit codes, scratchpad paths, and anything extracted
from a subagent hand-back (a long model-written report that arrived as a user
turn — see MACHINE_PROMPT_TAGS in the Claude Code hook, which now drops them at
the source). These are true, worthless, and were never addressed to the
extractor.

The rules are deliberately conservative and listed in one place below. Being
wrong in the direction of keeping something is cheap: decay and the archive
sweep handle a fact that stops mattering, while a wrongly deleted memory is
gone.

Usage
-----
    python scripts/triage_pending_memories.py                 # dry run
    python scripts/triage_pending_memories.py --apply
    python scripts/triage_pending_memories.py --apply --keep-ephemeral

``--apply`` is required; without it nothing is written. Deletion is
irreversible, so take a backup (``scripts/backup.sh``) if the instance holds
anything you cannot re-derive.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text

from life_graph.config import settings

#: Content that describes how a session was run, not what was decided in it.
#: Matched case-insensitively against the memory text.
NOISE_PATTERNS = [
    "%task with id%",
    "%background command%",
    "%the command executed%",
    "%wsl.exe%",
    "%exit code%",
    "%scratchpad%",
    "transitioned to%",  # the signature of an extractor failing on a long report
]

#: Facts that were true for an hour. Dropped unless --keep-ephemeral, because
#: a knowledge base full of "CI checks passed" teaches recall about yesterday.
EPHEMERAL_PATTERNS = [
    "%ci checks%",
    "%is being monitored%",
    "%was completed successfully%",
]

_NOISE_SQL = " OR ".join(f"content ILIKE :p{i}" for i in range(len(NOISE_PATTERNS)))
_EPH_SQL = " OR ".join(f"content ILIKE :e{i}" for i in range(len(EPHEMERAL_PATTERNS)))

#: Memories extracted from a subagent hand-back. Identified through the capture
#: event rather than by content, because the extractor's output from those is
#: arbitrary and unmatchable.
_HANDBACK_SQL = """
    properties->>'capture_event_id' IN (
        SELECT id::text FROM capture_events WHERE content LIKE '<agent-message%'
    )
"""


def _params() -> dict[str, str]:
    params = {f"p{i}": p for i, p in enumerate(NOISE_PATTERNS)}
    params.update({f"e{i}": p for i, p in enumerate(EPHEMERAL_PATTERNS)})
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    parser.add_argument(
        "--keep-ephemeral",
        action="store_true",
        help="approve short-lived status facts instead of deleting them",
    )
    args = parser.parse_args()

    drop = f"({_NOISE_SQL}) OR {_HANDBACK_SQL}"
    if not args.keep_ephemeral:
        drop = f"{drop} OR ({_EPH_SQL})"

    engine = create_engine(settings.database_url_sync)
    params = _params()

    with engine.begin() as conn:
        pending = conn.execute(
            text("SELECT count(*) FROM memories WHERE status = 'pending'")
        ).scalar_one()
        doomed = conn.execute(
            text(f"SELECT count(*) FROM memories WHERE status = 'pending' AND ({drop})"), params
        ).scalar_one()
        print(f"pending: {pending}")
        print(f"  noise to delete: {doomed}")
        print(f"  to approve:      {pending - doomed}")

        for label, clause in (("delete", drop), ("approve", f"NOT ({drop})")):
            rows = conn.execute(
                text(
                    f"SELECT left(content, 88) FROM memories "
                    f"WHERE status = 'pending' AND ({clause}) "
                    f"ORDER BY importance DESC LIMIT 4"
                ),
                params,
            ).scalars()
            print(f"\nsample to {label}:")
            for row in rows:
                print(f"  - {row}")

    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    with engine.begin() as conn:
        deleted = conn.execute(
            text(f"DELETE FROM memories WHERE status = 'pending' AND ({drop})"), params
        ).rowcount
        # Approve in SQL rather than through POST /memories/approvals/bulk: that
        # route transitions one memory per request, and several hundred HTTP
        # round trips to set one column is a long way round. The transition is
        # a status change with no side effects beyond it.
        approved = conn.execute(
            text(
                "UPDATE memories SET status = 'active', updated_at = now() "
                "WHERE status = 'pending'"
            )
        ).rowcount

    with engine.begin() as conn:
        remaining = conn.execute(
            text("SELECT status, count(*) FROM memories GROUP BY 1 ORDER BY 2 DESC")
        ).all()
    print(f"\ndeleted {deleted}, approved {approved}")
    for status, count in remaining:
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
