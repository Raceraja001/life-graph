"""Sliding window rate limiter using Redis sorted sets.

Implements a per-tenant rate limiter with configurable limits
based on tenant plan tier. Uses Redis ZSET with timestamps
as scores for precise sliding window calculation.
"""

from __future__ import annotations

import logging
import time

from life_graph.config import settings
from life_graph.storage.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimitResult:
    """Result of a rate limit check."""

    __slots__ = ("allowed", "limit", "remaining", "reset_at")

    def __init__(self, allowed: bool, limit: int, remaining: int, reset_at: int):
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at

    @property
    def headers(self) -> dict[str, str]:
        """Rate limit headers for HTTP response."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset_at),
        }


async def check_rate_limit(
    tenant_id: str,
    resource: str = "requests",
    window_seconds: int = 60,
) -> RateLimitResult:
    """Check if a request is within the tenant's rate limit.

    Uses a Redis sorted set (ZSET) as a sliding window counter.
    Each request is stored as a member with its timestamp as score.
    Expired entries are pruned on each check.

    Args:
        tenant_id: The tenant making the request.
        resource: Rate limit bucket name (e.g., "requests", "ask").
        window_seconds: Sliding window duration in seconds.

    Returns:
        RateLimitResult with allowed status and remaining quota.
    """
    redis = get_redis()

    # Get plan limits
    plan_limits = settings.get_plan_limits(tenant_id)

    if resource == "ask":
        limit = plan_limits.get("max_ask_per_day", 50)
        window_seconds = 86400  # 24 hours for ask
    else:
        limit = plan_limits.get("requests_per_min", 60)

    # 0 = unlimited
    if limit == 0:
        return RateLimitResult(allowed=True, limit=0, remaining=999999, reset_at=0)

    # No Redis → allow (degraded mode)
    if not redis:
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_at=0)

    now = time.time()
    window_start = now - window_seconds
    key = f"ratelimit:{tenant_id}:{resource}"
    reset_at = int(now) + window_seconds

    try:
        pipe = redis.pipeline(transaction=True)
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add this request
        pipe.zadd(key, {f"{now}": now})
        # Set TTL on the key
        pipe.expire(key, window_seconds + 10)

        results = await pipe.execute()
        current_count = results[1]  # zcard result

        remaining = limit - current_count - 1  # -1 for this request
        allowed = current_count < limit

        if not allowed:
            logger.warning(
                "Rate limit exceeded: tenant=%s resource=%s count=%d limit=%d",
                tenant_id, resource, current_count, limit,
            )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    except Exception:
        logger.exception("Rate limit check failed, allowing request")
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_at=0)


async def get_usage_count(tenant_id: str, resource: str = "requests") -> int:
    """Get current request count for a tenant within the window."""
    redis = get_redis()
    if not redis:
        return 0

    now = time.time()
    key = f"ratelimit:{tenant_id}:{resource}"

    try:
        # Count entries in the last minute
        return await redis.zcount(key, now - 60, now)
    except Exception:
        return 0
