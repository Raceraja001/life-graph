"""ResilientLLM — ordered free-model failover with cooldowns + health recording.

Every completion tries the caller's model first, then the configured free
fallback chain, skipping any model currently in cooldown. A 429 benches a model
for `llm_cooldown_429_seconds` (or its Retry-After); other errors for
`llm_cooldown_error_seconds`. Health is recorded to LLMHealth from real outcomes
— never a probe. When every model is exhausted (or all cooling and the one forced
retry also fails) it raises ResilientLLMExhausted; callers run their own fallback.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import litellm

from life_graph.config import settings
from life_graph.services.llm_health import LLMHealth

logger = logging.getLogger(__name__)


class ResilientLLMExhausted(Exception):
    """Raised when every model in the chain failed or is unavailable."""


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
        self._health = health or LLMHealth()

    def _chain(self, model: str | None, tier: str) -> list[str]:
        """Build the de-duped attempt order: caller's model/tier default, then fallbacks."""
        primary = model or (
            settings.llm_model_expensive if tier == "expensive" else settings.llm_model_cheap
        )
        chain = [primary, *settings.llm_fallback_chain_list]
        seen: set[str] = set()
        return [m for m in chain if m and not (m in seen or seen.add(m))]

    async def _attempt(self, model: str, messages: list[dict], kwargs: dict) -> Any:
        """Make one live call to `model`, recording success health on return."""
        t0 = time.monotonic()
        resp = await litellm.acompletion(model=model, messages=messages, **kwargs)
        await self._health.record_success(model, (time.monotonic() - t0) * 1000)
        return resp

    async def acompletion(
        self, *, messages: list[dict], model: str | None = None, tier: str = "cheap", **kwargs: Any
    ) -> Any:
        """Try models in order (skipping cooling ones), returning the raw LiteLLM response.

        Raises ResilientLLMExhausted if every model in the chain fails, including the
        one forced attempt made when all candidates were skipped for being in cooldown.
        """
        chain = self._chain(model, tier)
        skipped: list[str] = []
        for m in chain:
            if await self._health.in_cooldown(m):
                skipped.append(m)
                continue
            try:
                return await self._attempt(m, messages, kwargs)
            except Exception as exc:  # noqa: BLE001 - classify + fail over
                kind = _classify(exc)
                await self._health.record_failure(m, kind)
                cd = (
                    _retry_after(exc) or settings.llm_cooldown_429_seconds
                    if kind == "429"
                    else settings.llm_cooldown_error_seconds
                )
                await self._health.set_cooldown(m, cd)
                logger.warning("Model %s failed (%s); benched %ss", m, kind, cd)

        # Every model failed or was skipped. If some were only SKIPPED (cooling),
        # force ONE live attempt on the one soonest to recover — don't give up blind.
        if skipped:
            cooldowns = {mm: await _safe_cooldown(self._health, mm) for mm in skipped}
            forced = min(cooldowns, key=cooldowns.get)
            try:
                return await self._attempt(forced, messages, kwargs)
            except Exception as exc:  # noqa: BLE001
                await self._health.record_failure(forced, _classify(exc))
        raise ResilientLLMExhausted(f"All models exhausted: {chain}")

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


async def _safe_cooldown(health: LLMHealth, model: str) -> float:
    """Resolve a model's cooldown-until timestamp, defaulting to 0.0 on any error."""
    try:
        return await health.cooldown_until(model)
    except Exception:  # pragma: no cover
        return 0.0
