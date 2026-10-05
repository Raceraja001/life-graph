"""MCP dev-agent tools: an editor agent (Claude Code, Cline, ...) can start
and watch Life Graph dev tasks, and see what's waiting on the human -- but
can never approve or reject anything itself.

No network: httpx.AsyncClient's verbs are patched with a per-URL router.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from life_graph import mcp_server

PROJECT_ID = "24c80519-f0bb-49ad-9911-2e5a24c52841"
PROJECTS = {
    "data": {
        "projects": [{"id": PROJECT_ID, "name": "life-graph"}],
        "total": 1,
    }
}


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Router:
    """Patch httpx verbs; answer by (verb, url). Records every call."""

    def __init__(self, routes: dict[tuple[str, str], object]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []
        self._patches = []

    def __enter__(self):
        def _make(verb):
            async def _call(_self, url, **kw):
                self.calls.append((verb, url, kw))
                return _Resp(self.routes[(verb, url)])

            return _call

        self._patches = [
            patch.object(httpx.AsyncClient, verb, _make(verb)) for verb in ("get", "post")
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()


async def _call(tool: str, args: dict):
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(tool, args)
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_dev_agent_tools_are_registered():
    async with Client(mcp_server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert {
        "list_projects",
        "start_dev_task",
        "get_dev_task",
        "list_dev_tasks",
        "list_approvals",
    } <= names


@pytest.mark.asyncio
async def test_no_tool_can_approve_or_reject():
    """The caller of an MCP tool is a model; approval gates are for humans."""
    async with Client(mcp_server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    offenders = [n for n in names if any(w in n for w in ("approve", "reject", "resolve"))]
    assert not offenders, f"{offenders} would let a model clear its own approval gate"


@pytest.mark.asyncio
async def test_start_dev_task_resolves_a_project_name_and_passes_the_flags():
    task = {
        "data": {
            "id": "t1",
            "title": "Fix x",
            "stage": "queued",
            "status": "queued",
            "output": "x" * 5000,
        }
    }
    routes = {
        ("get", "/api/v1/kernel/projects"): PROJECTS,
        ("post", "/api/v1/kernel/drivers/tasks"): task,
    }
    with _Router(routes) as r:
        out = await _call(
            "start_dev_task",
            {"instruction": "Fix x", "project": "Life-Graph", "plan_only": True},
        )

    body = r.calls[-1][2]["json"]
    assert body["project_id"] == PROJECT_ID  # name matched case-insensitively
    assert body["plan_only"] is True
    assert body["spec_first"] is False
    assert body["persona_name"] == "code-fixer-local"
    assert out["id"] == "t1"
    assert "output" not in out  # compact row, not the full task


@pytest.mark.asyncio
async def test_start_dev_task_with_an_id_skips_the_project_lookup():
    routes = {("post", "/api/v1/kernel/drivers/tasks"): {"data": {"id": "t2"}}}
    with _Router(routes) as r:
        await _call("start_dev_task", {"instruction": "Fix y", "project": PROJECT_ID})

    assert [c[1] for c in r.calls] == ["/api/v1/kernel/drivers/tasks"]
    assert r.calls[0][2]["json"]["project_id"] == PROJECT_ID


@pytest.mark.asyncio
async def test_start_dev_task_unknown_project_names_the_registered_ones():
    routes = {("get", "/api/v1/kernel/projects"): PROJECTS}
    with _Router(routes), pytest.raises(ToolError, match="life-graph"):
        await _call("start_dev_task", {"instruction": "Fix z", "project": "nope"})


@pytest.mark.asyncio
async def test_list_dev_tasks_returns_compact_rows():
    rows = {"data": [{"id": "t1", "stage": "merged", "output": "long narrative"}]}
    routes = {("get", "/api/v1/kernel/drivers/tasks"): rows}
    with _Router(routes) as r:
        out = await _call("list_dev_tasks", {"limit": 5})

    assert r.calls[-1][2]["params"] == {"limit": 5}
    assert out[0]["id"] == "t1"
    assert "output" not in out[0]


@pytest.mark.asyncio
async def test_get_dev_task_hits_the_single_task_endpoint():
    routes = {("get", "/api/v1/kernel/drivers/tasks/t9"): {"data": {"id": "t9"}}}
    with _Router(routes):
        out = await _call("get_dev_task", {"task_id": "t9"})
    assert out["id"] == "t9"


@pytest.mark.asyncio
async def test_list_approvals_truncates_detail_and_passes_status():
    rows = {
        "data": [
            {
                "id": "a1",
                "kind": "driver_plan",
                "title": "Review plan",
                "status": "pending",
                "detail": "d" * 5000,
                "payload": {"spec": "big"},
            }
        ]
    }
    routes = {("get", "/api/v1/approvals"): rows}
    with _Router(routes) as r:
        out = await _call("list_approvals", {})

    assert r.calls[-1][2]["params"] == {"status": "pending", "limit": 20}
    assert len(out[0]["detail"]) == mcp_server._APPROVAL_DETAIL_CHARS
    assert "payload" not in out[0]


@pytest.mark.asyncio
async def test_check_spec_conformance_posts_to_the_task():
    report = {"data": {"conforms": True, "criteria": []}}
    routes = {("post", "/api/v1/kernel/drivers/tasks/t5/conformance"): report}
    with _Router(routes):
        out = await _call("check_spec_conformance", {"task_id": "t5"})
    assert out["conforms"] is True
