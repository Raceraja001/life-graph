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


def _body(n: int) -> str:
    """A function body of n lines."""
    return "".join(f"    x{i} = {i}\n" for i in range(n - 2)) + "    return x0\n"


def _logic(n, branches):
    """A function body of n lines with `branches` if-statements."""
    ifs = "".join(f"    if x == {i}:\n        return {i}\n" for i in range(branches))
    pad = max(n - 2 - 2 * branches, 0)
    return ifs + "".join(f"    y{i} = {i}\n" for i in range(pad)) + "    return None\n"


def _untested_project(tmp_path, *, fakes=True):
    pkg = tmp_path / "app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "svc.py").write_text(
        "import functools\n\n\n"
        f"def tested_fn():\n{_logic(6, 2)}\n\n"
        f"async def query_rows(session, tenant_id):\n{_logic(7, 2)}\n\n"
        f"def plain_helper(x):\n{_logic(10, 3)}\n\n"
        f"def thin_wrapper(text):\n{_body(8)}\n\n"
        f"def too_short():\n{_logic(3, 1)}\n\n"
        f"def too_long():\n{_logic(45, 3)}\n\n"
        f"def _private():\n{_logic(8, 2)}\n\n"
        f"@functools.cache\ndef decorated():\n{_logic(8, 2)}\n"
    )
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_svc.py").write_text(
        "from app.svc import tested_fn\n\ndef test_it():\n    assert tested_fn() == 0\n"
    )
    if fakes:
        (tmp_path / "tests" / "unit" / "fakes.py").write_text("class FakeSession: ...\n")
    return tmp_path


def test_untested_findings_are_short_public_undecorated_functions(tmp_path):
    root = _untested_project(tmp_path)
    found = ds.untested_findings(root)
    # Most logic first; tested, logic-free, too short/long, private and
    # decorated are skipped.
    assert [f.title for f in found] == [
        "Add tests for plain_helper in app/svc.py",
        "Add tests for query_rows in app/svc.py",
    ]
    helper, rows = found
    assert "3 decision points" in helper.instruction
    assert rows.kind == "untested" and "tests/unit/test_svc_query_rows.py" in rows.instruction
    assert "tests/unit/fakes.py" in rows.instruction  # takes a session
    assert "fakes.py" not in helper.instruction
    assert rows.key == ds.untested_findings(root)[1].key  # stable across scans


def test_untested_findings_without_the_fakes_or_any_tests(tmp_path):
    root = _untested_project(tmp_path, fakes=False)
    assert all("fakes.py" not in f.instruction for f in ds.untested_findings(root))
    bare = tmp_path / "bare"
    (bare / "app").mkdir(parents=True)
    (bare / "app" / "m.py").write_text(f"def f():\n{_logic(8, 2)}\n")
    assert ds.untested_findings(bare) == []  # no test suite to add to


def test_untested_findings_respect_paths(tmp_path):
    root = _untested_project(tmp_path)
    (root / "other").mkdir()
    (root / "other" / "x.py").write_text(f"def elsewhere(x):\n{_logic(8, 2)}\n")
    assert all(f.title.endswith("app/svc.py") for f in ds.untested_findings(root, ["app"]))
    assert any("elsewhere" in f.title for f in ds.untested_findings(root))


def _shape_of(source):
    import ast

    return ds._logic_shape(ast.parse(source).body[0])


def test_logic_shape_counts_decisions_and_spots_what_to_test():
    shape = _shape_of(
        "async def f(session, tenant, rows):\n"
        "    if not rows or tenant is None:\n"
        "        raise ValueError('no rows')\n"
        "    for r in rows:\n"
        "        try:\n"
        "            r.x = 1\n"
        "        except KeyError:\n"
        "            continue\n"
        "    q = [r for r in rows if r.tenant_id == tenant]\n"
        "    return {'n': len(q)}\n"
    )
    # if, or, raise, for, except, comprehension-if
    assert shape == {"score": 6, "raises": True, "tenant": True, "returns_dict": True}
    assert _shape_of("def g(x):\n    return h(x)\n")["score"] == 0


def test_untested_hints_follow_the_shape():
    shape = {"score": 4, "raises": True, "tenant": True, "returns_dict": True}
    hints = ds._untested_hints(shape)
    assert "4 decision points" in hints
    assert "pytest.raises" in hints
    assert "filters by the tenant" in hints
    assert "left out" in hints
    assert "never constants or strings copied" in hints
    plain = ds._untested_hints(
        {"score": 2, "raises": False, "tenant": False, "returns_dict": False}
    )
    assert "pytest.raises" not in plain and "tenant" not in plain and "left out" not in plain


def test_wrappers_and_dict_builders_without_logic_are_not_picked(tmp_path):
    root = _untested_project(tmp_path)
    (root / "app" / "views.py").write_text(
        "def to_dict(card):\n"
        "    return {\n"
        "        'id': str(card.id),\n"
        "        'front': card.front,\n"
        "        'back': card.back,\n"
        "        'due': card.due_on.isoformat(),\n"
        "    }\n"
    )
    titles = [f.title for f in ds.untested_findings(root)]
    assert not any("to_dict" in t or "thin_wrapper" in t for t in titles)
