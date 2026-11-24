"""The dev-agent services live in life_graph/services/dev/.

They were flat modules (life_graph/services/dev_tasks.py, verifiers.py, ...)
until 2026-11-17, then old-name aliases until 2026-11-24, when the aliases
were deleted (audit L1). These tests keep the old names from coming back.
"""

import importlib
from pathlib import Path

import pytest

MOVES = {
    "acceptance": "acceptance",
    "change_policy": "change_policy",
    "code_graph": "code_graph",
    "conformance": "conformance",
    "dev_outcomes": "outcomes",
    "dev_suggestions": "suggestions",
    "dev_tasks": "tasks",
    "failure_causes": "failure_causes",
    "github_pr": "github_pr",
    "local_merge": "local_merge",
    "plan_policy": "plan_policy",
    "pr_agent_review": "pr_agent_review",
    "pr_description": "pr_description",
    "production_findings": "production_findings",
    "project_learning": "project_learning",
    "proof_checks": "proof_checks",
    "second_opinion": "second_opinion",
    "trajectories": "trajectories",
    "verifiers": "verifiers",
    "sandbox": "sandbox",
}

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("old", sorted(MOVES))
def test_the_old_name_is_gone(old):
    # The aliases were deleted on 2026-11-24 (audit L1). Re-adding one would
    # reopen the "edit the ten-line alias instead of the code" trap.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"life_graph.services.{old}")


def test_the_sandbox_still_finds_its_compose_file():
    # sandbox.py locates the repo root from its own path, one level deeper now.
    from life_graph.services.dev import sandbox

    src = (ROOT / "life_graph" / "services" / "dev" / "sandbox.py").read_text(encoding="utf-8")
    assert "parents[3] / SANDBOX_COMPOSE_FILE" in src
    assert (ROOT / sandbox.SANDBOX_COMPOSE_FILE).is_file()


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
    for sh in (ROOT / "scripts").rglob("*.sh"):
        text = sh.read_text(encoding="utf-8")
        offenders += [
            f"{sh.relative_to(ROOT).as_posix()}: {n}" for n in old_dotted if f"{n} " in text
        ]
    assert offenders == [], f"import life_graph.services.dev.<module> instead: {offenders}"
