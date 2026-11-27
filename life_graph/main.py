"""FastAPI application entry point — Life Graph.

Brain-inspired memory + agent system with multi-tenant isolation,
service-to-service auth, API versioned under /api/v1/, and middleware pipeline:
  RequestID → Auth → Tenant → RateLimit → Logging
"""

import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from life_graph.api import admin, agent, graph, identity, intentions, memories, search, sessions
from life_graph.api.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    TenantMiddleware,
)
from life_graph.api.multimodal import router as multimodal_router
from life_graph.api.responses import InvalidCursorError, error_response, http_error_body
from life_graph.api.websocket import (
    start_relay,
    stop_relay,
    websocket_endpoint,
    ws_event_handler,
)
from life_graph.config import settings
from life_graph.core.errors import DomainError
from life_graph.core.events import enable_redis_bridge, event_bus
from life_graph.core.logging import setup_logging
from life_graph.core.plugins import PluginManager
from life_graph.core.startup_guards import (
    check_auth_exposure,
    langfuse_env,
    langfuse_tracing_allowed,
)
from life_graph.runtime import close_arq_pool, get_arq_pool
from life_graph.storage.database import async_session
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


async def _step_durable_authorization(app: FastAPI, report: StartupReport) -> None:
    # The owner's authority moves into Postgres before anything that can
    # issue or verify a mandate runs. Attaching is unconditional once the
    # setting is on and needs no probe: each operation reconnects and fails
    # closed on its own (autonomy/approvals/durable_store.py), so a database
    # that is down at boot does not leave this process minting in-memory
    # capabilities that no other worker can resolve.
    if settings.durable_authorization:
        with startup_step(report, "durable_authorization"):
            from life_graph.autonomy.approvals.durable_store import attach_durable_stores

            attach_durable_stores()
            logger.info("Authorization store: durable (capabilities, standing_rules)")


async def _step_agent_tools(app: FastAPI, report: StartupReport) -> None:
    # Startup — register agent tools (import triggers @tool decorator)
    with startup_step(report, "agent_tools"):
        from life_graph.tools.load import register_all
        from life_graph.tools.registry import registry

        logger.info("Agent tools registered: %s", register_all())

        # Capture-spine tool-exhaust observation hook (secret redaction +
        # daily-cap sampling handled inside the hook).
        from life_graph.services.tool_observation import ToolObservationHook

        registry.add_post_exec_hook(ToolObservationHook())
        logger.info("Tool-exhaust observation hook registered")


async def _step_mcp_bridge(app: FastAPI, report: StartupReport) -> None:
    # Startup — connect configured external MCP servers (bridge)
    with startup_step(report, "mcp_bridge"):
        from life_graph.services.mcp_bridge import connect_all

        bridged_count = await connect_all(app.state.mcp_exit_stack)
        logger.info("MCP bridge: %d external tool(s) registered", bridged_count)


async def _step_connectors(app: FastAPI, report: StartupReport) -> None:
    # Startup — connectors (calendar, email): discover plugins, register tools
    if settings.connectors_enabled:
        with startup_step(report, "connectors"):
            from life_graph.connectors.runtime import get_runtime
            from life_graph.connectors.tools import register_tools

            get_runtime()
            register_tools()


async def _step_webhook_handler(app: FastAPI, report: StartupReport) -> None:
    # Startup — wire webhook event handler
    with startup_step(report, "webhook_handler"):
        from life_graph.integrations.webhook import WebhookEventHandler

        webhook_handler = WebhookEventHandler(event_bus)
        webhook_handler.start()
        app.state.webhook_handler = webhook_handler
        logger.info("Webhook event handler started")

        # Wire ARQ pool for async webhook delivery
        with startup_step(report, "webhook_arq_pool"):
            # The process's shared pool (runtime.get_arq_pool), closed below.
            arq_pool = await get_arq_pool()
            webhook_handler.set_arq_pool(arq_pool)
            logger.info("Webhook ARQ pool connected")


async def _step_seed_personas(app: FastAPI, report: StartupReport) -> None:
    # Every seeded tenant, not just "default" (this and the two seed steps
    # after it). A tenant with no rows in action_safety_rules is not an
    # unconfigured tenant that falls back to something sensible — the
    # classifier calls an action it cannot match dangerous, so such a tenant
    # can do nothing autonomously and the logs never mention it.
    # LIFE_GRAPH_SEED_TENANTS is the list.
    seed_tenants = settings.seed_tenants_list
    # Startup — seed kernel personas
    with startup_step(report, "seed_personas"):
        from life_graph.runtime import get_persona_service

        persona_svc = get_persona_service()
        for tenant in seed_tenants:
            seeded = await persona_svc.seed_builtins(tenant)
            if seeded:
                # Inserted OR reconciled — seed_builtins logs the breakdown.
                logger.info("Seeded/reconciled %d built-in personas for tenant=%s", seeded, tenant)
        # Every other tenant that already has personas gets new built-ins and
        # prompt fixes too; otherwise only "default" ever saw them.
        from sqlalchemy import distinct, select

        from life_graph.models.db import AgentPersona

        async with async_session() as session:
            persona_tenants = (
                (await session.execute(select(distinct(AgentPersona.tenant_id)))).scalars().all()
            )
        for persona_tenant in persona_tenants:
            if persona_tenant and persona_tenant not in seed_tenants:
                n = await persona_svc.seed_builtins(persona_tenant)
                if n:
                    logger.info("Seeded/reconciled %d built-in personas for %s", n, persona_tenant)


async def _step_seed_ambient_jobs(app: FastAPI, report: StartupReport) -> None:
    seed_tenants = settings.seed_tenants_list
    # Startup — seed ambient scheduled jobs
    with startup_step(report, "seed_ambient_jobs"):
        from life_graph.kernel.ambient import seed_ambient_jobs
        from life_graph.runtime import get_scheduler_service

        for tenant in seed_tenants:
            seeded_jobs = await seed_ambient_jobs(get_scheduler_service(), tenant)
            if seeded_jobs:
                logger.info("Seeded %d ambient scheduled jobs for tenant=%s", seeded_jobs, tenant)


async def _step_seed_ambient_autonomy(app: FastAPI, report: StartupReport) -> None:
    seed_tenants = settings.seed_tenants_list
    # Startup — seed ambient project safety rules + L1 autonomy level (Sub-project B)
    with startup_step(report, "seed_ambient_autonomy"):
        from life_graph.autonomy.safety.ambient_rules import seed_ambient_autonomy

        for tenant in seed_tenants:
            await seed_ambient_autonomy(tenant)
            logger.info("Seeded ambient autonomy safety rules + L1 level for tenant=%s", tenant)


async def _step_scheduler_outcomes(app: FastAPI, report: StartupReport) -> None:
    # Startup — wire schedule outcome reconciliation
    with startup_step(report, "scheduler_outcomes"):
        from life_graph.runtime import get_scheduler_service

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


async def _step_event_subscribers(app: FastAPI, report: StartupReport) -> None:
    """The EventBus listeners: judgment, brief delivery, approvals, findings, autonomy."""
    # Startup — wire judgment engine
    with startup_step(report, "judgment_engine"):
        from life_graph.services.judgment import judgment_service

        judgment_service.subscribe()
        logger.info("Judgment engine enabled (decision candidate listener)")

    # Startup — wire daily brief -> Web Push delivery
    with startup_step(report, "push_delivery"):
        from life_graph.services.notifications.push_delivery import push_delivery_handler

        push_delivery_handler.subscribe()
        logger.info("Web push brief delivery enabled")

    # Startup — wire daily brief -> Telegram delivery
    with startup_step(report, "telegram_delivery"):
        from life_graph.services.notifications.telegram_delivery import telegram_delivery_handler

        telegram_delivery_handler.subscribe()
        logger.info("Telegram brief delivery enabled")

    # Startup — wire a filed approval (driver_pr/merge/plan/deploy/...) -> push/Telegram
    with startup_step(report, "approval_notifications"):
        from life_graph.services.notifications.approval import approval_notification_handler

        approval_notification_handler.subscribe()
        logger.info("Approval-filed notifications enabled")

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


async def _step_agent_drivers(app: FastAPI, report: StartupReport) -> None:
    # Startup — register agent drivers
    with startup_step(report, "agent_drivers"):
        from life_graph.drivers.setup import register_default_drivers

        logger.info("Agent drivers registered: %s", register_default_drivers())


async def _step_adopted_models(app: FastAPI, report: StartupReport) -> None:
    # Free models adopted through a model_adoption approval join the cloud
    # model list (services/llm/offers.py, compute_router.set_adopted).
    with startup_step(report, "adopted_models"):
        from life_graph.services.llm.offers import refresh_adopted
        from life_graph.storage.database import async_session as _session

        async with _session() as session:
            adopted = await refresh_adopted(session)
        if adopted:
            logger.info("Adopted free models: %s", adopted)


async def _step_kernel_tasks_recovery(app: FastAPI, report: StartupReport) -> None:
    # Chat turns and persona runs die with the process that ran them; their
    # rows would stay queued/running for ever. Every process may run this:
    # it only touches rows far past their own timeout (kernel/recovery.py),
    # so it cannot fail a run the ARQ worker or another API is still doing.
    with startup_step(report, "kernel_tasks_recovery"):
        from life_graph.kernel.recovery import fail_interrupted_kernel_tasks

        await fail_interrupted_kernel_tasks(async_session)


async def _step_dev_task_runner_lock(app: FastAPI, report: StartupReport) -> None:
    # Only the process holding the runner lock recovers and runs dev tasks, so
    # a second instance on the same database (a preview from another worktree)
    # can neither claim queued tasks nor fail the real runner's in-flight one.
    app.state.dev_task_runner_lock = None
    with startup_step(report, "dev_task_runner_lock"):
        from life_graph.services.dev.tasks import acquire_runner_lock
        from life_graph.storage.database import engine

        if settings.dev_task_runner_mode == "worker":
            # The dedicated worker (python -m life_graph.workers.dev_runner)
            # holds the lock and runs tasks; this API only queues and inspects.
            logger.info("Dev tasks run in the dedicated worker (dev_task_runner_mode=worker)")
        elif settings.dev_task_runner_enabled:
            app.state.dev_task_runner_lock = await acquire_runner_lock(engine)
            if app.state.dev_task_runner_lock is None:
                logger.warning(
                    "Another Life Graph process is the dev-task runner for this "
                    "database; this one will not recover or run dev tasks"
                )
        else:
            logger.info("Dev-task runner disabled (LIFE_GRAPH_DEV_TASK_RUNNER_ENABLED=false)")


def _is_dev_task_runner(app: FastAPI) -> bool:
    return app.state.dev_task_runner_lock is not None


async def _step_dev_tasks_recovery(app: FastAPI, report: StartupReport) -> None:
    is_dev_task_runner = _is_dev_task_runner(app)
    with startup_step(report, "dev_tasks_recovery"):
        from life_graph.services.dev.tasks import fail_interrupted

        if is_dev_task_runner:
            interrupted = await fail_interrupted(async_session)
            if interrupted:
                logger.warning("Marked %d interrupted dev task(s) as failed", interrupted)


async def _step_dev_task_runtime_sweep(app: FastAPI, report: StartupReport) -> None:
    is_dev_task_runner = _is_dev_task_runner(app)
    with startup_step(report, "dev_task_runtime_sweep"):
        # After recovery, so the tasks it just re-queued count as not running:
        # their containers, networks and staged tokens are leftovers now.
        if is_dev_task_runner:
            from life_graph.services.dev.task_runtime import sweep_orphans

            await sweep_orphans(async_session)


async def _step_dev_recorders(app: FastAPI, report: StartupReport) -> None:
    with startup_step(report, "dev_outcome_recorder"):
        from life_graph.services.dev.outcomes import dev_outcome_recorder

        # APPROVAL_RESOLVED is emitted by the approvals API in this process.
        dev_outcome_recorder.subscribe()

    with startup_step(report, "trajectory_recorder"):
        from life_graph.services.dev.trajectories import trajectory_recorder

        # driver:steps is emitted by the dispatcher, in whichever process runs
        # the dev task: that is this one, the runner-lock holder.
        trajectory_recorder.subscribe()


async def _step_dev_task_queue(app: FastAPI, report: StartupReport) -> None:
    is_dev_task_runner = _is_dev_task_runner(app)
    app.state.dev_task_queue = None
    with startup_step(report, "dev_task_queue"):
        import asyncio

        from life_graph.services.dev.tasks import run_queue

        # Queued dev tasks (nightly suggestions) run here, where the drivers
        # are registered, one at a time.
        if is_dev_task_runner:
            app.state.dev_task_queue = asyncio.create_task(
                run_queue(async_session, app.state.dev_task_runner_lock)
            )
        elif settings.dev_task_runner_mode != "worker" and settings.dev_task_runner_enabled:
            # Lost the lock race at startup: keep trying, so start buttons
            # don't depend on whichever process happened to win.
            app.state.dev_task_standby = asyncio.create_task(_dev_runner_standby(app))


# The extended-domain startup, in the order it has always run (it was one
# 260-line function, moved out of ``lifespan`` unchanged on 2026-10-29 and
# split into these steps on 2026-11-20, audit M15). Order matters: tools
# before the MCP bridge adds to them, personas before the jobs that run as
# them, the runner lock before recovery, the sweep and the queue that only
# its holder may run. tests/unit/test_startup_steps.py pins the sequence of
# recorded step names.
_EXTENDED_STARTUP: tuple[Callable[[FastAPI, StartupReport], Awaitable[None]], ...] = (
    _step_durable_authorization,
    _step_agent_tools,
    _step_mcp_bridge,
    _step_connectors,
    _step_webhook_handler,
    _step_seed_personas,
    _step_seed_ambient_jobs,
    _step_seed_ambient_autonomy,
    _step_scheduler_outcomes,
    _step_event_subscribers,
    _step_agent_drivers,
    _step_adopted_models,
    _step_kernel_tasks_recovery,
    _step_dev_task_runner_lock,
    _step_dev_tasks_recovery,
    _step_dev_task_runtime_sweep,
    _step_dev_recorders,
    _step_dev_task_queue,
)


async def _start_extended_domains(app: FastAPI, report: StartupReport) -> None:
    """Startup for the domains beyond the memory engine (profile ``full``).

    Each step records its own outcome(s) on *report*; a failed step is logged
    and startup carries on, as it always has (see :func:`startup_step`).
    """
    for step in _EXTENDED_STARTUP:
        await step(app, report)


async def _dev_runner_standby(app: FastAPI) -> None:
    """API mode, lock held elsewhere: take over as the runner when it is free."""
    import asyncio

    from life_graph.services.dev.task_runtime import sweep_orphans
    from life_graph.services.dev.tasks import acquire_runner_lock, fail_interrupted, run_queue
    from life_graph.storage.database import async_session, engine

    while True:
        await asyncio.sleep(30)
        try:
            conn = await acquire_runner_lock(engine)
        except Exception:
            logger.debug("Dev-task runner lock retry failed", exc_info=True)
            continue
        if conn is None:
            continue
        logger.warning("This API process is now the dev-task runner")
        app.state.dev_task_runner_lock = conn
        await fail_interrupted(async_session)
        await sweep_orphans(async_session)
        app.state.dev_task_queue = asyncio.create_task(run_queue(async_session, conn))
        return


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

    # Startup — refuse to serve unauthenticated requests beyond this machine
    # (audit M5). Fatal, so deliberately NOT wrapped in startup_step().
    check_auth_exposure()

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
    from life_graph.runtime import get_embedding_service

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

    # Startup — enable Langfuse tracing via LiteLLM (if configured). Every
    # prompt goes to langfuse_host, so only a self-hosted one is accepted
    # unless langfuse_allow_remote is set (core/startup_guards.py).
    if langfuse_tracing_allowed(settings):
        with startup_step(report, "langfuse_tracing"):
            import litellm

            # LiteLLM reads the host and keys from the environment only.
            os.environ.update(langfuse_env(settings))
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]
            logger.info("Langfuse tracing enabled → %s", settings.langfuse_host)

    app.state.mcp_exit_stack = AsyncExitStack()
    # Startup — Life Graph's own MCP tools over HTTP at /mcp/ (api/mcp_http.py);
    # its session manager runs for the app's lifetime and closes with the stack.
    if mcp_http_app is not None:
        with startup_step(report, "mcp_http"):
            await app.state.mcp_exit_stack.enter_async_context(mcp_http_app.lifespan(app))
            logger.info("MCP over HTTP at /mcp/")

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

    # Startup — Redis. The relay sends what ws_event_handler publishes to Redis
    # on to this process's sockets (api/websocket.py start_subscriber).
    app.state.ws_relay = None
    with startup_step(report, "redis"):
        await init_redis()
        enable_redis_bridge()
        app.state.ws_relay = start_relay()

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

    # Startup — owner-only approvals: warn when turning them on would leave no
    # way in but Telegram (no owner key, no paired phone). Counts only.
    with startup_step(report, "approvals_owner_check"):
        from life_graph.services.owner_enforcement import check_at_startup
        from life_graph.storage.database import async_session as owner_check_session

        await check_at_startup(owner_check_session)

    # Everything beyond the memory engine (docs/modular_memory_service_plan.md):
    # agent tools and drivers, personas, the ARQ pool, delivery handlers, the
    # dev-task runner. Only in the full profile; memory_core serves memory alone.
    app.state.dev_task_runner_lock = None
    app.state.dev_task_queue = None
    if settings.is_full_profile:
        await _start_extended_domains(app, report)
    else:
        logger.info("Profile memory_core: extended domains not started")

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
        # Let the cancellation finish (agent processes/containers killed,
        # runtimes torn down) before the lock is released below.
        import asyncio

        await asyncio.wait([app.state.dev_task_queue], timeout=30)
    standby = getattr(app.state, "dev_task_standby", None)
    if standby is not None:
        standby.cancel()
    if app.state.dev_task_runner_lock is not None:
        from life_graph.services.dev.tasks import release_runner_lock

        try:
            await release_runner_lock(app.state.dev_task_runner_lock)
        except Exception:
            logger.warning("Closing the dev-task runner lock failed", exc_info=True)

    # Shutdown — close MCP bridge connections
    try:
        await app.state.mcp_exit_stack.aclose()
    except Exception:
        logger.warning("MCP bridge shutdown failed", exc_info=True)

    # Shutdown — close the shared arq pool, then Redis

    await close_arq_pool()
    await stop_relay(app.state.ws_relay)
    await close_redis()

    # Shutdown — close DB
    from life_graph.storage.database import engine

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


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Every ``HTTPException`` answers in the documented error envelope (audit M2).

    ``detail`` stays at the top level as well, unchanged, for the clients that
    read FastAPI's original ``{"detail": ...}`` shape.
    """
    if exc.status_code in (204, 304):  # no body allowed, as Starlette's default
        return Response(status_code=exc.status_code, headers=exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        content=http_error_body(
            exc.status_code, exc.detail, getattr(request.state, "request_id", None)
        ),
        headers=exc.headers,
    )


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Domain exceptions (core/errors.py) map to 404/409/400 by type (audit L3)."""
    return JSONResponse(
        status_code=exc.status_code,
        content=http_error_body(
            exc.status_code,
            str(exc),
            getattr(request.state, "request_id", None),
            code=exc.code,
        ),
    )


@app.exception_handler(InvalidCursorError)
async def invalid_cursor_handler(request: Request, exc: InvalidCursorError) -> JSONResponse:
    """A malformed pagination cursor is client error, not a server fault."""
    return JSONResponse(
        status_code=422,
        content=http_error_body(
            422, str(exc), getattr(request.state, "request_id", None), code="INVALID_CURSOR"
        ),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions — return clean JSON, never stack traces."""
    request_id = getattr(request.state, "request_id", "")
    logger.exception("Unhandled exception [rid=%s]: %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content=http_error_body(
            500, "An internal error occurred.", request_id, code="INTERNAL_ERROR"
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

    content = error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        details=details,
        request_id=request_id,
    )
    # Same top-level ``detail`` as every other error (a string, so clients
    # that show ``detail`` show the same message as ``error.message``).
    content["detail"] = content["error"]["message"]
    return JSONResponse(status_code=422, content=content)


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
# Two tiers (docs/modular_memory_service_plan.md). Tier 1, the memory engine,
# always registers. Tier 2, every other domain, registers only with
# LIFE_GRAPH_PROFILE=full; its modules are not even imported otherwise.
v1_router = APIRouter(prefix="/api/v1")

# ── Tier 1: core memory engine ──
# memories, search, preferences, identity, capture, graph and health, plus what
# the MCP memory tools call: sessions (start/end_session), memory links,
# intentions (set_intention) and the Claude Code transcript intake.
from life_graph.api import capture as capture_api
from life_graph.api import health as health_api
from life_graph.api import ingest_transcript as ingest_transcript_api
from life_graph.api import memory_links
from life_graph.api import memory_page as memory_page_api
from life_graph.api import preferences as preferences_api
from life_graph.api import transcript_ingest as transcript_ingest_api

# Before memories.router: its GET /memories/{memory_id} would take /memories/overview.
v1_router.include_router(memory_page_api.router)
v1_router.include_router(memories.router)
v1_router.include_router(search.router)
v1_router.include_router(intentions.router)
v1_router.include_router(graph.router)
v1_router.include_router(sessions.router)
v1_router.include_router(identity.router)
v1_router.include_router(memory_links.router)
v1_router.include_router(preferences_api.router)
v1_router.include_router(ingest_transcript_api.router)
v1_router.include_router(transcript_ingest_api.router)
v1_router.include_router(capture_api.router)
v1_router.include_router(health_api.router)

# ── Tier 2: extended domains (profile "full") ──
if settings.is_full_profile:
    from life_graph.api import advisor as advisor_api
    from life_graph.api import agent_accounts as agent_accounts_api
    from life_graph.api import agent_context as agent_context_api
    from life_graph.api import agent_messages as agent_messages_api
    from life_graph.api import agent_tasks as agent_tasks_api
    from life_graph.api import agent_workflows as agent_workflows_api
    from life_graph.api import approvals as approvals_api
    from life_graph.api import assistant as assistant_api
    from life_graph.api import brief as brief_api
    from life_graph.api import connectors as connectors_api
    from life_graph.api import context as context_api
    from life_graph.api import conversations as conversations_api

    # The phone app (docs/design/12_android_app_plan.md): pairing, and the only
    # endpoints a device token opens.
    from life_graph.api import devices as devices_api
    from life_graph.api import drivers as drivers_api
    from life_graph.api import evidence as evidence_api
    from life_graph.api import integrations_telegram as telegram_api
    from life_graph.api import internal_sync as internal_sync_api
    from life_graph.api import interview as interview_api
    from life_graph.api import jarvis as jarvis_api
    from life_graph.api import judgment as judgment_api
    from life_graph.api import kernel as kernel_api
    from life_graph.api import llm_offers as llm_offers_api
    from life_graph.api import model_health as model_health_api
    from life_graph.api import observability as observability_api
    from life_graph.api import procedures
    from life_graph.api import push as push_api
    from life_graph.api import research as research_api
    from life_graph.api import skills as skills_api
    from life_graph.api import vault as vault_api
    from life_graph.api import watchers as watchers_api
    from life_graph.api import web_research as web_research_api
    from life_graph.autonomy.router import router as autonomy_router
    from life_graph.self_improving import router as self_improving_router

    v1_router.include_router(admin.router)
    v1_router.include_router(multimodal_router)
    v1_router.include_router(agent.router)
    v1_router.include_router(procedures.router)
    v1_router.include_router(skills_api.router)
    v1_router.include_router(kernel_api.router)
    v1_router.include_router(observability_api.router)
    v1_router.include_router(evidence_api.router)
    v1_router.include_router(advisor_api.router)
    v1_router.include_router(research_api.router)
    v1_router.include_router(self_improving_router.router)
    v1_router.include_router(watchers_api.router)
    v1_router.include_router(agent_workflows_api.router)
    v1_router.include_router(agent_context_api.router)
    v1_router.include_router(agent_tasks_api.router)
    v1_router.include_router(agent_messages_api.router)
    v1_router.include_router(internal_sync_api.router)
    v1_router.include_router(autonomy_router)
    v1_router.include_router(interview_api.router)
    v1_router.include_router(brief_api.router)
    v1_router.include_router(judgment_api.router)
    v1_router.include_router(connectors_api.router)
    v1_router.include_router(drivers_api.router)
    v1_router.include_router(agent_accounts_api.router)
    v1_router.include_router(approvals_api.router)
    v1_router.include_router(push_api.router)
    v1_router.include_router(conversations_api.router)
    v1_router.include_router(model_health_api.router)
    v1_router.include_router(telegram_api.router)
    v1_router.include_router(assistant_api.router)
    v1_router.include_router(llm_offers_api.router)
    v1_router.include_router(web_research_api.router)
    v1_router.include_router(devices_api.router)
    v1_router.include_router(jarvis_api.router)
    v1_router.include_router(vault_api.router)
    # M8 Stage 1: read-only context snapshot (services/memory/snapshot.py).
    v1_router.include_router(context_api.router)

app.include_router(v1_router)


# ── WebSocket (root-level, not versioned) ─────────────────────
app.add_api_websocket_route("/ws", websocket_endpoint)

# ── MCP over HTTP (opt-in; behind AuthMiddleware like the API) ─
mcp_http_app = None
if settings.mcp_http_enabled:
    from life_graph.api.mcp_http import build_app as build_mcp_http_app

    mcp_http_app = build_mcp_http_app()
    app.mount("/mcp", mcp_http_app)

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
    except Exception:
        # /health is unauthenticated: the driver's message can carry the DB
        # host, user and role names, so it goes to the log, not the body.
        logger.exception("Health check: Postgres probe failed")
        checks["postgres"] = {
            "status": "unhealthy",
            "error": "database unreachable",
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
        # check_redis returns "error: <exception text>"; keep only the kind.
        if redis_status.startswith("error"):
            logger.warning("Health check: Redis probe failed: %s", redis_status)
            redis_status = "error"
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
    from life_graph.runtime import get_embedding_service

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
        "edition": settings.edition or None,
        "profile": settings.profile,
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
