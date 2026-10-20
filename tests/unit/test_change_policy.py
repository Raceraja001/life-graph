"""change_policy: what a landed change is, and whether it may land unattended."""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services import change_policy as cp
from tests.unit.fakes import FakeSession


@pytest.mark.parametrize(
    ("files", "kind"),
    [
        (["tests/unit/test_a.py"], "tests"),
        (["tests/unit/test_a.py", "docs/notes.md"], "tests"),
        (["docs/design/10.md", "README.md"], "docs"),
        (["life_graph/services/money.py", "tests/unit/test_money.py"], "code"),
        (["life_graph/services/money.py"], "code"),
        ([], "code"),
    ],
)
def test_classify(files, kind):
    assert cp.classify(files) == kind


def test_protected_hits_defaults_and_project_globs():
    files = [
        ".github/workflows/ci.yml",
        "alembic/versions/050_x.py",
        "uv.lock",
        "AGENTS.md",
        ".env",
        "life_graph/drivers/local.py",
        "life_graph/services/money.py",
    ]
    assert cp.protected_hits(files) == files[:5]
    assert cp.protected_hits(files, ["life_graph/drivers/*"]) == files[:6]


def test_review_reasons():
    policy = cp.policy_from_project({"auto_merge_max_lines": 100, "auto_merge_max_files": 2})
    small = {"files": ["tests/unit/test_a.py"], "lines": 40, "protected": []}
    assert cp.review_reasons(small, policy) == []
    big = {"files": ["a.py", "b.py", "c.py"], "lines": 101, "protected": ["uv.lock"]}
    reasons = cp.review_reasons(big, policy)
    assert len(reasons) == 3
    assert "uv.lock" in reasons[0] and "101 changed lines" in reasons[1] and "3 files" in reasons[2]


def test_policy_defaults():
    assert cp.policy_from_project(None) == {
        "protected_paths": [],
        "max_lines": cp.AUTO_MAX_LINES,
        "max_files": cp.AUTO_MAX_FILES,
    }


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _rev(repo, ref="HEAD"):
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", ref], capture_output=True, text=True)
    return out.stdout.strip()


async def test_describe_change_reads_the_landed_diff(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "app.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    base = _rev(repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_app.py").write_text("def test_x():\n    assert 1\n")
    (repo / "uv.lock").write_text("lock\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")

    change = await cp.describe_change(str(repo), base, _rev(repo))
    assert sorted(change["files"]) == ["tests/test_app.py", "uv.lock"]
    assert change["lines"] == 3
    assert change["kind"] == "code"  # uv.lock is not a test
    assert change["protected"] == ["uv.lock"]
    assert any("uv.lock" in r for r in change["review_reasons"])


async def test_describe_change_fails_closed_without_a_readable_diff(tmp_path):
    change = await cp.describe_change(str(tmp_path), "not-a-sha", None)
    assert change["kind"] == "code"
    assert "the landed diff could not be read" in change["review_reasons"]


def _records(monkeypatch, by_agent):
    from life_graph.services import dev_outcomes

    async def track_record(_session, _tenant, agent, _project):
        merged, failed = by_agent.get(agent, (0, 0))
        total = merged + failed
        return {
            "merged": merged,
            "failed": failed,
            "total": total,
            "merge_rate": merged / total if total else None,
            "established": total >= 3,
        }

    monkeypatch.setattr(dev_outcomes, "track_record", track_record)


async def test_tests_fall_back_to_the_drivers_record_but_code_never_does(monkeypatch):
    _records(monkeypatch, {"local": (10, 0)})
    tests = await cp.kind_record(FakeSession(), "raja", "local", "tests", "p")
    code = await cp.kind_record(FakeSession(), "raja", "local", "code", "p")
    assert tests["established"] and tests["fallback"] and tests["merged"] == 10
    assert not code["established"] and code["total"] == 0


async def test_code_needs_its_own_larger_record(monkeypatch):
    _records(monkeypatch, {"local:code": (4, 0)})
    assert not (await cp.kind_record(FakeSession(), "raja", "local", "code", "p"))["established"]
    _records(monkeypatch, {"local:code": (5, 0)})
    assert (await cp.kind_record(FakeSession(), "raja", "local", "code", "p"))["established"]


def _payload(kind="tests", reasons=(), checks=()):
    return {
        "driver": "local",
        "project_id": "p",
        "checks": list(checks),
        "change": {"files": ["x"], "lines": 1, "kind": kind, "review_reasons": list(reasons)},
    }


PROOF = ["build_ok_diff", *cp.CODE_PROOF_CHECKS]


async def test_auto_gate(monkeypatch):
    _records(monkeypatch, {"local": (8, 1), "local:code": (2, 0)})
    ok, why, _ = await cp.auto_gate(FakeSession(), "raja", _payload("tests"))
    assert ok and "8/9 tests PRs merged" in why

    ok, why, _ = await cp.auto_gate(FakeSession(), "raja", _payload("code", checks=PROOF))
    assert not ok and why.startswith("not yet trusted for code changes")

    _records(monkeypatch, {"local:code": (6, 0)})
    ok, why, _ = await cp.auto_gate(FakeSession(), "raja", _payload("code", checks=PROOF))
    assert ok and "6/6 code PRs merged" in why


async def test_code_without_proof_checks_never_lands_unattended(monkeypatch):
    _records(monkeypatch, {"local:code": (9, 0)})
    ok, why, _ = await cp.auto_gate(
        FakeSession(), "raja", _payload("code", checks=["build_ok_diff", "diff_coverage"])
    )
    assert (
        not ok and why == "needs review: no proof checks ran for this code change: change_explained"
    )

    ok, why, _ = await cp.auto_gate(FakeSession(), "raja", _payload("tests", ["touches uv.lock"]))
    assert not ok and why == "needs review: touches uv.lock"


async def test_auto_gate_describes_an_old_payload_from_git(monkeypatch):
    _records(monkeypatch, {"local": (8, 0)})
    seen = {}

    async def describe(repo, base, head, policy=None):
        seen["args"] = (repo, base, head)
        return {"files": ["a.py"], "lines": 3, "kind": "code", "review_reasons": []}

    monkeypatch.setattr(cp, "describe_change", describe)
    ok, why, _ = await cp.auto_gate(
        FakeSession(),
        "raja",
        {"driver": "local", "repo_path": "/r", "base_commit": "b", "head_commit": "h"},
    )
    assert seen["args"] == ("/r", "b", "h")
    assert not ok and "code" in why


def _llm(monkeypatch, reply=None, error=None):
    from life_graph.api import dependencies

    seen = {}

    class LLM:
        async def chat(self, messages, **kw):
            seen.update(kw, prompt=messages[0]["content"])
            if error:
                raise error
            return reply

    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: LLM())
    return seen


@pytest.mark.parametrize(
    ("reply", "ok", "note"),
    [
        (
            '{"verdict": "ok", "reason": "matches the task"}',
            True,
            "second opinion: ok (matches the task)",
        ),
        (
            'Sure: {"verdict": "block", "reason": "drops the tenant filter"}',
            False,
            "second opinion: drops the tenant filter",
        ),
        ("looks fine to me", False, "second-opinion review gave no readable verdict"),
    ],
)
async def test_second_opinion_verdicts(monkeypatch, reply, ok, note):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "change_review_model", "openrouter/x:free")
    seen = _llm(monkeypatch, reply)
    assert await cp.second_opinion("Fix the bug", "diff --git a/x b/x") == (ok, note)
    assert seen["model"] == "openrouter/x:free" and seen["temperature"] == 0
    assert "Fix the bug" in seen["prompt"] and "diff --git a/x b/x" in seen["prompt"]


async def test_second_opinion_fails_closed(monkeypatch):
    _llm(monkeypatch, error=RuntimeError("all models exhausted"))
    ok, note = await cp.second_opinion("t", "d")
    assert not ok and note == "second-opinion review unavailable (RuntimeError)"
