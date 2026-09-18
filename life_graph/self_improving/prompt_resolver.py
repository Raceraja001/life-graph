"""Resolve the prompt a task should run with: the active version, or the default.

This is what makes an optimized prompt *matter*. prompt_versions existed, and
could be created and activated through the API, but no production code ever
read them — every task ran its hardcoded prompt, so a "deployed" improvement
changed nothing. Tasks now ask here first and fall back to their built-in
prompt when no version is active, when the lookup fails, or when the kill
switch (``self_improving_prompts_enabled``) is off.

Lookups are cached per (tenant, task) for a minute: extraction runs on every
capture, and a DB round-trip per call to learn "nothing changed" would be
waste. Activation paths call ``invalidate`` so a deploy or rollback takes
effect on the next call rather than after the TTL.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_VERSION_ID = "default"
_CACHE_TTL_SECONDS = 60.0
_cache: dict[tuple[str, str], tuple[float, ResolvedPrompt | None]] = {}


@dataclass(frozen=True)
class ResolvedPrompt:
    """The prompt a task runs with, and which version it came from."""

    version_id: str
    prompt_text: str
    few_shot: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_default(self) -> bool:
        return self.version_id == DEFAULT_VERSION_ID


def invalidate(tenant_id: str | None = None, task_type: str | None = None) -> None:
    """Drop cached lookups — all of them, or one (tenant, task)."""
    if tenant_id is None:
        _cache.clear()
    else:
        _cache.pop((tenant_id, task_type or ""), None)


async def resolve_prompt(
    tenant_id: str | None, task_type: str, default_text: str
) -> ResolvedPrompt:
    """Return the active version for (tenant, task), or the built-in prompt.

    Never raises: a failed lookup must not break the task that asked.
    """
    from life_graph.config import settings

    default = ResolvedPrompt(DEFAULT_VERSION_ID, default_text)
    if not settings.self_improving_prompts_enabled or not tenant_id:
        return default

    key = (tenant_id, task_type)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1] or default

    try:
        version = await _load_active(tenant_id, task_type)
    except Exception:
        logger.warning(
            "Prompt version lookup failed for %s/%s", tenant_id, task_type, exc_info=True
        )
        return default

    _cache[key] = (now + _CACHE_TTL_SECONDS, version)
    return version or default


async def load_version(version_id: str, default_text: str) -> ResolvedPrompt:
    """Load a specific version by id (``"default"`` means the built-in prompt).

    Used by evals, which must run a candidate that is not active.
    """
    if version_id == DEFAULT_VERSION_ID:
        return ResolvedPrompt(DEFAULT_VERSION_ID, default_text)

    import uuid

    from life_graph.self_improving.models import PromptVersion
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = await session.get(PromptVersion, uuid.UUID(str(version_id)))
    if row is None:
        raise ValueError(f"prompt version {version_id} not found")
    return ResolvedPrompt(str(row.id), row.prompt_text, list(row.few_shot_examples or []))


async def _load_active(tenant_id: str, task_type: str) -> ResolvedPrompt | None:
    from sqlalchemy import select

    from life_graph.self_improving.models import PromptVersion
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = (
            await session.execute(
                select(PromptVersion).where(
                    PromptVersion.tenant_id == tenant_id,
                    PromptVersion.task_type == task_type,
                    PromptVersion.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    if row is None:
        return None
    return ResolvedPrompt(str(row.id), row.prompt_text, list(row.few_shot_examples or []))
