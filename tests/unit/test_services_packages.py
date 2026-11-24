"""The jarvis, llm, finance and notifications services live in packages.

They were flat modules in life_graph/services/ until 2026-11-18 (the memory
and dev groups have their own tests), then old-name aliases until
2026-11-24, when the aliases were deleted (audit L1). These tests keep the
old names from coming back.
"""

import importlib
from pathlib import Path

import pytest

MOVES = {
    "jarvis": {
        "jarvis_cards": "cards",
        "jarvis_inbox": "inbox",
        "jarvis_memory": "memory",
        "jarvis_plan": "plan",
        "jarvis_today": "today",
    },
    "llm": {
        "llm_client": "client",
        "llm_health": "health",
        "llm_offers": "offers",
        "resilient_llm": "resilient",
        "model_catalog": "model_catalog",
        "model_eval": "model_eval",
        "local_runtime": "local_runtime",
        "local_model_registry": "local_model_registry",
        "claude_cli_reply": "claude_cli_reply",
        "compute_router": "compute_router",
    },
    "finance": {
        "money": "money",
        "money_checkin": "checkin",
        "invoices": "invoices",
    },
    "notifications": {
        "approval_notifications": "approval",
        "due_notifications": "due",
        "notification_actions": "actions",
        "push_delivery": "push_delivery",
        "telegram_delivery": "telegram_delivery",
        "webpush": "webpush",
        "telegram_binding": "telegram_binding",
    },
}
OLD_TO_NEW = {old: f"{pkg}.{new}" for pkg, m in MOVES.items() for old, new in m.items()}

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("old", sorted(OLD_TO_NEW))
def test_the_old_name_is_gone(old):
    # The aliases were deleted on 2026-11-24 (audit L1). Re-adding one would
    # reopen the "edit the ten-line alias instead of the code" trap.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"life_graph.services.{old}")


def test_model_eval_still_finds_the_bench_script():
    # model_eval locates the repo root from its own path, one level deeper now.
    from life_graph.services.llm import model_eval

    assert model_eval.BENCH_SCRIPT == ROOT / "scripts" / "bench_drivers.py"
    assert model_eval.BENCH_SCRIPT.is_file()


def test_nothing_in_the_repo_imports_the_old_names():
    old_dotted = tuple(f"life_graph.services.{old}" for old in OLD_TO_NEW)
    offenders = []
    for base in ("life_graph", "tests", "scripts"):
        for p in (ROOT / base).rglob("*.py"):
            if p == Path(__file__).resolve():
                continue  # names the old modules on purpose
            text = p.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.strip().startswith("from life_graph.services import "):
                    names = line.split(" import ", 1)[1].replace("(", "").split(",")
                    if any(n.split(" as ")[0].strip() in OLD_TO_NEW for n in names):
                        offenders.append(f"{p.relative_to(ROOT).as_posix()}: {line.strip()}")
            for name in old_dotted:
                i = text.find(name)
                while i != -1:
                    end = i + len(name)
                    if end == len(text) or not (text[end].isalnum() or text[end] == "_"):
                        offenders.append(f"{p.relative_to(ROOT).as_posix()}: {name}")
                        break
                    i = text.find(name, end)
    assert offenders == [], f"import the package path instead: {offenders}"
