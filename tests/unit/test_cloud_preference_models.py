"""The advisor and the research stance check keep preferences local by default.

Both put the owner's preferences in their prompts (topic, choice, confidence,
reason). With ``allow_cloud_preference_models`` off (the default, D25) they
run on local models only, pinned with ``local_only`` so a failure cannot fail
over to the cloud chain; cloud models are not asked. On: today's cloud models.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

import life_graph.services.llm.resilient as resilient_mod
from life_graph.config import settings
from life_graph.services.multi_model_advisor import DEFAULT_MODELS, MultiModelAdvisor
from life_graph.services.research_engine import ResearchEngine

LOCAL = "ollama_chat/qwen3:14b"
CLOUD = "openrouter/openai/gpt-4o-mini"
SECRET = "my-private-choice-xyz"


def _resp(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class _FakeResilient:
    """Records each call's model, kwargs and the chain limit in force."""

    def __init__(self, reply: str) -> None:
        self.calls: list[dict] = []
        self._reply = reply

    async def acompletion(self, *, messages, model=None, **kw):
        self.calls.append(
            {
                "model": model,
                "kwargs": kw,
                "prompt": json.dumps(messages),
                "allowed": resilient_mod._allowed_fallbacks.get(),
            }
        )
        return _resp(self._reply)


ADVICE = '{"recommendation": "use X", "pros": [], "cons": [], "confidence": 0.8, "reasoning": "r"}'
STANCE = '{"stance": "supports", "strength": 0.9, "reasoning": "r"}'


@pytest.fixture
def fake(monkeypatch):
    llm = _FakeResilient(ADVICE)
    monkeypatch.setattr("life_graph.runtime.get_resilient_llm", lambda: llm)
    monkeypatch.setattr(settings, "lead_local_model", LOCAL)
    return llm


@pytest.fixture
def cloud_off(monkeypatch):
    monkeypatch.setattr(settings, "allow_cloud_preference_models", False)


@pytest.fixture
def cloud_on(monkeypatch):
    monkeypatch.setattr(settings, "allow_cloud_preference_models", True)


def test_setting_defaults_to_off():
    from life_graph.config.research import ResearchSettings

    assert ResearchSettings().allow_cloud_preference_models is False


def _advisor() -> MultiModelAdvisor:
    return MultiModelAdvisor(session_factory=None, openrouter_api_key="sk-or-fake")


def _prefs():
    return [SimpleNamespace(topic="database", choice=SECRET, confidence=0.9)]


# ── multi_model_advisor ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advisor_off_does_not_ask_a_cloud_model(fake, cloud_off):
    result = await _advisor()._query_model(CLOUD, "Which DB?", [{"choice": SECRET}])

    assert fake.calls == []
    assert result.status == "skipped"
    assert "cloud comparison is off" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_advisor_off_pins_a_local_model_and_sends_no_cloud_credentials(fake, cloud_off):
    result = await _advisor()._query_model(LOCAL, "Which DB?", [{"choice": SECRET}])

    assert result.status == "completed"
    assert [c["model"] for c in fake.calls] == [LOCAL]
    assert fake.calls[0]["allowed"] == (LOCAL,)
    assert "api_key" not in fake.calls[0]["kwargs"]
    assert "api_base" not in fake.calls[0]["kwargs"]


@pytest.mark.asyncio
async def test_advisor_on_asks_the_cloud_model_as_before(fake, cloud_on):
    advisor = _advisor()
    result = await advisor._query_model(CLOUD, "Which DB?", [])

    assert result.status == "completed"
    assert [c["model"] for c in fake.calls] == [CLOUD]
    assert fake.calls[0]["allowed"] is None
    assert fake.calls[0]["kwargs"]["api_key"] == "sk-or-fake"
    assert fake.calls[0]["kwargs"]["api_base"] == advisor._api_base


def test_models_to_query_off_keeps_local_ones_and_leaves_cloud_out(fake, cloud_off):
    asked, left_out = MultiModelAdvisor._models_to_query([CLOUD, "ollama/llama3", LOCAL])
    assert asked == ["ollama/llama3", LOCAL]
    assert left_out == [CLOUD]


def test_models_to_query_off_with_only_cloud_models_asks_the_local_model(fake, cloud_off):
    asked, left_out = MultiModelAdvisor._models_to_query(DEFAULT_MODELS)
    assert asked == [LOCAL]
    assert left_out == DEFAULT_MODELS


def test_models_to_query_on_asks_every_model(fake, cloud_on):
    assert MultiModelAdvisor._models_to_query(DEFAULT_MODELS) == (DEFAULT_MODELS, [])


async def _ask(monkeypatch, advisor: MultiModelAdvisor):
    saved: list = []

    async def _fetch(_tenant_id, limit=20):
        return _prefs()

    async def _save(_tenant_id, result):
        saved.append(result)

    monkeypatch.setattr(advisor, "_fetch_preferences", _fetch)
    monkeypatch.setattr(advisor, "_save_session", _save)
    result = await advisor.ask("t-r3a-pref", "Which DB?", models=list(DEFAULT_MODELS))
    assert saved == [result]
    return result


@pytest.mark.asyncio
async def test_ask_off_sends_preferences_only_to_the_local_model(fake, cloud_off, monkeypatch):
    result = await _ask(monkeypatch, _advisor())

    assert [c["model"] for c in fake.calls] == [LOCAL]
    assert SECRET in fake.calls[0]["prompt"]
    by_model = {r.model: r.status for r in result.responses}
    assert by_model == {LOCAL: "completed", **dict.fromkeys(DEFAULT_MODELS, "skipped")}
    assert result.responses[0].model == LOCAL  # its reasoning is the one saved
    assert result.winning_choice == "use X"


@pytest.mark.asyncio
async def test_ask_on_queries_every_cloud_model(fake, cloud_on, monkeypatch):
    result = await _ask(monkeypatch, _advisor())

    assert sorted(c["model"] for c in fake.calls) == sorted(DEFAULT_MODELS)
    assert {r.status for r in result.responses} == {"completed"}


# ── research_engine stance check ──────────────────────────────────────


def _engine() -> ResearchEngine:
    return ResearchEngine(
        session_factory=None,
        preference_store=None,
        evidence_store=None,
        advisor=_advisor(),
        settings=settings,
    )


def _pref():
    return SimpleNamespace(id=uuid.uuid4(), topic="database", choice=SECRET, reason="fast")


ARTICLE = {"title": "Postgres is great", "content": "Postgres is great for most apps."}


@pytest.mark.asyncio
async def test_stance_off_runs_on_the_pinned_local_model(fake, cloud_off):
    fake._reply = STANCE
    got = await _engine()._detect_stance(_pref(), ARTICLE)

    assert got == {"stance": "supports", "strength": 0.9}
    assert [c["model"] for c in fake.calls] == [LOCAL]
    assert fake.calls[0]["allowed"] == (LOCAL,)
    assert SECRET in fake.calls[0]["prompt"]
    assert "api_key" not in fake.calls[0]["kwargs"]
    assert "api_base" not in fake.calls[0]["kwargs"]


@pytest.mark.asyncio
async def test_stance_off_without_a_local_model_sends_nothing(fake, cloud_off, monkeypatch):
    monkeypatch.setattr(settings, "lead_local_model", CLOUD)
    fake._reply = STANCE

    assert await _engine()._detect_stance(_pref(), ARTICLE) is None
    assert fake.calls == []


@pytest.mark.asyncio
async def test_stance_on_uses_gpt_4o_mini_as_before(fake, cloud_on):
    fake._reply = STANCE
    got = await _engine()._detect_stance(_pref(), ARTICLE)

    assert got == {"stance": "supports", "strength": 0.9}
    assert [c["model"] for c in fake.calls] == [CLOUD]
    assert fake.calls[0]["allowed"] is None
    assert fake.calls[0]["kwargs"]["api_key"] == "sk-or-fake"
