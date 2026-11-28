"""Dev automation API: intake → backlog, schedules, circuit breakers, digest preview.

Prefix: /kernel/automation. Spec: docs/specs/dev-automation.md. Reads are
tenant-scoped; every write (settings, start/skip, poll now, run now, breaker
reset) is **owner only** (api/approval_identity.owner_only): each one decides
what may run on its own. Field names are camelCase, mirroring race-app's
``AutomationSettings`` / ``BacklogItem`` / ``BreakerState`` so its cockpit can
be re-pointed; snake_case is accepted on input too.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from life_graph.api.approval_identity import owner_only, resolver
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.dev.automation import service as _service
from life_graph.services.dev.automation.intake import IntakeError
from life_graph.services.dev.automation.scheduler import ScheduleError
from life_graph.services.dev.automation.service import SettingsError
from life_graph.services.dev.automation.settings import AutomationSettings

router = APIRouter(prefix="/kernel/automation", tags=["dev-automation"])

_OWNER = "Changing dev automation"

BacklogStatus = Literal["new", "queued", "running", "done", "skipped", "failed"]


def _svc() -> _service.AutomationService:
    return _service.get_service()


def _refused(exc: IntakeError | ScheduleError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


@router.get("/settings", summary="The automation settings (intake, schedules, digest, breaker)")
async def get_settings() -> dict[str, Any]:
    doc = await _svc().get_settings(get_current_tenant_id())
    return success_response(data=doc.dump())


@router.put("/settings", summary="Replace the automation settings (owner)")
async def put_settings(body: AutomationSettings, request: Request) -> dict[str, Any]:
    """Sources and jobs are upserted by id (a missing or non-UUID id gets a new
    one, and ``after`` references to a draft id are translated); ones left out
    are deleted. 400 on an unknown project/persona or a chain problem."""
    owner_only(request, _OWNER)
    try:
        saved = await _svc().save_settings(get_current_tenant_id(), body, resolver(request))
    except SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return success_response(data=saved.dump())


@router.get("/backlog", summary="Backlog items, newest first")
async def list_backlog(
    status: BacklogStatus | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    items = await _svc().list_backlog(get_current_tenant_id(), status, limit)
    return success_response(data={"items": items, "count": len(items)})


@router.post("/backlog/{item_id}/start", summary="Start a backlog item now (owner)")
async def start_item(item_id: str, request: Request) -> dict[str, Any]:
    """Ignores maxConcurrent / maxPerDay and a tripped breaker; the kill switch
    applies. 404 unknown item, 409 not startable."""
    owner_only(request, _OWNER)
    try:
        item = await _svc().start_item(get_current_tenant_id(), item_id, resolver(request))
    except IntakeError as exc:
        raise _refused(exc) from None
    return success_response(data={"item": item})


@router.post("/backlog/{item_id}/skip", summary="Skip a new or failed backlog item (owner)")
async def skip_item(item_id: str, request: Request) -> dict[str, Any]:
    owner_only(request, _OWNER)
    try:
        item = await _svc().skip_item(get_current_tenant_id(), item_id)
    except IntakeError as exc:
        raise _refused(exc) from None
    return success_response(data={"item": item})


@router.post("/intake/poll", summary="Poll every enabled source now (owner)")
async def poll_now(request: Request) -> dict[str, Any]:
    """Poll, sync, reconcile and start eligible items, exactly like a tick but
    with every enabled source due."""
    owner_only(request, _OWNER)
    report = await _svc().poll(get_current_tenant_id(), force=True)
    return success_response(data=report)


@router.post("/schedules/{job_id}/run", summary="Run a scheduled job now (owner)")
async def run_now(job_id: str, request: Request) -> dict[str, Any]:
    """Bypasses the breaker and the budget; the kill switch and the overlap
    check apply. 404 unknown job, 409 refused."""
    owner_only(request, _OWNER)
    try:
        data = await _svc().run_now(get_current_tenant_id(), job_id)
    except (IntakeError, ScheduleError) as exc:
        raise _refused(exc) from None
    return success_response(data=data)


@router.get("/schedules/{job_id}/runs", summary="A job's handled slots, newest first")
async def list_runs(job_id: str, limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    try:
        items = await _svc().list_runs(get_current_tenant_id(), job_id, limit)
    except IntakeError as exc:
        raise _refused(exc) from None
    return success_response(data={"items": items, "count": len(items)})


@router.get("/breakers", summary="Circuit breaker states, tripped first")
async def list_breakers() -> dict[str, Any]:
    items = await _svc().list_breakers(get_current_tenant_id())
    return success_response(data={"items": items, "count": len(items)})


@router.post("/breakers/{key:path}/reset", summary="Reset a circuit breaker (owner)")
async def reset_breaker(key: str, request: Request) -> dict[str, Any]:
    """``key`` is ``intake:<sourceId>`` or ``schedule:<jobId>``. 404 unknown key."""
    owner_only(request, _OWNER)
    try:
        item = await _svc().reset_breaker(get_current_tenant_id(), key)
    except IntakeError as exc:
        raise _refused(exc) from None
    return success_response(data={"item": item})


@router.get("/digest/preview", summary="The morning digest as it would be sent now")
async def digest_preview() -> dict[str, Any]:
    return success_response(data=await _svc().digest_preview(get_current_tenant_id()))
