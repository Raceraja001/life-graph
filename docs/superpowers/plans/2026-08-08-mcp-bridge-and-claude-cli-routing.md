# MCP-Client Bridge + Claude CLI Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Let Life Graph act as an MCP *client* — connect to configured external MCP servers and register their tools into the existing `ToolRegistry`, so personas can call them like any local tool. (2) Let a persona's `model` be set to `claude-cli`, routing that persona's replies through the Claude subscription CLI instead of litellm — plain conversational replies only, no tool-calling, per the design's explicit scope decision.

**Architecture:** Two independent subsystems built together. The MCP bridge is a new `life_graph/services/mcp_bridge.py` connecting via the official `mcp` SDK's `stdio_client`/`ClientSession`, held open for the app's life via an `AsyncExitStack` on `app.state`, wired into `main.py`'s existing lifespan. Claude CLI routing adds one branch to `AgentOrchestrator.run()` that bypasses the litellm loop entirely when `self.model == "claude-cli"`, reusing `drivers/claude_code.py`'s exact subprocess pattern via a new `life_graph/services/claude_cli_reply.py`.

**Tech Stack:** FastAPI, the official `mcp` Python SDK (v1.29.0, already transitively available via `fastmcp`), `asyncio` subprocess management, `httpx`/litellm (unchanged, for every non-`claude-cli` model).

## Global Constraints

- Specs: `docs/superpowers/specs/2026-08-08-mcp-client-bridge-design.md` and `docs/superpowers/specs/2026-08-08-claude-cli-model-routing-design.md` — read for full rationale.
- MCP bridge v1 ships with **zero configured servers by default** — `mcp_servers` unset/empty means the bridge does nothing, app boots exactly as today.
- MCP bridge config is **env-var-only** (a JSON string, `mcp_servers`) — no admin CRUD API in this pass.
- Bridged tools go through the registry's existing `TOOL_TIMEOUT_SECONDS=15` and `MAX_TOOL_RESULT_CHARS=4000` unchanged — no per-tool timeout override in this pass.
- Bridged tool names are always `mcp_<server_name>_<tool_name>` — avoids collisions without changing `ToolRegistry.register`'s existing silent-overwrite behavior.
- One broken MCP server config must never block app boot or other configured servers — each server's connection attempt is independently wrapped in `try/except`, logged and skipped on failure, matching `main.py`'s existing local-tool-registration failure pattern (`main.py:70-91`).
- Claude CLI routing v1 supports **plain conversational replies only — no tool-calling**. A persona routed to `claude-cli` cannot call any tool (including `delegate_to_persona`) during that turn. This is a deliberate, documented scope limit, not a gap to work around.
- Claude CLI replies are **not streamed token-by-token** — the CLI returns one complete JSON blob, so the reply arrives as a single SSE `token` event, not incremental deltas like every other model.
- Add `mcp` as an **explicit direct dependency** in `pyproject.toml` (currently only present transitively via `fastmcp` → `fastmcp-slim`).
- Follow this repo's existing test-mocking conventions exactly: `monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)` with a `_FakeProcess` class (`returncode`, `async def communicate()`) — the pattern already used in `tests/unit/test_claude_code_driver_tool_scoping.py`.

---

### Task 1: MCP bridge core — config, service module, reference test server

**Files:**
- Modify: `life_graph/config.py` (add `mcp_servers` setting + `mcp_servers_list` property, near `tenant_plans`/`tenant_plans_dict` at `config.py:160`, `config.py:259-265`)
- Create: `life_graph/services/mcp_bridge.py`
- Create: `tests/fixtures/reference_mcp_server.py`
- Test: `tests/unit/test_mcp_bridge.py`
- Test: `tests/unit/test_mcp_servers_config.py`

**Interfaces:**
- Produces: `settings.mcp_servers_list -> list[dict]` where each dict is `{"name": str, "command": str, "args": list[str], "env": dict[str, str] | None}` (missing `args`/`env` default to `[]`/`None`).
- Produces: `async def connect_all(exit_stack: AsyncExitStack) -> int` in `life_graph.services.mcp_bridge` — connects every configured server, registers its tools into the global `registry`, returns the total tool count registered. Never raises. Task 2 calls this from `main.py`'s lifespan.

- [ ] **Step 1: Write the failing config test**

Create `tests/unit/test_mcp_servers_config.py`:

```python
from life_graph.config import Settings


def test_mcp_servers_list_parses_valid_json():
    s = Settings(mcp_servers='[{"name": "x", "command": "echo", "args": ["hi"]}]')
    assert s.mcp_servers_list == [{"name": "x", "command": "echo", "args": ["hi"]}]


def test_mcp_servers_list_empty_string_returns_empty_list():
    s = Settings(mcp_servers="")
    assert s.mcp_servers_list == []


def test_mcp_servers_list_malformed_json_returns_empty_list():
    s = Settings(mcp_servers="not json")
    assert s.mcp_servers_list == []


def test_mcp_servers_list_default_is_empty():
    s = Settings()
    assert s.mcp_servers_list == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/unit/test_mcp_servers_config.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'mcp_servers_list'` (or a pydantic validation error for the unknown `mcp_servers` kwarg).

- [ ] **Step 3: Add the config setting**

In `life_graph/config.py`, add near `tenant_plans` (`config.py:160`):

```python
    mcp_servers: str = "[]"  # JSON: [{"name": ..., "command": ..., "args": [...], "env": {...}}]
```

Add near `tenant_plans_dict` (`config.py:259-265`):

```python
    @property
    def mcp_servers_list(self) -> list[dict]:
        """Parse JSON list of configured external MCP servers."""
        try:
            parsed = json.loads(self.mcp_servers) if self.mcp_servers else []
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/unit/test_mcp_servers_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Create the reference MCP server test fixture**

Create `tests/fixtures/reference_mcp_server.py` — a tiny real MCP server the bridge's tests launch as a subprocess (no mocking of the MCP protocol itself):

```python
"""Reference MCP server for mcp_bridge tests. Launched as a real subprocess
by tests/unit/test_mcp_bridge.py — not imported directly."""

from fastmcp import FastMCP

mcp = FastMCP("reference-test-server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo the input text back."""
    return text


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 6: Write the failing bridge tests**

Create `tests/unit/test_mcp_bridge.py`:

```python
import sys
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from life_graph.services import mcp_bridge
from life_graph.tools.registry import registry

FIXTURE = str(Path(__file__).parent.parent / "fixtures" / "reference_mcp_server.py")


@pytest.fixture(autouse=True)
def _clean_registry():
    # Bridge tests register real tool names into the global registry —
    # snapshot and restore so they don't leak into other test files.
    before = dict(registry._tools)
    yield
    registry._tools.clear()
    registry._tools.update(before)


@pytest.mark.asyncio
async def test_connect_all_registers_tools_from_reference_server():
    # connect_all reads servers from settings.mcp_servers_list directly, so
    # this calls the per-server helper with a config passed explicitly —
    # exercising the same connection/registration code without needing to
    # monkeypatch global settings for this test.
    server_config = {"name": "ref", "command": sys.executable, "args": [FIXTURE]}
    async with AsyncExitStack() as stack:
        registered = await mcp_bridge._connect_one(stack, server_config)

        assert registered == 2
        assert "mcp_ref_echo" in registry.tool_names
        assert "mcp_ref_add" in registry.tool_names


@pytest.mark.asyncio
async def test_bridged_tool_call_round_trips_through_registry():
    server_config = {"name": "ref", "command": sys.executable, "args": [FIXTURE]}
    async with AsyncExitStack() as stack:
        await mcp_bridge._connect_one(stack, server_config)
        result = await registry.execute("mcp_ref_echo", {"text": "hello"})
        assert result == "hello"


@pytest.mark.asyncio
async def test_bad_server_config_skipped_second_server_still_connects(monkeypatch):
    monkeypatch.setattr(
        "life_graph.config.settings.mcp_servers_list",
        [
            {"name": "broken", "command": "this-binary-does-not-exist", "args": []},
            {"name": "ref", "command": sys.executable, "args": [FIXTURE]},
        ],
        raising=False,
    )
    async with AsyncExitStack() as stack:
        count = await mcp_bridge.connect_all(stack)

    assert count == 2  # only the "ref" server's 2 tools — "broken" contributed 0
    assert "mcp_ref_echo" in registry.tool_names
    assert "mcp_broken_echo" not in registry.tool_names
```

`registry.execute(name: str, args: dict) -> str` and `registry.tool_names -> list[str]` (both confirmed in `life_graph/tools/registry.py:133-135,217`) are the exact APIs used above — no adjustment needed.

- [ ] **Step 7: Run to verify they fail**

Run: `python -m pytest tests/unit/test_mcp_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_graph.services.mcp_bridge'`

- [ ] **Step 8: Add `mcp` as an explicit dependency**

In `pyproject.toml`, add `"mcp>=1.29.0"` alongside the existing `"fastmcp>=2.0"` dependency line.

Run: `pip install -e ".[dev]"` (or however this repo's dev install is normally refreshed) to confirm it resolves cleanly against the existing `fastmcp` pin.

- [ ] **Step 9: Write the bridge module**

Create `life_graph/services/mcp_bridge.py`:

```python
"""MCP-client bridge: connects to configured external MCP servers and
registers their tools into Life Graph's ToolRegistry, so personas can call
external MCP servers (browser automation, calendar, voice, etc.) the same
way they call any local tool.

life_graph/mcp_server.py is the SERVER side (exposes Life Graph's own tools
outward). This module is the CLIENT side — the two are independent,
unrelated directions; nothing here talks to mcp_server.py.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from life_graph.config import settings
from life_graph.tools.registry import registry

logger = logging.getLogger(__name__)


async def connect_all(exit_stack: AsyncExitStack) -> int:
    """Connect every server in settings.mcp_servers_list and register its
    tools. Never raises — each server's connection is independently
    isolated so one broken config never blocks the others or app startup.
    Returns the total number of tools registered."""
    registered = 0
    for server_config in settings.mcp_servers_list:
        try:
            registered += await _connect_one(exit_stack, server_config)
        except Exception:
            logger.warning(
                "mcp_bridge: failed to connect server %r",
                server_config.get("name", "<unnamed>"),
                exc_info=True,
            )
    return registered


async def _connect_one(exit_stack: AsyncExitStack, server_config: dict) -> int:
    """Connect one server, register its tools. Raises on failure — the
    caller (connect_all) is responsible for catching and isolating."""
    name = server_config["name"]
    params = StdioServerParameters(
        command=server_config["command"],
        args=server_config.get("args", []),
        env=server_config.get("env") or None,
    )
    read, write = await exit_stack.enter_async_context(stdio_client(params))
    session = await exit_stack.enter_async_context(ClientSession(read, write))
    await session.initialize()

    result = await session.list_tools()
    for tool in result.tools:
        registry.register(
            name=f"mcp_{name}_{tool.name}",
            description=tool.description or "",
            parameters_schema=tool.inputSchema,
            handler=_make_bridge_handler(session, tool.name),
        )
    logger.info("mcp_bridge: connected %r, registered %d tool(s)", name, len(result.tools))
    return len(result.tools)


def _make_bridge_handler(session: ClientSession, tool_name: str):
    """Returns an async handler matching ToolRegistry's expected signature
    for the given MCP tool on the given (already-connected) session."""

    async def handler(**kwargs: Any) -> str:
        result = await session.call_tool(tool_name, arguments=kwargs)
        parts: list[str] = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
            else:
                parts.append(f"[non-text content: {getattr(block, 'type', 'unknown')}]")
        return "\n".join(parts)

    return handler
```

- [ ] **Step 10: Run to verify they pass**

Run: `python -m pytest tests/unit/test_mcp_bridge.py -v`
Expected: PASS (3 tests). If `test_bridged_tool_call_round_trips_through_registry` needed adjusting per Step 9's note, re-verify it passes with the corrected call.

- [ ] **Step 11: Run the full unit suite and commit**

Run: `python -m pytest tests/unit/ -v`
Expected: PASS, no new failures.

```bash
git add life_graph/config.py life_graph/services/mcp_bridge.py tests/fixtures/reference_mcp_server.py tests/unit/test_mcp_bridge.py tests/unit/test_mcp_servers_config.py pyproject.toml
git commit -m "feat: MCP-client bridge — config, service, reference test server"
```

---

### Task 2: Wire the bridge into app lifespan

**Files:**
- Modify: `life_graph/main.py:69-91` (add MCP bridge startup near the existing local-tool registration block), `life_graph/main.py:241-247` (add shutdown)
- Test: `tests/integration/test_app_boot.py` (new, or extend an existing boot-smoke-test file if one already exists — check first)

**Interfaces:**
- Consumes: `connect_all(exit_stack) -> int` from `life_graph.services.mcp_bridge` (Task 1).

- [ ] **Step 1: Check for an existing app-boot smoke test**

Run: `find tests -iname "*boot*" -o -iname "*lifespan*" -o -iname "*app_startup*"` (or the Windows-shell equivalent) to see if a test already exercises `main.py`'s lifespan end-to-end. If one exists, extend it per Step 4 below instead of creating a new file — update the file path in this task accordingly.

- [ ] **Step 2: Write the failing boot test**

If no existing file, create `tests/integration/test_app_boot.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app


@pytest.mark.asyncio
async def test_app_boots_with_no_mcp_servers_configured(monkeypatch):
    monkeypatch.setattr("life_graph.config.settings.mcp_servers", "[]", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            resp = await client.get("/health")
    assert resp.status_code in (200, 503)  # 503 acceptable if DB/Redis unreachable in CI
```

Adjust to match this repo's actual existing pattern for exercising `lifespan` in a test — check `tests/conftest.py` and any existing test that already does something similar (e.g. tests around `main.py`'s startup) before assuming the shape above is exactly right; it may already have a fixture for this.

- [ ] **Step 3: Run to verify current behavior**

Run: `python -m pytest tests/integration/test_app_boot.py -v`
Expected: PASS already (this test should pass even before Task 2's code changes, since it's testing that boot doesn't break — it's a regression guard being written test-first for the change about to happen, not a test of not-yet-existing functionality). If it fails for unrelated reasons (DB/Redis unavailable), note that and adjust the assertion per this repo's documented pattern of accepting 500/503 when infra is unreachable (see `CLAUDE.md`'s testing conventions).

- [ ] **Step 4: Wire the bridge into `main.py`**

In `life_graph/main.py`, add after the existing local-tool registration block (after line 91's `except Exception: logger.warning(...)`):

```python
    # Startup — connect configured external MCP servers (bridge)
    from contextlib import AsyncExitStack

    app.state.mcp_exit_stack = AsyncExitStack()
    try:
        from life_graph.services.mcp_bridge import connect_all

        bridged_count = await connect_all(app.state.mcp_exit_stack)
        logger.info("MCP bridge: %d external tool(s) registered", bridged_count)
    except Exception:
        logger.warning("MCP bridge startup failed", exc_info=True)
```

Add before the existing `# Shutdown — close Redis` block (`main.py:243`):

```python
    # Shutdown — close MCP bridge connections
    await app.state.mcp_exit_stack.aclose()
```

- [ ] **Step 5: Run to verify it still passes**

Run: `python -m pytest tests/integration/test_app_boot.py -v`
Expected: PASS — app boots cleanly with the bridge wired in but zero servers configured.

- [ ] **Step 6: Manual check with a configured server (optional but recommended)**

If you have a moment: set `LIFE_GRAPH_MCP_SERVERS='[{"name": "ref", "command": "python", "args": ["tests/fixtures/reference_mcp_server.py"]}]'` as an env var, start the app locally (`python -m uvicorn life_graph.main:app --port 8080`), and check the startup logs for `"MCP bridge: 2 external tool(s) registered"`. Note in your report whether this was possible in your sandbox; skip if not, it's not a hard requirement for this task's completion.

- [ ] **Step 7: Run the full test suite and commit**

Run: `python -m pytest tests/ -v`
Expected: PASS, no new failures.

```bash
git add life_graph/main.py tests/integration/test_app_boot.py
git commit -m "feat: wire MCP bridge into app lifespan (startup connect, shutdown close)"
```

---

### Task 3: Claude CLI reply service + model picker entry

**Files:**
- Create: `life_graph/services/claude_cli_reply.py`
- Modify: `life_graph/services/model_catalog.py:23-35` (add `claude-cli` entry to `FALLBACK_MODELS`)
- Test: `tests/unit/test_claude_cli_reply.py`
- Test: `tests/unit/test_model_catalog.py` (extend — one new assertion)

**Interfaces:**
- Produces: `async def run_claude_cli(prompt: str, timeout: float = 60.0) -> ClaudeCliResult` in `life_graph.services.claude_cli_reply`, where `ClaudeCliResult` is a dataclass with fields `success: bool`, `text: str`, `error: str | None`, `duration_ms: int`. Task 4 consumes this exact signature and field set.

- [ ] **Step 1: Add the `claude-cli` catalog entry**

In `life_graph/services/model_catalog.py`, add to `FALLBACK_MODELS` (`model_catalog.py:23-35`), after the existing `"openrouter/deepseek/deepseek-chat"` entry:

```python
    {
        "id": "claude-cli",
        "name": "Claude CLI (subscription, no tool-calling)",
        "is_free": False,
    },
```

- [ ] **Step 2: Extend the existing model_catalog test**

In `tests/unit/test_model_catalog.py`, add:

```python
@pytest.mark.asyncio
async def test_claude_cli_entry_always_present_on_success():
    _FakeAsyncClient.body = {"data": []}

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "claude-cli" in ids
```

Match this repo's existing fixture setup in that file exactly (the `_FakeAsyncClient`/`_reset` fixture already there from the live-model-search feature) — don't redefine it.

- [ ] **Step 3: Run to verify it passes**

Run: `python -m pytest tests/unit/test_model_catalog.py -v`
Expected: PASS (all tests including the new one — this is a data-only change, no new branching logic, so no separate red step is needed here; the assertion should pass immediately once Step 1's entry is in place).

- [ ] **Step 4: Write the failing claude_cli_reply tests**

Create `tests/unit/test_claude_cli_reply.py`:

```python
import pytest

from life_graph.services.claude_cli_reply import run_claude_cli


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        pass


@pytest.mark.asyncio
async def test_success_returns_parsed_result_text(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(0, b'{"result": "hello there", "is_error": false}')

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    assert result.success is True
    assert result.text == "hello there"
    assert result.error is None


@pytest.mark.asyncio
async def test_binary_not_found_returns_failure(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        raise FileNotFoundError("claude not found")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_timeout_kills_process_and_returns_failure(monkeypatch):
    import asyncio

    class _HangingProcess(_FakeProcess):
        def __init__(self):
            super().__init__(0, b"")

        async def communicate(self):
            raise TimeoutError()

    async def _fake_exec(*args, **kwargs):
        return _HangingProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(
        "asyncio.wait_for",
        lambda coro, timeout: (_ for _ in ()).throw(TimeoutError()),
    )

    result = await run_claude_cli("hi", timeout=1.0)

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_non_zero_exit_returns_failure(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(1, b'{"result": "bad request", "is_error": true}', b"")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    assert result.success is False
    assert "bad request" in result.error


@pytest.mark.asyncio
async def test_malformed_json_output_tolerated_as_plain_text(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(0, b"not valid json at all")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    # Mirrors claude_code.py's _parse_output tolerance: non-JSON stdout on
    # a zero exit code is treated as the literal result text, not an error.
    assert result.success is True
    assert result.text == "not valid json at all"
```

Note on the timeout test: `monkeypatch.setattr("asyncio.wait_for", ...)` is a broad patch — if it causes issues interacting with pytest-asyncio's own internals, instead patch `_FakeProcess.communicate` to `raise asyncio.TimeoutError()` directly and don't touch `asyncio.wait_for` at all (simpler, less invasive); adjust `run_claude_cli`'s implementation to catch `TimeoutError` from the `communicate()` call however `asyncio.wait_for` surfaces it in practice (verify empirically by running the test) rather than assuming.

- [ ] **Step 5: Run to verify they fail**

Run: `python -m pytest tests/unit/test_claude_cli_reply.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_graph.services.claude_cli_reply'`

- [ ] **Step 6: Write the service**

Create `life_graph/services/claude_cli_reply.py`:

```python
"""One-shot, non-streaming, tool-free replies via the Claude CLI.

Mirrors drivers/claude_code.py's subprocess mechanics (binary resolution,
timeout handling, JSON parsing) but is a standalone caller for the model-
routing path (AgentOrchestrator selecting "claude-cli" as a persona's
model), not a Driver — this is unrelated to the claude_code driver's
task-dispatch use case, which is untouched by this module.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from dataclasses import dataclass

from life_graph.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ClaudeCliResult:
    success: bool
    text: str
    error: str | None
    duration_ms: int


def _binary() -> str:
    return getattr(settings, "driver_claude_code_bin", "claude")


async def run_claude_cli(prompt: str, timeout: float = 60.0) -> ClaudeCliResult:
    """Shell out to the Claude CLI for a one-shot, non-streaming reply.

    No tool-calling — this is a plain text-in, text-out call. See
    docs/superpowers/specs/2026-08-08-claude-cli-model-routing-design.md
    for why that's a deliberate v1 scope limit, not an oversight.
    """
    start = time.monotonic()
    binary = _binary()

    try:
        proc = await asyncio.create_subprocess_exec(
            binary, "-p", prompt, "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return ClaudeCliResult(
            success=False,
            text="",
            error=f"claude_cli binary {binary!r} not found",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as exc:
        logger.error("claude_cli_reply dispatch failed: %s", exc, exc_info=True)
        return ClaudeCliResult(
            success=False,
            text="",
            error=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return ClaudeCliResult(
            success=False,
            text="",
            error=f"claude_cli timed out after {timeout}s",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    duration = int((time.monotonic() - start) * 1000)
    data = _parse_output(out)
    is_error = bool(data.get("is_error", False))
    success = proc.returncode == 0 and not is_error

    if success:
        return ClaudeCliResult(
            success=True, text=str(data.get("result", "")), error=None, duration_ms=duration
        )
    return ClaudeCliResult(
        success=False,
        text="",
        error=str(data.get("result") or err.decode(errors="replace"))[:2000]
        or f"exit code {proc.returncode}",
        duration_ms=duration,
    )


def _parse_output(out: bytes) -> dict:
    """Parse the CLI's JSON stdout; tolerate plain-text output.

    Same tolerance as drivers/claude_code.py's _parse_output — kept as a
    separate copy here rather than importing that module's private
    staticmethod, since claude_code.py is driver-specific and this module
    is intentionally independent of it.
    """
    text = (out or b"").decode(errors="replace").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"result": data}
    except json.JSONDecodeError:
        return {"result": text}
```

If Step 4's timeout test needed adjusting per its note, make sure this implementation's timeout handling matches whatever the test actually verifies empirically.

- [ ] **Step 7: Run to verify they pass**

Run: `python -m pytest tests/unit/test_claude_cli_reply.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Run the full unit suite and commit**

Run: `python -m pytest tests/unit/ -v`
Expected: PASS, no new failures.

```bash
git add life_graph/services/claude_cli_reply.py life_graph/services/model_catalog.py tests/unit/test_claude_cli_reply.py tests/unit/test_model_catalog.py
git commit -m "feat: Claude CLI reply service + claude-cli model picker entry"
```

---

### Task 4: Wire `claude-cli` into the orchestrator

**Files:**
- Modify: `life_graph/agents/orchestrator.py:78-108` (add the branch, before the existing `for iteration in range(self.MAX_ITERATIONS):` loop at line 108)
- Test: `tests/unit/test_orchestrator_claude_cli_routing.py`

**Interfaces:**
- Consumes: `run_claude_cli(prompt, timeout) -> ClaudeCliResult` from `life_graph.services.claude_cli_reply` (Task 3).

- [ ] **Step 1: Write the failing orchestrator tests**

Create `tests/unit/test_orchestrator_claude_cli_routing.py`:

```python
import json

import pytest

from life_graph.agents.orchestrator import AgentOrchestrator
from life_graph.services.claude_cli_reply import ClaudeCliResult


@pytest.mark.asyncio
async def test_claude_cli_model_yields_token_usage_done_only(monkeypatch):
    async def _fake_run_claude_cli(prompt, timeout=60.0):
        return ClaudeCliResult(success=True, text="hi there", error=None, duration_ms=42)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    events = []
    async for chunk in orchestrator.run(messages=[{"role": "user", "content": "hi"}]):
        events.append(json.loads(chunk.removeprefix("data: ").strip()))

    types = [e["type"] for e in events]
    assert types == ["token", "usage", "done"]
    assert events[0]["content"] == "hi there"


@pytest.mark.asyncio
async def test_claude_cli_model_never_calls_resilient_llm(monkeypatch):
    called = {"count": 0}

    def _fake_get_resilient_llm():
        called["count"] += 1
        raise AssertionError("get_resilient_llm should never be called for claude-cli")

    monkeypatch.setattr(
        "life_graph.api.dependencies.get_resilient_llm", _fake_get_resilient_llm
    )

    async def _fake_run_claude_cli(prompt, timeout=60.0):
        return ClaudeCliResult(success=True, text="ok", error=None, duration_ms=1)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    async for _ in orchestrator.run(messages=[{"role": "user", "content": "hi"}]):
        pass

    assert called["count"] == 0


@pytest.mark.asyncio
async def test_claude_cli_failure_yields_partial_error_then_done(monkeypatch):
    async def _fake_run_claude_cli(prompt, timeout=60.0):
        return ClaudeCliResult(success=False, text="", error="claude not found", duration_ms=5)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    events = []
    async for chunk in orchestrator.run(messages=[{"role": "user", "content": "hi"}]):
        events.append(json.loads(chunk.removeprefix("data: ").strip()))

    # Matches the existing ResilientLLMExhausted failure shape exactly
    # (orchestrator.py:297-304): a "partial_error" event with a "message"
    # key, always followed by a terminal "done" — not a bare "error" event.
    types = [e["type"] for e in events]
    assert types == ["partial_error", "done"]
    assert "claude not found" in events[0]["message"]
    assert events[0]["retryable"] is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/unit/test_orchestrator_claude_cli_routing.py -v`
Expected: FAIL — for `claude-cli`, the current code tries to run it through the normal litellm loop and either errors differently or hangs waiting on a real (unmocked) `get_resilient_llm()` call.

- [ ] **Step 3: Add the branch**

In `life_graph/agents/orchestrator.py`, add the import near the top (alongside `orchestrator.py:16-18`):

```python
from life_graph.services.claude_cli_reply import run_claude_cli
```

Insert this branch in `run()`, after `resolved_tools`/`has_tools`/`allowed_tool_names` are computed (`orchestrator.py:79-85`) and before `total_tokens = 0` / the `for iteration in range(self.MAX_ITERATIONS):` loop (`orchestrator.py:105-108`). `working_messages` (built at `orchestrator.py:88-96`, just above the insertion point) already has `system_prompt` prepended as a `{"role": "system", ...}` entry when set, so flattening just needs to walk `working_messages` — no separate system-prompt handling needed:

```python
        if self.model == "claude-cli":
            prompt = "\n".join(f"{msg['role']}: {msg['content']}" for msg in working_messages)

            result = await run_claude_cli(prompt)
            if not result.success:
                # Matches the existing ResilientLLMExhausted failure shape
                # exactly (orchestrator.py:297-304) — "partial_error" with a
                # "message" key, always followed by a terminal "done".
                yield _sse(
                    {"type": "partial_error", "message": result.error, "retryable": True}
                )
                yield _sse({"type": "done", "model": self.model, "tokens": 0})
                return

            yield _sse({"type": "token", "content": result.text})
            yield _sse(
                {
                    "type": "usage",
                    "completion_tokens": len(result.text.split()),
                    "total_tokens": len(result.text.split()),
                }
            )
            yield _sse({"type": "done", "model": self.model, "tokens": len(result.text.split())})
            return
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/unit/test_orchestrator_claude_cli_routing.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Regression check — existing orchestrator tests unaffected**

Run: `python -m pytest tests/unit/test_orchestrator_tool_enforcement.py tests/unit/test_llm_client_resilient.py tests/unit/test_advisor_resilient.py -v` (or whatever the actual existing orchestrator/litellm-path test files are — `grep -rl "AgentOrchestrator" tests/unit/` to find them all) — confirm every existing test still passes unchanged, proving the `claude-cli` branch is additive and doesn't alter behavior for any other model value.

- [ ] **Step 6: Run the full test suite and commit**

Run: `python -m pytest tests/ -v`
Expected: PASS, no new failures.

```bash
git add life_graph/agents/orchestrator.py tests/unit/test_orchestrator_claude_cli_routing.py
git commit -m "feat: route claude-cli persona model through the Claude CLI (no tool-calling, v1)"
```
