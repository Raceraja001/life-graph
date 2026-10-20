"""Evaluate a free cloud model before anyone relies on it (Job 1, AC-3.x/4.1).

Two steps, cheapest first:

1. **Smoke test** — one completion asking for one tool call. A model that
   cannot call a tool correctly cannot drive an agent; it fails here and costs
   nothing more.
2. **Coding benchmark** — the same hidden-tested tasks every engine is judged
   on (``evals/driver_tasks.yaml`` via ``scripts/bench_drivers.py``), on the
   cloud engine. Run with the failover chain narrowed to this one model, so a
   rate-limited model is not scored on another model's answers.

Cloud only: an evaluation never touches the GPU.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
BENCH_SCRIPT = ROOT / "scripts" / "bench_drivers.py"

# Adoption bar (AC-4.1).
ADOPT_MIN_PASSED = 5  # of the 6 tasks
ADOPT_MAX_AVG_S = 300
ADOPT_LIST_TARGET = 4  # below this many models, any model over the bar is proposed

_ADD_TOOL = {
    "type": "function",
    "function": {
        "name": "add",
        "description": "Add two numbers.",
        "parameters": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
}


UNREACHABLE_TRIES = 3


async def smoke_test(model_id: str) -> tuple[bool | None, str]:
    """One tool call: does the model call ``add(2, 3)`` when asked?

    ``None`` means the model could not be reached (rate-limited, down): that
    says nothing about the model, so the caller tries again later instead of
    failing it (gemma-4-31b was 429 on its first live evaluation, 2026-10-20).
    """
    from life_graph.api.dependencies import get_resilient_llm
    from life_graph.services.resilient_llm import only_models

    try:
        with only_models([model_id]):
            resp = await get_resilient_llm().acompletion(
                messages=[{"role": "user", "content": "Call the add tool with 2 and 3."}],
                model=model_id,
                tools=[_ADD_TOOL],
                max_tokens=200,
                temperature=0,
            )
    except Exception as exc:  # noqa: BLE001 - unreachable is a result, not a crash
        return None, f"no answer: {type(exc).__name__}"
    calls = getattr(resp.choices[0].message, "tool_calls", None) or []
    for call in calls:
        fn = getattr(call, "function", None)
        if getattr(fn, "name", None) != "add":
            continue
        try:
            args = json.loads(fn.arguments or "{}")
        except ValueError:
            return False, "add was called with arguments that are not JSON"
        if float(args.get("a", 0)) == 2 and float(args.get("b", 0)) == 3:
            return True, "add(2, 3) called"
        return False, f"add called with {args}"
    return False, "no tool call"


def _bench_module():
    spec = importlib.util.spec_from_file_location("bench_drivers", BENCH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def run_benchmark(model_id: str, *, timeout: int = 900) -> dict[str, Any]:
    """The coding benchmark for one free cloud model; a summary of its rows."""
    import yaml

    from life_graph.services.resilient_llm import only_models

    bench = _bench_module()
    spec = yaml.safe_load(bench.TASKS.read_text())
    import life_graph.tools.code  # noqa: F401  registers the code_* tools

    rows = []
    started = time.monotonic()
    with only_models([model_id]):
        for task in spec["tasks"]:
            row = await bench.run_one(
                f"cloud:{model_id}", task, spec["fixtures"][task["fixture"]], timeout
            )
            rows.append(row)
    return summarise(rows, seconds=round(time.monotonic() - started))


def summarise(rows: list[dict], seconds: float | None = None) -> dict[str, Any]:
    """passed/total, honest/total, average seconds and edits, plus slim rows."""
    total = len(rows)
    return {
        "passed": sum(bool(r.get("passed")) for r in rows),
        "total": total,
        "honest": sum(r.get("passed") == r.get("driver_success") for r in rows),
        "avg_s": round(sum(r.get("seconds") or 0 for r in rows) / total, 1) if total else None,
        "edits_ok": sum(r.get("edits_ok") or 0 for r in rows),
        "edits_failed": sum(r.get("edits_failed") or 0 for r in rows),
        "seconds": seconds,
        "rows": [
            {k: r.get(k) for k in ("task", "passed", "driver_success", "stop_reason", "seconds")}
            for r in rows
        ],
    }


def score(evaluation: dict[str, Any]) -> tuple:
    """Order models: more passed, then more honest, then faster."""
    return (
        evaluation.get("passed") or 0,
        evaluation.get("honest") or 0,
        -(evaluation.get("avg_s") or 10_000),
    )


def meets_bar(evaluation: dict[str, Any]) -> bool:
    """Passed the adoption bar (AC-4.1): ≥ 5/6 and ≤ 300 s on average."""
    return (evaluation.get("passed") or 0) >= ADOPT_MIN_PASSED and (
        evaluation.get("avg_s") or 10_000
    ) <= ADOPT_MAX_AVG_S


def worth_proposing(
    evaluation: dict[str, Any], list_size: int, adopted_evals: list[dict[str, Any]]
) -> bool:
    """Over the bar AND either the list is short or it beats the weakest adopted model."""
    if not meets_bar(evaluation):
        return False
    if list_size < ADOPT_LIST_TARGET or not adopted_evals:
        return True
    return score(evaluation) > min(score(e) for e in adopted_evals)
