"""The cloud driver: free cloud models only, no personal context, its own record."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.drivers import local
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.cloud import CloudDriver
from life_graph.services import resilient_llm

FREE = "openrouter/poolside/laguna-s-2.1:free"


def _packet(model):
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="raja",
        task_type="code_change",
        instruction="Fix it",
        preferences=[{"topic": "family", "choice": "dinner at 8"}],
        procedures=[{"name": "p"}],
        memories=[{"content": "personal"}],
        persona_model=model,
    )


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    monkeypatch.setattr(settings, "dev_cloud_models", f"{FREE},openrouter/other:free")


async def test_refuses_a_model_that_is_not_free(keys, monkeypatch):
    async def must_not_run(*_a, **_k):
        raise AssertionError("ran a non-free model")

    monkeypatch.setattr(local.LocalDriver, "dispatch", must_not_run)
    for model in ("openrouter/deepseek/deepseek-chat", "ollama_chat/gpt-oss:20b", None):
        result = await CloudDriver().dispatch(_packet(model), Path("."))
        assert result.success is False
        assert result.metadata["stop_reason"] == "refused"


async def test_strips_personal_context_and_limits_failover(keys, monkeypatch):
    seen = {}

    async def fake_dispatch(self, packet, workdir, timeout=300):
        seen["packet"] = packet
        seen["allowed"] = resilient_llm._allowed_fallbacks.get()
        return DriverResult(success=True, output="done")

    monkeypatch.setattr(local.LocalDriver, "dispatch", fake_dispatch)
    result = await CloudDriver().dispatch(_packet(FREE), Path("."), timeout=60)
    assert result.success
    packet = seen["packet"]
    assert (packet.preferences, packet.procedures, packet.memories) == ([], [], [])
    assert seen["allowed"] == (FREE, "openrouter/other:free")
    assert resilient_llm._allowed_fallbacks.get() is None  # reset afterwards


async def test_available_only_with_a_key(monkeypatch):
    monkeypatch.setattr(settings, "dev_cloud_models", FREE)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert await CloudDriver().available() is False
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    assert await CloudDriver().available() is True


def test_never_picked_by_cheapest_capable_selection():
    assert CloudDriver().capabilities() == []
    assert CloudDriver.name == "cloud"  # trust and stats are keyed by this


def test_budget_treats_only_free_models_as_free():
    from life_graph.drivers.dispatcher import runs_on_local_model

    assert runs_on_local_model("cloud", FREE) is True
    assert runs_on_local_model("cloud", "openrouter/deepseek/deepseek-chat") is False
    assert runs_on_local_model("cloud", None) is False


async def test_an_unavailable_cloud_pin_does_not_fall_through(monkeypatch):
    from life_graph.drivers.dispatcher import DispatchError, TaskDispatcher
    from life_graph.drivers.registry import driver_registry

    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(driver_registry, "get", lambda name: CloudDriver())
    disp = TaskDispatcher(session_factory=lambda: None, event_bus=None)
    persona = SimpleNamespace(driver="cloud", properties={})
    with pytest.raises(DispatchError, match="not available"):
        await disp._select_driver(
            "code_change", "code-fixer-cloud", "raja", session=None, persona=persona
        )


def test_the_cloud_persona_seeds_on_a_free_model(monkeypatch):
    from life_graph.kernel.personas import _BUILTIN_PERSONAS, _seed_model

    monkeypatch.setattr(settings, "dev_cloud_models", FREE)
    (defn,) = [p for p in _BUILTIN_PERSONAS if p["name"] == "code-fixer-cloud"]
    assert defn["driver"] == "cloud"
    assert _seed_model(defn) == FREE
    (other,) = [p for p in _BUILTIN_PERSONAS if p["name"] == "code-fixer-local"]
    assert _seed_model(other) == settings.agent_llm_model
