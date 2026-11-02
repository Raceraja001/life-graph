"""Memory quality report: how well Life Graph is turning what the owner says into memories.

Read-only (one READ ONLY transaction). Counts by default; ``--examples N`` adds up
to N real examples per problem, for review by the owner (or with their OK).

    PYTHONPATH=. python scripts/memory_quality_report.py [--days 7] [--tenant raja]
        [--examples 3] [--spool ~/.life-graph/claude-code/spool.db]

The database is LIFE_GRAPH_DATABASE_URL_SYNC (run it from the copy whose .env
you mean: dev holds the Claude Code captures since 2026-10-29, prod the phone
and Jarvis app). Sections:

- captures: what arrived, per surface, and how much of it became memory;
- the hook queue: captures waiting to be sent (a stuck queue looked like
  silence for three weeks, 2026-10-13..11-02);
- extraction: yield, fact types, hedged share, and questions or pasted text
  stored as preferences or decisions (thinking aloud is not a decision);
- review: what the owner kept, dropped or has not looked at, per fact type;
- people: roles and other names learned, entities that name nothing (dates,
  URLs, paths), relations in memories that contradict the people table.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, text

QUESTION = re.compile(
    r"\?\s*$|\?\s+\S{0,40}$|^(can|could|should|shall) we\b|\bwe can\b.*\?", re.I | re.M
)
PASTED = re.compile(r"<(pasted_content|task-notification|agent-message)\b", re.I)


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "-"


def report(c, tenant: str, days: int, examples: int) -> list[str]:
    out: list[str] = []
    since = {"t": tenant, "d": f"{days} days"}
    window = "created_at > now() - CAST(:d AS interval)"

    out.append(f"== captures, last {days} days (tenant {tenant})")
    rows = c.execute(
        text(f"""
        SELECT ce.surface, count(*), count(DISTINCT m.capture_event_id)
        FROM capture_events ce LEFT JOIN memories m ON m.capture_event_id = ce.id
        WHERE ce.tenant_id = :t AND ce.{window} GROUP BY 1 ORDER BY 2 DESC"""),
        since,
    ).all()
    for surface, n, with_memory in rows:
        out.append(f"  {surface:<20} {n:>6} captures, {with_memory:>4} gave memories")
    if not rows:
        out.append("  NONE - is the API the hook posts to running?")
    last = c.execute(
        text(
            "SELECT max(occurred_at) FROM capture_events WHERE tenant_id = :t AND surface <> 'tool_exhaust'"
        ),
        since,
    ).scalar()
    out.append(f"  last non-tool capture: {last}")

    out.append(f"\n== extraction, last {days} days")
    traces, with_facts = c.execute(
        text(f"""
        SELECT count(*), count(*) FILTER (WHERE jsonb_array_length(COALESCE(facts, '[]'::jsonb)) > 0)
        FROM extraction_traces WHERE tenant_id = :t AND {window}"""),
        since,
    ).one()
    out.append(f"  extractions {traces}, with facts {with_facts} ({_pct(with_facts, traces)})")
    mems = c.execute(
        text(f"""
        SELECT COALESCE(properties->>'fact_type', '?') AS ft, status,
               COALESCE(properties->>'certainty', 'firm') AS cert, count(*)
        FROM memories WHERE tenant_id = :t AND {window} AND source_type = 'capture'
        GROUP BY 1, 2, 3"""),
        since,
    ).all()
    by_type: Counter = Counter()
    by_status: dict[str, Counter] = {}
    hedged = 0
    for ft, status, cert, n in mems:
        by_type[ft] += n
        by_status.setdefault(ft, Counter())[status] += n
        hedged += n if cert == "hedged" else 0
    total = sum(by_type.values())
    out.append(f"  memories from captures {total}, hedged {hedged} ({_pct(hedged, total)})")
    out.append("\n== review (status of those memories), per fact type")
    for ft, n in by_type.most_common():
        s = by_status[ft]
        out.append(
            f"  {ft:<15} {n:>4}  active {s['active']:>3}  pending {s['pending']:>3}  "
            f"rejected {s['rejected']:>3}  archived {s['archived']:>3}  superseded {s['superseded']:>3}"
        )

    rows = c.execute(
        text(f"""
        SELECT m.properties->>'fact_type', m.status, left(m.content, 140), left(t.input_text, 160)
        FROM memories m JOIN extraction_traces t ON t.id::text = m.properties->>'extraction_trace_id'
        WHERE m.tenant_id = :t AND m.{window}
          AND m.properties->>'fact_type' IN ('preference', 'decision')
          -- What the owner said; an assistant's "…next?" is not their question.
          AND COALESCE(m.properties->>'surface', '') NOT IN ('assistant_message', 'tool_exhaust')"""),
        since,
    ).all()
    from_questions = [r for r in rows if QUESTION.search(r[3] or "")]
    from_pasted = [r for r in rows if PASTED.search(r[3] or "")]
    out.append("\n== thinking aloud stored as settled")
    out.append(
        f"  preferences/decisions {len(rows)}: from a question {len(from_questions)}, from pasted text {len(from_pasted)}"
    )
    for ft, status, content, inp in (from_questions + from_pasted)[:examples]:
        out.append(f"    [{ft}/{status}] {content!r}\n        said: {inp!r}")

    out.append("\n== people")
    roles, aliases_, total_e = c.execute(
        text("""SELECT count(*) FILTER (WHERE role IS NOT NULL), count(*) FILTER (WHERE canonical_id IS NOT NULL),
                count(*) FROM entities WHERE tenant_id = :t"""),
        since,
    ).one()
    out.append(f"  entities {total_e}: with a role {roles}, other names {aliases_}")
    try:
        from life_graph.services.entities import names_a_thing
    except ImportError:  # before #221
        names_a_thing = None
    if names_a_thing:
        names = [
            r[0] for r in c.execute(text("SELECT name FROM entities WHERE tenant_id = :t"), since)
        ]
        junk = [n for n in names if not names_a_thing(n)]
        out.append(f"  entities that name nothing (dates, URLs, paths…): {len(junk)}")
        out.extend(f"    {n!r}" for n in junk[:examples])

    from life_graph.core import aliases
    from life_graph.services.entities import _GLOSS, normalize

    known = {
        r[0]: r[1]
        for r in c.execute(
            text("SELECT key, role FROM entities WHERE tenant_id = :t AND role IS NOT NULL"), since
        )
    }
    clash: list[tuple[str, str, str]] = []
    for (content,) in c.execute(
        text(
            f"SELECT content FROM memories WHERE tenant_id = :t AND {window} AND content LIKE '%owner''s%'"
        ),
        since,
    ):
        for m in _GLOSS.finditer(content or ""):
            said = aliases.role_of_word(m.group(2).split(",")[0].strip())
            role = known.get(normalize(m.group(1)))
            if said and role and said != role:
                clash.append((m.group(1), said, role))
    out.append(f"  relations in memories that contradict the people table: {len(clash)}")
    out.extend(
        f"    {who}: memory says {said}, table says {role}" for who, said, role in clash[:examples]
    )
    return out


def spool_lines(path: Path) -> list[str]:
    if not path.exists():
        return [f"\n== hook queue: no {path}"]
    try:
        n, oldest = (
            sqlite3.connect(path)
            .execute("SELECT count(*), min(created_at) FROM pending")
            .fetchone()
        )
    except sqlite3.Error as exc:
        return [f"\n== hook queue: unreadable ({exc})"]
    from datetime import UTC, datetime

    age = f", oldest {datetime.fromtimestamp(oldest, UTC):%Y-%m-%d %H:%M} UTC" if oldest else ""
    warn = "  <- STUCK? the hook sends these on its next runs" if n > 50 else ""
    return [f"\n== hook queue: {n} waiting{age}{warn}"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--tenant", default="raja")
    ap.add_argument(
        "--examples", type=int, default=0, help="real examples per problem (0 = counts only)"
    )
    ap.add_argument(
        "--spool", type=Path, default=Path("~/.life-graph/claude-code/spool.db").expanduser()
    )
    a = ap.parse_args()
    url = os.environ.get("LIFE_GRAPH_DATABASE_URL_SYNC")
    if not url:
        from life_graph.config import settings

        url = settings.database_url_sync
    db = url.rsplit("/", 1)[-1]
    with create_engine(url).connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        lines = [f"memory quality report · database {db}"] + report(c, a.tenant, a.days, a.examples)
    print("\n".join(lines + spool_lines(a.spool)))


if __name__ == "__main__":
    main()
