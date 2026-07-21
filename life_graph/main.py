"""FastAPI application entry point — Life Graph.

Brain-inspired memory + agent system with multi-tenant isolation,
service-to-service auth, API versioned under /api/v1/, and middleware pipeline:
  RequestID → Auth → Tenant → RateLimit → Logging
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from life_graph.api import admin, graph, intentions, memories, search
from life_graph.api import sessions, identity, agent
from life_graph.api.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    TenantMiddleware,
)
from life_graph.api.multimodal import router as multimodal_router
from life_graph.api.responses import error_response
from life_graph.api.websocket import websocket_endpoint, ws_event_handler, ws_manager
from life_graph.config import settings
from life_graph.core.events import event_bus, enable_redis_bridge
from life_graph.core.plugins import PluginManager
from life_graph.storage.database import engine, async_session
from life_graph.storage.redis import init_redis, close_redis, check_redis


from life_graph.core.logging import setup_logging

# Configure structured logging (JSON in prod, text in dev)
setup_logging(format=settings.log_format, level=settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup — log environment
    logger.info(
        "Starting Life Graph v%s [%s mode]",
        settings.version,
        settings.environment,
    )
    if settings.is_development:
        logger.warning("Running in DEVELOPMENT mode — auth/tenant requirements relaxed")

    # Startup — enable Langfuse tracing via LiteLLM (if configured)
    if settings.langfuse_public_key:
        try:
            import litellm
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]
            logger.info("Langfuse tracing enabled → %s", settings.langfuse_host)
        except Exception:
            logger.warning("Failed to enable Langfuse tracing")

    # Startup — register agent tools (import triggers @tool decorator)
    try:
        import life_graph.tools.calculator  # noqa: F401
        import life_graph.tools.datetime_tool  # noqa: F401
        import life_graph.tools.web_search  # noqa: F401
        import life_graph.tools.terminal  # noqa: F401
        import life_graph.tools.git  # noqa: F401
        import life_graph.tools.browser  # noqa: F401
        from life_graph.tools.registry import registry
        logger.info("Agent tools registered: %s", registry.tool_names)

        # Capture-spine tool-exhaust observation hook (secret redaction +
        # daily-cap sampling handled inside the hook).
        from life_graph.services.tool_observation import ToolObservationHook
        registry.add_post_exec_hook(ToolObservationHook())
        logger.info("Tool-exhaust observation hook registered")
    except Exception:
        logger.warning("Failed to register agent tools", exc_info=True)

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
    try:
        await init_redis()
        enable_redis_bridge()
    except Exception:
        logger.warning("Redis not available — rate limiting/pub-sub disabled", exc_info=True)

    # Startup — wire webhook event handler
    try:
        from life_graph.integrations.webhook import WebhookEventHandler
        webhook_handler = WebhookEventHandler(event_bus)
        webhook_handler.start()
        app.state.webhook_handler = webhook_handler
        logger.info("Webhook event handler started")

        # Wire ARQ pool for async webhook delivery
        try:
            from arq import create_pool
            from life_graph.workers.settings import parse_redis_settings
            arq_pool = await create_pool(parse_redis_settings())
            webhook_handler.set_arq_pool(arq_pool)
            logger.info("Webhook ARQ pool connected")
        except Exception:
            logger.warning("ARQ pool not available — webhooks will log but not deliver", exc_info=True)
    except Exception:
        logger.warning("Webhook handler not available", exc_info=True)

    # Startup — seed kernel personas for default tenant
    try:
        from life_graph.api.dependencies import get_persona_service
        persona_svc = get_persona_service()
        seeded = await persona_svc.seed_builtins("default")
        if seeded:
            logger.info("Seeded %d built-in personas for default tenant", seeded)
    except Exception:
        logger.warning("Failed to seed kernel personas", exc_info=True)

    # Startup — wire preference → knowledge graph sync
    try:
        from life_graph.services.preference_graph import preference_graph_service
        preference_graph_service.subscribe()
        logger.info("Preference graph sync enabled (auto-sync via EventBus)")
    except Exception:
        logger.warning("Preference graph sync not available", exc_info=True)

    # Startup — wire capture spine processors
    try:
        from life_graph.services.capture_processors import capture_processors
        capture_processors.subscribe()
        logger.info("Capture spine processors enabled (extraction + decision detection)")
    except Exception:
        logger.warning("Capture spine processors not available", exc_info=True)

    # Startup — wire judgment engine
    try:
        from life_graph.services.judgment import judgment_service
        judgment_service.subscribe()
        logger.info("Judgment engine enabled (decision candidate listener)")
    except Exception:
        logger.warning("Judgment engine not available", exc_info=True)

    # Startup — register agent drivers
    try:
        from life_graph.drivers.registry import driver_registry
        from life_graph.drivers.local import LocalDriver
        from life_graph.drivers.claude_code import ClaudeCodeDriver
        driver_registry.register(LocalDriver())
        driver_registry.register(ClaudeCodeDriver())
        logger.info("Agent drivers registered: %s", [d.name for d in driver_registry.list_all()])
    except Exception:
        logger.warning("Agent drivers not available", exc_info=True)

    yield

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

    # Redis check (non-critical)
    t0 = time.monotonic()
    redis_status = await check_redis()
    checks["redis"] = {
        "status": "healthy" if redis_status == "ok" else "unhealthy",
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
    }
    if redis_status != "ok":
        checks["redis"]["error"] = redis_status

    # Overall status
    pg_ok = checks["postgres"]["status"] == "healthy"
    redis_ok = checks["redis"]["status"] == "healthy"

    if pg_ok and redis_ok:
        overall = "healthy"
    elif pg_ok:
        overall = "degraded"
    else:
        overall = "unhealthy"

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
    from life_graph.core.metrics import get_metrics_text, get_metrics_content_type

    return StarletteResponse(
        content=get_metrics_text(),
        media_type=get_metrics_content_type(),
    )
