"""Unit tests for the tool registry post-execution observation hook."""

from __future__ import annotations

from life_graph.tools.registry import ToolRegistry


def _reg_echo(reg: ToolRegistry):
    reg.register(
        "echo",
        "echo back",
        {"type": "object", "properties": {"msg": {"type": "string"}}},
        lambda msg="": f"you said {msg}",
    )


async def test_hook_fires_on_success():
    reg = ToolRegistry()
    _reg_echo(reg)
    seen = []
    reg.add_post_exec_hook(lambda obs: seen.append(obs) or _noop())
    out = await reg.execute("echo", {"msg": "hi"})
    assert "you said hi" in out
    assert len(seen) == 1
    obs = seen[0]
    assert obs["tool"] == "echo"
    assert obs["exit_status"] == "ok"
    assert "duration_ms" in obs
    assert "hi" in obs["args_summary"]


async def test_hook_fires_on_error_with_error_status():
    reg = ToolRegistry()

    def boom(**_):
        raise RuntimeError("nope")

    reg.register("boom", "always fails", {"type": "object"}, boom)
    captured = []

    async def hook(obs):
        captured.append(obs)

    reg.add_post_exec_hook(hook)
    out = await reg.execute("boom", {})
    assert "error" in out
    assert captured[0]["exit_status"] == "error"


async def test_hook_secrets_are_redacted_in_summary():
    reg = ToolRegistry()
    reg.register("run", "run", {"type": "object"}, lambda **k: "ok")
    captured = []

    async def hook(obs):
        captured.append(obs)

    reg.add_post_exec_hook(hook)
    await reg.execute("run", {"token": "ghp_0123456789abcdefghij0123456789"})
    assert "ghp_0123456789abcdefghij0123456789" not in captured[0]["args_summary"]


async def test_failing_hook_does_not_break_tool():
    reg = ToolRegistry()
    _reg_echo(reg)

    async def bad_hook(obs):
        raise ValueError("hook blew up")

    reg.add_post_exec_hook(bad_hook)
    out = await reg.execute("echo", {"msg": "still works"})
    assert "still works" in out


async def test_no_hooks_is_a_noop():
    reg = ToolRegistry()
    _reg_echo(reg)
    out = await reg.execute("echo", {"msg": "x"})
    assert "x" in out


async def _noop():
    return None
