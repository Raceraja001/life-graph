"""Redis connection pool for shared state across instances.

Provides async Redis client for rate limiting, WebSocket pub/sub,
metering counters, and job queue coordination.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis

from life_graph.config import settings

logger = logging.getLogger(__name__)

# Module-level pool — created once, shared across requests
_pool: aioredis.ConnectionPool | None = None
_redis: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Initialize the Redis connection pool.

    Called during application startup. Creates a connection pool
    from the configured Redis URL.
    """
    global _pool, _redis

    _pool = aioredis.ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,
        decode_responses=True,
    )
    _redis = aioredis.Redis(connection_pool=_pool)

    # Verify connectivity
    try:
        await _redis.ping()
        logger.info("Redis connected: %s", settings.redis_url)
    except Exception:
        logger.warning(
            "Redis not available at %s — rate limiting and pub/sub will be disabled",
            settings.redis_url,
        )

    return _redis


async def close_redis() -> None:
    """Close the Redis connection pool. Called during shutdown."""
    global _pool, _redis

    if _redis:
        await _redis.close()
        _redis = None
    if _pool:
        await _pool.disconnect()
        _pool = None
    logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis | None:
    """Get the shared Redis client.

    Returns None if Redis hasn't been initialized or connection failed.
    Callers should handle None gracefully (degraded mode).
    """
    return _redis


async def get_redis_dependency() -> AsyncGenerator[aioredis.Redis | None, None]:
    """FastAPI dependency for Redis client."""
    yield _redis


async def check_redis() -> str:
    """Health check — returns 'ok' or error description."""
    if not _redis:
        return "not_configured"
    try:
        await _redis.ping()
        return "ok"
    except Exception as e:
        return f"error: {e}"
