"""Agent Drivers API — list drivers, view stats, test dispatch.

Prefix: /kernel/drivers
Tags: [drivers]
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kernel/drivers", tags=["drivers"])


# ── Pydantic Schemas ─────────────────────────────────────────


class DriverInfo(BaseModel):
    """Summary of a registered driver."""

    name: str
    available: bool
    capabilities: list[str]
    cost_per_task: float
    billing: str = "api"
    # Readiness detail from drivers that probe a CLI (codex, gemini): enabled,
    # installed, binary, version, logged_in, hint. None for the others.
    detail: dict | None = None


class DriverStatResponse(BaseModel):
    """Driver performance statistics."""

    driver_name: str
    success_count: int = 0
    failure_count: int = 0
    total_tasks: int = 0
    success_rate: float = 0.0
    total_cost_usd: float = 0.0
    avg_cost_usd: float = 0.0
    total_duration_ms: int = 0
    avg_duration_ms: int = 0
    last_used_at: datetime | None = None


class DispatchRequest(BaseModel):
    """Request body for test dispatch."""

    instruction: str = Field(
        ...,
        min_length=1,
        description="Natural language task description",
    )
    task_type: str = Field("general", description="Task type (code, research, etc.)")
    project_id: str | None = Field(None, description="Optional project context")
    persona_name: str | None = Field(None, description="Optional persona pin")
    private: bool = Field(False, description="Strip memories/preferences")
    verify_chain: list[str] | None = Field(
        None,
        description="Verifier names to run (default: build_ok, lint_clean)",
    )
    isolate_workdir: bool = Field(
        True,
        description=(
            "Run the driver in a throwaway git worktree off the project. Without "
            "it the driver edits the live checkout and nothing is landed on a "
            "branch or offered as a PR."
        ),
    )


class DispatchResponse(BaseModel):
    """Response from a test dispatch."""

    success: bool
    output: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    driver: str = ""
    metadata: dict = {}


# ── Endpoints ────────────────────────────────────────────────


@router.get(
    "",
    summary="List registered drivers",
)
async def list_drivers():
    """List all registered drivers with availability and capabilities.

    Returns each driver's name, current availability status,
    supported task types, and estimated cost per task.
    """
    from life_graph.drivers.registry import billing_of, driver_registry

    drivers = driver_registry.list_all()
    result = []
    for d in drivers:
        try:
            avail = await d.available()
        except Exception:  # best-effort: a driver whose probe raises is listed as unavailable
            avail = False
        detail = None
        describe = getattr(d, "describe", None)
        if describe is not None:
            try:
                detail = await describe()
            except Exception:  # best-effort, like the probe above
                detail = None

        result.append(
            DriverInfo(
                name=d.name,
                available=avail,
                capabilities=d.capabilities(),
                cost_per_task=d.cost_per_task(),
                billing=billing_of(d),
                detail=detail,
            ).model_dump()
        )

    return success_response(data={"drivers": result, "total": len(result)})


@router.get(
    "/stats",
    summary="Driver performance stats",
)
async def driver_stats(
    window: int = Query(30, ge=1, le=365, description="Stats window in days"),
):
    """Get performance statistics for all drivers.

    Includes success rate, total tasks, cost, and duration metrics
    within the specified time window.
    """
    tenant_id = get_current_tenant_id()

    try:
        from sqlalchemy import func, select

        from life_graph.models.db import DriverStat

        async with async_session() as session:
            # Aggregate across day-bucketed rows, grouped by driver
            result = await session.execute(
                select(
                    DriverStat.driver,
                    func.sum(DriverStat.dispatched).label("dispatched"),
                    func.sum(DriverStat.verified_landed).label("landed"),
                    func.sum(DriverStat.failed).label("failed"),
                    func.sum(DriverStat.total_cost_usd).label("cost"),
                    func.sum(DriverStat.total_duration_ms).label("duration"),
                    func.max(DriverStat.window_start).label("last_window"),
                )
                .where(
                    DriverStat.tenant_id == tenant_id,
                )
                .group_by(DriverStat.driver)
            )
            rows = result.all()

            stat_list = []
            for row in rows:
                dispatched = row.dispatched or 0
                landed = row.landed or 0
                failed = row.failed or 0
                cost = row.cost or 0.0
                duration = row.duration or 0
                stat_list.append(
                    DriverStatResponse(
                        driver_name=row.driver,
                        success_count=landed,
                        failure_count=failed,
                        total_tasks=dispatched,
                        success_rate=landed / dispatched if dispatched > 0 else 0.0,
                        total_cost_usd=cost,
                        avg_cost_usd=cost / dispatched if dispatched > 0 else 0.0,
                        total_duration_ms=duration,
                        avg_duration_ms=duration // dispatched if dispatched > 0 else 0,
                        last_used_at=None,  # Day-bucketed, no precise timestamp
                    ).model_dump()
                )

            return success_response(data={"stats": stat_list, "window_days": window})
    except Exception:
        # DriverStat table may not exist yet
        return success_response(
            data={"stats": [], "window_days": window, "note": "No stats available yet"}
        )


@router.post(
    "/dispatch",
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch a task to a driver (testing)",
)
async def dispatch_task(body: DispatchRequest, request: Request):
    """Dispatch a task to a driver for testing purposes.

    Uses the full dispatch pipeline: driver selection, context building,
    verification chain, and one-bounce rule. Useful for testing driver
    integration without going through the kernel task system.

    Off unless ``LIFE_GRAPH_DRIVERS_DISPATCH_ENDPOINT=true`` (404 otherwise):
    it bypasses the runner's lock, limits and budget (audit L5).
    """
    if not settings.drivers_dispatch_endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    tenant_id = get_current_tenant_id()

    try:
        import uuid

        from life_graph.core.events import event_bus
        from life_graph.drivers.dispatcher import TaskDispatcher

        dispatcher = TaskDispatcher(
            session_factory=async_session,
            event_bus=event_bus,
        )

        task_id = str(uuid.uuid4())

        async with async_session() as session:
            result = await dispatcher.dispatch_task(
                tenant_id=tenant_id,
                task_id=task_id,
                instruction=body.instruction,
                task_type=body.task_type,
                project_id=body.project_id,
                session=session,
                persona_name=body.persona_name,
                private=body.private,
                verify_chain=body.verify_chain,
                isolate_workdir=body.isolate_workdir,
            )
            await session.commit()

        return success_response(
            data=DispatchResponse(
                success=result.success,
                output=result.output[:2000],  # Cap response size
                cost_usd=result.cost_usd,
                duration_ms=result.duration_ms,
                error=result.error,
                driver=result.metadata.get("driver", "unknown"),
                metadata=result.metadata,
            ).model_dump()
        )

    except Exception as e:
        # The detail stays in the server log; the client gets a fixed message,
        # and the app's HTTPException handler adds the request_id (audit M3).
        logger.exception(
            "Driver dispatch failed [rid=%s]", getattr(request.state, "request_id", "")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dispatch failed.",
        ) from e


# ── Dev tasks (dashboard: "do X in project Y") ───────────────


class DevTaskCreate(BaseModel):
    """Request body for a background dev task."""

    instruction: str = Field(..., min_length=5, max_length=8000)
    project_id: str = Field(..., description="Registered project to work in")
    persona_name: str = Field("code-fixer", description="A persona with a driver set")
    spec_first: bool = Field(
        False,
        description=(
            "Ask the driver to write a short requirements/design/tasks spec "
            "before it touches anything, and surface it on the task. Costs "
            "nothing extra (same driver call) but adds a few lines to the "
            "response — worth it for ambiguous or multi-step work, not for "
            "a one-line fix."
        ),
    )
    plan_only: bool = Field(
        False,
        description=(
            "Dispatch a PLAN, not code: the driver may only write a spec "
            "(## Spec: requirements/design/tasks), enforced by a verifier — "
            "any file change bounces it, same one-bounce rule as any other "
            "failure. A successful plan files a driver_plan approval; "
            "approving it dispatches the instruction + spec together as a "
            "normal code-writing task. Implies spec_first."
        ),
    )
    queue: bool = Field(
        False,
        description=(
            "Queue the task instead of starting it: the API's queue runner "
            "runs queued tasks one at a time (one local model, one GPU). Use "
            "it to hand over a backlog. Queued work is unattended, so the "
            "budget cap applies to it unless every model it uses is local."
        ),
    )
    timeout_seconds: int | None = Field(
        None,
        ge=60,
        le=86400,
        description=(
            "Per-call time limit for the agent, in seconds (each driver call, "
            "including one bounce). Capped by dev_task_max_timeout_seconds; "
            "default: the driver's own limit."
        ),
    )


@router.post(
    "/tasks",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a dev task in the background",
)
async def create_dev_task(body: DevTaskCreate, request: Request):
    """Validate, record and start a dev task; poll ``GET /tasks/{id}`` for progress.

    Always isolated: the agent works in a worktree, and a verified result is
    offered back as ``driver_pr`` / ``driver_merge`` approvals. Who asked is
    recorded as ``properties.requested_by`` (api/approval_identity.py
    ``resolver``), so a non-owner caller — an agent over MCP — cannot then
    approve its own task's plan, PR, merge or deploy (api/approvals.py).
    """
    from life_graph.api.approval_identity import resolver
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.services.dev import tasks as dev_tasks

    tenant_id = get_current_tenant_id()
    project = await get_project_registry().get_by_id(tenant_id, body.project_id)
    if not project or not project.get("is_active"):
        raise HTTPException(status_code=404, detail="Project not found")
    persona = await get_persona_service().get_by_name(tenant_id, body.persona_name)
    if not persona or not persona.get("is_active", True):
        raise HTTPException(status_code=404, detail=f"Persona {body.persona_name!r} not found")
    if not persona.get("driver"):
        raise HTTPException(
            status_code=400,
            detail=f"Persona {body.persona_name!r} has no driver and cannot run dev tasks",
        )
    task = await dev_tasks.create_dev_task(
        async_session,
        tenant_id,
        instruction=body.instruction,
        project=project,
        persona_name=body.persona_name,
        task_type="plan" if body.plan_only else "code_change",
        spec_first=body.spec_first or body.plan_only,
        verify_chain=["no_diff_in_plan"] if body.plan_only else None,
        start=not body.queue,
        timeout_seconds=body.timeout_seconds,
        properties={"requested_by": resolver(request)},
    )
    return success_response(data=task)


@router.get("/tasks", summary="List dev tasks with PR and merge state")
async def list_dev_tasks(limit: int = Query(50, ge=1, le=200)):
    from life_graph.services.dev import tasks as dev_tasks

    async with async_session() as session:
        data = await dev_tasks.list_dev_tasks(session, get_current_tenant_id(), limit)
    return success_response(data=data)


@router.get(
    "/tasks/stats",
    summary="Merge rate and timing per persona/project, from dev task history",
)
async def get_dev_task_stats():
    """Complements GET /stats (driver-level, tenant-wide, from DriverStat
    day buckets): this breaks the same kind of question down by project too,
    so "local: 62% success" doesn't quietly blend a struggling project in
    with a thriving one. Answers "is this actually working" without reading
    every task by hand: merge rate, in-flight/needs-review counts, and
    average duration/cost, per (persona, project) pair. Same trust bar the
    dispatcher itself uses lives in TrustScore/track_record; this is a
    *readable summary* of dev_task outcomes, not another trust source."""
    from life_graph.services.dev import tasks as dev_tasks

    async with async_session() as session:
        data = await dev_tasks.dev_task_stats(session, get_current_tenant_id())
    return success_response(data=data)


@router.get(
    "/tasks/auto-merge-status",
    summary="Trust-gate numbers auto_open_pr/auto_merge actually check, per persona/project",
)
async def get_auto_merge_status():
    """Same numbers dispatcher.py's maybe_auto_merge reads before deciding
    whether to skip an approval — merge_rate, established, the threshold,
    and whether the project opted in — so "why isn't this auto-merging" is
    answered by one glance instead of a hand-run curl against /tasks/stats
    plus mentally comparing it to 80%."""
    from life_graph.services.dev import tasks as dev_tasks

    async with async_session() as session:
        data = await dev_tasks.auto_merge_status(session, get_current_tenant_id())
    return success_response(data=data)


@router.get(
    "/tasks/dependency-audit-readiness",
    summary="Which registered projects can actually run no_vulnerable_deps_in_diff",
)
async def get_dependency_audit_readiness():
    """The verifier itself already reports 'pip-audit not available' per
    task, correctly, as inconclusive rather than a silent pass — but that
    only surfaces after someone dispatches a task that happens to touch a
    dependency manifest. This checks every active project's own manifest
    for a declared pip-audit dependency up front, so the gap is visible
    before it's found the hard way."""
    from life_graph.services.dev import tasks as dev_tasks

    data = await dev_tasks.dependency_audit_readiness(get_current_tenant_id())
    return success_response(data=data)


class PresenceUpdate(BaseModel):
    """The manual active/away switch for routing queued coding work."""

    mode: str = Field(..., pattern="^(auto|active|away)$", examples=["away"])
    # For how long; omitted = until changed. Ignored for "auto".
    minutes: int | None = Field(None, ge=1, le=7 * 24 * 60, examples=[120])


async def _compute_status(tenant_id: str) -> dict:
    from life_graph.services.llm import compute_router

    snap = await compute_router.snapshot(async_session, tenant_id)
    sample = compute_router.decide("code-fixer-local", {}, snap)
    return {
        "presence": await compute_router.get_presence(tenant_id),
        "active": snap.active,
        "local_hours": snap.local_hours,
        "free_gb": round(snap.free_gb, 1) if snap.free_gb is not None else None,
        "cloud_models": list(snap.cloud),
        "cloud_cooling": await compute_router.cloud_cooling(),
        "next_task": {"where": sample.where, "persona": sample.persona, "reason": sample.reason},
    }


@router.get(
    "/compute",
    summary="Where queued coding work runs right now: local GPU, free cloud model, or later",
)
async def get_compute_status():
    """The routing facts (services/llm/compute_router.py) and what a nightly
    local-model task would do if it were claimed now."""
    return success_response(data=await _compute_status(get_current_tenant_id()))


@router.get(
    "/night-shift",
    summary="What the coding engines did: merged, waiting for you and why, failed and why",
)
async def get_night_shift(hours: int = Query(24, ge=1, le=24 * 14)):
    """The night shift report (services/night_shift.py, Job 2) — the same data
    as the daily brief's Night shift section."""
    from datetime import UTC, timedelta
    from datetime import datetime as _dt

    from life_graph.services import night_shift

    since = _dt.now(UTC) - timedelta(hours=hours)
    async with async_session() as session:
        rep = await night_shift.report(session, get_current_tenant_id(), since)
    return success_response(data={**rep, "lines": night_shift.lines(rep)})


@router.put("/compute/presence", summary="Set the active/away switch (auto clears it)")
async def put_presence(body: PresenceUpdate):
    """Mode "active" keeps queued coding work off the GPU; "away" lets it run
    locally even if speech models are loaded; "auto" goes back to detecting
    it from chat, Telegram and voice activity."""
    from life_graph.services.llm import compute_router

    tenant_id = get_current_tenant_id()
    if not await compute_router.set_presence(tenant_id, body.mode, body.minutes):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Redis is not available")
    return success_response(data=await _compute_status(tenant_id))


@router.get("/tasks/{task_id}", summary="Get one dev task")
async def get_dev_task(task_id: str):
    from life_graph.services.dev import tasks as dev_tasks

    async with async_session() as session:
        data = await dev_tasks.get_dev_task(session, get_current_tenant_id(), task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Dev task not found")
    return success_response(data=data)


def _task_uuid(task_id: str) -> str:
    try:
        return str(uuid.UUID(task_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Dev task not found") from None


@router.get(
    "/tasks/{task_id}/events",
    summary="The task's live session events after a sequence number (long-poll)",
)
async def get_dev_task_events(
    task_id: str,
    after: int = Query(0, ge=0, description="Return events with seq > after"),
    limit: int = Query(200, ge=1, le=500),
    wait: float = Query(
        0, ge=0, le=25, description="Seconds to wait for the first new event (long-poll)"
    ),
):
    """Reconnectable by construction: ask for ``after=<last seq you have>``.

    With ``wait`` the call holds until there is something new, the task ends,
    or the wait runs out -- the dashboard's live session view loops on this.
    ``next_after`` is the cursor for the next call; ``live`` says whether more
    can still come.
    """
    from life_graph.services.dev import task_events

    tid = _task_uuid(task_id)
    tenant_id = get_current_tenant_id()
    events, status_ = await task_events.wait_for_events(
        async_session, tenant_id, tid, after=after, limit=limit, wait=wait
    )
    if status_ is None:
        raise HTTPException(status_code=404, detail="Dev task not found")
    return success_response(
        data={
            "events": events,
            "next_after": events[-1]["seq"] if events else after,
            "status": status_,
            "live": status_ not in task_events.TERMINAL_STATUSES,
        }
    )


@router.get(
    "/tasks/{task_id}/events/stream",
    summary="The task's live session as Server-Sent Events (resumes from Last-Event-ID)",
)
async def stream_dev_task_events(
    task_id: str,
    request: Request,
    after: int = Query(0, ge=0),
):
    """``text/event-stream``: one ``event: <kind>`` per row, ``id`` = seq, so a
    client that reconnects with ``Last-Event-ID`` resumes without gaps. Ends
    once the task is over and everything was sent. For clients that can set
    headers (the CLI, scripts); the dashboard long-polls ``/events``."""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from life_graph.services.dev import task_events

    tid = _task_uuid(task_id)
    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        if await task_events.task_status(session, tenant_id, tid) is None:
            raise HTTPException(status_code=404, detail="Dev task not found")
    last = request.headers.get("last-event-id")
    cursor = int(last) if last and last.isdigit() else after

    async def gen():
        nonlocal cursor
        idle = 0.0
        while True:
            if await request.is_disconnected():
                return
            events, status_ = await task_events.wait_for_events(
                async_session, tenant_id, tid, after=cursor, limit=200, wait=10
            )
            for ev in events:
                cursor = ev["seq"]
                yield f"id: {ev['seq']}\nevent: {ev['kind']}\ndata: {json.dumps(ev)}\n\n"
            if events:
                idle = 0.0
            elif status_ is None or status_ in task_events.TERMINAL_STATUSES:
                yield f"event: end\ndata: {json.dumps({'status': status_})}\n\n"
                return
            else:
                idle += 10
                yield ": keep-alive\n\n"
                if idle > 3600:
                    return
            await asyncio.sleep(0)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/tasks/{task_id}/cancel", summary="Cancel a queued or running dev task")
async def cancel_dev_task(task_id: str):
    """Queued: cancelled at once. Running: the runner (in whichever process
    holds the runner lock) stops the agent -- its process group or container
    -- and records ``cancelled``; poll the task to see it land. 409 when the
    task already finished. The task's live capabilities are revoked too; if
    the capability store cannot be reached the cancel still stands and the
    answer is 503 saying so (cancel again to retry the revocation)."""
    from life_graph.services.dev import tasks as dev_tasks

    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dev task not found") from None
    state = await dev_tasks.request_cancel(async_session, get_current_tenant_id(), task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Dev task not found")
    if state.get("revoke_error"):
        raise HTTPException(
            status_code=503,
            detail=(
                f"Dev task is {state['status']} (cancel {state['cancel']}), but its live"
                f" capabilities could not be revoked ({state['revoke_error']})."
                " Cancel again to retry the revocation."
            ),
        )
    if state["cancel"] == "not_cancellable":
        raise HTTPException(status_code=409, detail=f"Dev task is already {state['status']}")
    return success_response(data=state)


@router.post(
    "/tasks/{task_id}/conformance",
    summary="Re-check a task's spec against the project's current code",
)
async def check_dev_task_conformance(task_id: str):
    """Run every acceptance criterion's bound test against the project's
    current HEAD (in a throwaway worktree) and store a per-criterion report
    on the task. Synchronous: returns once the tests have run."""
    from life_graph.services.dev.conformance import ConformanceError, check_conformance

    try:
        report = await check_conformance(async_session, get_current_tenant_id(), task_id)
    except ConformanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(data=report)


@router.get(
    "/tasks/{task_id}/steps",
    summary="Every recorded step of a dev task's driver runs, in order",
)
async def get_dev_task_steps(task_id: str):
    """What the agent said, each tool call and its result, per attempt
    (attempt 2 is the bounce). Content is redacted and size-capped; a step
    cut short carries ``properties.original_chars``. Empty when the task's
    driver ran before step recording existed."""
    from life_graph.services.dev.trajectories import list_steps

    try:
        tid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="task_id must be a UUID") from exc
    async with async_session() as session:
        steps = await list_steps(session, get_current_tenant_id(), tid)
    return success_response(data={"task_id": task_id, "count": len(steps), "steps": steps})


@router.get(
    "/tasks/{task_id}/diff",
    summary="The change a landed dev task made, as a unified diff",
)
async def get_dev_task_diff(task_id: str):
    """From the task's newest driver_pr approval: branch, commits, changed
    files and the diff (capped; ``truncated`` says so). 404 until the task
    has landed a change."""
    from life_graph.services.dev import tasks as dev_tasks

    try:
        uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="task_id must be a UUID") from exc
    async with async_session() as session:
        data = await dev_tasks.task_diff(session, get_current_tenant_id(), task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="No landed change for this dev task")
    return success_response(data=data)


# ── Plans, scorecards, failures (docs/specs/agent-observability.md) ──


@router.get("/plans", summary="Plan tasks, each with its tasks counted by stage")
async def list_dev_plans(limit: int = Query(30, ge=1, le=200)):
    from life_graph.services.agent_insights import list_plans

    async with async_session() as session:
        data = await list_plans(session, get_current_tenant_id(), limit=limit)
    return success_response(data=data)


@router.get("/plans/{plan_id}", summary="One plan: spec, criteria and its tasks in order")
async def get_dev_plan(plan_id: str):
    from life_graph.services.agent_insights import get_plan

    async with async_session() as session:
        data = await get_plan(session, get_current_tenant_id(), plan_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return success_response(data=data)


@router.get("/scorecards", summary="Per driver and model: success, bounces, merges, cost")
async def get_driver_scorecards(days: int = Query(30, ge=1, le=365)):
    from life_graph.services.agent_insights import scorecards

    async with async_session() as session:
        data = await scorecards(session, get_current_tenant_id(), days=days)
    return success_response(data=data)


@router.get("/failures", summary="Failed dev tasks with their primary cause")
async def get_driver_failures(
    days: int = Query(30, ge=1, le=365), limit: int = Query(200, ge=1, le=1000)
):
    from life_graph.services.agent_insights import failures

    async with async_session() as session:
        data = await failures(session, get_current_tenant_id(), days=days, limit=limit)
    return success_response(data=data)


class ProductionFindingBody(BaseModel):
    """A production failure reported by a monitor (uptime check, error tracker, ...)."""

    kind: str = Field("monitor", max_length=64, description="What saw it, e.g. uptime, sentry")
    title: str = Field(..., min_length=3, max_length=300, description="One line: what broke")
    detail: str = Field("", max_length=8000, description="Evidence: error, status, stack trace")
    signature: str | None = Field(
        None, max_length=500, description="Same failure, same signature (de-duplication key)"
    )


@router.post(
    "/projects/{project_id}/findings",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Report a production failure; queues a fix task (de-duplicated)",
)
async def report_production_finding(project_id: str, body: ProductionFindingBody):
    """For external monitors: the fix goes through the normal dev-task gates
    (budget, verification, PR and merge approvals), never straight to production."""
    from life_graph.kernel.project_registry import ProjectRegistry
    from life_graph.services.dev.production_findings import file_fix_task

    tenant = get_current_tenant_id()
    try:
        project = await ProjectRegistry(session_factory=async_session).get_by_id(tenant, project_id)
    except ValueError:
        project = None
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await file_fix_task(
        async_session,
        tenant,
        project,
        kind=body.kind,
        title=body.title,
        detail=body.detail,
        signature=body.signature,
    )
    return success_response(data=result)


class BootstrapBody(BaseModel):
    """A new app: a name, a starting template and, optionally, the idea to plan."""

    name: str = Field(..., min_length=2, max_length=41, description="lowercase, digits, dashes")
    template: str = Field(..., max_length=64, description="see GET /kernel/drivers/templates")
    idea: str | None = Field(None, max_length=8000, description="What the app should do")
    start_plan: bool = Field(False, description="Start a plan-only dev task from the idea")
    persona_name: str = Field("code-fixer-opencode", max_length=100)


@router.get("/templates", summary="App templates a new project can start from")
async def list_app_templates():
    from life_graph.services.bootstrap import list_templates

    return success_response(data=list_templates())


@router.post(
    "/projects/bootstrap",
    status_code=status.HTTP_201_CREATED,
    summary="Idea to app: scaffold, version, register and optionally plan a new app",
)
async def bootstrap_app(body: BootstrapBody):
    from life_graph.services.bootstrap import BootstrapError, bootstrap

    try:
        data = await bootstrap(
            get_current_tenant_id(),
            name=body.name,
            template=body.template,
            idea=body.idea,
            start_plan=body.start_plan,
            persona_name=body.persona_name,
        )
    except (BootstrapError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(data=data)
