#!/usr/bin/env python3
"""Sort a memory backlog with the local model: keep lasting facts, set the rest aside.

Why: on 2026-10-22, 3,668 memories sat at ``pending`` (none approved since
2026-10-13), mostly the assistant narrating its own work and regex fragments
like "They → the same code"; and among the 484 active ones the most-read were
tool-use ids. The review gate cannot be worked by hand at that size.

What it does — and never does:
- Pending memories judged noise become ``rejected``; active ones judged noise
  become ``archived``. Both are reversible (approve / un-archive). Nothing is
  deleted.
- Memories judged worth keeping are left exactly as they are, so the owner
  reviews a short list instead of thousands.
- Every decision and the reason is written to a JSON report, and stamped on the
  memory (``properties.triage``) when applied.
- The model is the local one only (``chat_local_only``): these are the owner's
  memories.

Two passes: deterministic rules for the obvious noise, then the local model in
batches for the rest.

Usage:
    python scripts/triage_memories_llm.py --tenant raja                 # dry run
    python scripts/triage_memories_llm.py --tenant raja --apply
    python scripts/triage_memories_llm.py --tenant raja --status active --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

#: Noise recognisable without a model. Each is (name, pattern).
RULES: list[tuple[str, re.Pattern[str]]] = [
    ("arrow-fragment", re.compile(r"→")),
    ("tool-id", re.compile(r"\btoolu_[A-Za-z0-9]+|\btool use (?:with )?id\b", re.I)),
    ("task-id", re.compile(r"\btask(?:[- ]id)?\s*['\"`]?[a-z0-9]{8,}\b", re.I)),
    ("temp-path", re.compile(r"AppData\\Local\\Temp|/tmp/|scratchpad", re.I)),
    ("command-trace", re.compile(r"\b(?:the command|exit code|was executed|output file)\b", re.I)),
]

PROMPT = """\
You are cleaning one person's memory store. Most of these items were taken
from an assistant's work log, and most should be dropped.

For each numbered memory ask: in a new conversation a month from now, would
the owner want an assistant to know this? KEEP only:
- who the owner is, what they prefer or avoid, how they like to work;
- a decision the owner made, or a rule they set, that still applies;
- the owner's plans and goals, people and things in their life;
- what a project IS or how it is set up for good (its purpose, its stack,
  where it runs, a standing rule for it).
DROP everything else, in particular:
- progress, status or results of work ("tests pass", "pages load", "the plan
  is complete", "the branch was renamed", "PR merged", "N errors remain");
- what the assistant did, found, suggests, recommends or asks;
- bugs and fixes, counts, commit hashes, ids, paths, commands, settings that
  were only mentioned in passing;
- general advice or descriptions of tools that say nothing about the owner;
- fragments that do not make sense on their own.

Examples: KEEP "The owner wants Life Graph to stay closed source." KEEP "The
owner's Android phone has 8 GB RAM." KEEP "Uzhavu is the owner's farm
marketplace app." DROP "All 53 school checks pass." DROP "A squash merge
would leave main with one tidy commit." DROP "The user is asking whether to
fix the first two bugs." DROP "PR-Agent reviews real diffs."

Answer with JSON only: {"decisions": [{"n": 1, "keep": false, "why": "few words"}, ...]}
one entry per memory, same numbers."""

SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "triage",
        "schema": {
            "type": "object",
            "properties": {
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "n": {"type": "integer"},
                            "keep": {"type": "boolean"},
                            "why": {"type": "string"},
                        },
                        "required": ["n", "keep", "why"],
                    },
                }
            },
            "required": ["decisions"],
        },
    },
}


def rule_verdict(content: str) -> str | None:
    for name, pattern in RULES:
        if pattern.search(content):
            return name
    return None


async def judge(client, model: str, batch: list[tuple[str, str]]) -> dict[str, tuple[bool, str]]:
    """{memory id: (keep, why)} for one batch; ids the model skipped are kept."""
    listing = "\n".join(f"{i + 1}. {' '.join(c.split())[:400]}" for i, (_, c) in enumerate(batch))
    reply = await client.chat_local_only(
        [{"role": "system", "content": PROMPT}, {"role": "user", "content": listing}],
        model=model,
        temperature=0.0,
        max_tokens=2048,
        response_format=SCHEMA,
    )
    out: dict[str, tuple[bool, str]] = {}
    try:
        for d in json.loads(reply).get("decisions", []):
            idx = int(d["n"]) - 1
            if 0 <= idx < len(batch):
                out[batch[idx][0]] = (bool(d["keep"]), str(d.get("why", ""))[:120])
    except (ValueError, KeyError, TypeError):
        pass  # an unreadable answer keeps the whole batch: erring towards keeping is cheap
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--status", default="pending", choices=["pending", "active"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N (for trying it)")
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings
    from life_graph.storage.database import async_session

    if not settings.use_local_llm:
        print("STOP: local LLM is off; the owner's memories must not go to a cloud model.")
        return 2
    model = settings.lm_extraction_model
    new_status = "rejected" if args.status == "pending" else "archived"

    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "select id::text, content from memories where tenant_id=:t and status=:st "
                    "order by created_at" + (" limit :n" if args.limit else "")
                ),
                {"t": args.tenant, "st": args.status, **({"n": args.limit} if args.limit else {})},
            )
        ).all()
    print(f"{len(rows)} {args.status} memories for {args.tenant}; model {model}")

    decisions: dict[str, dict] = {}
    to_model: list[tuple[str, str]] = []
    for mid, content in rows:
        rule = rule_verdict(content)
        if rule:
            decisions[mid] = {"keep": False, "why": f"rule:{rule}", "content": content}
        else:
            to_model.append((mid, content))
    print(f"rules set aside {len(decisions)}; {len(to_model)} go to the model")

    client = get_lm_client()
    for start in range(0, len(to_model), args.batch):
        batch = to_model[start : start + args.batch]
        verdicts = await judge(client, model, batch)
        for mid, content in batch:
            keep, why = verdicts.get(mid, (True, "model gave no answer: kept"))
            decisions[mid] = {"keep": keep, "why": why, "content": content}
        done = min(start + args.batch, len(to_model))
        if done % (args.batch * 10) == 0 or done == len(to_model):
            kept = sum(1 for d in decisions.values() if d["keep"])
            print(f"  {done}/{len(to_model)} judged; kept so far {kept}", flush=True)

    keep_ids = [m for m, d in decisions.items() if d["keep"]]
    drop_ids = [m for m, d in decisions.items() if not d["keep"]]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = Path(args.report or f"triage-{args.tenant}-{args.status}-{stamp}.json")
    report.write_text(
        json.dumps(
            {
                "tenant": args.tenant,
                "status": args.status,
                "model": model,
                "applied": args.apply,
                "kept": len(keep_ids),
                "set_aside": len(drop_ids),
                "decisions": decisions,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"keep {len(keep_ids)}, set aside {len(drop_ids)} -> {new_status}; report {report}")

    if not args.apply:
        print("dry run: nothing written (use --apply)")
        return 0
    async with async_session() as s:
        for mid in drop_ids:
            note = json.dumps(
                {"triage": {"at": stamp, "why": decisions[mid]["why"], "was": args.status}}
            )
            await s.execute(
                text(
                    "update memories set status=:new, updated_at=now(), "
                    "properties = coalesce(properties, '{}'::jsonb) || CAST(:note AS jsonb) "
                    "where id=CAST(:id AS uuid) and tenant_id=:t and status=:st"
                ),
                {"new": new_status, "note": note, "id": mid, "t": args.tenant, "st": args.status},
            )
        await s.commit()
    print(f"applied: {len(drop_ids)} memories -> {new_status}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
