"""Nightly suggestion collectors: TODOs, lint and failing tests → findings."""

from __future__ import annotations

import json
import subprocess

import pytest

from life_graph.services import dev_suggestions as ds
from life_graph.services import sandbox


def test_todo_findings_key_survives_line_moves_and_skips_junk(tmp_path):
    (tmp_path / "pkg").mkdir()
    src = tmp_path / "pkg" / "mod.py"
    src.write_text("x = 1\n# TODO: handle the empty list case\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("// vendored noise here\n")
    outside = tmp_path.parent / "outside_todo"
    outside.mkdir(exist_ok=True)
    (outside / "leak.py").write_text("# This should never be scanned\n")
    (tmp_path / "link").symlink_to(outside)

    (first,) = ds.todo_findings(tmp_path)
    assert first.kind == "todo"
    assert "pkg/mod.py" in first.instruction and "around line 2" in first.instruction

    src.write_text("\n\n\nx = 1\n# TODO: handle the empty list case\n")
    (moved,) = ds.todo_findings(tmp_path)
    assert moved.key == first.key  # same finding, different line


async def test_lint_findings_group_by_file(tmp_path, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    issues = [
        {
            "filename": "/work/a.py",
            "code": "F401",
            "message": "unused import",
            "location": {"row": 1},
        },
        {"filename": "/work/a.py", "code": "E501", "message": "too long", "location": {"row": 9}},
        {"filename": "/work/b.py", "code": "F841", "message": "unused var", "location": {"row": 3}},
    ]

    async def fake_run(argv, workdir, **kw):
        assert "--output-format" in argv
        return sandbox.SandboxResult(1, json.dumps(issues), "")

    monkeypatch.setattr(sandbox, "run", fake_run)
    found = await ds.lint_findings(tmp_path)
    assert [f.title for f in found] == ["Fix ruff E501, F401 in a.py", "Fix ruff F841 in b.py"]
    assert "line 9: E501 too long" in found[0].instruction


async def test_lint_findings_need_the_sandbox(tmp_path, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "none")
    assert await ds.lint_findings(tmp_path) == []  # never run on the host


@pytest.mark.parametrize(
    "returncode, stdout, expected",
    [
        (1, "FAILED tests/test_a.py::test_x - assert\nFAILED tests/test_b.py::test_y\n", 1),
        (0, "5 passed", 0),
        (2, "collection error, no FAILED lines", 0),
    ],
)
async def test_test_findings(tmp_path, monkeypatch, returncode, stdout, expected):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "docker")

    async def fake_prepare(root, setup=None):
        return tmp_path / "venv"

    async def fake_run(argv, workdir, **kw):
        return sandbox.SandboxResult(returncode, stdout, "")

    monkeypatch.setattr(sandbox, "prepare_env", fake_prepare)
    monkeypatch.setattr(sandbox, "run", fake_run)
    found = await ds.test_findings(tmp_path, {"sandbox_test_command": "pytest -q"})
    assert len(found) == expected
    if expected:
        assert "tests/test_a.py::test_x" in found[0].instruction
        assert "Do not skip" in found[0].instruction


async def test_no_test_command_means_no_test_run(tmp_path, monkeypatch):
    async def must_not_run(*a, **k):
        raise AssertionError("tests must not run without a configured command")

    monkeypatch.setattr(sandbox, "run", must_not_run)
    assert await ds.test_findings(tmp_path, {}) == []


async def test_collect_scans_head_not_uncommitted_edits(tmp_path, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "none")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    (repo / "a.py").write_text("# TODO: committed work item\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    (repo / "b.py").write_text("# TODO: uncommitted scratch note\n")  # not in HEAD

    found = await ds.collect_findings(str(repo), {})
    assert [f.title for f in found] == ["Resolve TODO in a.py: committed work item"]
    worktrees = subprocess.run(
        ["git", "worktree", "list"], cwd=repo, capture_output=True, text=True
    )
    assert len(worktrees.stdout.strip().splitlines()) == 1  # scan worktree cleaned up


async def test_lint_scan_is_scoped_and_skips_migrations(tmp_path, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    seen = {}

    async def fake_run(argv, workdir, **kw):
        seen["argv"] = argv
        return sandbox.SandboxResult(0, "[]", "")

    monkeypatch.setattr(sandbox, "run", fake_run)
    await ds.lint_findings(tmp_path, ["life_graph", "--fix"])  # option-like path dropped
    argv = seen["argv"]
    excluded = argv[argv.index("--extend-exclude") + 1].split(",")
    assert "alembic" in excluded and "migrations" in excluded
    assert argv[argv.index("--") + 1 :] == ["life_graph"]
