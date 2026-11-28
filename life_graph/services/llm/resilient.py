"""ResilientLLM — ordered free-model failover with cooldowns + health recording.

Every completion tries the caller's model first, then the configured free
fallback chain, skipping any model currently in cooldown. Health is recorded to
LLMHealth from real outcomes — never a probe. When every model is exhausted (or
all cooling and the one forced retry also fails) it raises
ResilientLLMExhaustedError; callers run their own fallback.

Errors are classified (``classify_error``, router council decision 2026-11-28):

* Real failures bench the model, with an exponential cooldown: ``429`` (rate
  limit; `llm_cooldown_429_seconds` or its Retry-After), ``timeout`` and
  ``error`` (5xx, connection errors, anything unrecognised; base
  `llm_cooldown_error_seconds`).
* Request errors are about this request (or our configuration), not the
  model's health, so they never bench it: ``bad_request`` (400/422),
  ``context_window``, ``content_policy``, and ``auth`` (401/403, its own class
  so a misconfigured key is visible). The call still moves on down the chain:
  after ``context_window`` the models known to have a larger context window
  go next; after ``content_policy`` the models of other providers go next.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import litellm

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

from life_graph.config import settings
from life_graph.services.llm import local_runtime
from life_graph.services.llm.fallback_pin import _allowed_fallbacks
from life_graph.services.llm.health import LLMHealth

logger = logging.getLogger(__name__)


class ResilientLLMExhaustedError(Exception):
    """Raised when every model in the chain failed or is unavailable."""


# _allowed_fallbacks (imported above) is the pin only_models() sets; it lives
# in fallback_pin.py so connectors/locality.py can read it without litellm.


_reasoning_off: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "resilient_llm_reasoning_off", default=False
)


@contextmanager
def reasoning_off():
    """Within this block, ask OpenRouter models not to reason before answering.

    Free reasoning models given a dense page to extract from spent the whole
    output budget thinking and returned no content at all (8,000 of 8,000
    tokens, finish=length, 2026-10-20); with reasoning off the same models
    returned 14-17 offers in 40-50 s. For extraction, not for agents that
    plan. Applied per attempt, so a fallback to another provider never gets
    a parameter it does not know.
    """
    token = _reasoning_off.set(True)
    try:
        yield
    finally:
        _reasoning_off.reset(token)


def _reasoning_kwargs(model: str) -> dict[str, Any]:
    if _reasoning_off.get() and model.startswith("openrouter/"):
        return {"extra_body": {"reasoning": {"enabled": False}}}
    return {}


def provider_of(model: str) -> str:
    """``openrouter`` for ``openrouter/x/y:free``; '' for a bare model id."""
    return model.split("/", 1)[0].lower() if "/" in model else ""


def _quota_key(provider: str) -> str:
    from datetime import UTC, datetime

    return f"lg:quota:{provider}:{datetime.now(UTC):%Y%m%d}"


async def provider_usage(provider: str) -> tuple[int, int | None]:
    """(requests made today, daily limit) for a provider; limit None = unlimited.

    Free tiers cap requests per day (OpenRouter ~1000 with credit); counting
    our own requests lets the router spread load before the provider starts
    refusing, and lets the evaluation job hold off near the limit.
    """
    from life_graph.storage.redis import get_redis

    limit = settings.provider_daily_limits_map.get(provider)
    redis = get_redis()
    if not limit or redis is None:
        return 0, limit
    try:
        return int(await redis.get(_quota_key(provider)) or 0), limit
    except Exception:  # noqa: BLE001 - quota tracking never blocks a call
        return 0, limit


async def _over_quota(model: str) -> bool:
    used, limit = await provider_usage(provider_of(model))
    return bool(limit) and used >= limit


async def _count_request(model: str) -> None:
    from life_graph.storage.redis import get_redis

    provider = provider_of(model)
    redis = get_redis()
    if redis is None or not settings.provider_daily_limits_map.get(provider):
        return
    try:
        key = _quota_key(provider)
        await redis.incr(key)
        await redis.expire(key, 2 * 86_400)
    except Exception:  # noqa: BLE001
        logger.debug("quota count failed for %s", provider, exc_info=True)


@contextmanager
def only_models(models: list[str]):
    """Within this block, completions fail over only to *models*.

    The global chain (local models, OmniRoute, the paid fallback) is skipped
    entirely. The cloud driver runs under this so that a free cloud run whose
    models are rate-limited fails instead of quietly continuing on the GPU the
    user is using, or on a paid model.
    """
    token = _allowed_fallbacks.set(tuple(models))
    try:
        yield
    finally:
        _allowed_fallbacks.reset(token)


# Providers served from this machine, where `keep_alive` means something.
# Deliberately not "openai/": in this codebase that prefix appears inside
# OpenRouter ids like "openrouter/openai/gpt-oss-20b:free", which is a hosted
# model that must not be handed an Ollama-only option.
LOCAL_PROVIDERS = ("ollama/", "ollama_chat/", "lm_studio/")


@contextmanager
def local_only(model: str | None) -> Iterator[str | None]:
    """For a call that carries the owner's personal data (owner decision D25).

    Yields *model* when it runs on this machine (a ``LOCAL_PROVIDERS``
    prefix), with the chain limited to that one model (``only_models``), so
    a failure cannot fail over to a cloud model. Yields None when *model* is
    not local: the caller then skips the call (fail closed), never sends it.

        with local_only(settings.llm_model_cheap) as model:
            if model is None:
                return []  # and log why
            await llm.chat(messages, model=model)

    Also reachable as ``ResilientLLM.local_only``, for callers that hold the
    wrapper and import this module lazily (it loads litellm).
    """
    name = (model or "").strip()
    if not name.startswith(LOCAL_PROVIDERS):
        yield None
        return
    with only_models([name]):
        yield name


# How long Ollama holds a model after a request, and with what context size:
# services/llm/local_runtime.py (waking hours: until they end; night: a few minutes).


def _local_model_kwargs(model: str) -> dict[str, Any]:
    """Completion options that only apply to a locally served model.

    Empty for anything hosted elsewhere — a cloud provider handed `keep_alive`
    would at best ignore it, and at worst reject the request.
    """
    if not model.startswith(LOCAL_PROVIDERS):
        return {}

    extra: dict[str, Any] = {"keep_alive": local_runtime.keep_alive()}
    if model.startswith(("ollama/", "ollama_chat/")):
        # The same context size as every other Life Graph request: a different
        # one makes Ollama load a second copy (services/llm/local_runtime.py).
        extra["num_ctx"] = local_runtime.num_ctx()
    if settings.lm_reasoning_effort:
        # A thinking model answers "hi" with 141 tokens of hidden reasoning and
        # 12 of greeting: 1.9s against 0.19s with thinking off, and far worse on
        # a real question. This setting already said it applied to "local chat
        # calls", but only the extraction client ever sent it, so every persona
        # reply paid for reasoning nobody reads. Sent through extra_body so an
        # SDK-side enum cannot reject values like "none".
        extra["extra_body"] = {"reasoning_effort": settings.lm_reasoning_effort}
    return extra


def _bridge_provider_credentials() -> None:
    """Export LIFE_GRAPH_-configured provider creds to the env var names LiteLLM
    expects, so every provider in the fallback chain authenticates.

    Per-provider only — never forward one provider's credentials to another's
    attempt. Idempotent: only sets a var when settings has a value AND the env
    var isn't already set, so repeated construction (e.g. via the `lru_cache`d
    `get_resilient_llm()`) is harmless and an operator's own env wins.

    Gemini's direct API key is intentionally left untouched here: it already
    resolves via ambient `GEMINI_API_KEY` pre-branch. Vertex AI is a separate
    Gemini access path — billed to a different GCP project via a service
    account — so it needs its own credentials bridged, same as OpenRouter.
    """
    if settings.openrouter_api_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.openrouter_url and not os.environ.get("OPENROUTER_API_BASE"):
        os.environ["OPENROUTER_API_BASE"] = settings.openrouter_url
    if settings.nvidia_nim_api_key and not os.environ.get("NVIDIA_NIM_API_KEY"):
        os.environ["NVIDIA_NIM_API_KEY"] = settings.nvidia_nim_api_key

    if settings.vertex_credentials_path and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            Path(settings.vertex_credentials_path).resolve()
        )
    if settings.vertex_project and not os.environ.get("VERTEXAI_PROJECT"):
        os.environ["VERTEXAI_PROJECT"] = settings.vertex_project
    if settings.vertex_location and not os.environ.get("VERTEXAI_LOCATION"):
        os.environ["VERTEXAI_LOCATION"] = settings.vertex_location


# Error classes. BENCHING ones say the model is unwell; the rest say the
# request (or our credentials) was wrong and another model may still serve it.
RATE_LIMIT = "429"
TIMEOUT = "timeout"
SERVER_ERROR = "error"
BAD_REQUEST = "bad_request"
CONTEXT_WINDOW = "context_window"
CONTENT_POLICY = "content_policy"
AUTH = "auth"
BENCHING_KINDS = frozenset({RATE_LIMIT, TIMEOUT, SERVER_ERROR})

# Providers that report an overflow as a plain 400 LiteLLM couldn't map.
_CONTEXT_PHRASES = (
    "context length",
    "context window",
    "context_length_exceeded",
    "maximum context",
    "prompt is too long",
    "too many tokens",
    "input is too long",
)


def classify_error(exc: BaseException) -> str:
    """Put an LLM call failure into one of the classes above.

    LiteLLM's own exception types first (subclasses before their 400 parent),
    then a bare HTTP ``status_code`` for anything else. Unknown → ``error``,
    which benches: an unexplained failure is treated as the model's.
    """
    if isinstance(exc, litellm.ContextWindowExceededError):
        return CONTEXT_WINDOW
    if isinstance(exc, litellm.ContentPolicyViolationError):
        return CONTENT_POLICY
    if isinstance(exc, litellm.RateLimitError):
        return RATE_LIMIT
    if isinstance(exc, (litellm.Timeout, TimeoutError)) or exc.__class__.__name__ in {
        "Timeout",
        "APITimeoutError",
    }:
        return TIMEOUT
    if isinstance(exc, (litellm.AuthenticationError, litellm.PermissionDeniedError)):
        return AUTH
    if isinstance(exc, (litellm.BadRequestError, litellm.UnprocessableEntityError)):
        return _bad_request_kind(exc)
    status = getattr(exc, "status_code", None)
    if status == 429:
        return RATE_LIMIT
    if status in (401, 403):
        return AUTH
    if status in (400, 422):
        return _bad_request_kind(exc)
    return SERVER_ERROR


def _bad_request_kind(exc: BaseException) -> str:
    text = str(exc).lower()
    return CONTEXT_WINDOW if any(p in text for p in _CONTEXT_PHRASES) else BAD_REQUEST


def context_window_of(model: str) -> int | None:
    """Best-known input context size for *model*, or None when unknown.

    Ollama models all run with the one ``num_ctx`` Life Graph asks for
    (services/llm/local_runtime.py), whatever the model could hold; anything
    else comes from LiteLLM's model map, which knows most hosted models.
    """
    if model.startswith(("ollama/", "ollama_chat/")):
        return local_runtime.num_ctx() or None
    try:
        info = litellm.get_model_info(model)
    except Exception:  # noqa: BLE001 - unmapped model: size unknown
        return None
    size = info.get("max_input_tokens") or info.get("max_tokens")
    return int(size) if size else None


def reorder_after(kind: str, failed: str, rest: list[str]) -> list[str]:
    """The rest of the chain, reordered for a request error on *failed*.

    ``context_window``: models known to be larger than *failed* first (chain
    order kept), then models of unknown size, then those known not to be
    larger — they would very likely overflow too. If *failed*'s own size is
    unknown, the chain is left as it is (next model).
    ``content_policy``: models of another provider first, then the same
    provider's. Anything else: unchanged.
    """
    if kind == CONTEXT_WINDOW:
        limit = context_window_of(failed)
        if limit is None:
            return rest
        sizes = {m: context_window_of(m) for m in rest}
        larger = [m for m in rest if (sizes[m] or 0) > limit]
        unknown = [m for m in rest if sizes[m] is None]
        smaller = [m for m in rest if sizes[m] is not None and sizes[m] <= limit]
        return [*larger, *unknown, *smaller]
    if kind == CONTENT_POLICY:
        provider = provider_of(failed)
        if not provider:
            return rest
        others = [m for m in rest if provider_of(m) != provider]
        same = [m for m in rest if provider_of(m) == provider]
        return [*others, *same]
    return rest


def _retry_after(exc: Exception) -> float | None:
    """Extract a Retry-After hint (seconds) from an exception's HTTP response, if any."""
    response = getattr(exc, "response", None)
    try:
        headers = getattr(response, "headers", {}) if response else {}
        ra = headers.get("retry-after") if headers else None
        return float(ra) if ra else None
    except (TypeError, ValueError):
        return None


class ResilientLLM:
    """Ordered failover wrapper around `litellm.acompletion` with health-aware skipping."""

    # See the module-level local_only(): personal data runs on local models only.
    local_only = staticmethod(local_only)

    def __init__(self, health: LLMHealth | None = None) -> None:
        _bridge_provider_credentials()
        self._health = health or LLMHealth()

    def _primary(self, model: str | None, tier: str) -> str:
        """Resolve the caller's model/tier choice into the primary model id."""
        return model or (
            settings.llm_model_expensive if tier == "expensive" else settings.llm_model_cheap
        )

    async def _rank_fallbacks(self, primary: str) -> list[str]:
        """De-dupe the configured fallback pool against `primary`, then sort it by
        health: fewest consecutive failures first, then lowest average latency.
        A model with no recorded history yet sorts as best-case (fair first
        try) rather than being buried behind models with a real track record.
        Ties preserve the pool's original `.env` list order (stable sort).
        """
        seen: set[str] = {primary}
        pool = [m for m in settings.llm_fallback_chain_list if m and not (m in seen or seen.add(m))]
        if not pool:
            return []

        def _rank_key(rec: dict[str, str]) -> tuple[int, float]:
            fails = int(rec.get("consecutive_failures", 0) or 0)
            latency = rec.get("avg_latency_ms")
            return (fails, float(latency) if latency else -1.0)

        # Fetch every candidate's health concurrently instead of one
        # sequential Redis round-trip per model before the primary is even
        # attempted.
        records = await asyncio.gather(*(self._health.get(m) for m in pool))
        keyed = [(_rank_key(rec), m) for m, rec in zip(pool, records, strict=False)]
        keyed.sort(key=lambda pair: pair[0])
        return [m for _, m in keyed]

    @staticmethod
    def _append_last_resorts(chain: list[str]) -> None:
        """Append OmniRoute, then the paid fallback, to the end of *chain*."""
        # OmniRoute's own "auto" combo already prefers subscription/free
        # tiers internally, so it goes before the hard-paid fallback below —
        # tried only once our own free chain is exhausted, but still ahead
        # of the model we've explicitly flagged as a paid last resort.
        if settings.omniroute_api_key and settings.omniroute_model not in chain:
            chain.append(settings.omniroute_model)
        if settings.llm_paid_fallback_model and settings.llm_paid_fallback_model not in chain:
            chain.append(settings.llm_paid_fallback_model)
        elif settings.llm_paid_fallback_model:
            logger.warning(
                "Paid fallback model %s is already present in the free fallback chain; "
                "the 'always last, cost-gated' guarantee does not hold in this configuration",
                settings.llm_paid_fallback_model,
            )

    async def _attempt(self, model: str, messages: list[dict], kwargs: dict) -> Any:
        """Make one live call to `model`, recording success health on return.

        For streaming calls, `litellm.acompletion` returns a lazy stream
        wrapper that makes no real network call until first iterated — so the
        first chunk is pulled here, inside this method (and thus inside the
        caller's try/except in `acompletion()`), to catch connect/first-byte
        failures (bad model id, auth, deprecated model, etc.) as an ordinary
        failure that fails over, instead of letting them surface later,
        unprotected, when the orchestrator iterates the stream itself.
        """
        t0 = time.monotonic()
        # Per attempt, not per call: the chain can start on a local model and
        # fail over to a hosted one, and these options mean nothing there.
        kwargs = {**kwargs, **_local_model_kwargs(model), **_reasoning_kwargs(model)}
        if model == settings.omniroute_model:
            # api_base/api_key passed per-call, not bridged into OPENAI_API_KEY
            # env — that var is also OpenAI's own, and clobbering it would
            # break every other direct-OpenAI call in the process for the
            # sake of one entry in this chain.
            kwargs = {
                **kwargs,
                "api_base": settings.omniroute_url,
                "api_key": settings.omniroute_api_key,
            }
        resp = await litellm.acompletion(model=model, messages=messages, **kwargs)
        if kwargs.get("stream"):
            first_chunk = await resp.__anext__()
            await self._health.record_success(model, (time.monotonic() - t0) * 1000)
            return _rechain(first_chunk, resp)
        await self._health.record_success(model, (time.monotonic() - t0) * 1000)
        return resp

    async def acompletion(
        self, *, messages: list[dict], model: str | None = None, tier: str = "cheap", **kwargs: Any
    ) -> Any:
        """Try models in order (skipping cooling ones), returning the raw LiteLLM response.

        Raises ResilientLLMExhaustedError if every model in the chain fails, including the
        one forced attempt made when all candidates were skipped for being in cooldown.
        """
        primary = self._primary(model, tier)
        allowed = _allowed_fallbacks.get()
        if allowed is not None:
            # only_models(): no global chain, no OmniRoute, no paid fallback.
            chain = [primary, *(m for m in dict.fromkeys(allowed) if m != primary)]
        else:
            chain = [primary, *await self._rank_fallbacks(primary)]
            self._append_last_resorts(chain)
        skipped: list[str] = []
        last_kind: str | None = None
        queue = list(chain)
        while queue:
            m = queue.pop(0)
            # A provider at its daily limit is skipped outright, and is not a
            # candidate for the forced retry below either: that limit is the
            # provider's rule, not a transient cooldown.
            if await _over_quota(m):
                logger.info("Skipping %s: %s is at its daily limit", m, provider_of(m))
                continue
            if await self._health.in_cooldown(m):
                skipped.append(m)
                continue
            if m == settings.llm_paid_fallback_model:
                logger.warning("Falling back to paid model %s", m)
            elif m == settings.omniroute_model and settings.omniroute_api_key:
                logger.warning("Falling back to OmniRoute (%s)", settings.omniroute_url)
            await _count_request(m)
            try:
                return await self._attempt(m, messages, kwargs)
            except Exception as exc:  # noqa: BLE001 - classify + fail over
                last_kind = kind = classify_error(exc)
                if kind not in BENCHING_KINDS:
                    # The request, not the model: no failure count, no cooldown.
                    await self._health.record_request_error(m, kind)
                    queue = reorder_after(kind, m, queue)
                    logger.warning(
                        "Model %s rejected the request (%s); not benched, next: %s",
                        m,
                        kind,
                        queue[0] if queue else "none",
                    )
                    continue
                await self._bench(m, kind, exc)

        # Every model failed or was skipped. If some were only SKIPPED (cooling),
        # force ONE live attempt on the one soonest to recover — don't give up blind.
        if skipped:
            cooldowns = {mm: await _safe_cooldown(self._health, mm) for mm in skipped}
            forced = min(cooldowns, key=cooldowns.__getitem__)
            await _count_request(forced)
            try:
                return await self._attempt(forced, messages, kwargs)
            except Exception as exc:  # noqa: BLE001
                last_kind = kind = classify_error(exc)
                if kind in BENCHING_KINDS:
                    await self._health.record_failure(forced, kind)
                else:
                    await self._health.record_request_error(forced, kind)
        raise ResilientLLMExhaustedError(
            f"All models exhausted: {chain}" + (f" (last error: {last_kind})" if last_kind else "")
        )

    async def _bench(self, model: str, kind: str, exc: Exception) -> None:
        """Record a real failure and cool *model* down (exponential, capped)."""
        fails = await self._health.record_failure(model, kind)
        retry_after = _retry_after(exc) if kind == RATE_LIMIT else None
        if retry_after is not None:
            cd = retry_after
        else:
            base = (
                settings.llm_cooldown_429_seconds
                if kind == RATE_LIMIT
                else settings.llm_cooldown_error_seconds
            )
            cd = min(base * 2 ** (fails - 1), settings.llm_cooldown_max_seconds)
        await self._health.set_cooldown(model, cd)
        logger.warning("Model %s failed (%s); benched %ss (failure #%d)", model, kind, cd, fails)

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        tier: str = "cheap",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        response_format: dict | None = None,
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper over `acompletion` that returns just the response text."""
        opts: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens, **kwargs}
        if response_format:
            opts["response_format"] = response_format
        resp = await self.acompletion(messages=messages, model=model, tier=tier, **opts)
        return resp.choices[0].message.content or ""


async def _rechain(first_chunk: Any, rest: Any) -> AsyncGenerator[Any, None]:
    """Re-yield an already-fetched first chunk, then delegate to the rest of the stream."""
    yield first_chunk
    async for chunk in rest:
        yield chunk


async def _safe_cooldown(health: LLMHealth, model: str) -> float:
    """Resolve a model's cooldown-until timestamp, defaulting to 0.0 on any error."""
    try:
        return await health.cooldown_until(model)
    except Exception:  # pragma: no cover - best-effort: no health store, no cooldown
        return 0.0
