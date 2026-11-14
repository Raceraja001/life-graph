"""Procedure (strategy memory) API routes (Feature 7).

Provides CRUD endpoints for managing learned behavioral patterns
and strategies. Procedures capture recurring workflows that have
been observed across multiple sessions.

All routes are prefixed with ``/procedures`` and tagged for OpenAPI docs.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id, get_scoped
from life_graph.models.db import Procedure
from life_graph.models.schemas import ProcedureCreate, ProcedureResponse, ProcedureUpdate
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/procedures", tags=["procedures"])


async def _load_procedure(db: AsyncSession, procedure_id: uuid.UUID) -> Procedure:
    """The current tenant's procedure; another tenant's id reads as a 404."""
    try:
        proc = await get_scoped(db, Procedure, procedure_id)
    except LookupError:
        proc = None
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procedure {procedure_id} not found",
        )
    return proc


# ── CRUD ──────────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a procedure",
)
async def create_procedure(body: ProcedureCreate):
    """Create a new procedural memory (learned strategy).

    Stores a trigger condition, ordered steps, and optional metadata.
    """
    proc = Procedure(
        tenant_id=get_current_tenant_id(),
        trigger=body.trigger,
        steps=body.steps,
        description=body.description,
        confidence=body.confidence,
        tags=body.tags,
        learned_from=body.learned_from or [],
    )

    async with async_session() as db:
        db.add(proc)
        await db.commit()
        await db.refresh(proc)

    logger.info("Created procedure %s: %s", proc.id, proc.trigger[:60])
    return success_response(data=ProcedureResponse.model_validate(proc))


@router.get(
    "/",
    summary="List procedures",
)
async def list_procedures(
    status_filter: str | None = Query(None, alias="status"),
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(20, ge=1, le=100),
):
    """List all procedures, optionally filtered by status or tag."""
    stmt = (
        select(Procedure)
        .where(Procedure.tenant_id == get_current_tenant_id())
        .order_by(Procedure.confidence.desc())
        .limit(limit)
    )

    if status_filter:
        stmt = stmt.where(Procedure.status == status_filter)
    if tag:
        stmt = stmt.where(Procedure.tags.contains([tag]))

    async with async_session() as db:
        result = await db.execute(stmt)
        procedures = result.scalars().all()

    return success_response(data=[ProcedureResponse.model_validate(p) for p in procedures])


@router.get(
    "/{procedure_id}",
    summary="Get a procedure by ID",
)
async def get_procedure(procedure_id: uuid.UUID):
    """Retrieve a single procedure."""
    async with async_session() as db:
        proc = await _load_procedure(db, procedure_id)
    return success_response(data=ProcedureResponse.model_validate(proc))


@router.patch(
    "/{procedure_id}",
    summary="Update a procedure",
)
async def update_procedure(procedure_id: uuid.UUID, body: ProcedureUpdate):
    """Update an existing procedure's trigger, steps, or metadata."""
    updates: dict[str, Any] = {}
    for field_name in ("trigger", "steps", "description", "confidence", "tags", "status"):
        val = getattr(body, field_name, None)
        if val is not None:
            updates[field_name] = val

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No fields to update",
        )

    async with async_session() as db:
        proc = await _load_procedure(db, procedure_id)
        for k, v in updates.items():
            setattr(proc, k, v)
        await db.commit()
        await db.refresh(proc)

    logger.info("Updated procedure %s", procedure_id)
    return success_response(data=ProcedureResponse.model_validate(proc))


@router.delete(
    "/{procedure_id}",
    summary="Delete a procedure",
)
async def delete_procedure(procedure_id: uuid.UUID):
    """Soft-delete a procedure by setting status to 'archived'."""
    async with async_session() as db:
        proc = await _load_procedure(db, procedure_id)
        proc.status = "archived"
        await db.commit()

    logger.info("Archived procedure %s", procedure_id)
    return success_response(data={"id": str(procedure_id), "status": "archived"})


# ── Application Tracking ─────────────────────────────────────


@router.post(
    "/{procedure_id}/apply",
    summary="Record a procedure application",
)
async def apply_procedure(
    procedure_id: uuid.UUID,
    success: bool = Query(True, description="Whether the application succeeded"),
):
    """Record that a procedure was applied, updating statistics.

    Increments ``times_applied`` and optionally ``success_count``.
    Recalculates confidence based on success rate.
    """
    async with async_session() as db:
        proc = await _load_procedure(db, procedure_id)
        proc.times_applied += 1
        if success:
            proc.success_count += 1

        # Update confidence based on success rate (Bayesian-ish update)
        if proc.times_applied >= 3:
            proc.confidence = min(0.95, proc.success_rate * 0.9 + 0.1)

        await db.commit()
        await db.refresh(proc)

    logger.info(
        "Procedure %s applied (success=%s, rate=%.2f)",
        procedure_id,
        success,
        proc.success_rate,
    )
    return success_response(data=ProcedureResponse.model_validate(proc))


# ── Match ─────────────────────────────────────────────────────


@router.get(
    "/match/{query}",
    summary="Find matching procedures",
)
async def match_procedures(
    query: str,
    limit: int = Query(5, ge=1, le=20),
):
    """Find procedures whose trigger matches the given query.

    Uses simple substring matching (case-insensitive).
    A future version will use embedding-based matching.
    """
    stmt = (
        select(Procedure)
        .where(
            Procedure.tenant_id == get_current_tenant_id(),
            Procedure.status == "active",
            Procedure.trigger.ilike(f"%{query}%"),
        )
        .order_by(Procedure.confidence.desc())
        .limit(limit)
    )

    async with async_session() as db:
        result = await db.execute(stmt)
        procedures = result.scalars().all()

    return success_response(data=[ProcedureResponse.model_validate(p) for p in procedures])


#: Verified runs a procedure needs before it is described as reliable.
#:
#: One success is an anecdote. It can succeed because of the day's state — a
#: warm cache, a branch that happened to be clean, a service that happened to
#: be up — and a procedure promoted off that single run then gets replayed
#: into a different world. Two independently verified outcomes are the
#: cheapest evidence that the steps, not the circumstances, did the work. The
#: owner saying so outright is the other way in.
MIN_VERIFIED_OUTCOMES = 2


def _clean_list(values: list[str] | None) -> list[str]:
    return [v.strip() for v in (values or []) if v and v.strip()]


def _count_verified_outcomes(outcomes: list[dict[str, Any]] | None) -> int:
    """How many runs both passed *and* left evidence that they passed.

    A run that reports ``passed`` with nothing to show for it is the agent's
    own say-so about its own work, which is exactly the claim that needs
    backing; it does not count towards promotion.
    """
    return sum(
        1
        for o in (outcomes or [])
        if isinstance(o, dict) and bool(o.get("passed")) and bool(o.get("observed_evidence"))
    )


def build_procedure_candidate(
    *,
    trigger: str,
    steps: list[str],
    prerequisites: list[str] | None = None,
    verification_checks: list[str] | None = None,
    failure_recovery: list[str] | None = None,
    failure_modes: list[str] | None = None,
    tool_versions: dict[str, Any] | None = None,
    has_side_effects: bool = False,
) -> dict[str, Any]:
    """Construct a procedural learning candidate — a candidate, never a procedure.

    Everything a replay would need to know whether it is even in the same
    situation is recorded here: what must be true first, how to tell it
    worked, how it is known to fail, and which tool versions it was learned
    against. Nothing built here is reliable: that is
    :func:`verify_procedure_candidate`'s to grant, and only on evidence.
    """
    return {
        "trigger": trigger.strip(),
        "steps": _clean_list(steps),
        "prerequisites": _clean_list(prerequisites),
        "verification_checks": _clean_list(verification_checks),
        "failure_recovery": _clean_list(failure_recovery),
        "failure_modes": _clean_list(failure_modes),
        "tool_versions": dict(tool_versions or {}),
        "has_side_effects": bool(has_side_effects),
        "grants_side_effect_permission": False,
        "status": "candidate",
        "verified": False,
        "verified_outcomes_count": 0,
        "owner_confirmed": False,
        "is_reliable": False,
    }


def verify_procedure_candidate(
    candidate: dict[str, Any],
    *,
    observed_outcomes: list[dict[str, Any]],
    owner_confirmed: bool = False,
) -> dict[str, Any]:
    """Score a candidate against its observed runs; promote only on real evidence.

    Two gates, deliberately separate:

    * ``verified`` — the candidate is *well-formed and has worked once*: it
      records its prerequisites, checks and recovery, and at least one run
      passed with evidence.
    * ``is_reliable`` — it may be presented as a procedure to follow. That
      needs :data:`MIN_VERIFIED_OUTCOMES` independently verified runs, or the
      owner confirming it themselves. A one-off success stays a candidate.

    Neither gate ever grants side-effect permission: see
    :func:`can_auto_execute_side_effects`.
    """
    updated = dict(candidate)
    has_structure = bool(
        updated.get("steps")
        and updated.get("prerequisites")
        and updated.get("verification_checks")
        and updated.get("failure_recovery")
    )
    verified_count = _count_verified_outcomes(observed_outcomes)
    updated["verified"] = bool(has_structure and verified_count >= 1)
    updated["verified_outcomes_count"] = verified_count
    updated["owner_confirmed"] = bool(owner_confirmed)
    updated["is_reliable"] = bool(
        updated["verified"] and (verified_count >= MIN_VERIFIED_OUTCOMES or owner_confirmed)
    )
    updated["status"] = "reliable" if updated["is_reliable"] else "candidate"
    updated["observed_outcomes"] = list(observed_outcomes or [])
    updated["grants_side_effect_permission"] = False
    return updated


def can_auto_execute_side_effects(
    procedure: Any,
    *,
    explicit_action_approval: bool = False,
) -> bool:
    """Past procedure success never grants permanent permission for side effects."""
    return bool(explicit_action_approval)
