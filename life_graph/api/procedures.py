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


def build_procedure_candidate(
    *,
    trigger: str,
    steps: list[str],
    prerequisites: list[str] | None = None,
    verification_checks: list[str] | None = None,
    failure_recovery: list[str] | None = None,
    has_side_effects: bool = False,
) -> dict[str, Any]:
    """Construct a procedural learning candidate with safety and verification metadata."""
    return {
        "trigger": trigger.strip(),
        "steps": [s.strip() for s in steps if s and s.strip()],
        "prerequisites": [p.strip() for p in (prerequisites or []) if p and p.strip()],
        "verification_checks": [v.strip() for v in (verification_checks or []) if v and v.strip()],
        "failure_recovery": [f.strip() for f in (failure_recovery or []) if f and f.strip()],
        "has_side_effects": bool(has_side_effects),
        "grants_side_effect_permission": False,
        "verified": False,
    }


def verify_procedure_candidate(
    candidate: dict[str, Any],
    *,
    observed_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify a procedure candidate only when prerequisites, checks, recovery, and observed pass exist."""
    updated = dict(candidate)
    has_structure = bool(
        updated.get("steps")
        and updated.get("prerequisites")
        and updated.get("verification_checks")
        and updated.get("failure_recovery")
    )
    passed_observed = any(bool(o.get("passed")) and bool(o.get("observed_evidence")) for o in (observed_outcomes or []))
    updated["verified"] = bool(has_structure and passed_observed)
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
