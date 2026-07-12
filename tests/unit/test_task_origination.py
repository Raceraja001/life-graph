"""Unit tests for watcher → task origination (Agent Drivers spec, Story 6).

Exercises the pure origination logic — actionable filtering, pipeline-rule
selection, per-tenant / per-project WIP limits, and dedup — with a fake
ProcessManager and in-memory counts (no database).
"""

from __future__ import annotations

import pytest

from life_graph.watchers.origination import TaskOriginationService


class FakeProcessManager:
    """Records spawn calls; returns a fake task id."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def spawn(self, tenant_id, agent_name, input_data, **kw):
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "input_data": input_data,
                **kw,
            }
        )
        return {"task_id": f"task-{len(self.calls)}", "status": "queued"}


class StubOrigination(TaskOriginationService):
    """Origination service with DB access stubbed by in-memory state."""

    def __init__(self, pm, *, tenant_open=0, project_open=None, open_fps=None, **kw):
        super().__init__(pm, **kw)
        self._tenant_open = tenant_open
        self._project_open = project_open or {}
        self._open_fps = set(open_fps or [])

    async def _open_task_count(self, tenant_id, project_id=None):
        if project_id is not None:
            return self._project_open.get(project_id, 0)
        return self._tenant_open

    async def _has_open_task(self, tenant_id, fingerprint):
        return fingerprint in self._open_fps


def _payload(findings, tenant="t1", watcher="dependency"):
    return {"tenant_id": tenant, "watcher_name": watcher, "findings": findings}


@pytest.mark.asyncio
async def test_actionable_findings_spawn_tasks():
    pm = FakeProcessManager()
    svc = StubOrigination(pm)
    findings = [
        {"severity": "critical", "title": "urllib3 1.0 → 2.0"},
        {"severity": "info", "title": "pytest 8.0 → 8.1"},  # not actionable
    ]
    spawned = await svc.originate(_payload(findings))
    assert len(spawned) == 1
    assert len(pm.calls) == 1
    call = pm.calls[0]
    assert call["agent_name"] == "dependency-updater"
    assert call["input_data"]["task_type"] == "dependency_update"
    assert call["input_data"]["origin"] == "watcher"
    assert "fingerprint" in call["input_data"]


@pytest.mark.asyncio
async def test_explicit_actionable_flag_overrides_severity():
    pm = FakeProcessManager()
    svc = StubOrigination(pm)
    findings = [{"severity": "info", "actionable": True, "title": "manual flag"}]
    spawned = await svc.originate(_payload(findings))
    assert len(spawned) == 1


@pytest.mark.asyncio
async def test_unknown_watcher_originates_nothing():
    pm = FakeProcessManager()
    svc = StubOrigination(pm)
    findings = [{"severity": "critical", "title": "x"}]
    spawned = await svc.originate(_payload(findings, watcher="mystery_watcher"))
    assert spawned == []
    assert pm.calls == []


@pytest.mark.asyncio
async def test_finding_level_rule_override():
    pm = FakeProcessManager()
    svc = StubOrigination(pm)
    findings = [
        {
            "severity": "critical",
            "title": "prod down",
            "agent_name": "uzhavu-ops",
            "task_type": "incident_fix",
        }
    ]
    await svc.originate(_payload(findings, watcher="server_health"))
    assert pm.calls[0]["agent_name"] == "uzhavu-ops"
    assert pm.calls[0]["input_data"]["task_type"] == "incident_fix"


@pytest.mark.asyncio
async def test_tenant_wip_limit_caps_spawns():
    pm = FakeProcessManager()
    # tenant already has 4 open tasks, limit is 5 → only 1 more allowed
    svc = StubOrigination(pm, tenant_open=4, tenant_wip=5)
    findings = [
        {"severity": "critical", "title": f"dep-{i}"} for i in range(3)
    ]
    spawned = await svc.originate(_payload(findings))
    assert len(spawned) == 1


@pytest.mark.asyncio
async def test_project_wip_limit_skips_over_budget_project():
    pm = FakeProcessManager()
    svc = StubOrigination(pm, project_open={"proj-A": 2}, project_wip=2)
    findings = [
        {"severity": "critical", "title": "a", "project_id": "proj-A"},
        {"severity": "critical", "title": "b", "project_id": "proj-B"},
    ]
    spawned = await svc.originate(_payload(findings))
    # proj-A already at limit → only proj-B spawns
    assert len(spawned) == 1
    assert pm.calls[0]["input_data"]["finding"]["project_id"] == "proj-B"


@pytest.mark.asyncio
async def test_dedup_skips_existing_open_task():
    pm = FakeProcessManager()
    svc = StubOrigination(pm)
    finding = {"severity": "critical", "title": "urllib3 1.0 → 2.0"}
    fp = svc.fingerprint("t1", "dependency", "dependency-updater", finding)
    svc._open_fps.add(fp)  # simulate an already-open task for this finding
    spawned = await svc.originate(_payload([finding]))
    assert spawned == []
    assert pm.calls == []


@pytest.mark.asyncio
async def test_missing_tenant_or_watcher_is_noop():
    pm = FakeProcessManager()
    svc = StubOrigination(pm)
    assert await svc.originate({"findings": [{"severity": "critical"}]}) == []
    assert await svc.originate({"tenant_id": "t1", "findings": []}) == []
    assert pm.calls == []
