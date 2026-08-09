"""Unit tests for the tool registry's per-tool execution timeout override.

The bug this guards: registry.execute() used ONE global timeout
(TOOL_TIMEOUT_SECONDS) for every tool, no matter how it's implemented.
Fine for fast local tools, but bridged MCP tools (real network I/O against
a remote process — e.g. browser automation against real, sometimes slow
or heavily ad-laden, websites) routinely need much longer. Observed in
production: real-world site navigations were cut off at 15s before the
underlying Playwright action's own (60s default) timeout ever got a
chance to resolve on its own terms.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from life_graph.tools.registry import ToolRegistry

# life_graph/tools/__init__.py does `from .registry import registry` — that
# rebinds the ATTRIBUTE life_graph.tools.registry to the singleton
# ToolRegistry INSTANCE, shadowing the submodule at the package-attribute
# level. `import life_graph.tools.registry as X` resolves via that SAME
# attribute chain (per Python's import semantics for `import a.b.c as X`),
# so it hits the shadowed instance too — only a direct sys.modules lookup
# reliably gets the real module object to monkeypatch its constant.
registry_module = sys.modules["life_graph.tools.registry"]


def _reg_slow(reg: ToolRegistry, delay: float, timeout_seconds: int | None = None):
    async def slow(**_):
        await asyncio.sleep(delay)
        return "done"

    reg.register(
        "slow",
        "sleeps then returns",
        {"type": "object"},
        slow,
        timeout_seconds=timeout_seconds,
    )


@pytest.mark.asyncio
async def test_default_timeout_unchanged_when_not_specified(monkeypatch):
    # Every existing caller that never passes timeout_seconds must keep
    # today's exact behavior — verified by shrinking the global default to
    # something the slow tool will clearly miss, then confirming it does.
    monkeypatch.setattr(registry_module, "TOOL_TIMEOUT_SECONDS", 0.05)
    reg = ToolRegistry()
    _reg_slow(reg, delay=0.5)  # timeout_seconds omitted -> falls back to the global

    out = await reg.execute("slow", {})
    assert "timed out after 0.05s" in out


@pytest.mark.asyncio
async def test_custom_timeout_cuts_off_before_the_global_default_would():
    reg = ToolRegistry()
    _reg_slow(reg, delay=0.5, timeout_seconds=0.05)

    out = await reg.execute("slow", {})
    assert "timed out after 0.05s" in out


@pytest.mark.asyncio
async def test_custom_timeout_allows_a_call_the_global_default_would_have_killed(
    monkeypatch,
):
    monkeypatch.setattr(registry_module, "TOOL_TIMEOUT_SECONDS", 0.05)
    reg = ToolRegistry()
    _reg_slow(reg, delay=0.15, timeout_seconds=1.0)

    out = await reg.execute("slow", {})
    assert out == "done"
