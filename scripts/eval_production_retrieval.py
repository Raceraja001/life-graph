#!/usr/bin/env python3
"""Run the memory lab's questions through the production retrieval path (M3).

Needs Postgres with pgvector. It writes the lab's synthetic messages as a
throwaway tenant (``m3eval_<hex>``), asks every question through
``hybrid_search`` and ``retrieve()`` with a deterministic fake embedder and the
judge disabled, writes `evals/production_retrieval_report.json`, and deletes
the tenant's rows again, also on failure.

By default it uses the integration test database, the same one the
integration suite uses: the configured database name with `_test` appended
(tests/conftest.py). Load the DB env first, as for the integration tests:

    set -a; . <(grep -E '^LIFE_GRAPH_(DATABASE_URL|DATABASE_URL_SYNC|REDIS_URL)=' .env); set +a
    python scripts/eval_production_retrieval.py

A second, manual run checks real vectors: ``--ollama-model bge-m3`` embeds
every message and question once with a local Ollama (production's model) and
writes evals/production_retrieval_report_bge_m3.json. The hashing run is the
yardstick; the bge-m3 run shows what a change does next to semantic vectors.

The integration suite keeps a floor on the hashing run's tuning split
(tests/integration/test_production_retrieval_arm.py).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "evals" / "production_retrieval_report.json"
OLLAMA_OUTPUT = ROOT / "evals" / "production_retrieval_report_{model}.json"


def _with_suffix(url: str, suffix: str) -> str:
    """*url* with *suffix* appended to its database name (as tests/conftest.py does)."""
    head, sep, tail = url.rpartition("/")
    if not sep or not tail:
        return url
    name, qmark, query = tail.partition("?")
    if not name or name.endswith(suffix):
        return url
    return f"{head}/{name}{suffix}{qmark}{query}"


def _point_at_test_database(suffix: str) -> None:
    """Move both URLs before anything imports storage.database and freezes them."""
    from life_graph.config import settings

    if suffix:
        settings.database_url = _with_suffix(settings.database_url, suffix)
        settings.database_url_sync = _with_suffix(settings.database_url_sync, suffix)


def _print(report: dict) -> None:
    print(f"{report['embedder']}\njudge: {report['judge']}\n")
    header = (
        f"{'split':<11} {'arm':<24} {'R@1':>6} {'R@5':>6} {'P@1':>6} {'P@5':>6} "
        f"{'MRR':>6} {'nDCG@5':>7} {'Sup@5':>6} {'p50ms':>7}"
    )
    print(header)
    print("-" * len(header))
    for split_name, split in report["splits"].items():
        for arm, rep in split["arms"].items():
            ov = rep["overall"]
            print(
                f"{split_name:<11} {arm:<24} {ov['recall_at_1']:>6.4f} {ov['recall_at_5']:>6.4f} "
                f"{ov['precision_at_1']:>6.4f} {ov['precision_at_5']:>6.4f} {ov['mrr']:>6.4f} "
                f"{ov['ndcg_at_5']:>7.4f} {ov['full_support_at_5']:>6.4f} "
                f"{rep['latency_ms']['p50']:>7.2f}"
            )
        ab = split["arms"].get("retrieve_judge_disabled", {}).get("abstention_indicator")
        if ab:
            print(
                f"{'':<11} retrieve abstention indicator: flagged {ab['flagged']}, "
                f"P={ab['precision']:.4f} R={ab['recall']:.4f} "
                f"({ab['abstain_questions']} unanswerable questions)"
            )
        print(f"{'':<11} memories left after cleanup: {split['memories_left_after_cleanup']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--ollama-model",
        default="",
        help="Embed with this local Ollama model (e.g. bge-m3) instead of the hashing stand-in",
    )
    parser.add_argument("--ollama-url", default="", help="Default: settings.ollama_api_base")
    parser.add_argument(
        "--db-suffix",
        default=os.environ.get("LIFE_GRAPH_TEST_DATABASE_SUFFIX", "_test"),
        help='Suffix for the database name (default "_test"; "" uses the configured DB)',
    )
    parser.add_argument("--max-questions", type=int, default=None, help="First N per split")
    args = parser.parse_args()

    _point_at_test_database(args.db_suffix)
    # The disabled judge is the point of the run, not news: one warning per question.
    logging.getLogger("life_graph.services.memory.retrieval").setLevel(logging.ERROR)
    from life_graph.evals import production_retrieval_arm as arm

    output = args.output or DEFAULT_OUTPUT
    ctx: contextlib.AbstractContextManager = contextlib.nullcontext()
    if args.ollama_model:
        from life_graph.config import settings
        from life_graph.evals import memory_benchmark as lab

        texts: list[str] = []
        for path in (lab.TUNING_DATASET, lab.HELDOUT_DATASET):
            data = json.loads(path.read_text(encoding="utf-8"))
            texts += [m["text"] for m in data["messages"]] + [q["q"] for q in data["questions"]]
        url = args.ollama_url or settings.ollama_api_base
        embed = arm.ollama_embedder(texts, model=args.ollama_model, base_url=url)
        ctx = arm.using_embedder(embed, f"ollama {args.ollama_model} (local model, manual run)")
        slug = re.sub(r"[^a-z0-9]+", "_", args.ollama_model.lower()).strip("_")
        output = args.output or OLLAMA_OUTPUT.with_name(OLLAMA_OUTPUT.name.format(model=slug))
    with ctx:
        report = asyncio.run(arm.run_production_arm(max_questions=args.max_questions))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _print(report)
    left = sum(s["memories_left_after_cleanup"] for s in report["splits"].values())
    if left:
        print(f"FAIL: {left} memories of the throwaway tenants were left behind", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
