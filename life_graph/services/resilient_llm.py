"""ResilientLLM — ordered free-model failover with cooldowns + health recording.

Every completion tries the caller's model first, then the configured free
fallback chain, skipping any model currently in cooldown. A 429 benches a model
for `llm_cooldown_429_seconds` (or its Retry-After); other errors for
`llm_cooldown_error_seconds`. Health is recorded to LLMHealth from real outcomes
— never a probe. When every model is exhausted (or all cooling and the one forced
retry also fails) it raises ResilientLLMExhaustedError; callers run their own fallback.
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
    from collections.abc import AsyncGenerator

from life_graph.config import settings
from life_graph.services.llm_health import LLMHealth

logger = logging.getLogger(__name__)


class ResilientLLMExhaustedError(Exception):
    """Raised when every model in the chain failed or is unavailable."""


# When set, the only models a completion may fail over to (see only_models).
_allowed_fallbacks: contextvars.ContextVar[tuple[str, ...] | None] = contextvars.ContextVar(
    "resilient_llm_allowed_fallbacks", default=None
)


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

# How long Ollama holds a model after a request, and with what context size:
# services/local_runtime.py (waking hours: until they end; night: a few minutes).


def _local_model_kwargs(model: str) -> dict[str, Any]:
    """Completion options that only apply to a locally served model.

    Empty for anything hosted elsewhere — a cloud provider handed `keep_alive`
    would at best ignore it, and at worst reject the request.
    """
    if not model.startswith(LOCAL_PROVIDERS):
        return {}

    from life_graph.services import local_runtime

    extra: dict[str, Any] = {"keep_alive": local_runtime.keep_alive()}
    if model.startswith(("ollama/", "ollama_chat/")):
        # The same context size as every other Life Graph request: a different
        # one makes Ollama load a second copy (services/local_runtime.py).
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


def _classify(exc: Exception) -> str:
    """Classify an LLM call failure into a cooldown/health-recording bucket."""
    if isinstance(exc, litellm.RateLimitError):
        return "429"
    if isinstance(exc, litellm.Timeout) or exc.__class__.__name__ in {
        "Timeout",
        "APITimeoutError",
    }:
        return "timeout"
    return "error"


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
        for m in chain:
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
                kind = _classify(exc)
                fails = await self._health.record_failure(m, kind)
                retry_after = _retry_after(exc) if kind == "429" else None
                if retry_after is not None:
                    cd = retry_after
                else:
                    base = (
                        settings.llm_cooldown_429_seconds
                        if kind == "429"
                        else settings.llm_cooldown_error_seconds
                    )
                    cd = min(base * 2 ** (fails - 1), settings.llm_cooldown_max_seconds)
                await self._health.set_cooldown(m, cd)
                logger.warning(
                    "Model %s failed (%s); benched %ss (failure #%d)", m, kind, cd, fails
                )

        # Every model failed or was skipped. If some were only SKIPPED (cooling),
        # force ONE live attempt on the one soonest to recover — don't give up blind.
        if skipped:
            cooldowns = {mm: await _safe_cooldown(self._health, mm) for mm in skipped}
            forced = min(cooldowns, key=cooldowns.get)
            await _count_request(forced)
            try:
                return await self._attempt(forced, messages, kwargs)
            except Exception as exc:  # noqa: BLE001
                await self._health.record_failure(forced, _classify(exc))
        raise ResilientLLMExhaustedError(f"All models exhausted: {chain}")

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
    except Exception:  # pragma: no cover
        return 0.0
