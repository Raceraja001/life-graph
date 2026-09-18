"""Code tools and the local coding driver.

Pins: per-task confinement (the worktree and nothing else), paging that stays
under the registry's result cap, exact-snippet edits that fail loudly, search
that skips junk and never follows symlinks out, and a local driver that uses
the persona's model, confines its tools, and reports timeouts/errors as
failures.
"""

from __future__ import annotations

import json
import uuid

import pytest

from life_graph.tools import code
from life_graph.tools._guards import confine_to
from life_graph.tools.registry import MAX_TOOL_RESULT_CHARS


@pytest.fixture
def repo(tmp_path, monkeypatch):
    from life_graph.config import settings

    root = tmp_path / "projects"
    wt = tmp_path / "worktree"
    (root / "other").mkdir(parents=True)
    (root / "other" / "secret.py").write_text("TOKEN = 1\n")
    (wt / "pkg").mkdir(parents=True)
    (wt / "pkg" / "mod.py").write_text("def a():\n    return 1\n\n\ndef b():\n    return 1\n")
    # Settings roots cover the projects folder but not the worktree.
    monkeypatch.setattr(settings, "tool_fs_roots", str(root))
    return {"root": root, "wt": wt}


async def test_confinement_reaches_only_the_task_worktree(repo):
    outside = json.loads(await code.code_read(str(repo["wt"] / "pkg" / "mod.py")))
    assert "outside the permitted roots" in outside["error"]  # /tmp worktree not a root

    with confine_to(repo["wt"]):
        inside = json.loads(await code.code_read("pkg/mod.py"))  # relative to worktree
        assert inside["total_lines"] == 6
        other = json.loads(await code.code_read(str(repo["root"] / "other" / "secret.py")))
        assert "outside the permitted roots" in other["error"]  # rest of roots excluded


async def test_code_read_pages_stay_under_registry_cap(repo):
    big = repo["wt"] / "big.py"
    big.write_text("\n".join(f"x_{i} = '{'y' * 90}'" for i in range(400)))
    with confine_to(repo["wt"]):
        start, seen = 1, 0
        while start:
            raw = await code.code_read("big.py", start_line=start)
            assert len(raw) < MAX_TOOL_RESULT_CHARS
            page = json.loads(raw)
            seen += len(page["content"].splitlines())
            start = page["next_start_line"]
    assert seen == 400


async def test_code_edit_replaces_exactly_one_snippet(repo):
    with confine_to(repo["wt"]):
        ambiguous = json.loads(
            await code.code_edit("pkg/mod.py", "    return 1\n", "    return 2\n")
        )
        assert "found 2 times" in ambiguous["error"]
        missing = json.loads(await code.code_edit("pkg/mod.py", "return 99", "x"))
        assert "not found" in missing["error"]
        ok = json.loads(
            await code.code_edit(
                "pkg/mod.py", "def b():\n    return 1\n", "def b():\n    return 2\n"
            )
        )
        assert ok["at_line"] == 5
    assert (repo["wt"] / "pkg" / "mod.py").read_text().endswith("def b():\n    return 2\n")


async def test_code_edit_creates_but_never_clobbers(repo):
    with confine_to(repo["wt"]):
        created = json.loads(await code.code_edit("pkg/new.py", "", "X = 1\n"))
        assert "created" in created
        clobber = json.loads(await code.code_edit("pkg/new.py", "", "Y = 2\n"))
        assert "File exists" in clobber["error"]
    assert (repo["wt"] / "pkg" / "new.py").read_text() == "X = 1\n"


async def test_code_edit_refuses_git_internals(repo):
    (repo["wt"] / ".git").write_text("gitdir: /somewhere\n")
    with confine_to(repo["wt"]):
        out = json.loads(await code.code_edit(".git", "gitdir: /somewhere\n", "gitdir: /evil\n"))
    assert "inside a .git directory" in out["error"]


async def test_search_and_list_skip_junk_and_symlinks(repo, tmp_path):
    (repo["wt"] / "node_modules" / "dep").mkdir(parents=True)
    (repo["wt"] / "node_modules" / "dep" / "index.py").write_text("def a(): pass\n")
    escape = tmp_path / "escape"
    escape.mkdir()
    (escape / "leak.py").write_text("def a(): pass\n")
    (repo["wt"] / "link").symlink_to(escape)
    with confine_to(repo["wt"]):
        found = json.loads(await code.code_search(r"^def a"))
        listed = json.loads(await code.code_list(glob="*.py"))
    assert found["matches"] == ["pkg/mod.py:1: def a():"]
    assert listed["files"] == ["pkg/mod.py"]


async def test_bad_regex_is_reported(repo):
    with confine_to(repo["wt"]):
        out = json.loads(await code.code_search("("))
    assert "Bad pattern" in out["error"]


# ── Local driver ─────────────────────────────────────────────


def _packet(**kw):
    from life_graph.drivers.base import ContextPacket

    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t",
        task_type="code_change",
        instruction="change b to return 2",
        allowed_tools=["code_read", "code_edit"],
        persona_model="ollama_chat/qwen3-coder:30b",
        **kw,
    )


@pytest.fixture
def fake_orchestrator(monkeypatch):
    import life_graph.agents.orchestrator as orch_mod

    seen = {}

    class Fake:
        MAX_ITERATIONS = 8

        def __init__(self, model=None, **_):
            self.model = model
            seen["instance"] = self

        async def run(self, messages, system_prompt=None, tools=None):
            seen["tools"] = [t["function"]["name"] for t in tools or []]
            behaviour = seen.get("behaviour", "edit")
            if behaviour == "hang":
                import asyncio

                await asyncio.sleep(10)
            if behaviour == "error":
                yield 'data: {"type": "error", "message": "model unavailable"}\n\n'
                return
            # Tool call made from inside the run: confinement must apply.
            seen["read"] = json.loads(await code.code_read("pkg/mod.py"))
            yield 'data: {"type": "tool_call", "name": "code_read"}\n\n'
            yield 'data: {"type": "token", "content": "Changed b."}\n\n'

    monkeypatch.setattr(orch_mod, "AgentOrchestrator", Fake)
    import life_graph.tools.code  # noqa: F401  (register code_* for tool filtering)

    return seen


async def test_local_driver_uses_persona_model_and_confines_tools(repo, fake_orchestrator):
    from life_graph.drivers.local import LocalDriver

    result = await LocalDriver().dispatch(_packet(), repo["wt"], timeout=5)
    assert result.success, result.error
    assert result.output == "Changed b."
    assert result.metadata["model"] == "ollama_chat/qwen3-coder:30b"
    assert result.metadata["tool_calls"] == 1
    assert fake_orchestrator["instance"].MAX_ITERATIONS == LocalDriver.MAX_AGENT_ITERATIONS
    assert sorted(fake_orchestrator["tools"]) == ["code_edit", "code_read"]
    assert fake_orchestrator["read"]["total_lines"] == 6  # worktree reachable during the run
    # ...and only during it.
    after = json.loads(await code.code_read(str(repo["wt"] / "pkg" / "mod.py")))
    assert "error" in after


async def test_local_driver_timeout_and_errors_fail_the_run(repo, fake_orchestrator):
    from life_graph.drivers.local import LocalDriver

    fake_orchestrator["behaviour"] = "hang"
    timed_out = await LocalDriver().dispatch(_packet(), repo["wt"], timeout=1)
    assert not timed_out.success and "timed out" in timed_out.error

    fake_orchestrator["behaviour"] = "error"
    errored = await LocalDriver().dispatch(_packet(), repo["wt"], timeout=5)
    assert not errored.success and "model unavailable" in errored.error


def test_dispatcher_honours_driver_timeout():
    from life_graph.drivers.local import LocalDriver

    assert LocalDriver.dispatch_timeout > 300
