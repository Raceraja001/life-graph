"""Agent-driver automation API (Phase 4b): the PR feedback loop and the arena.

Prefix: /kernel/drivers (same tag as api/drivers.py). Parallel plans show in
the existing ``GET /kernel/drivers/plans/{id}`` (``team``), the owner retries a
team's failed worker here (Team upgrades, 2026-11-28), and dependencies on
the task routes (``depends_on`` on create, ``depends_on`` /
``dependency_wait`` on read). docs/specs/agent-drivers.md, "Phase 4b".
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from life_graph.api import dependencies as api_deps
from life_graph.api.approval_identity import owner_only, resolver
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.dev import arena as _arena
from life_graph.services.dev import pr_watch as _pr_watch
from life_graph.services.dev import team_retry as _team_retry
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kernel/drivers", tags=["drivers"])


def _uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{what} must be a UUID") from None


# ── PR feedback loop ─────────────────────────────────────────


@router.get("/pr-watch", summary="Watched pull requests of the PR feedback loop")
async def list_pr_watches() -> dict[str, Any]:
    """Every PR the loop watches for this tenant, newest first, with the loop's
    settings (``enabled``, ``poll_minutes``, ``max_rounds``, the three toggles)."""
    async with async_session() as session:
        watches = await _pr_watch.list_watches(session, get_current_tenant_id())
    return success_response(
        data={"settings": _pr_watch.current_settings().as_dict(), "watches": watches}
    )


@router.post("/pr-watch/poll", summary="Check every watched PR now (owner)")
async def poll_pr_watches(request: Request) -> dict[str, Any]:
    """Discover new PRs to watch and check each one now, ignoring the poll
    interval (one round in flight and the round limit still hold). Returns the
    outcome counts; ``enabled: false`` when the loop is off."""
    owner_only(request, "Polling pull requests for feedback")
    result = await _pr_watch.poll(async_session, force=True, tenant_id=get_current_tenant_id())
    return success_response(data=result)


@router.post("/pr-watch/{task_id}/stop", summary="Stop watching a task's PR (owner)")
async def stop_pr_watch(task_id: str, request: Request) -> dict[str, Any]:
    """The watch goes to ``stopped`` and is never resumed for this task."""
    owner_only(request, "Stopping the PR feedback loop")
    _uuid(task_id, "task_id")
    data = await _pr_watch.stop_watch(async_session, get_current_tenant_id(), task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="No watched pull request for this task")
    return success_response(data=data)


# ── Arena ────────────────────────────────────────────────────


class ArenaRacer(BaseModel):
    """One racer: a driver, optionally pinned to one of its agent accounts."""

    model_config = {"extra": "forbid"}

    driver: str = Field(..., min_length=1, max_length=32)
    account_id: str | None = Field(None, max_length=64)


class ArenaCreate(BaseModel):
    """Race one instruction on several drivers or accounts."""

    model_config = {"extra": "forbid"}

    project_id: str
    instruction: str = Field(..., min_length=5, max_length=8000)
    drivers: list[str | ArenaRacer] = Field(..., min_length=2, max_length=5)
    persona_name: str = Field("code-fixer", description="Prompt and tools; the driver is pinned")


class ArenaPick(BaseModel):
    """The winning racer's task."""

    model_config = {"extra": "forbid"}

    task_id: str


def _arena_error(exc: _arena.ArenaError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=f"{exc.code}: {exc}")


@router.post("/arena", status_code=202, summary="Start an arena race (owner)")
async def create_arena(body: ArenaCreate, request: Request) -> dict[str, Any]:
    """Queue one dev task per racer, the same instruction, each pinned to its
    driver/account and never auto-opened or auto-merged. 409 when the arena is
    off; 422 for an unknown driver or account, or fewer than 2 / more than 5."""
    owner_only(request, "Starting an arena race")
    tenant_id = get_current_tenant_id()
    project = await api_deps.get_project_registry().get_by_id(tenant_id, body.project_id)
    if not project or not project.get("is_active"):
        raise HTTPException(status_code=404, detail="Project not found")
    persona = await api_deps.get_persona_service().get_by_name(tenant_id, body.persona_name)
    if not persona or not persona.get("is_active", True):
        raise HTTPException(status_code=404, detail=f"Persona {body.persona_name!r} not found")
    entries = [d if isinstance(d, str) else d.model_dump() for d in body.drivers]
    try:
        data = await _arena.create_arena(
            async_session,
            tenant_id,
            project=project,
            instruction=body.instruction,
            entries=entries,
            persona_name=body.persona_name,
            requested_by=resolver(request),
        )
    except _arena.ArenaError as exc:
        raise _arena_error(exc) from exc
    return success_response(data=data)


@router.get("/arena/{arena_id}", summary="An arena race, its racers side by side")
async def get_arena(arena_id: str) -> dict[str, Any]:
    """Each racer's status/stage, diff size, verification, cost, rounds, time,
    its approval and its driver's scorecard; ``status`` is ``racing``,
    ``ready_to_pick`` or ``decided``."""
    _uuid(arena_id, "arena_id")
    async with async_session() as session:
        data = await _arena.get_arena(session, get_current_tenant_id(), arena_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arena race not found")
    return success_response(data=data)


@router.post("/arena/{arena_id}/pick", summary="Pick the arena's winner (owner)")
async def pick_arena_winner(arena_id: str, body: ArenaPick, request: Request) -> dict[str, Any]:
    """The other racers still running are cancelled and their pending approvals
    rejected; the winner's ``driver_pr`` approval stays pending for the owner
    to approve as usual. 409 when already decided or the winner has not landed."""
    owner_only(request, "Picking an arena winner")
    _uuid(arena_id, "arena_id")
    task_id = _uuid(body.task_id, "task_id")
    try:
        data = await _arena.pick_winner(async_session, get_current_tenant_id(), arena_id, task_id)
    except _arena.ArenaError as exc:
        raise _arena_error(exc) from exc
    return success_response(data=data)


# ── Teams (parallel plans) ───────────────────────────────────


class WorkerRetry(BaseModel):
    """Optional overrides for one retried team worker."""

    model_config = {"extra": "forbid"}

    tier: Literal["cheap", "balanced", "best"] | None = None
    persona: str | None = Field(None, min_length=1, max_length=100)


@router.post(
    "/plans/{plan_id}/workers/{task_id}/retry",
    status_code=202,
    summary="Re-run one failed worker of a parallel plan (owner)",
)
async def retry_team_worker(
    plan_id: str, task_id: str, request: Request, body: WorkerRetry | None = None
) -> dict[str, Any]:
    """Queue a fresh attempt of a failed, timed-out or cancelled worker (on
    *tier*'s rung / as *persona* when given, else one rung up). When the team
    failed because of this worker it is reopened: status ``running`` again and
    the tasks the team cancelled are queued again. 404 unknown plan/worker;
    409 ``not_failed`` / ``superseded`` / ``retry_pending`` / ``team_busy`` /
    ``failed_elsewhere``; 422 ``unknown_persona`` or a bad tier."""
    owner_only(request, "Retrying a team worker")
    plan = _uuid(plan_id, "plan_id")
    task = _uuid(task_id, "task_id")
    body = body or WorkerRetry()
    try:
        data = await _team_retry.owner_retry(
            async_session,
            get_current_tenant_id(),
            plan,
            task,
            tier=body.tier,
            persona=body.persona,
            by=resolver(request) or "owner",
        )
    except _team_retry.TeamError as exc:
        raise HTTPException(status_code=exc.http_status, detail=f"{exc.code}: {exc}") from exc
    return success_response(data=data)
