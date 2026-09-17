"""FastAPI application entry point — Life Graph.

Brain-inspired memory + agent system with multi-tenant isolation,
service-to-service auth, API versioned under /api/v1/, and middleware pipeline:
  RequestID → Auth → Tenant → RateLimit → Logging
"""

import logging
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from life_graph.api import admin, agent, graph, identity, intentions, memories, search, sessions
from life_graph.api.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    TenantMiddleware,
)
from life_graph.api.multimodal import router as multimodal_router
from life_graph.api.responses import InvalidCursorError, error_response
from life_graph.api.websocket import websocket_endpoint, ws_event_handler
from life_graph.config import settings
from life_graph.core.events import enable_redis_bridge, event_bus
from life_graph.core.logging import setup_logging
from life_graph.core.plugins import PluginManager
from life_graph.storage.database import async_session, engine
from life_graph.storage.redis import check_redis, close_redis, init_redis

# Configure structured logging (JSON in prod, text in dev)
setup_logging(format=settings.log_format, level=settings.log_level)

logger = logging.getLogger(__name__)


# ── Startup step tracking ─────────────────────────────────────


@dataclass
class StartupStep:
    """Outcome of one optional startup step."""

    name: str
    ok: bool
    error: str | None = None

    def as_dict(self) -> dict:
        d: dict = {"status": "ok" if self.ok else "failed"}
        if self.error:
            d["error"] = self.error
        return d


class StartupReport:
    """Records which optional startup steps succeeded.

    Every step in ``lifespan`` is optional by design — a missing Redis or an
    unavailable driver must not stop the process from serving. But each was
    previously wrapped in its own ``try/except`` that logged a warning and
    moved on, so a subsystem that failed to wire itself left no trace anywhere
    a probe could see it: ``/health`` reported "healthy" while the judgment
    engine, the capture processors or the webhook handler were simply absent.

    This records each outcome so ``/health`` can report ``degraded`` and name
    what is missing.
    """

    def __init__(self) -> None:
        self._steps: dict[str, StartupStep] = {}

    def record(self, name: str, ok: bool, error: str | None = None) -> None:
        self._steps[name] = StartupStep(name=name, ok=ok, error=error)

    @property
    def failed(self) -> list[str]:
        return sorted(n for n, s in self._steps.items() if not s.ok)

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict:
        return {name: step.as_dict() for name, step in sorted(self._steps.items())}


@contextmanager
def startup_step(report: StartupReport, name: str):
    """Run one optional startup step, recording success or failure.

    Replaces the bare ``try/except Exception: logger.warning(...)`` blocks.
    Behaviour on failure is unchanged — the exception is logged and startup
    continues — but the outcome is now recorded rather than only logged.
    """
    try:
        yield
    except Exception as e:  # noqa: BLE001 - startup must never abort here
        logger.warning("Startup step %r failed: %s", name, e, exc_info=True)
        report.record(name, ok=False, error=f"{type(e).__name__}: {e}")
    else:
        report.record(name, ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    report = StartupReport()
    app.state.startup_report = report

    # Startup — log environment
    logger.info(
        "Starting Life Graph v%s [%s mode]",
        settings.version,
        settings.environment,
    )
    if settings.is_development:
        logger.warning("Running in DEVELOPMENT mode — auth/tenant requirements relaxed")

    # Startup — refuse to boot with no embedding backend at all.
    #
    # With neither sentence-transformers installed nor a remote backend wired,
    # every embed() call returns an empty vector: ingestion keeps reporting
    # success while semantic search quietly returns nothing. That is the worst
    # failure mode a memory system can have, so it is fatal by default.
    #
    # Deliberately NOT wrapped in startup_step() — that helper swallows
    # exceptions so an optional step can never abort boot, and this one must.
    # It only catches the statically knowable case (no local model, no client);
    # a configured backend that happens to be down still fails at call time.
    from life_graph.api.dependencies import get_embedding_service

    if not get_embedding_service().available:
        msg = (
            "No embedding backend is available — semantic search would silently "
            "return nothing. Install the local extra "
            "(pip install 'life-graph[local-nlp]') or configure a remote backend "
            "(LIFE_GRAPH_USE_LOCAL_LLM=true). To run without embeddings on "
            "purpose, set LIFE_GRAPH_REQUIRE_EMBEDDING_BACKEND=false."
        )
        if settings.require_embedding_backend:
            raise RuntimeError(msg)
        logger.warning("%s — continuing, require_embedding_backend is false", msg)

    # Startup — enable Langfuse tracing via LiteLLM (if configured)
    if settings.langfuse_public_key:
        with startup_step(report, "langfuse_tracing"):
            import litellm

            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]
            logger.info("Langfuse tracing enabled → %s", settings.langfuse_host)

    # Startup — register agent tools (import triggers @tool decorator)
    with startup_step(report, "agent_tools"):
        import life_graph.tools.browser  # noqa: F401
        import life_graph.tools.calculator  # noqa: F401
        import life_graph.tools.code  # noqa: F401
        import life_graph.tools.datetime_tool  # noqa: F401
        import life_graph.tools.delegate  # noqa: F401
        import life_graph.tools.filesystem  # noqa: F401
        import life_graph.tools.git  # noqa: F401
        import life_graph.tools.system_inspect  # noqa: F401
        import life_graph.tools.terminal  # noqa: F401
        import life_graph.tools.web_search  # noqa: F401
        from life_graph.tools.registry import registry

        logger.info("Agent tools registered: %s", registry.tool_names)

        # Capture-spine tool-exhaust observation hook (secret redaction +
        # daily-cap sampling handled inside the hook).
        from life_graph.services.tool_observation import ToolObservationHook

        registry.add_post_exec_hook(ToolObservationHook())
        logger.info("Tool-exhaust observation hook registered")

    # Startup — connect configured external MCP servers (bridge)
    app.state.mcp_exit_stack = AsyncExitStack()
    with startup_step(report, "mcp_bridge"):
        from life_graph.services.mcp_bridge import connect_all

        bridged_count = await connect_all(app.state.mcp_exit_stack)
        logger.info("MCP bridge: %d external tool(s) registered", bridged_count)

    # Startup — load plugins
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
    plugin_manager = PluginManager(event_bus, plugins_dir=plugins_dir)
    plugin_manager.load_all()
    app.state.plugin_manager = plugin_manager
    app.state.event_bus = event_bus
    logger.info(
        "Loaded %d plugin(s): %s",
        len(plugin_manager.loaded),
        list(plugin_manager.loaded.keys()),
    )

    # Startup — wire WebSocket event broadcasting
    event_bus.subscribe_all(ws_event_handler)
    logger.info("WebSocket event handler registered")

    # Startup — Redis
    with startup_step(report, "redis"):
        await init_redis()
        enable_redis_bridge()

    # Startup — wire webhook event handler
    with startup_step(report, "webhook_handler"):
        from life_graph.integrations.webhook import WebhookEventHandler

        webhook_handler = WebhookEventHandler(event_bus)
        webhook_handler.start()
        app.state.webhook_handler = webhook_handler
        logger.info("Webhook event handler started")

        # Wire ARQ pool for async webhook delivery
        with startup_step(report, "webhook_arq_pool"):
            from arq import create_pool

            from life_graph.workers.settings import parse_redis_settings

            arq_pool = await create_pool(parse_redis_settings())
            webhook_handler.set_arq_pool(arq_pool)
            logger.info("Webhook ARQ pool connected")

    # Startup — seed kernel personas for default tenant
    with startup_step(report, "seed_personas"):
        from life_graph.api.dependencies import get_persona_service

        persona_svc = get_persona_service()
        seeded = await persona_svc.seed_builtins("default")
        if seeded:
            # Inserted OR reconciled — seed_builtins logs the breakdown.
            logger.info("Seeded/reconciled %d built-in personas for default tenant", seeded)

    # Startup — seed ambient scheduled jobs for default tenant
    with startup_step(report, "seed_ambient_jobs"):
        from life_graph.api.dependencies import get_scheduler_service
        from life_graph.kernel.ambient import seed_ambient_jobs

        seeded_jobs = await seed_ambient_jobs(get_scheduler_service(), "default")
        if seeded_jobs:
            logger.info("Seeded %d ambient scheduled jobs for default tenant", seeded_jobs)

    # Startup — seed ambient project safety rules + L1 autonomy level (Sub-project B)
    with startup_step(report, "seed_ambient_autonomy"):
        from life_graph.autonomy.safety.ambient_rules import seed_ambient_autonomy

        await seed_ambient_autonomy("default")
        logger.info("Seeded ambient autonomy safety rules + L1 level for default tenant")

    # Startup — wire schedule outcome reconciliation
    with startup_step(report, "scheduler_outcomes"):
        from life_graph.api.dependencies import get_scheduler_service

        # fire_job only enqueues, so a schedule cannot know whether its work
        # succeeded until the task settles. Without this subscription every
        # run stays "dispatched" forever and a permanently failing job is
        # never auto-disabled.
        #
        # get_scheduler_service is @lru_cache(maxsize=1), so this subscribes
        # the same instance the request handlers and the ARQ tick use — the
        # subscription is not stranded on a throwaway object.
        get_scheduler_service().subscribe()
        logger.info("Scheduler outcome reconciliation enabled (via EventBus)")

    # Startup — wire preference → knowledge graph sync
    with startup_step(report, "preference_graph_sync"):
        from life_graph.services.preference_graph import preference_graph_service

        preference_graph_service.subscribe()
        logger.info("Preference graph sync enabled (auto-sync via EventBus)")

    # Startup — wire capture spine processors
    with startup_step(report, "capture_processors"):
        from life_graph.services.capture_processors import capture_processors

        capture_processors.subscribe()
        logger.info("Capture spine processors enabled (extraction + decision detection)")

    # Startup — wire judgment engine
    with startup_step(report, "judgment_engine"):
        from life_graph.services.judgment import judgment_service

        judgment_service.subscribe()
        logger.info("Judgment engine enabled (decision candidate listener)")

    # Startup — wire daily brief -> Web Push delivery
    with startup_step(report, "push_delivery"):
        from life_graph.services.push_delivery import push_delivery_handler

        push_delivery_handler.subscribe()
        logger.info("Web push brief delivery enabled")

    # Startup — wire daily brief -> Telegram delivery
    with startup_step(report, "telegram_delivery"):
        from life_graph.services.telegram_delivery import telegram_delivery_handler

        telegram_delivery_handler.subscribe()
        logger.info("Telegram brief delivery enabled")

    # Startup — wire advisory runs -> notifications/push
    with startup_step(report, "findings_bridge"):
        from life_graph.services.findings_bridge import findings_bridge_handler

        findings_bridge_handler.subscribe()
        logger.info("Ambient findings bridge enabled (web)")

    # Startup — wire ops proposal runs -> autonomy engine, and pending actions -> approvals feed
    with startup_step(report, "autonomous_action_bridges"):
        from life_graph.services.action_proposal_bridge import action_proposal_handler
        from life_graph.services.autonomous_approvals import autonomous_approval_producer

        action_proposal_handler.subscribe()
        autonomous_approval_producer.subscribe()
        logger.info("Autonomous action bridges enabled (web)")

    # Startup — register agent drivers
    with startup_step(report, "agent_drivers"):
        from life_graph.drivers.claude_code import ClaudeCodeDriver
        from life_graph.drivers.local import LocalDriver
        from life_graph.drivers.registry import driver_registry

        driver_registry.register(LocalDriver())
        driver_registry.register(ClaudeCodeDriver())
        logger.info("Agent drivers registered: %s", [d.name for d in driver_registry.list_all()])

    with startup_step(report, "dev_tasks_recovery"):
        from life_graph.services.dev_tasks import fail_interrupted

        interrupted = await fail_interrupted(async_session)
        if interrupted:
            logger.warning("Marked %d interrupted dev task(s) as failed", interrupted)

    with startup_step(report, "dev_outcome_recorder"):
        from life_graph.services.dev_outcomes import dev_outcome_recorder

        # APPROVAL_RESOLVED is emitted by the approvals API in this process.
        dev_outcome_recorder.subscribe()

    app.state.dev_task_queue = None
    with startup_step(report, "dev_task_queue"):
        import asyncio

        from life_graph.services.dev_tasks import run_queue

        # Queued dev tasks (nightly suggestions) run here, where the drivers
        # are registered, one at a time.
        app.state.dev_task_queue = asyncio.create_task(run_queue(async_session))

    if report.failed:
        logger.warning(
            "Startup finished with %d degraded subsystem(s): %s",
            len(report.failed),
            ", ".join(report.failed),
        )
    else:
        logger.info("Startup complete — all %d optional subsystems wired", len(report.as_dict()))

    yield

    # Shutdown — stop the dev task queue runner (an in-flight task is marked
    # failed by fail_interrupted on the next start).
    if app.state.dev_task_queue is not None:
        app.state.dev_task_queue.cancel()

    # Shutdown — close MCP bridge connections
    try:
        await app.state.mcp_exit_stack.aclose()
    except Exception:
        logger.warning("MCP bridge shutdown failed", exc_info=True)

    # Shutdown — close Redis
    await close_redis()

    # Shutdown — close DB
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Brain-inspired memory + agent system. "
    "Multi-tenant, horizontally scalable, with LLM tool-calling, "
    "streaming SSE, and local + cloud hybrid inference.",
    lifespan=lifespan,
)


# ── Global Exception Handlers ────────────────────────────────


@app.exception_handler(InvalidCursorError)
async def invalid_cursor_handler(request: Request, exc: InvalidCursorError) -> JSONResponse:
    """A malformed pagination cursor is client error, not a server fault."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "request_id": getattr(request.state, "request_id", None)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions — return clean JSON, never stack traces."""
    request_id = getattr(request.state, "request_id", "")
    logger.exception("Unhandled exception [rid=%s]: %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content=error_response(
            code="INTERNAL_ERROR",
            message="An internal error occurred.",
            request_id=request_id,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return clean 422 with field-level error details."""
    request_id = getattr(request.state, "request_id", "")
    details = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error.get("loc", []))
        details.append({"field": field, "message": error.get("msg", "")})

    return JSONResponse(
        status_code=422,
        content=error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=details,
            request_id=request_id,
        ),
    )


# ── Middleware stack (applied bottom-to-top) ──────────────────────
# Order of execution: RequestID → Auth → Tenant → RateLimit → Logging
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API v1 Router ─────────────────────────────────────────────
v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(memories.router)
v1_router.include_router(search.router)
v1_router.include_router(intentions.router)
v1_router.include_router(admin.router)
v1_router.include_router(graph.router)
v1_router.include_router(multimodal_router)
v1_router.include_router(sessions.router)
v1_router.include_router(identity.router)
v1_router.include_router(agent.router)
from life_graph.api import memory_links

v1_router.include_router(memory_links.router)

from life_graph.api import procedures

v1_router.include_router(procedures.router)

from life_graph.api import kernel as kernel_api

v1_router.include_router(kernel_api.router)

from life_graph.api import preferences as preferences_api

v1_router.include_router(preferences_api.router)

from life_graph.api import evidence as evidence_api

v1_router.include_router(evidence_api.router)

from life_graph.api import advisor as advisor_api

v1_router.include_router(advisor_api.router)

from life_graph.api import ingest_transcript as ingest_transcript_api

v1_router.include_router(ingest_transcript_api.router)

from life_graph.api import transcript_ingest as transcript_ingest_api

v1_router.include_router(transcript_ingest_api.router)

from life_graph.api import research as research_api

v1_router.include_router(research_api.router)

from life_graph.self_improving import router as self_improving_router

v1_router.include_router(self_improving_router.router)

from life_graph.api import watchers as watchers_api

v1_router.include_router(watchers_api.router)

from life_graph.api import agent_workflows as agent_workflows_api

v1_router.include_router(agent_workflows_api.router)

from life_graph.api import agent_context as agent_context_api

v1_router.include_router(agent_context_api.router)

from life_graph.api import agent_tasks as agent_tasks_api

v1_router.include_router(agent_tasks_api.router)

from life_graph.api import agent_messages as agent_messages_api

v1_router.include_router(agent_messages_api.router)

from life_graph.api import internal_sync as internal_sync_api

v1_router.include_router(internal_sync_api.router)

from life_graph.autonomy.router import router as autonomy_router

v1_router.include_router(autonomy_router)

from life_graph.api import capture as capture_api

v1_router.include_router(capture_api.router)

from life_graph.api import interview as interview_api

v1_router.include_router(interview_api.router)

from life_graph.api import brief as brief_api

v1_router.include_router(brief_api.router)

from life_graph.api import judgment as judgment_api

v1_router.include_router(judgment_api.router)

from life_graph.api import drivers as drivers_api

v1_router.include_router(drivers_api.router)

from life_graph.api import approvals as approvals_api

v1_router.include_router(approvals_api.router)

from life_graph.api import push as push_api

v1_router.include_router(push_api.router)

from life_graph.api import conversations as conversations_api

v1_router.include_router(conversations_api.router)

from life_graph.api import model_health as model_health_api

v1_router.include_router(model_health_api.router)

from life_graph.api import integrations_telegram as telegram_api

v1_router.include_router(telegram_api.router)

app.include_router(v1_router)


# ── WebSocket (root-level, not versioned) ─────────────────────
app.add_api_websocket_route("/ws", websocket_endpoint)

# ── Static files (Brain Viewer dashboard) ─────────────────────
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/brain", StaticFiles(directory=str(static_dir), html=True), name="static")


# ── Root-level endpoints (not versioned) ──────────────────────


@app.get("/")
async def root():
    """Redirect root to the Brain Viewer dashboard."""
    return RedirectResponse(url="/brain/")


from life_graph.api.openapi_examples import HEALTH_CHECK


@app.get("/health", responses=HEALTH_CHECK)
async def health_check():
    """Deep health check — verifies DB and Redis connectivity with latency.

    Returns per-dependency status and latency. HTTP 503 if Postgres
    is unreachable (critical), 200 otherwise (even if Redis is down).
    ``checks.graph`` reports the optional Apache AGE knowledge graph as
    ``enabled`` / ``disabled`` / ``unavailable`` and never affects the 503.
    ``checks.embeddings`` probes the embedding backend (``healthy`` /
    ``unreachable`` / ``unavailable``); a backend that is down degrades the
    overall status but likewise never causes a 503.
    ``checks.telegram`` reports the bridge's poller (``leading`` / ``stopped``
    / ``disabled`` / ``unknown``) as observed through Redis; it affects
    neither the 503 nor the overall status.
    """
    import time

    checks = {}

    # DB check (critical — 503 if down)
    t0 = time.monotonic()
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except Exception as e:
        checks["postgres"] = {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    pg_ok = checks["postgres"]["status"] == "healthy"

    # Redis check (non-critical)
    t0 = time.monotonic()
    redis_status = await check_redis()
    checks["redis"] = {
        "status": "healthy" if redis_status == "ok" else "unhealthy",
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
    }
    if redis_status != "ok":
        checks["redis"]["error"] = redis_status

    # Knowledge graph (non-critical). Apache AGE is a compiled extension that
    # managed Postgres cannot install, so its absence is a supported
    # configuration, not a fault — it never affects the 503 decision below.
    # Probing only once Postgres is known healthy keeps a momentary DB outage
    # from latching the graph off for the rest of the process.
    from life_graph.storage.graph import graph_status

    checks["graph"] = {"status": await graph_status(probe=pg_ok)}

    # Embedding backend (non-critical). Startup refuses to boot when no backend
    # is configured at all, but one that was configured and has since gone down
    # — LM Studio not running, a remote provider unreachable — fails silently:
    # writes keep succeeding while every vector comes back empty and semantic
    # search returns nothing. Probe it so the degradation is visible. It never
    # affects the 503, which stays Postgres-only.
    from life_graph.api.dependencies import get_embedding_service

    t0 = time.monotonic()
    checks["embeddings"] = {
        "status": await get_embedding_service().probe(),
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
    }

    # Telegram bridge (non-critical). The poller runs in the ARQ worker, so
    # this reports what that process published to Redis rather than anything
    # in this one. It never affects the 503 and never degrades the overall
    # status: running the API without the worker is a normal way to develop,
    # and a permanently degraded /health is a health check nobody reads.
    from life_graph.api.integrations_telegram import poller_state

    checks["telegram"] = await poller_state()

    # Startup subsystems — wired once at boot, each optional and each
    # previously failing silently. A subsystem that never subscribed cannot
    # be detected by probing Postgres or Redis, so report it here.
    report: StartupReport | None = getattr(app.state, "startup_report", None)
    if report is None:
        # Lifespan never ran (e.g. bare ASGITransport in tests).
        subsystems: dict = {}
        startup_failures: list[str] = []
    else:
        subsystems = report.as_dict()
        startup_failures = report.failed

    checks["startup"] = {
        "status": "healthy" if not startup_failures else "degraded",
        "total": len(subsystems),
        "failed": startup_failures,
        "subsystems": subsystems,
    }

    # Overall status
    redis_ok = checks["redis"]["status"] == "healthy"
    embeddings_ok = checks["embeddings"]["status"] == "healthy"

    if not pg_ok:
        # Postgres is the only critical dependency — everything else degrades.
        overall = "unhealthy"
    elif redis_ok and embeddings_ok and not startup_failures:
        overall = "healthy"
    else:
        overall = "degraded"

    from fastapi.responses import JSONResponse

    body = {
        "status": overall,
        "version": settings.version,
        "environment": settings.environment,
        "checks": checks,
    }
    status_code = 503 if overall == "unhealthy" else 200
    return JSONResponse(content=body, status_code=status_code)


@app.get("/live")
async def liveness():
    """Kubernetes liveness probe — always returns 200 if process is running."""
    return {"status": "alive"}


@app.get("/ready")
async def readiness():
    """Kubernetes readiness probe — returns 200 only when DB is reachable."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from starlette.responses import Response as StarletteResponse

    from life_graph.core.metrics import get_metrics_content_type, get_metrics_text

    return StarletteResponse(
        content=get_metrics_text(),
        media_type=get_metrics_content_type(),
    )
