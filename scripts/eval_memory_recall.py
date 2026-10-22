#!/usr/bin/env python3
"""Measure memory retrieval on the owner's own memories, per search method.

Why: the one existing set (evals/recall_gold.yaml) has 20 questions from
2026-10-03, counts pending memories agents never see, and measures one mode.
This builds a set from the tenant's ACTIVE memories and scores each search
method the same way, so a change to retrieval is a number, not a guess.

build   For each active memory the local model writes one question a person
        would ask whose answer is that memory, plus questions on topics the
        memories do not cover (the right answer to those is "I don't know").
        Written to evals/local/<tenant>_recall.json — personal, never in git.
run     Scores each method: hit@1, hit@5 and MRR for answerable questions
        (a hit is the source memory's id among the results, no substring
        guessing), and for unanswerable ones how often the method returns
        nothing (only a method with a relevance filter can).

Local model only: these are the owner's memories.

Usage:
    python scripts/eval_memory_recall.py build --tenant raja
    python scripts/eval_memory_recall.py run --tenant raja [--methods vector,hybrid]
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

QUESTION_PROMPT = """\
For each numbered note about a person (the owner), write ONE short question the
owner might ask their assistant whose answer is that note. Ask it the way a
person would ("When does my car insurance renew?"), without copying the note's
wording, and without naming the answer.
Answer with JSON only: {"questions": [{"n": 1, "q": "..."}, ...]}"""

UNANSWERABLE_PROMPT = """\
Here are notes about a person. Write %d short questions the person might ask
their assistant that these notes do NOT answer: everyday personal topics (health,
family, travel, money, food, hobbies, work) that none of the notes mention.
Answer with JSON only: {"questions": ["...", ...]}"""


def _schema(name: str, items: dict) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": {
                "type": "object",
                "properties": {"questions": {"type": "array", "items": items}},
                "required": ["questions"],
            },
        },
    }


async def _active(tenant: str) -> list[tuple[str, str]]:
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = await s.execute(
            text(
                "select id::text, content from memories where tenant_id=:t and status='active' "
                "order by created_at"
            ),
            {"t": tenant},
        )
        return [(r[0], r[1]) for r in rows]


async def build(tenant: str, unanswerable: int) -> Path:
    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings

    client, model = get_lm_client(), settings.lm_extraction_model
    memories = await _active(tenant)
    cases: list[dict] = []
    for start in range(0, len(memories), 10):
        batch = memories[start : start + 10]
        listing = "\n".join(
            f"{i + 1}. {' '.join(c.split())[:300]}" for i, (_, c) in enumerate(batch)
        )
        reply = await client.chat_local_only(
            [{"role": "system", "content": QUESTION_PROMPT}, {"role": "user", "content": listing}],
            model=model,
            temperature=0.2,
            max_tokens=2048,
            response_format=_schema(
                "qs",
                {
                    "type": "object",
                    "properties": {"n": {"type": "integer"}, "q": {"type": "string"}},
                    "required": ["n", "q"],
                },
            ),
        )
        try:
            for item in json.loads(reply).get("questions", []):
                idx = int(item["n"]) - 1
                if 0 <= idx < len(batch) and item.get("q"):
                    cases.append(
                        {"q": item["q"], "memory_id": batch[idx][0], "memory": batch[idx][1]}
                    )
        except (ValueError, KeyError, TypeError):
            continue
    sample = "\n".join(f"- {' '.join(c.split())[:160]}" for _, c in memories[:80])
    reply = await client.chat_local_only(
        [
            {"role": "system", "content": UNANSWERABLE_PROMPT % unanswerable},
            {"role": "user", "content": sample},
        ],
        model=model,
        temperature=0.4,
        max_tokens=1024,
        response_format=_schema("un", {"type": "string"}),
    )
    try:
        for q in json.loads(reply).get("questions", [])[:unanswerable]:
            cases.append({"q": q, "memory_id": None})
    except (ValueError, TypeError):
        pass
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{tenant}_recall.json"
    path.write_text(json.dumps({"tenant": tenant, "cases": cases}, ensure_ascii=False, indent=1))
    answerable = sum(1 for c in cases if c["memory_id"])
    print(f"{len(cases)} cases ({answerable} answerable) from {len(memories)} memories -> {path}")
    return path


async def _search(method: str, query: str, k: int) -> list[str]:
    """Ids in rank order for one method."""
    from life_graph.api.dependencies import get_memory_manager, get_store

    store = get_store()
    embedding = await get_memory_manager().generate_embedding(query)
    if method == "vector":
        rows = await store.search_similar(
            embedding=embedding, limit=k, filters={"status": "active"}, include_embedding=False
        )
        return [str(r.id) for r in rows]
    if method == "hybrid":
        hits = await store.hybrid_search(
            embedding=embedding, query_text=query, limit=k, statuses=("active",)
        )
        return [str(m.id) for m, _ in hits]
    if method == "recall":
        from life_graph.services.memory_retrieval import retrieve

        found = await retrieve(query, limit=k)
        return [str(m.id) for m in found or []]
    raise ValueError(method)


async def run(tenant: str, methods: list[str], k: int) -> dict:
    from life_graph.core.tenant import tenant_scope

    cases = json.loads((OUT_DIR / f"{tenant}_recall.json").read_text())["cases"]
    report: dict = {}
    with tenant_scope(tenant):
        for method in methods:
            ranks, empty_on_unanswerable, unanswerable, started = [], 0, 0, time.monotonic()
            for case in cases:
                ids = await _search(method, case["q"], k)
                if case["memory_id"] is None:
                    unanswerable += 1
                    empty_on_unanswerable += not ids
                    continue
                ranks.append(ids.index(case["memory_id"]) + 1 if case["memory_id"] in ids else None)
            n = len(ranks)
            hit1 = sum(1 for r in ranks if r == 1)
            hit5 = sum(1 for r in ranks if r and r <= 5)
            mrr = sum(1 / r for r in ranks if r) / n if n else 0.0
            report[method] = {
                "answerable": n,
                "hit@1": round(hit1 / n, 3) if n else 0,
                "hit@5": round(hit5 / n, 3) if n else 0,
                "mrr": round(mrr, 3),
                "abstained_on_unanswerable": f"{empty_on_unanswerable}/{unanswerable}",
                "ms_per_query": round((time.monotonic() - started) * 1000 / max(len(cases), 1)),
            }
            print(method, report[method], flush=True)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["build", "run"])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--methods", default="vector,hybrid")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--unanswerable", type=int, default=15)
    args = ap.parse_args()

    from life_graph.config import settings

    if not settings.use_local_llm:
        print("STOP: local LLM is off; the owner's memories must not go to a cloud model.")
        return 2
    if args.action == "build":
        asyncio.run(build(args.tenant, args.unanswerable))
    else:
        asyncio.run(run(args.tenant, args.methods.split(","), args.k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
