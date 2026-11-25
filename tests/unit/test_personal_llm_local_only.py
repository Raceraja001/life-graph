"""Callers that carry the owner's personal data never reach a cloud model (D25).

``ResilientLLM`` fails over to the cloud chain (``llm_fallback_chain``,
OmniRoute, the paid fallback) even when its primary model is local, and
``LMStudioClient.chat()`` goes to OpenRouter when ``use_hybrid_llm`` is on.
The personal-data callers use ``local_only()`` or ``chat_local_only()``
instead, and skip (fail closed) when no local model is configured.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import life_graph.services.llm.resilient as resilient_mod
from life_graph.config import settings
from life_graph.extraction.llm import LLMExtractor
from life_graph.extraction.transcript_extract import extract_transcript_facts
from life_graph.self_improving.task_runner import llm_fn_for
from life_graph.services.failure_mining import FailurePatternMiner
from life_graph.services.llm.client import LMStudioClient
from life_graph.services.llm.resilient import ResilientLLM, ResilientLLMExhaustedError, local_only

LOCAL = "ollama_chat/qwen3:14b"
CLOUD = "openrouter/openai/gpt-oss-20b:free"


def _resp(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
        _hidden_params={},
    )


class _FakeResilient:
    """The real ``local_only`` gate, with a recording ``acompletion``/``chat``.

    Each call records the model it was asked for and the chain limit that was
    in force (``only_models``), so a test can prove the call could not fail
    over to anything else.
    """

    local_only = staticmethod(local_only)

    def __init__(self, reply: str = '{"facts": []}') -> None:
        self.calls: list[dict] = []
        self._reply = reply

    async def acompletion(self, *, messages, model=None, **_kw):
        self.calls.append({"model": model, "allowed": resilient_mod._allowed_fallbacks.get()})
        return _resp(self._reply)

    async def chat(self, messages, *, model=None, **_kw):
        self.calls.append({"model": model, "allowed": resilient_mod._allowed_fallbacks.get()})
        return self._reply


@pytest.fixture
def hybrid_on(monkeypatch):
    """Hybrid on with an OpenRouter key: chat() would use the cloud. Cloud
    attempts are recorded (chat() swallows their errors and falls back, so
    the record is what tests check); the local runtime is faked."""
    monkeypatch.setattr(settings, "use_hybrid_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-fake")
    seen: dict = {"cloud": [], "local": [], "reply": '{"facts": []}'}

    async def _cloud(*a, **kw):
        seen["cloud"].append((a, kw))
        raise AssertionError("personal data sent to the cloud LLM")

    async def _local(self, messages, model, temperature, max_tokens, response_format):
        seen["local"].append({"messages": messages, "model": model})
        return seen["reply"]

    monkeypatch.setattr(LMStudioClient, "_cloud_chat", _cloud)
    monkeypatch.setattr(LMStudioClient, "_local_chat", _local)
    assert LMStudioClient()._use_cloud
    return seen


# ── the gate itself ───────────────────────────────────────────────────


def test_local_only_yields_a_local_model_and_limits_the_chain_to_it():
    with local_only(f"  {LOCAL} ") as model:
        assert model == LOCAL
        assert resilient_mod._allowed_fallbacks.get() == (LOCAL,)
    assert resilient_mod._allowed_fallbacks.get() is None


@pytest.mark.parametrize("model", [CLOUD, "gemini/gemini-3.6-flash", "", None])
def test_local_only_yields_none_for_a_cloud_or_missing_model(model):
    with local_only(model) as got:
        assert got is None
        assert resilient_mod._allowed_fallbacks.get() is None


@pytest.mark.asyncio
async def test_a_failing_local_model_does_not_fail_over_to_the_cloud(monkeypatch):
    """The finding itself: without local_only the chain goes on to cloud models."""
    monkeypatch.setattr(settings, "llm_fallback_chain", f"{CLOUD},gemini/gemini-3.5-flash-lite")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", "openai/gpt-5")
    tried: list[str] = []

    async def _litellm(*, model, **_kw):
        tried.append(model)
        raise RuntimeError("down")

    async def _no(*_a, **_kw):
        return False

    async def _none(*_a, **_kw):
        return None

    monkeypatch.setattr(resilient_mod.litellm, "acompletion", _litellm)
    monkeypatch.setattr(resilient_mod, "_over_quota", _no)
    monkeypatch.setattr(resilient_mod, "_count_request", _none)
    health = AsyncMock()
    health.in_cooldown.return_value = False
    health.record_failure.return_value = 1
    health.get.return_value = {}
    llm = ResilientLLM(health=health)

    with llm.local_only(LOCAL) as model, pytest.raises(ResilientLLMExhaustedError):
        await llm.acompletion(messages=[{"role": "user", "content": "x"}], model=model)
    assert tried == [LOCAL]


# ── extraction (LiteLLM path, when there is no local LM client) ───────


@pytest.mark.asyncio
async def test_extraction_with_a_cloud_model_sends_nothing(monkeypatch):
    fake = _FakeResilient()
    monkeypatch.setattr("life_graph.runtime.get_resilient_llm", lambda: fake)

    assert await LLMExtractor(model=CLOUD)._extract_cloud("my bank pin is 1234") == []
    assert fake.calls == []


@pytest.mark.asyncio
async def test_extraction_with_a_local_model_cannot_fail_over(monkeypatch):
    fake = _FakeResilient()
    monkeypatch.setattr("life_graph.runtime.get_resilient_llm", lambda: fake)

    await LLMExtractor(model=LOCAL)._extract_cloud("I moved to Chennai")
    assert fake.calls == [{"model": LOCAL, "allowed": (LOCAL,)}]


# ── transcript extraction ─────────────────────────────────────────────

_TURNS = [{"role": "user", "text": "my daughter's school is X", "ts": None}]


@pytest.mark.asyncio
async def test_transcript_with_a_cloud_cheap_model_sends_nothing(monkeypatch):
    monkeypatch.setattr(settings, "llm_model_cheap", CLOUD)
    fake = _FakeResilient()

    assert await extract_transcript_facts(_TURNS, resilient_llm=fake) == []
    assert fake.calls == []


@pytest.mark.asyncio
async def test_transcript_with_a_local_cheap_model_cannot_fail_over(monkeypatch):
    monkeypatch.setattr(settings, "llm_model_cheap", LOCAL)
    fake = _FakeResilient(json.dumps({"facts": [{"content": "School is X.", "category": "fact"}]}))

    facts = await extract_transcript_facts(_TURNS, resilient_llm=fake)
    assert [f.content for f in facts] == ["School is X."]
    assert fake.calls == [{"model": LOCAL, "allowed": (LOCAL,)}]


# ── self-improving eval runner (replays extraction on the owner's words) ─


@pytest.mark.asyncio
async def test_eval_runner_stays_local_in_hybrid_mode(hybrid_on):
    run = llm_fn_for("capture_extraction", "acme")
    await run("default", "I take metformin every morning")

    assert hybrid_on["cloud"] == []
    assert hybrid_on["local"]
    assert "metformin" in hybrid_on["local"][0]["messages"][-1]["content"]


# ── failure mining (the owner's decision journal) ─────────────────────


@pytest.mark.asyncio
async def test_failure_mining_stays_local_in_hybrid_mode(hybrid_on):
    hybrid_on["reply"] = '{"patterns": []}'
    miner = FailurePatternMiner(session_factory=MagicMock(), llm=LMStudioClient())
    failures = [{"decision_id": "d1", "status": "reversed", "title": "quit job", "domain_tags": []}]

    assert await miner.mine(failures) == []
    assert hybrid_on["cloud"] == []
    assert "quit job" in hybrid_on["local"][0]["messages"][0]["content"]
