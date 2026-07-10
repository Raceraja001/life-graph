"""Prometheus metrics for Life Graph observability.

Exposes counters, histograms, and gauges for monitoring
API performance, LLM latency, and tenant-level usage.

Usage:
    from life_graph.core.metrics import track_request, get_metrics_text

    # Track a request
    track_request(method="POST", path="/memories/", status=201, duration=0.15)

    # Expose metrics
    @app.get("/metrics")
    def metrics():
        return Response(get_metrics_text(), media_type="text/plain")
"""

from __future__ import annotations

import logging
import time

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Metrics (only if prometheus_client is installed) ──────────

if PROMETHEUS_AVAILABLE:
    # Request metrics
    REQUEST_COUNT = Counter(
        "lg_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    REQUEST_DURATION = Histogram(
        "lg_request_duration_seconds",
        "Request latency in seconds",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    # LLM metrics
    LLM_DURATION = Histogram(
        "lg_llm_duration_seconds",
        "LLM call latency in seconds",
        ["provider", "model", "operation"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    )
    LLM_TOKENS = Counter(
        "lg_llm_tokens_total",
        "Total LLM tokens used",
        ["provider", "model"],
    )

    # Business metrics
    MEMORIES_CREATED = Counter(
        "lg_memories_created_total",
        "Total memories created",
        ["tenant_id"],
    )
    ACTIVE_SESSIONS = Gauge(
        "lg_active_sessions",
        "Currently active sessions",
        ["tenant_id"],
    )
    WS_CONNECTIONS = Gauge(
        "lg_ws_connections",
        "Active WebSocket connections",
    )


def track_request(
    method: str, path: str, status: int, duration: float
) -> None:
    """Record request metrics."""
    if not PROMETHEUS_AVAILABLE:
        return
    # Normalize path to remove IDs for cardinality control
    normalized = _normalize_path(path)
    REQUEST_COUNT.labels(method=method, path=normalized, status=str(status)).inc()
    REQUEST_DURATION.labels(method=method, path=normalized).observe(duration)


def track_llm_call(
    provider: str, model: str, operation: str, duration: float, tokens: int = 0
) -> None:
    """Record LLM call metrics."""
    if not PROMETHEUS_AVAILABLE:
        return
    LLM_DURATION.labels(provider=provider, model=model, operation=operation).observe(
        duration
    )
    if tokens > 0:
        LLM_TOKENS.labels(provider=provider, model=model).inc(tokens)


def track_memory_created(tenant_id: str) -> None:
    """Increment memory creation counter."""
    if not PROMETHEUS_AVAILABLE:
        return
    MEMORIES_CREATED.labels(tenant_id=tenant_id).inc()


def get_metrics_text() -> bytes:
    """Generate Prometheus text format metrics."""
    if not PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n"
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get the Prometheus content type header."""
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"
    return CONTENT_TYPE_LATEST


def _normalize_path(path: str) -> str:
    """Normalize path for metric labels — replace UUIDs with :id."""
    import re

    # Replace UUID segments
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        ":id",
        path,
    )
    return path
