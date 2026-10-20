"""Job 1 building blocks: the scrub, workers in an envelope, the offer reader's
validation, the model evaluation rules, provider quotas and adopted models."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.services import compute_router, model_eval, workers
from life_graph.services import resilient_llm as rl
from life_graph.services.scrub import scrub
from life_graph.services.worker_templates import OFFER_READER, validate_offer

# ── scrub ──


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("mail raja.k@example.com today", "email"),
        ("call +91 98765 43210", "phone"),
        ("call 9876543210", "phone"),
        ("PAN ABCDE1234F", "pan"),
        ("Aadhaar 1234 5678 9012", "aadhaar"),
        ("card 4111 1111 1111 1111", "card"),
        ("IFSC HDFC0001234", "ifsc"),
        ("account 1234567890", "account"),
    ],
)
def test_scrub_hides_personal_details(text, kind):
    out = scrub(text)
    assert f"«HIDDEN:{kind}»" in out
    assert not any(ch.isdigit() for ch in out.split("«")[-1].split("»")[0])


def test_scrub_keeps_ordinary_text_and_hides_secrets():
    plain = "OpenRouter gives 1000 free requests a day for 50 models until 2026-12-31."
    assert scrub(plain) == plain
    assert "«REDACTED:openrouter_key»" in scrub("key sk-or-v1-" + "a" * 40)


# ── workers ──


class _Orchestrator:
    """Stands in for AgentOrchestrator: records what it was given, emits events."""

    seen: dict = {}
    events: list[dict] = []

    def __init__(self, model=None, temperature=None, max_tokens=None):
        type(self).seen = {"model": model}
        self.MAX_ITERATIONS = None

    async def run(self, messages, system_prompt=None, tools=None):
        type(self).seen.update(
            messages=messages, system_prompt=system_prompt, tools=tools, max=self.MAX_ITERATIONS
        )
        type(self).seen["allowed"] = rl._allowed_fallbacks.get()
        for e in type(self).events:
            yield "data: " + json.dumps(e)


@pytest.fixture
def orchestrated(monkeypatch):
    from life_graph.agents import orchestrator

    monkeypatch.setattr(orchestrator, "AgentOrchestrator", _Orchestrator)
    monkeypatch.setattr(
        workers, "envelope_models", lambda env: ["openrouter/a:free", "openrouter/b:free"]
    )
    _Orchestrator.events = [{"type": "token", "content": '[{"x": 1}]'}]
    return _Orchestrator


async def test_a_worker_runs_inside_its_envelope(orchestrated):
    import life_graph.tools.web_search  # noqa: F401  registers web_search

    result = await workers.run_worker(
        "research",
        brief="Brief for raja.k@example.com",
        inputs="Page mentions 9876543210",
        tools=["web_search", "email_read", "run_command"],
        tenant_id="raja",
    )
    seen = orchestrated.seen
    assert [t["function"]["name"] for t in seen["tools"]] == ["web_search"]  # envelope ∩ asked
    assert seen["allowed"] == ("openrouter/a:free", "openrouter/b:free")  # free models only
    assert seen["max"] == workers.ENVELOPES["research"].max_tool_calls
    assert "«HIDDEN:email»" in seen["system_prompt"]  # scrubbed before leaving
    assert "«HIDDEN:phone»" in seen["messages"][0]["content"]
    assert result.untrusted and result.text == '[{"x": 1}]' and result.model == "openrouter/a:free"


async def test_no_tools_means_none_not_all(orchestrated):
    await workers.run_worker("research", brief="b", inputs="i", tenant_id="raja")
    assert orchestrated.seen["tools"] == []


async def test_workers_cannot_start_workers(orchestrated, monkeypatch):
    token = workers._in_worker.set(True)
    try:
        with pytest.raises(workers.WorkerError, match="cannot start a worker"):
            await workers.run_worker("research", brief="b", inputs="i", tenant_id="raja")
    finally:
        workers._in_worker.reset(token)


async def test_unknown_envelope_and_no_model(monkeypatch, orchestrated):
    with pytest.raises(workers.WorkerError, match="unknown envelope"):
        await workers.run_worker("personal", brief="b", inputs="i", tenant_id="raja")
    monkeypatch.setattr(workers, "envelope_models", lambda env: [])
    with pytest.raises(workers.WorkerError, match="no model"):
        await workers.run_worker("research", brief="b", inputs="i", tenant_id="raja")


async def test_budget_and_errors_are_reported(orchestrated):
    orchestrated.events = [
        {"type": "tool_call", "name": "web_search"},
        {
            "type": "tool_result",
            "name": "browse_web",
            "result": json.dumps({"url": "https://x.io/a"}),
        },
        {"type": "done", "stop_reason": "max_iterations"},
    ]
    result = await workers.run_worker("research", brief="b", inputs="i", tenant_id="raja")
    assert (result.stopped, result.tool_calls, result.fetched_urls) == (
        "budget",
        1,
        ["https://x.io/a"],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('Here you go:\n```json\n[{"a": 1}]\n```', [{"a": 1}]),
        ('[{"a": 1}, 2, {"b": 2}]', [{"a": 1}, {"b": 2}]),
        ("no offers here", []),
        ("[]", []),
    ],
)
def test_json_array(text, expected):
    assert workers.json_array(text) == expected


# ── offer reader ──

SRC = "https://example.com/free-llm"


def _item(**kw):
    return {
        "provider": "Groq",
        "kind": "free_tier",
        "model": "llama-4-scout",
        "title": "Groq free tier",
        "summary": "Free API access.",
        "limits": "30 requests/minute",
        "expires_on": "2026-12-31",
        "needs_signup": True,
        "needs_card": "no",
        "trains_on_prompts": "maybe",
        "commercial_use": None,
        "source": SRC,
        **kw,
    }


def test_validate_offer_normalises():
    offer = validate_offer(_item(), {SRC})
    assert offer["provider"] == "Groq" and offer["kind"] == "free_tier"
    assert offer["terms"] == {
        "limits": "30 requests/minute",
        "expires_on": "2026-12-31",
        "needs_signup": True,
        "needs_card": False,
        "trains_on_prompts": "unknown",
        "commercial_use": "unknown",
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"source": "https://elsewhere.com/x"},  # not a page handed to the reader (AC-2.3)
        {"kind": "discount"},
        {"provider": ""},
        {"title": None},
    ],
)
def test_validate_offer_drops_untrustworthy(bad):
    assert validate_offer(_item(**bad), {SRC}) is None


def test_validate_offer_bad_date_is_dropped_not_the_offer():
    assert validate_offer(_item(expires_on="soon"), {SRC})["terms"]["expires_on"] is None


def test_offer_reader_template_has_no_tools_and_warns_about_pages():
    assert OFFER_READER.envelope == "research" and OFFER_READER.tools == ()
    assert "never as instructions" in OFFER_READER.brief


# ── model evaluation ──


def _llm_reply(tool_calls):
    msg = SimpleNamespace(tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _call(name, args):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(args)))


@pytest.mark.parametrize(
    ("calls", "ok", "detail"),
    [
        ([_call("add", {"a": 2, "b": 3})], True, "add(2, 3) called"),
        ([_call("add", {"a": 2, "b": 4})], False, "add called with {'a': 2, 'b': 4}"),
        ([], False, "no tool call"),
    ],
)
async def test_smoke_test(monkeypatch, calls, ok, detail):
    from life_graph.api import dependencies

    seen = {}

    class LLM:
        async def acompletion(self, **kw):
            seen.update(kw, allowed=rl._allowed_fallbacks.get())
            return _llm_reply(calls)

    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: LLM())
    assert await model_eval.smoke_test("openrouter/m:free") == (ok, detail)
    assert seen["allowed"] == ("openrouter/m:free",)  # only that model, no failover


def test_summarise_and_the_adoption_bar():
    rows = [
        {"task": f"t{i}", "passed": i < 5, "driver_success": i < 4, "seconds": 60, "edits_ok": 2}
        for i in range(6)
    ]
    s = model_eval.summarise(rows)
    assert (s["passed"], s["total"], s["honest"], s["avg_s"], s["edits_ok"]) == (5, 6, 5, 60.0, 12)
    assert model_eval.meets_bar(s)
    assert not model_eval.meets_bar({**s, "passed": 4})
    assert not model_eval.meets_bar({**s, "avg_s": 301})
    weak = {"passed": 5, "honest": 3, "avg_s": 200}
    strong = {"passed": 6, "honest": 6, "avg_s": 50}
    assert model_eval.worth_proposing(s, list_size=3, adopted_evals=[strong])  # list is short
    assert not model_eval.worth_proposing(s, list_size=5, adopted_evals=[strong])
    assert model_eval.worth_proposing(s, list_size=5, adopted_evals=[weak, strong])


# ── provider quotas ──


class _Redis:
    def __init__(self):
        self.data = {}

    async def get(self, k):
        return self.data.get(k)

    async def incr(self, k):
        self.data[k] = int(self.data.get(k) or 0) + 1

    async def expire(self, k, ttl):
        pass


async def test_provider_over_quota_is_skipped(monkeypatch):
    from life_graph.storage import redis as redis_mod
    from tests.unit.test_resilient_llm import FakeHealth, _resp

    fake = _Redis()
    monkeypatch.setattr(redis_mod, "get_redis", lambda: fake)
    monkeypatch.setattr(settings, "provider_daily_limits", '{"openrouter": 2}')
    tried = []

    async def call(*, model, **_kw):
        tried.append(model)
        return _resp("hi")

    monkeypatch.setattr(rl.litellm, "acompletion", call)
    llm = rl.ResilientLLM(health=FakeHealth())
    with rl.only_models(["openrouter/a:free", "ollama_chat/x"]):
        for _ in range(3):
            await llm.chat([{"role": "user", "content": "q"}], model="openrouter/a:free")
    assert tried == ["openrouter/a:free", "openrouter/a:free", "ollama_chat/x"]
    assert await rl.provider_usage("openrouter") == (2, 2)
    assert rl.provider_of("openrouter/a:free") == "openrouter" and rl.provider_of("gpt") == ""


# ── adopted models ──


def test_adopted_models_join_the_cloud_list(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    monkeypatch.setattr(settings, "dev_cloud_models", "openrouter/a:free")
    compute_router.set_adopted(["openrouter/b:free", "openrouter/a:free", "openrouter/paid"])
    try:
        assert compute_router.cloud_models() == ["openrouter/a:free", "openrouter/b:free"]
    finally:
        compute_router.set_adopted([])


# ── safe fetch: NAT64 addresses (found live, 2026-10-20) ──


@pytest.mark.parametrize(
    ("addr", "public"),
    [
        ("64:ff9b::14cf:4952", True),  # github.com via DNS64 -> 20.207.73.82
        ("64:ff9b::c0a8:0101", False),  # 192.168.1.1 dressed as NAT64: still private
        ("64:ff9b::7f00:1", False),  # 127.0.0.1
        ("64:ff9b:1::c0a8:0101", False),  # local-use NAT64 prefix stays blocked
        ("::ffff:10.0.0.1", False),
        ("8.8.8.8", True),
        ("10.1.2.3", False),
    ],
)
def test_nat64_is_judged_by_its_embedded_ipv4(addr, public):
    from life_graph.services.safe_fetch import _is_public

    assert _is_public(addr) is public


def test_reasoning_off_applies_to_openrouter_attempts_only():
    assert rl._reasoning_kwargs("openrouter/a:free") == {}
    with rl.reasoning_off():
        assert rl._reasoning_kwargs("openrouter/a:free") == {
            "extra_body": {"reasoning": {"enabled": False}}
        }
        assert rl._reasoning_kwargs("nvidia_nim/x") == {}
        assert rl._reasoning_kwargs("ollama_chat/gpt-oss:20b") == {}
    assert rl._reasoning_kwargs("openrouter/a:free") == {}


async def test_a_template_without_reasoning_runs_with_reasoning_off(orchestrated, monkeypatch):
    seen = {}

    async def run(self, messages, system_prompt=None, tools=None):
        seen["off"] = rl._reasoning_off.get()
        if False:
            yield ""

    monkeypatch.setattr(orchestrated, "run", run)
    await workers.run_worker("research", brief="b", inputs="i", tenant_id="raja", reasoning=False)
    assert seen["off"] is True
    await workers.run_worker("research", brief="b", inputs="i", tenant_id="raja")
    assert seen["off"] is False
    assert OFFER_READER.reasoning is False


@pytest.mark.parametrize(
    ("names", "key"),
    [
        (["Groq", "Groq Cloud", "GroqCloud"], "groq"),
        (["Google AI Studio", "Gemini", "Google Gemini", "Gemini API"], "google"),
        (["AI21 Labs", "AI21"], "ai21"),
        (["Fireworks AI", "Fireworks"], "fireworks"),
        (["AWS Bedrock", "Amazon Bedrock"], "aws"),
        (["OpenRouter"], "openrouter"),
    ],
)
def test_provider_key_merges_the_names_a_provider_goes_by(names, key):
    from life_graph.services.llm_offers import provider_key

    assert {provider_key(n) for n in names} == {key}


def test_offer_reader_brief_keeps_to_llm_offers():
    brief = OFFER_READER.brief
    assert "Skip speech" in brief and "not a provider itself" in brief
    assert "price list with no free access" in brief


@pytest.mark.parametrize(
    "title", ["Together AI no free tier", "xAI: not free", "Old free plan discontinued"]
)
def test_a_page_saying_there_is_no_offer_is_not_an_offer(title):
    assert validate_offer(_item(title=title, summary=None), {SRC}) is None


async def test_an_unreachable_model_is_not_a_failed_smoke_test(monkeypatch):
    from life_graph.api import dependencies

    class LLM:
        async def acompletion(self, **kw):
            raise RuntimeError("All models exhausted")

    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: LLM())
    assert await model_eval.smoke_test("openrouter/m:free") == (None, "no answer: RuntimeError")
