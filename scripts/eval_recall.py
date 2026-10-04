#!/usr/bin/env python3
"""Score retrieval against a local gold set — the measuring instrument.

Why this exists
---------------
Every change to extraction, ranking or retrieval is a guess until something
measures it. The public benchmarks will not do that job: an audit of LoCoMo
found 6.4% of its answer key wrong and its judge accepting 62.8% of
deliberately wrong answers, and re-scoring one vendor's own published answers
under four different judge prompts moved the score from 35% to 91%. Those
numbers measure harnesses, not memory.

So this measures the only thing that matters here: given a question about the
user's own history, does the system return the memory that answers it. The
gold set is in ``evals/recall_gold.yaml``, written from the capture trail, and
a case passes when any expected substring appears in a returned memory.

There is no LLM judge, deliberately. Substring matching is crude and cannot
reward a correct paraphrase — but it is deterministic, free, and it cannot be
tuned into looking good, which is exactly the failure mode the audits found.

Usage
-----
    python scripts/eval_recall.py                      # score, print a table
    python scripts/eval_recall.py --json out.json      # machine-readable
    python scripts/eval_recall.py --compare before.json  # show what moved
    python scripts/eval_recall.py --top-k 10 --mode vector

Needs a running API and credentials: ``LIFE_GRAPH_API_URL`` (default
http://localhost:8080), ``LIFE_GRAPH_TENANT_ID``, ``LIFE_GRAPH_API_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

GOLD = Path(__file__).resolve().parents[1] / "evals" / "recall_gold.yaml"


def _haystack(memory: dict[str, Any]) -> str:
    """Everything a reader would see — the fact and the line it came from."""
    return f"{memory.get('content', '')}\n{memory.get('reasoning') or ''}".lower()


def _rank_of_hit(memories: list[dict[str, Any]], expect: list[str]) -> int | None:
    """1-based rank of the first memory matching any expected substring."""
    wanted = [e.lower() for e in expect]
    for i, memory in enumerate(memories, start=1):
        hay = _haystack(memory)
        if any(w in hay for w in wanted):
            return i
    return None


def run_case(
    client: httpx.Client,
    case: dict[str, Any],
    top_k: int,
    mode: str,
    trail: bool = False,
) -> dict[str, Any]:
    body = {
        "query": case["question"],
        "limit": top_k,
        # Nothing is approved on a fresh instance, so without this the search
        # sees almost nothing and every case fails for the wrong reason.
        "include_pending": True,
        "search_mode": mode,
        "include_trail": trail,
    }
    response = client.post("/api/v1/search/", json=body)
    response.raise_for_status()
    data = response.json().get("data", {})
    memories = data.get("memories", [])

    result: dict[str, Any] = {
        "id": case["id"],
        "question": case["question"],
        "returned": len(memories),
        "ms": round(data.get("query_time_ms", 0)),
    }

    if case.get("expect_none"):
        # Abstention: the store holds no answer, so the honest response is to
        # say so. Memories now carry a relevance score — and measurement says
        # it cannot carry this assertion. "What is my favourite restaurant",
        # which the store knows nothing about, outscores a question it answers
        # correctly, and the same overlap holds for the margin over second
        # place and for two relative measures (evals/score-separability.md).
        #
        # So these stay reported rather than scored, and the top score is
        # recorded next to them. Scoring them against a floor would be
        # inventing a number the data refuses to support.
        result["kind"] = "abstain"
        result["passed"] = None
        result["top_score"] = (
            round(max((m.get("score") or 0.0) for m in memories), 4) if memories else 0.0
        )
        result["top"] = (memories[0].get("content", "")[:70]) if memories else ""
        return result

    rank = _rank_of_hit(memories, case["expect"])
    result["kind"] = "recall"
    result["rank"] = rank

    # A trail passage counts as an answer. It is the verbatim sentence the
    # facts were drawn from, which is what the reader wanted in the first
    # place — and measuring it separately is the only way to tell whether
    # searching the trail earns its keep.
    passages = data.get("trail", [])
    if trail:
        wanted = [e.lower() for e in case["expect"]]
        hit = next(
            (
                i
                for i, p in enumerate(passages, start=1)
                if any(w in p.get("excerpt", "").lower() for w in wanted)
            ),
            None,
        )
        result["trail_rank"] = hit
        result["trail_only"] = hit is not None and rank is None

    result["passed"] = rank is not None or bool(result.get("trail_rank"))
    result["top"] = (memories[0].get("content", "")[:70]) if memories else ""
    return result


def summarize(results: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    recall = [r for r in results if r["kind"] == "recall"]
    abstain = [r for r in results if r["kind"] == "abstain"]
    hits = [r for r in recall if r["passed"]]
    rescued = [r for r in recall if r.get("trail_only")]
    # Mean reciprocal rank over the recall cases; a miss contributes nothing.
    # A case answered only by the trail ranks by its passage: the reader got
    # an answer either way, and scoring it as a miss would hide the thing this
    # measurement exists to detect.
    ranks = [r["rank"] or r.get("trail_rank") for r in hits]
    mrr = sum(1 / rank for rank in ranks if rank) / len(recall) if recall else 0.0
    return {
        "cases": len(results),
        "recall_cases": len(recall),
        f"hit_at_{top_k}": len(hits),
        "hit_rate": round(len(hits) / len(recall), 3) if recall else 0.0,
        "mrr": round(mrr, 3),
        # Cases the extracted memories missed and the raw trail answered.
        "rescued_by_trail": len(rescued),
        "abstain_cases": len(abstain),
        # Not a score: see run_case and evals/score-separability.md.
        "abstention_measurable": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mode", default="hybrid", choices=["vector", "hybrid", "tri_hybrid"])
    parser.add_argument("--json", dest="json_out", help="write results to this file")
    parser.add_argument("--compare", help="an earlier --json file to diff against")
    parser.add_argument("--gold", default=str(GOLD))
    parser.add_argument(
        "--trail",
        action="store_true",
        help="also search the raw capture trail and count its passages as answers",
    )
    args = parser.parse_args()

    tenant = os.environ.get("LIFE_GRAPH_TENANT_ID")
    key = os.environ.get("LIFE_GRAPH_API_KEY")
    if not tenant or not key:
        print("set LIFE_GRAPH_TENANT_ID and LIFE_GRAPH_API_KEY", file=sys.stderr)
        return 2

    cases = yaml.safe_load(Path(args.gold).read_text(encoding="utf-8"))["cases"]
    client = httpx.Client(
        base_url=os.environ.get("LIFE_GRAPH_API_URL", "http://localhost:8080"),
        headers={"X-Tenant-ID": tenant, "Authorization": f"Bearer {key}"},
        timeout=60.0,
    )

    results = [run_case(client, case, args.top_k, args.mode, args.trail) for case in cases]

    print(f"\n{'':2} {'case':24} {'rank':>5}  top result")
    print("-" * 100)
    for r in results:
        mark = {True: "ok", False: "--", None: "? "}[r["passed"]]
        rank = r.get("rank") or ("-" if r["kind"] == "recall" else f"{r['returned']} rows")
        if r.get("trail_only"):
            rank = f"trail#{r['trail_rank']}"
        if r["kind"] == "abstain":
            rank = f"{r['top_score']:.3f}"
        print(f"{mark:2} {r['id']:24} {str(rank):>5}  {r['top']}")

    summary = summarize(results, args.top_k)
    print("\n" + json.dumps(summary, indent=2))

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8"
        )
        print(f"\nwrote {args.json_out}")

    if args.compare:
        before = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        prev = {r["id"]: r for r in before["results"]}
        moved = [
            (r["id"], prev[r["id"]].get("rank"), r.get("rank"))
            for r in results
            if r["id"] in prev and prev[r["id"]].get("rank") != r.get("rank")
        ]
        print(f"\nvs {args.compare}:")
        print(f"  hit_rate {before['summary']['hit_rate']} → {summary['hit_rate']}")
        print(f"  mrr      {before['summary']['mrr']} → {summary['mrr']}")
        for case_id, was, now in moved:
            print(f"  {case_id:24} {was} → {now}")
        if not moved:
            print("  no case changed rank")

    return 0


if __name__ == "__main__":
    sys.exit(main())
