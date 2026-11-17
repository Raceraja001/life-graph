"""The memory services live in life_graph/services/memory/; the old names alias them.

They were flat modules (life_graph/services/memory_retrieval.py, recall.py,
...) until 2026-11-17. Each old name is kept as an alias for code on other
branches. It has to be the same module object, not a re-export: with two
objects, a test's ``monkeypatch.setattr(old_module, ...)`` would miss every
caller that imports the new path.
"""

import importlib
from pathlib import Path

import pytest

MOVES = {
    "memory_check": "check",
    "memory_context": "context",
    "memory_links": "links",
    "memory_page": "page",
    "memory_retrieval": "retrieval",
    "memory_sources": "sources",
    "memory_tiers": "tiers",
    "memory_yield": "capture_yield",
    "metamemory": "metamemory",
    "micro_consolidation": "micro_consolidation",
    "associations": "associations",
    "recall": "recall",
}

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("old", sorted(MOVES))
def test_the_old_name_is_the_same_module(old):
    moved = importlib.import_module(f"life_graph.services.memory.{MOVES[old]}")
    assert importlib.import_module(f"life_graph.services.{old}") is moved


def test_a_patch_through_the_old_name_reaches_new_path_callers(monkeypatch):
    import life_graph.services.memory.recall as new
    import life_graph.services.recall as old

    sentinel = object()
    monkeypatch.setattr(old, "_COOLDOWN_SECONDS", sentinel)
    assert new._COOLDOWN_SECONDS is sentinel


def test_nothing_in_the_repo_imports_the_old_names():
    old_dotted = tuple(f"life_graph.services.{old}" for old in MOVES)
    offenders = []
    for base in ("life_graph", "tests", "scripts"):
        for p in (ROOT / base).rglob("*.py"):
            if p.parent == ROOT / "life_graph" / "services" and p.stem in MOVES:
                continue  # the aliases themselves
            if p == Path(__file__).resolve():
                continue  # imports an old name on purpose, to test the alias
            text = p.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.strip().startswith("from life_graph.services import "):
                    names = line.split(" import ", 1)[1].replace("(", "").split(",")
                    if any(n.split(" as ")[0].strip() in MOVES for n in names):
                        offenders.append(f"{p.relative_to(ROOT).as_posix()}: {line.strip()}")
            for name in old_dotted:
                i = text.find(name)
                while i != -1:
                    end = i + len(name)
                    if end == len(text) or not (text[end].isalnum() or text[end] == "_"):
                        offenders.append(f"{p.relative_to(ROOT).as_posix()}: {name}")
                        break
                    i = text.find(name, end)
    assert offenders == [], f"import life_graph.services.memory.<module> instead: {offenders}"
