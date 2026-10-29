#!/usr/bin/env python3
"""Measure memory retrieval on the owner's own memories, per search method.

Why: the one existing set (evals/recall_gold.yaml) has 20 questions from
2026-10-03, counts pending memories agents never see, and measures one mode.
This builds sets from the tenant's own memories and scores each search method
the same way, so a change to retrieval is a number, not a guess.

Sets live in evals/local/<tenant>_<set>.json (personal, never in git):

- ``recall``: built 2026-10-22 from the memories active then. They were
  archived at the 2026-10-23 fresh start, so it is run with ``--pool archived``
  (797 memories on 2026-10-28: the answers plus every older archived memory as
  distractors).
- ``live``: built from the memories active now. ``build`` only ADDS questions
  for memories it has none for, so the set grows as the owner keeps memories
  (services/memory_check.py) and earlier numbers stay comparable.
- ``<set>_ta``: the same questions in Tamil (``translate``), because Tamil
  questions are where ranking broke on 2026-10-28 (a reranker took hit@1 from
  70% to 23%).

build      Questions for active memories that have none yet (local model), and
           on first build questions the memories cannot answer.
translate  A Tamil copy of a set's answerable questions (first --n).
run        Scores each method: hit@1, hit@5 and MRR for answerable questions (a
           hit is the source memory's id among the results, no substring
           guessing) and, for unanswerable ones, how often the method returns
           nothing (only a method with a relevance filter can). Each run is
           appended to evals/local/<tenant>_<set>_runs.jsonl.

Methods: ``vector``, ``hybrid`` (what search uses), ``judge`` (hybrid's top
10 filtered and ordered by the relevance judge, as Jarvis does) and ``recall``
(Jarvis's full retrieval: judge plus dated day summaries and entity links;
active pool only).

Local model only: these are the owner's memories.

Usage:
    python scripts/eval_memory_recall.py build --tenant raja [--set live]
    python scripts/eval_memory_recall.py translate --tenant raja --set recall --n 30
    python scripts/eval_memory_recall.py run --tenant raja --set recall --pool archived \\
        [--methods vector,hybrid,judge]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

OUT_DIR = Path("evals/local")
#: Candidates the judge sees, as in services/memory_retrieval.py.
JUDGE_CANDIDATES = 10

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

TAMIL_PROMPT = """\
Translate each numbered question into natural spoken Tamil, the way a Tamil
speaker would ask their assistant. Keep product and place names (life-graph,
Jarvis, Dify, Chennai, ...) as they are.
Answer with JSON only: {"questions": [{"n": 1, "q": "..."}, ...]}"""


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


NUMBERED = {
    "type": "object",
    "properties": {"n": {"type": "integer"}, "q": {"type": "string"}},
    "required": ["n", "q"],
}


def _path(tenant: str, name: str) -> Path:
    return OUT_DIR / f"{tenant}_{name}.json"


def _load(tenant: str, name: str) -> dict:
    path = _path(tenant, name)
    if not path.exists():
        return {"tenant": tenant, "cases": []}
    return json.loads(path.read_text())


def _save(tenant: str, name: str, data: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(tenant, name)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return path


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


async def _numbered(client, model: str, prompt: str, items: list[str]) -> dict[int, str]:
    """``{index: answer}`` for a numbered list sent to the local model."""
    listing = "\n".join(f"{i + 1}. {' '.join(c.split())[:300]}" for i, c in enumerate(items))
    reply = await client.chat_local_only(
        [{"role": "system", "content": prompt}, {"role": "user", "content": listing}],
        model=model,
        temperature=0.2,
        max_tokens=2048,
        response_format=_schema("qs", NUMBERED),
    )
    out: dict[int, str] = {}
    try:
        for item in json.loads(reply).get("questions", []):
            idx = int(item["n"]) - 1
            if 0 <= idx < len(items) and item.get("q"):
                out[idx] = item["q"]
    except (ValueError, KeyError, TypeError):
        pass
    return out


async def build(tenant: str, name: str, unanswerable: int) -> Path:
    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings

    client, model = get_lm_client(), settings.lm_extraction_model
    data = _load(tenant, name)
    cases: list[dict] = data["cases"]
    first_build = not cases
    asked = {c["memory_id"] for c in cases if c.get("memory_id")}
    memories = await _active(tenant)
    new = [(mid, c) for mid, c in memories if mid not in asked]
    for start in range(0, len(new), 10):
        batch = new[start : start + 10]
        found = await _numbered(client, model, QUESTION_PROMPT, [c for _, c in batch])
        for idx, q in found.items():
            cases.append({"q": q, "memory_id": batch[idx][0], "memory": batch[idx][1]})
    if first_build and memories:
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
    data["cases"] = cases
    data["updated"] = datetime.now(UTC).isoformat()
    path = _save(tenant, name, data)
    answerable = sum(1 for c in cases if c["memory_id"])
    print(
        f"{len(cases)} cases ({answerable} answerable); {len(new)} new memories asked about,"
        f" {len(memories)} active -> {path}"
    )
    return path


async def translate(tenant: str, name: str, n: int) -> Path:
    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings

    client, model = get_lm_client(), settings.lm_extraction_model
    source = [c for c in _load(tenant, name)["cases"] if c["memory_id"]][:n]
    out: list[dict] = []
    for start in range(0, len(source), 10):
        batch = source[start : start + 10]
        found = await _numbered(client, model, TAMIL_PROMPT, [c["q"] for c in batch])
        for idx, q in found.items():
            out.append({**batch[idx], "q": q, "en": batch[idx]["q"]})
    path = _save(tenant, f"{name}_ta", {"tenant": tenant, "from": name, "cases": out})
    print(f"{len(out)} Tamil questions from {len(source)} -> {path}")
    return path


async def _search(method: str, query: str, k: int, pool: str) -> list[str]:
    """Ids in rank order for one method."""
    if method == "recall" and pool != "active":
        raise ValueError("recall reads active memories only; use judge for other pools")
    from life_graph.api.dependencies import get_memory_manager, get_store

    store = get_store()
    embedding = await get_memory_manager().generate_embedding(query)
    if method == "vector":
        rows = await store.search_similar(
            embedding=embedding, limit=k, filters={"status": pool}, include_embedding=False
        )
        return [str(r.id) for r in rows]
    if method in ("hybrid", "judge"):
        hits = await store.hybrid_search(
            embedding=embedding,
            query_text=query,
            limit=JUDGE_CANDIDATES if method == "judge" else k,
            statuses=(pool,),
        )
        ids = [str(m.id) for m, _ in hits]
        if method == "hybrid":
            return ids
        from life_graph.services.memory_retrieval import judge

        picked = await judge(query, [m.content for m, _ in hits])
        # A judge failure falls back to the search order, as retrieval does.
        return ids if picked is None else [ids[i] for i in picked]
    if method == "recall":
        from life_graph.services.memory_retrieval import retrieve

        found = await retrieve(query, limit=k)
        return [str(m.id) for m in found or []]
    raise ValueError(method)


async def run(tenant: str, name: str, methods: list[str], k: int, pool: str) -> dict:
    from life_graph.core.tenant import tenant_scope

    cases = _load(tenant, name)["cases"]
    if not cases:
        print(f"no set {_path(tenant, name)}: build it first")
        return {}
    report: dict = {}
    with tenant_scope(tenant):
        for method in methods:
            ranks, empty_on_unanswerable, unanswerable, started = [], 0, 0, time.monotonic()
            for case in cases:
                ids = await _search(method, case["q"], k, pool)
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / f"{tenant}_{name}_runs.jsonl").open("a") as f:
        line = {"at": datetime.now(UTC).isoformat(), "pool": pool, "k": k, "report": report}
        f.write(json.dumps(line) + "\n")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["build", "translate", "run"])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--set", default="recall", help="evals/local/<tenant>_<set>.json")
    ap.add_argument("--pool", default="active", choices=["active", "archived"])
    ap.add_argument("--methods", default="vector,hybrid")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--n", type=int, default=30, help="translate: questions to translate")
    ap.add_argument("--unanswerable", type=int, default=15)
    args = ap.parse_args()

    from life_graph.config import settings

    if not settings.use_local_llm:
        print("STOP: local LLM is off; the owner's memories must not go to a cloud model.")
        return 2
    if args.action == "build":
        asyncio.run(build(args.tenant, args.set, args.unanswerable))
    elif args.action == "translate":
        asyncio.run(translate(args.tenant, args.set, args.n))
    else:
        asyncio.run(run(args.tenant, args.set, args.methods.split(","), args.k, args.pool))
    return 0


if __name__ == "__main__":
    sys.exit(main())
