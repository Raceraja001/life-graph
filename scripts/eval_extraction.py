#!/usr/bin/env python3
"""Measure the capture extractor against labelled owner messages: what it keeps, what it misses.

Why: since 2026-10-22 the extractor keeps only lasting facts about the owner,
and in its first day it kept nothing from 23 real messages. That may be right
(most were questions and instructions) or too strict; nothing measured it.

sample  Writes evals/local/<tenant>_extraction.json: N of the owner's own
        messages (capture surface ``cli`` by default), each with
        ``keep: null`` and ``expected: []`` to be labelled — keep true/false,
        and for true the facts a good extractor should save, in plain words.
        Personal, so evals/local/ is git-ignored.
run     Runs the extractor (local model only) on every labelled message and
        reports, per message, whether it kept something when it should
        (recall), kept nothing when it should not (precision), and what it
        produced, so a prompt change can be compared to the last run.

Usage:
    python scripts/eval_extraction.py sample --tenant raja --n 60
    python scripts/eval_extraction.py run --tenant raja [--save report.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from sqlalchemy import text

OUT_DIR = Path("evals/local")

#: Injected turns, not typed ones (the hook's MACHINE_PROMPT_TAGS and the like).
MACHINE_PREFIXES = ("<task-notification>", "<agent-message", "<local-command", "<command-", "<system-reminder>")


def _path(tenant: str) -> Path:
    return OUT_DIR / f"{tenant}_extraction.json"


async def sample(tenant: str, n: int, surface: str) -> None:
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "select distinct on (content_hash) id::text, content, created_at from capture_events "
                    "where tenant_id=:t and surface=:s and length(content) between 15 and 1500 "
                    "order by content_hash, created_at"
                ),
                {"t": tenant, "s": surface},
            )
        ).all()
    rows = [r for r in rows if not r[1].lstrip().startswith(MACHINE_PREFIXES)]
    rows.sort(key=lambda r: r[2])
    step = max(1, len(rows) // n)
    picked = rows[::step][:n]
    cases = [
        {"capture_id": r[0], "text": r[1], "keep": None, "expected": []} for r in picked
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _path(tenant).write_text(json.dumps({"tenant": tenant, "surface": surface, "cases": cases}, ensure_ascii=False, indent=1))
    print(f"{len(cases)} messages (of {len(rows)}) -> {_path(tenant)}; label keep/expected, then run")


async def run(tenant: str, save: str | None) -> dict:
    from life_graph.api.dependencies import get_extraction_pipeline
    from life_graph.core.tenant import tenant_scope

    data = json.loads(_path(tenant).read_text())
    cases = [c for c in data["cases"] if c.get("keep") is not None]
    pipe = get_extraction_pipeline()
    results, started = [], time.monotonic()
    with tenant_scope(tenant):
        for c in cases:
            facts = (await pipe.extract(c["text"], capture=True)).facts
            results.append(
                {
                    "capture_id": c["capture_id"],
                    "keep": c["keep"],
                    "kept": bool(facts),
                    "facts": [f.content for f in facts],
                    "expected": c.get("expected") or [],
                }
            )
    should = [r for r in results if r["keep"]]
    should_not = [r for r in results if not r["keep"]]
    tp = sum(1 for r in should if r["kept"])
    fp = sum(1 for r in should_not if r["kept"])
    report = {
        "labelled": len(results),
        "should_keep": len(should),
        "recall": round(tp / len(should), 3) if should else None,
        "false_keeps": f"{fp}/{len(should_not)}",
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else None,
        "s_per_message": round((time.monotonic() - started) / max(len(results), 1), 2),
        "missed": [r for r in should if not r["kept"]],
        "wrongly_kept": [r for r in should_not if r["kept"]],
        "results": results,
    }
    print(json.dumps({k: v for k, v in report.items() if k not in ("results",)}, ensure_ascii=False, indent=1))
    if save:
        Path(save).write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["sample", "run"])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--surface", default="cli")
    ap.add_argument("--save", default=None)
    args = ap.parse_args()

    from life_graph.config import settings

    if not settings.use_local_llm:
        print("STOP: local LLM is off; the owner's messages must not go to a cloud model.")
        return 2
    if args.action == "sample":
        asyncio.run(sample(args.tenant, args.n, args.surface))
    else:
        asyncio.run(run(args.tenant, args.save))
    return 0


if __name__ == "__main__":
    sys.exit(main())
