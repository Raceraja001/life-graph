"""The kill switch stops new autonomous work everywhere (Stage 0 finding 4, M1.7).

Before 2026-11-25 only AutoFixService._run_action checked it. Now the
scheduler, watcher findings, delegation, the dev runner's claims and errand
approvals refuse new work for a paused tenant. A tenant with no config row
cannot be paused, so it is not stopped; a database error still fails closed.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.autonomy import kill_switch


@pytest.fixture(autouse=True)
def _fresh_cache():
    kill_switch._pause_cache.clear()
    yield
    kill_switch._pause_cache.clear()


def _state(monkeypatch, value):
    """The tenant's flag as the database would give it (None = no config row)."""

    async def read(tenant_id):
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(kill_switch, "_pause_state", read)


@pytest.mark.parametrize(
    ("state", "stopped", "paused"),
    [
        (True, True, True),
        (False, False, False),
        (None, False, True),  # no row: not stopped, but the auto-fix gate stays closed
        (RuntimeError("db down"), True, True),  # both fail closed
    ],
)
@pytest.mark.asyncio
async def test_the_two_answers(monkeypatch, state, stopped, paused):
    _state(monkeypatch, state)
    assert await kill_switch.autonomy_stopped("t1") is stopped
    assert await kill_switch.is_autonomy_paused("t1") is paused


@pytest.mark.asyncio
async def test_a_paused_tenants_schedule_does_not_fire(monkeypatch):
    from life_graph.kernel.scheduler import SchedulerService

    _state(monkeypatch, True)
    pm = SimpleNamespace(spawn=AsyncMock())
    scheduler = SchedulerService.__new__(SchedulerService)
    scheduler._process_manager = pm
    scheduler.get_by_id = AsyncMock(
        return_value={"is_active": True, "name": "nightly", "agent_name": "scout", "input": {}}
    )

    assert await scheduler.fire_job("t1", str(uuid.uuid4())) is None
    pm.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_a_paused_tenants_persona_cannot_delegate(monkeypatch):
    from life_graph.tools import delegate

    _state(monkeypatch, True)
    monkeypatch.setattr(
        "life_graph.core.task_context.get_current_task_context",
        lambda: SimpleNamespace(tenant_id="t1", task_id=uuid.uuid4()),
    )
    pm = SimpleNamespace(spawn=AsyncMock(), get_task=AsyncMock())
    monkeypatch.setattr("life_graph.runtime.get_process_manager", lambda: pm)

    out = json.loads(await delegate.delegate_to_persona("scout", "look into it"))

    assert out["error"] == kill_switch.PAUSED_REFUSAL
    pm.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_a_paused_tenants_errand_tap_issues_no_capability(monkeypatch):
    from life_graph.services.notifications import actions

    _state(monkeypatch, True)
    issued = []
    monkeypatch.setattr(
        "life_graph.autonomy.approvals.capability_store.issue",
        lambda **kw: issued.append(kw),
    )
    note = SimpleNamespace(
        id=uuid.uuid4(),
        source_type=actions.ERRAND_APPROVAL,
        extra_metadata={"kind": actions.ERRAND_APPROVAL, "item_id": "e1", "step_index": 0,
                        "action_type": "click", "target_origin": "https://example.com"},
    )  # fmt: skip
    action = actions.actions_for(actions.ERRAND_APPROVAL, note.extra_metadata)[0]["id"]
    assert action != "reject"

    with pytest.raises(actions.ActionRefusedError, match="paused"):
        await actions.perform(None, "t1", note, action, datetime.now(UTC), UTC)
    assert issued == []
