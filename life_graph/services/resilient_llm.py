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
import logging
import os
import time
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
        chain = [primary, *await self._rank_fallbacks(primary)]
        if settings.llm_paid_fallback_model and settings.llm_paid_fallback_model not in chain:
            chain.append(settings.llm_paid_fallback_model)
        elif settings.llm_paid_fallback_model:
            logger.warning(
                "Paid fallback model %s is already present in the free fallback chain; "
                "the 'always last, cost-gated' guarantee does not hold in this configuration",
                settings.llm_paid_fallback_model,
            )
        skipped: list[str] = []
        for m in chain:
            if await self._health.in_cooldown(m):
                skipped.append(m)
                continue
            if m == settings.llm_paid_fallback_model:
                logger.warning("Falling back to paid model %s", m)
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
