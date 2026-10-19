"""The Node toolchain's safety rules, without docker: which JS test references
are accepted, and what the sandbox actually runs for a Node check.
"""

from __future__ import annotations

import pytest

from life_graph.services.acceptance import is_js_test_ref, is_safe_test_ref


@pytest.mark.parametrize(
    "ref",
    [
        "tests/todos.test.mjs::adds a todo",
        "src/components/Button.spec.tsx",
        "tests/api.test.ts::returns 404 for an unknown id",
        "tests/unit/test_x.py::test_a",  # pytest refs still work
    ],
)
def test_plain_test_refs_are_safe(ref):
    assert is_safe_test_ref(ref)


@pytest.mark.parametrize(
    "ref",
    [
        "tests/x.test.ts::a; rm -rf /",
        "tests/x.test.ts::$(id)",
        "../outside.test.ts",
        "-t.test.js",
        "tests/notatest.ts::name",  # not a *.test.* / *.spec.* file
        "/abs/x.test.ts",
    ],
)
def test_option_shell_and_path_tricks_are_refused(ref):
    assert not is_safe_test_ref(ref)


def test_js_refs_are_told_apart_from_pytest_refs():
    assert is_js_test_ref("tests/a.test.mjs::x")
    assert not is_js_test_ref("tests/unit/test_a.py::test_x")


@pytest.mark.asyncio
async def test_a_node_check_runs_in_a_tmp_copy_with_deps_at_root(tmp_path, monkeypatch):
    from life_graph.config import settings
    from life_graph.services import sandbox

    captured = {}

    async def fake_exec(argv, timeout, container=None, env=None):
        captured["argv"] = argv
        return sandbox.SandboxResult(0, "ok", "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    deps = tmp_path / "deps"
    (deps / "node_modules").mkdir(parents=True)

    await sandbox.run(["npm", "test"], tmp_path / "w", node_deps=deps)

    argv = captured["argv"]
    joined = " ".join(argv)
    assert settings.verifier_sandbox_node_image in argv
    assert f"{tmp_path / 'w'}:/work:ro" in joined  # the worktree is still read-only
    assert f"{deps / 'node_modules'}:/node_modules:ro" in joined
    assert argv[argv.index("--network") + 1] == "none"
    entry = argv.index("--entrypoint")
    assert argv[entry + 1] == "sh" and "cp -a /work/. /tmp/work/" in argv[entry + 4]
    assert argv[-2:] == ["npm", "test"]
