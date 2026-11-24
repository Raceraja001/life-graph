"""The memory services live in life_graph/services/memory/.

They were flat modules (life_graph/services/memory_retrieval.py, recall.py,
...) until 2026-11-17, then old-name aliases until 2026-11-24, when the
aliases were deleted (audit L1). These tests keep the old names from coming
back.
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
def test_the_old_name_is_gone(old):
    # The aliases were deleted on 2026-11-24 (audit L1). Re-adding one would
    # reopen the "edit the ten-line alias instead of the code" trap.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"life_graph.services.{old}")


def test_nothing_in_the_repo_imports_the_old_names():
    old_dotted = tuple(f"life_graph.services.{old}" for old in MOVES)
    offenders = []
    for base in ("life_graph", "tests", "scripts"):
        for p in (ROOT / base).rglob("*.py"):
            if p == Path(__file__).resolve():
                continue  # names the old modules on purpose
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
