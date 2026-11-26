"""Skill distillation and session summaries run on local models only.

Both read the owner's own work: a harvested coding session (prompts, paths,
errors) and a session's context. The distiller called ``ResilientLLM.chat``
with no model, i.e. the cheap tier plus the whole fail-over chain, cloud by
default; the summary called ``lm_client.chat``, which goes to the cloud chain
when ``use_hybrid_llm`` is on. Now: a pinned local model, or nothing.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.config import settings
from life_graph.services import session_lifecycle
from life_graph.services.llm import resilient as rl
from tests.unit.test_skill_distiller import engine, slice_of

LOCAL = "ollama_chat/qwen3:14b"


@pytest.fixture(autouse=True)
def _cloud_defaults(monkeypatch):
    """Everything the old call could reach: a cloud cheap model, a cloud
    chain, OmniRoute and a paid fallback."""
    monkeypatch.setattr(settings, "llm_model_cheap", "openrouter/cheap:free")
    monkeypatch.setattr(settings, "llm_fallback_chain", "gemini/flash,openrouter/x:free")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", "anthropic/paid")
    monkeypatch.setattr(settings, "omniroute_api_key", "k")
    monkeypatch.setattr(settings, "lead_local_model", LOCAL)


class _Health:
    async def in_cooldown(self, m):
        return False

    async def record_success(self, m, latency_ms):
        pass

    async def record_failure(self, m, kind):
        return 1

    async def set_cooldown(self, m, seconds):
        pass

    async def get(self, m):
        return {}


@pytest.fixture
def litellm_calls(monkeypatch):
    """Every model litellm is asked for; each call fails (local model down)."""
    tried: list[str] = []

    async def down(*, model, messages, **_kw):
        tried.append(model)
        raise ConnectionError("ollama is down")

    monkeypatch.setattr(rl.litellm, "acompletion", down)
    monkeypatch.setattr(rl, "_over_quota", AsyncMock(return_value=False))
    monkeypatch.setattr(rl, "_count_request", AsyncMock())
    return tried


@pytest.mark.asyncio
async def test_the_distiller_asks_the_local_model_by_name():
    distiller, _, llm = engine()
    result = await distiller.distill(slice_of(), dry_run=True)
    assert result.action == "CREATE_SKILL"
    assert llm.chat.await_args.kwargs["model"] == LOCAL


@pytest.mark.asyncio
async def test_the_local_model_down_never_fails_over_to_the_cloud(litellm_calls):
    """The real ResilientLLM, every call failing: only the local model is
    tried, then distillation gives up -- no cloud chain, OmniRoute or paid."""
    distiller, fake, _ = engine(llm=rl.ResilientLLM(health=_Health()))
    result = await distiller.distill(slice_of())
    assert litellm_calls == [LOCAL]
    assert result.action == "NOOP" and "LLM unavailable" in result.reasoning
    assert fake.added == []


@pytest.mark.asyncio
async def test_a_cloud_model_is_never_called(litellm_calls):
    distiller, fake, _ = engine(llm=rl.ResilientLLM(health=_Health()))
    distiller.model = "gemini/flash"
    result = await distiller.distill(slice_of())
    assert litellm_calls == []
    assert result.action == "NOOP" and "No local model" in result.reasoning
    assert fake.added == []


@pytest.mark.asyncio
async def test_the_session_summary_stays_on_the_local_runtime(monkeypatch):
    monkeypatch.setattr(settings, "use_hybrid_llm", True)
    lm = MagicMock()
    lm.chat = AsyncMock(return_value="cloud summary")
    lm.chat_local_only = AsyncMock(return_value="Fixed the build. Added a test.")
    monkeypatch.setattr(session_lifecycle.runtime, "get_lm_client", lambda: lm)

    out = await session_lifecycle.generate_summary(SimpleNamespace(context={"cwd": "/p"}), 2)

    assert out == "Fixed the build. Added a test."
    lm.chat.assert_not_called()
    assert "/p" in lm.chat_local_only.await_args.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_the_session_summary_with_hybrid_on_never_builds_a_cloud_client(monkeypatch):
    """The real client: with use_hybrid_llm on and the local runtime down,
    the summary falls back to the template; the cloud chain is not touched."""
    from life_graph.services.llm import client as client_mod

    monkeypatch.setattr(settings, "use_hybrid_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    lm = client_mod.LMStudioClient()
    cloud = AsyncMock(return_value="cloud summary")
    monkeypatch.setattr(lm, "_cloud_chat", cloud)
    monkeypatch.setattr(lm, "_local_chat", AsyncMock(return_value=""))  # local down
    monkeypatch.setattr(session_lifecycle.runtime, "get_lm_client", lambda: lm)

    out = await session_lifecycle.generate_summary(SimpleNamespace(context={"cwd": "/p"}), 2)

    assert out == "Session with 2 memories created"
    cloud.assert_not_called()
