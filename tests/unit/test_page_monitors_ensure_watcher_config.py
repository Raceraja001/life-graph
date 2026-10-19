import pytest

# Import the module to patch ensure_config
import life_graph.watchers.provision as provision
from life_graph.services.page_monitors import ensure_watcher_config
from tests.unit.fakes import FakeSession


@pytest.mark.asyncio
async def test_ensure_watcher_config_calls_ensure_config(monkeypatch):
    called = []

    async def fake_ensure_config(
        session, tenant_id, watcher_name, display_name, description, schedule="0 * * * *"
    ):
        called.append((session, tenant_id, watcher_name, display_name, description, schedule))

    monkeypatch.setattr(provision, "ensure_config", fake_ensure_config)

    session = FakeSession()
    tenant_id = "tenant1"

    result = await ensure_watcher_config(session, tenant_id)

    assert result is None
    assert len(called) == 1
    sess, t_id, watcher_name, display_name, description, sched = called[0]
    assert sess is session
    assert t_id == tenant_id
    assert watcher_name == "page_monitor"
    assert display_name == "Page monitors"
    assert (
        description
        == "Pages the user asked to watch (docs/specs/assistant-capabilities.md, Phase D)"
    )
    assert sched == "0 * * * *"


@pytest.mark.asyncio
async def test_ensure_watcher_config_propagates_exception(monkeypatch):
    async def fake_ensure_config(
        session, tenant_id, watcher_name, display_name, description, schedule="0 * * * *"
    ):
        raise ValueError("test error")

    monkeypatch.setattr(provision, "ensure_config", fake_ensure_config)

    session = FakeSession()
    tenant_id = "tenant1"

    with pytest.raises(ValueError, match="test error"):
        await ensure_watcher_config(session, tenant_id)


# Ensure that the function actually returns None when no exception occurs
@pytest.mark.asyncio
async def test_ensure_watcher_config_returns_none(monkeypatch):
    async def fake_ensure_config(
        session, tenant_id, watcher_name, display_name, description, schedule="0 * * * *"
    ):
        return None

    monkeypatch.setattr(provision, "ensure_config", fake_ensure_config)

    session = FakeSession()
    tenant_id = "tenant1"

    result = await ensure_watcher_config(session, tenant_id)
    assert result is None
