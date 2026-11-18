"""LLMHealth — a best-effort, fail-open record of free-LLM backend health.

Written from real call outcomes (never a probe). Stored in Redis so the API and
worker processes share one view. Every method degrades to a no-op / "not cooling"
when Redis is unavailable, so the resilience path never breaks on a Redis fault.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.storage.redis import get_redis

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_KEY = "llm:health:{model}"
_EMA_ALPHA = 0.3  # weight of the newest latency sample


class LLMHealth:
    """Per-model health hash in Redis; all ops best-effort."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time

    def _key(self, model: str) -> str:
        return _KEY.format(model=model)

    async def _read(self, model: str) -> dict[str, str]:
        r = get_redis()
        if r is None:
            return {}
        try:
            return await r.hgetall(self._key(model))
        except Exception:  # pragma: no cover - fail-open
            logger.debug("LLMHealth read failed for %s", model, exc_info=True)
            return {}

    async def _write(self, model: str, mapping: dict[str, Any]) -> None:
        r = get_redis()
        if r is None:
            return
        try:
            await r.hset(self._key(model), mapping={k: str(v) for k, v in mapping.items()})
            ttl_seconds = getattr(settings, "llm_health_ttl_seconds", 3600)
            await r.expire(self._key(model), ttl_seconds)
        except Exception:  # pragma: no cover - fail-open
            logger.debug("LLMHealth write failed for %s", model, exc_info=True)

    async def record_success(self, model: str, latency_ms: float) -> None:
        prev = await self._read(model)
        prev_lat = float(prev.get("avg_latency_ms", latency_ms) or latency_ms)
        ema = _EMA_ALPHA * latency_ms + (1 - _EMA_ALPHA) * prev_lat
        await self._write(
            model,
            {
                "last_success_at": self._clock(),
                "avg_latency_ms": round(ema, 1),
                "consecutive_failures": 0,
                "cooldown_until": 0,
            },
        )

    async def record_failure(self, model: str, kind: str) -> int:
        """Record a failure and return the model's updated consecutive-failure count."""
        prev = await self._read(model)
        fails = int(prev.get("consecutive_failures", 0) or 0) + 1
        await self._write(
            model,
            {"last_failure_at": self._clock(), "last_error": kind, "consecutive_failures": fails},
        )
        return fails

    async def set_cooldown(self, model: str, seconds: float) -> None:
        await self._write(model, {"cooldown_until": self._clock() + seconds})

    async def in_cooldown(self, model: str) -> bool:
        rec = await self._read(model)
        try:
            return float(rec.get("cooldown_until", 0) or 0) > self._clock()
        except (TypeError, ValueError):  # pragma: no cover
            return False

    async def cooldown_until(self, model: str) -> float:
        rec = await self._read(model)
        try:
            return float(rec.get("cooldown_until", 0) or 0)
        except (TypeError, ValueError):  # pragma: no cover
            return 0.0

    async def get(self, model: str) -> dict[str, str]:
        """Return a model's raw health record (empty dict if unknown or Redis is down)."""
        return await self._read(model)

    async def snapshot(self) -> list[dict]:
        r = get_redis()
        if r is None:
            return []
        try:
            keys = await r.keys("llm:health:*")
        except Exception:  # pragma: no cover - fail-open
            return []
        out: list[dict] = []
        now = self._clock()
        for key in keys:
            model = (key.decode() if isinstance(key, bytes) else key).removeprefix("llm:health:")
            rec = await self._read(model)
            if not rec:
                continue
            cooldown_until = float(rec.get("cooldown_until", 0) or 0)
            last_success = float(rec.get("last_success_at", 0) or 0)
            last_failure = float(rec.get("last_failure_at", 0) or 0)
            if cooldown_until > now:
                state = "cooling"
            elif last_success >= last_failure and last_success > 0:
                state = "up"
            elif last_failure > 0:
                state = "down"
            else:
                state = "unknown"
            out.append(
                {
                    "model": model,
                    "state": state,
                    "last_success_at": last_success or None,
                    "last_failure_at": last_failure or None,
                    "last_error": rec.get("last_error"),
                    "avg_latency_ms": float(rec.get("avg_latency_ms", 0) or 0) or None,
                    "cooldown_until": cooldown_until or None,
                }
            )
        return out
