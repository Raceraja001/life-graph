"""ResilientLLM error classes: which failures bench a model, and where a
rejected request goes next (router council decision, 2026-11-28)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

import life_graph.services.llm.resilient as rl
from life_graph.services.llm.resilient import ResilientLLM, ResilientLLMExhaustedError

L = rl.litellm


def _resp(text="ok"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _http(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "http://x"))


class FakeHealth:
    def __init__(self):
        self.success: list[str] = []
        self.failure: list[tuple[str, str]] = []
        self.request_errors: list[tuple[str, str]] = []
        self.cooldowns: dict[str, float] = {}
        self._fails: dict[str, int] = {}

    async def in_cooldown(self, m):
        return m in self.cooldowns

    async def cooldown_until(self, m):
        return self.cooldowns.get(m, 0)

    async def record_success(self, m, latency_ms):
        self.success.append(m)

    async def record_failure(self, m, kind):
        self.failure.append((m, kind))
        self._fails[m] = self._fails.get(m, 0) + 1
        return self._fails[m]

    async def record_request_error(self, m, kind):
        self.request_errors.append((m, kind))

    async def set_cooldown(self, m, seconds):
        self.cooldowns[m] = seconds

    async def get(self, m):
        return {}


@pytest.fixture(autouse=True)
def _chain(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_model_cheap", "A", raising=False)
    monkeypatch.setattr(rl.settings, "llm_fallback_chain", "B,C", raising=False)
    monkeypatch.setattr(rl.settings, "llm_cooldown_429_seconds", 60, raising=False)
    monkeypatch.setattr(rl.settings, "llm_cooldown_error_seconds", 30, raising=False)
    monkeypatch.setattr(rl.settings, "llm_paid_fallback_model", "", raising=False)
    monkeypatch.setattr(rl.settings, "omniroute_api_key", "", raising=False)


# ── classification ──

REAL_FAILURES = [
    (L.RateLimitError("rate", "prov", "A"), "429"),
    (L.Timeout("slow", "A", "prov"), "timeout"),
    (TimeoutError("slow"), "timeout"),
    (L.InternalServerError("boom", "prov", "A"), "error"),
    (L.ServiceUnavailableError("down", "prov", "A"), "error"),
    (L.BadGatewayError("bad gw", "prov", "A"), "error"),
    (L.APIConnectionError("refused", "prov", "A"), "error"),
    (L.APIError(500, "boom", "prov", "A"), "error"),
    (L.APIError(404, "not found", "prov", "A"), "error"),
    (RuntimeError("??"), "error"),
]

REQUEST_ERRORS = [
    (L.BadRequestError("bad param", "A", "prov"), "bad_request"),
    (L.UnprocessableEntityError("bad body", "A", "prov", response=_http(422)), "bad_request"),
    (L.APIError(400, "invalid", "prov", "A"), "bad_request"),
    (L.ContextWindowExceededError("too long", "A", "prov"), "context_window"),
    (
        L.BadRequestError("This model's maximum context length is 8192", "A", "prov"),
        "context_window",
    ),
    (L.ContentPolicyViolationError("refused", "A", "prov"), "content_policy"),
    (L.AuthenticationError("bad key", "prov", "A"), "auth"),
    (L.PermissionDeniedError("nope", "prov", "A", response=_http(403)), "auth"),
    (L.APIError(401, "unauthorized", "prov", "A"), "auth"),
]


@pytest.mark.parametrize(("exc", "kind"), REAL_FAILURES + REQUEST_ERRORS)
def test_classify_error(exc, kind):
    assert rl.classify_error(exc) == kind


@pytest.mark.parametrize(("exc", "kind"), REAL_FAILURES)
async def test_real_failures_bench_the_model(monkeypatch, exc, kind):
    monkeypatch.setattr(L, "acompletion", AsyncMock(side_effect=[exc, _resp("hi")]))
    h = FakeHealth()
    assert await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}]) == "hi"
    assert h.failure == [("A", kind)]
    assert "A" in h.cooldowns
    assert h.request_errors == []
    assert h.success == ["B"]


@pytest.mark.parametrize(("exc", "kind"), REQUEST_ERRORS)
async def test_request_errors_do_not_bench_the_model(monkeypatch, exc, kind):
    monkeypatch.setattr(rl, "context_window_of", lambda m: None)
    monkeypatch.setattr(L, "acompletion", AsyncMock(side_effect=[exc, _resp("hi")]))
    h = FakeHealth()
    assert await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}]) == "hi"
    assert h.failure == []  # no failure count ...
    assert h.cooldowns == {}  # ... and no cooldown
    assert h.request_errors == [("A", kind)]
    assert h.success == ["B"]  # still moved on down the chain


async def test_request_error_does_not_inflate_the_next_cooldown(monkeypatch):
    """A 400 between two 500s must not double the second 500's cooldown."""
    monkeypatch.setattr(
        L,
        "acompletion",
        AsyncMock(
            side_effect=[
                L.BadRequestError("bad", "A", "prov"),
                _resp(),
                L.APIError(500, "boom", "prov", "A"),
                _resp(),
            ]
        ),
    )
    h = FakeHealth()
    llm = ResilientLLM(health=h)
    await llm.chat([{"role": "user", "content": "q"}])
    await llm.chat([{"role": "user", "content": "q"}])
    assert h.cooldowns["A"] == 30  # base, first real failure


async def test_all_request_errors_exhaust_with_the_last_kind(monkeypatch):
    monkeypatch.setattr(L, "acompletion", AsyncMock(side_effect=L.BadRequestError("bad", "A", "p")))
    h = FakeHealth()
    with pytest.raises(ResilientLLMExhaustedError, match="bad_request"):
        await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert h.cooldowns == {}
    assert [m for m, _ in h.request_errors] == ["A", "B", "C"]


# ── fallback order ──


def _record_calls(results):
    order: list[str] = []
    it = iter(results)

    async def fake(model, messages, **kw):
        order.append(model)
        r = next(it)
        if isinstance(r, BaseException):
            raise r
        return r

    return order, fake


async def test_context_window_goes_to_a_larger_model_first(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_fallback_chain", "small,unknown,big", raising=False)
    sizes = {"A": 8_000, "small": 4_000, "unknown": None, "big": 128_000}
    monkeypatch.setattr(rl, "context_window_of", sizes.get)
    order, fake = _record_calls([L.ContextWindowExceededError("too long", "A", "p"), _resp("hi")])
    monkeypatch.setattr(L, "acompletion", fake)
    h = FakeHealth()
    assert await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}]) == "hi"
    assert order == ["A", "big"]
    assert h.cooldowns == {}


async def test_context_window_order_larger_then_unknown_then_smaller(monkeypatch):
    sizes = {"A": 8_000, "s": 4_000, "u": None, "b1": 32_000, "b2": 16_000, "eq": 8_000}
    monkeypatch.setattr(rl, "context_window_of", sizes.get)
    rest = ["s", "u", "b1", "eq", "b2"]
    assert rl.reorder_after("context_window", "A", rest) == ["b1", "b2", "u", "s", "eq"]


async def test_context_window_with_unknown_size_takes_the_next_model(monkeypatch):
    monkeypatch.setattr(rl, "context_window_of", lambda m: None)
    assert rl.reorder_after("context_window", "A", ["B", "C"]) == ["B", "C"]


async def test_content_policy_goes_to_another_provider_first(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_model_cheap", "openrouter/x/a:free", raising=False)
    monkeypatch.setattr(
        rl.settings,
        "llm_fallback_chain",
        "openrouter/y/b:free,gemini/gemini-2.5-flash,openrouter/z/c:free",
        raising=False,
    )
    order, fake = _record_calls(
        [L.ContentPolicyViolationError("refused", "openrouter/x/a:free", "openrouter"), _resp("hi")]
    )
    monkeypatch.setattr(L, "acompletion", fake)
    h = FakeHealth()
    assert await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}]) == "hi"
    assert order == ["openrouter/x/a:free", "gemini/gemini-2.5-flash"]
    assert h.cooldowns == {}


def test_content_policy_keeps_same_provider_models_as_a_last_resort():
    rest = ["openrouter/b", "gemini/g", "openrouter/c", "ollama/q"]
    assert rl.reorder_after("content_policy", "openrouter/a", rest) == [
        "gemini/g",
        "ollama/q",
        "openrouter/b",
        "openrouter/c",
    ]


def test_other_kinds_leave_the_chain_alone():
    assert rl.reorder_after("bad_request", "A", ["B", "C"]) == ["B", "C"]
    assert rl.reorder_after("auth", "A", ["B", "C"]) == ["B", "C"]


def test_context_window_of_local_and_unmapped(monkeypatch):
    monkeypatch.setattr(rl.settings, "local_llm_num_ctx", 16384, raising=False)
    assert rl.context_window_of("ollama/qwen3:14b") == 16384
    assert rl.context_window_of("openrouter/nobody/unmapped-model:free") is None
    assert rl.context_window_of("gpt-4o") and rl.context_window_of("gpt-4o") > 16384


async def test_forced_retry_request_error_is_not_counted(monkeypatch):
    monkeypatch.setattr(L, "acompletion", AsyncMock(side_effect=L.BadRequestError("bad", "B", "p")))
    h = FakeHealth()
    h.cooldowns = {"A": 100, "B": 10, "C": 50}
    with pytest.raises(ResilientLLMExhaustedError):
        await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert h.failure == []
    assert h.request_errors == [("B", "bad_request")]
