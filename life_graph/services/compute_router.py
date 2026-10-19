"""Where a queued coding task runs right now: the local GPU, a free cloud model, or later.

One 16 GB GPU serves both the user's speech models (tamil-ai's gemma3, whisper)
and the coding agents (gpt-oss:20b, qwen3-coder:30b). The user's rules
(2026-10-19):

* while he is active the GPU is his, so queued coding tasks go to a free cloud
  model or wait; while he is away they run locally as before;
* code may go to a free cloud model, personal data never does (the cloud
  driver, drivers/cloud.py, strips it);
* never paid: when the free models are rate-limited the task waits for the GPU.

:func:`decide` is pure and takes a :class:`Snapshot`; :func:`snapshot` gathers
the facts (presence switch, recent activity, loaded speech models, free RAM,
which free cloud models have a key and whether they are cooling down).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select

from life_graph.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Free local personas the router may move. Anything else (claude_code
# personas, the cloud persona itself) runs as assigned.
LOCAL_CODE_PERSONAS = frozenset({"code-fixer-local", "code-fixer-opencode"})
OPENCODE_PERSONA = "code-fixer-opencode"
CLOUD_PERSONA = "code-fixer-cloud"

PRESENCE_MODES = ("auto", "active", "away")
_PRESENCE_KEY = "lg:presence:{tenant_id}"
_CLOUD_COOLDOWN_KEY = "lg:cloud_route_cooldown"

# Capture surfaces only a person produces (tamil-ai posts "voice").
_PERSON_SURFACES = ("voice", "telegram")

Where = Literal["as_assigned", "local", "cloud", "wait"]


def is_free_cloud_model(model: str | None) -> bool:
    """True for a hosted model that costs nothing: OpenRouter ``:free`` ids and
    NVIDIA's build.nvidia.com API (``nvidia_nim/``)."""
    if not model:
        return False
    m = model.lower()
    return (m.startswith("openrouter/") and m.endswith(":free")) or m.startswith("nvidia_nim/")


def _has_key(model: str) -> bool:
    if model.lower().startswith("openrouter/"):
        return bool(settings.openrouter_api_key)
    if model.lower().startswith("nvidia_nim/"):
        return bool(settings.nvidia_nim_api_key)
    return False


def cloud_models() -> list[str]:
    """The configured free cloud coding models whose provider has a key."""
    return [m for m in settings.dev_cloud_models_list if is_free_cloud_model(m) and _has_key(m)]


def in_local_hours(hour: int, spec: str) -> bool:
    """Whether *hour* (0-23) falls in a ``"start-end"`` window like ``"23-7"``.

    An empty spec means any hour. A malformed one also means any hour, with a
    warning: a typo must not stop local work for good.
    """
    if not spec.strip():
        return True
    try:
        start, end = (int(p) % 24 for p in spec.split("-", 1))
    except ValueError:
        logger.warning("dev_local_hours %r is not 'start-end'; ignoring it", spec)
        return True
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def free_memory_gb(meminfo: Path = Path("/proc/meminfo")) -> float | None:
    """MemAvailable in GB, or None where /proc/meminfo is not readable."""
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        return None
    return None


async def speech_in_use() -> str | None:
    """The name of a loaded speech model in Ollama, or None.

    Ollama keeps a model loaded for its keep_alive after the last request, so
    "loaded" already means "used recently".
    """
    fragments = settings.speech_models_list
    if not fragments:
        return None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_api_base.rstrip('/')}/api/ps")
            resp.raise_for_status()
            models = resp.json().get("models") or []
    except Exception:  # noqa: BLE001 - Ollama down means no speech model loaded
        return None
    for m in models:
        name = str(m.get("name") or m.get("model") or "")
        if any(f in name.lower() for f in fragments):
            return name
    return None


async def get_presence(tenant_id: str) -> dict[str, Any]:
    """The manual switch: ``{"mode": auto|active|away, "expires_in": seconds|None}``."""
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return {"mode": "auto", "expires_in": None}
    try:
        key = _PRESENCE_KEY.format(tenant_id=tenant_id)
        raw = await redis.get(key)
        mode = raw.decode() if isinstance(raw, bytes) else raw
        if mode not in PRESENCE_MODES:
            return {"mode": "auto", "expires_in": None}
        ttl = await redis.ttl(key)
        return {"mode": mode, "expires_in": ttl if ttl and ttl > 0 else None}
    except Exception:  # noqa: BLE001
        logger.warning("Could not read the presence switch", exc_info=True)
        return {"mode": "auto", "expires_in": None}


async def set_presence(tenant_id: str, mode: str, minutes: int | None = None) -> bool:
    """Set the manual switch; ``auto`` clears it. False when Redis is unavailable."""
    from life_graph.storage.redis import get_redis

    if mode not in PRESENCE_MODES:
        raise ValueError(f"mode must be one of {PRESENCE_MODES}")
    redis = get_redis()
    if redis is None:
        return False
    key = _PRESENCE_KEY.format(tenant_id=tenant_id)
    if mode == "auto":
        await redis.delete(key)
    elif minutes:
        await redis.set(key, mode, ex=int(minutes) * 60)
    else:
        await redis.set(key, mode)
    return True


async def cloud_cooling() -> bool:
    """True while the free cloud route is benched after a rate limit."""
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return False
    try:
        return bool(await redis.exists(_CLOUD_COOLDOWN_KEY))
    except Exception:  # noqa: BLE001
        return False


async def cool_cloud_route(seconds: int | None = None) -> None:
    """Bench the free cloud route (its models were exhausted)."""
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.set(
            _CLOUD_COOLDOWN_KEY, "1", ex=seconds or settings.cloud_rate_limit_cooldown_seconds
        )
    except Exception:  # noqa: BLE001
        logger.warning("Could not bench the cloud route", exc_info=True)


async def last_activity(session: AsyncSession, tenant_id: str) -> tuple[datetime | None, str]:
    """When the user last did something only a person does, and where.

    His own chat messages, Telegram (the bot's binding is touched on every
    message) and voice captures. Agent and MCP surfaces are not counted.
    """
    from life_graph.models.db import CaptureEvent, ConversationMessage, TelegramBinding

    queries = {
        "chat": select(func.max(ConversationMessage.created_at)).where(
            ConversationMessage.tenant_id == tenant_id, ConversationMessage.role == "user"
        ),
        "telegram": select(func.max(TelegramBinding.last_seen_at)).where(
            TelegramBinding.tenant_id == tenant_id
        ),
        "voice": select(func.max(CaptureEvent.created_at)).where(
            CaptureEvent.tenant_id == tenant_id, CaptureEvent.surface.in_(_PERSON_SURFACES)
        ),
    }
    latest: datetime | None = None
    where = ""
    for name, query in queries.items():
        at = (await session.execute(query)).scalar()
        if at is not None and at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        if at is not None and (latest is None or at > latest):
            latest, where = at, name
    return latest, where


@dataclass(frozen=True)
class Snapshot:
    """The facts a routing decision is made from."""

    active: str | None  # why the user counts as active, or None if away
    local_hours: bool  # inside dev_local_hours
    free_gb: float | None  # MemAvailable; None = unknown
    cloud: tuple[str, ...]  # usable free cloud models (empty when benched)


@dataclass(frozen=True)
class Route:
    """Where one task runs: ``persona`` is the persona to run it as."""

    where: Where
    persona: str
    reason: str


async def snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    now: datetime | None = None,
) -> Snapshot:
    """Gather the routing facts for one tenant."""
    now = now or datetime.now(UTC)
    active: str | None = None
    switch = (await get_presence(tenant_id))["mode"]
    if switch == "active":
        active = "switch says active"
    elif switch == "auto":
        speech = await speech_in_use()
        if speech:
            active = f"{speech} is loaded"
        else:
            async with session_factory() as session:
                at, where = await last_activity(session, tenant_id)
            window = timedelta(minutes=settings.user_active_minutes)
            if at is not None and now - at < window:
                active = f"{where} {int((now - at).total_seconds() // 60)} min ago"
    try:
        hour = now.astimezone(ZoneInfo(settings.user_timezone)).hour
    except Exception:  # noqa: BLE001 - unknown zone: fall back to UTC
        hour = now.hour
    models = () if await cloud_cooling() else tuple(cloud_models())
    return Snapshot(
        active=active,
        local_hours=in_local_hours(hour, settings.dev_local_hours),
        free_gb=free_memory_gb(),
        cloud=models,
    )


def decide(persona: str, properties: dict[str, Any] | None, snap: Snapshot) -> Route:
    """Route one queued task from the facts in *snap*.

    Only the free local personas move. A task someone started and an API
    restart re-queued (``interactive``) stays as it was asked for, and
    ``local_only`` keeps a task off the cloud.
    """
    props = properties or {}
    if not settings.dev_route_queue or persona not in LOCAL_CODE_PERSONAS:
        return Route("as_assigned", persona, "not routed")
    if props.get("interactive"):
        return Route("as_assigned", persona, "started by a person")

    if snap.active:
        why = f"you are active ({snap.active})"
    elif not snap.local_hours:
        why = f"outside local hours {settings.dev_local_hours}"
    elif (
        persona == OPENCODE_PERSONA
        and snap.free_gb is not None
        and snap.free_gb < settings.opencode_min_free_gb
    ):
        why = f"only {snap.free_gb:.1f} GB RAM free for OpenCode"
    else:
        return Route("local", persona, "you are away")

    if snap.cloud and not props.get("local_only"):
        return Route("cloud", CLOUD_PERSONA, f"{why}; free cloud model")
    missing = "kept local" if props.get("local_only") else "no free cloud model available"
    return Route("wait", persona, f"{why}; {missing}")
