"""ARQ worker settings for Life Graph background tasks.

Run the worker with:
    arq life_graph.workers.settings.WorkerSettings

Or via the Dockerfile:
    CMD ["arq", "life_graph.workers.settings.WorkerSettings"]
"""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from life_graph.config import settings


def parse_redis_settings() -> RedisSettings:
    """Parse LIFE_GRAPH_REDIS_URL into ARQ RedisSettings."""
    url = settings.redis_url
    # redis://host:port/db
    if url.startswith("redis://"):
        url = url[8:]
    parts = url.split("/")
    host_port = parts[0]
    db = int(parts[1]) if len(parts) > 1 else 0

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 6379

    return RedisSettings(host=host, port=port, database=db)


class WorkerSettings:
    """ARQ worker configuration.

    Defines available task functions and cron schedules.
    The worker runs as a separate process from the API server.
    """

    redis_settings = parse_redis_settings()

    # Import task functions lazily to avoid circular imports
    functions = [
        "life_graph.workers.tasks.run_tenant_consolidation",
        "life_graph.workers.tasks.run_all_consolidations",
        "life_graph.workers.tasks.run_tenant_merge_suggestions",
        "life_graph.workers.tasks.run_all_merge_suggestions",
        "life_graph.workers.decay.run_decay_sweep",
        "life_graph.workers.decay.run_all_decay_sweeps",
        "life_graph.workers.embeddings.generate_embeddings_batch",
        "life_graph.workers.reembed.reembed_all",
        "life_graph.integrations.webhook.deliver_webhook",
        "life_graph.workers.tasks.run_all_research",
        "life_graph.workers.tasks.run_nightly_self_heal",
        "life_graph.workers.tasks.run_watchers",
        "life_graph.workers.tasks.run_daily_digest",
        "life_graph.workers.tasks.decay_trust_scores",
        "life_graph.workers.tasks.check_approval_timeouts",
        "life_graph.workers.tasks.send_approval_escalations",
        "life_graph.workers.tasks.run_daily_brief",
        "life_graph.workers.tasks.failure_pattern_mining",
    ]

    cron_jobs = [
        cron(
            "life_graph.workers.tasks.run_all_consolidations",
            hour=3,
            minute=0,
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.tasks.run_all_merge_suggestions",
            hour=3,
            minute=45,
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.decay.run_all_decay_sweeps",
            hour=4,
            minute=0,
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.tasks.run_all_research",
            weekday=6,
            hour=2,
            minute=0,
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.tasks.run_nightly_self_heal",
            hour=3,
            minute=30,
            run_at_startup=False,
        ),
        # ── Watcher Framework (Era 6) ────────────────────
        cron(
            "life_graph.workers.tasks.run_watchers",
            hour={0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
            minute=0,
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.tasks.run_daily_digest",
            hour=8,
            minute=0,
            run_at_startup=False,
        ),
        # ── Autonomous AI (Era 8) ────────────────────────
        cron(
            "life_graph.workers.tasks.decay_trust_scores",
            hour=5,
            minute=0,
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.tasks.check_approval_timeouts",
            hour={0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=False,
        ),
        cron(
            "life_graph.workers.tasks.send_approval_escalations",
            hour={0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
            minute={0, 30},
            run_at_startup=False,
        ),
        # ── Capture Spine: Daily Brief (Phase G) ─────────
        cron(
            "life_graph.workers.tasks.run_daily_brief",
            hour=settings.brief_hour_utc,
            minute=0,
            run_at_startup=False,
        ),
        # ── Judgment Engine: Monthly Failure-Pattern Mining (Phase H) ──
        cron(
            "life_graph.workers.tasks.failure_pattern_mining",
            day=1,
            hour=2,
            minute=30,
            run_at_startup=False,
        ),
    ]

    # Worker config
    max_jobs = 5
    job_timeout = 600  # 10 minutes max per job
    retry_jobs = True
    max_tries = 3
