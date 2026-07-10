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
from sqlalchemy import select, update

from life_graph.api.responses import success_response
from life_graph.models.db import Procedure
from life_graph.models.schemas import ProcedureCreate, ProcedureResponse, ProcedureUpdate
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/procedures", tags=["procedures"])


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
    stmt = select(Procedure).order_by(Procedure.confidence.desc()).limit(limit)

    if status_filter:
        stmt = stmt.where(Procedure.status == status_filter)
    if tag:
        stmt = stmt.where(Procedure.tags.contains([tag]))

    async with async_session() as db:
        result = await db.execute(stmt)
        procedures = result.scalars().all()

    return success_response(
        data=[ProcedureResponse.model_validate(p) for p in procedures]
    )


@router.get(
    "/{procedure_id}",
    summary="Get a procedure by ID",
)
async def get_procedure(procedure_id: uuid.UUID):
    """Retrieve a single procedure."""
    async with async_session() as db:
        proc = await db.get(Procedure, procedure_id)
        if proc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure {procedure_id} not found",
            )
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    async with async_session() as db:
        proc = await db.get(Procedure, procedure_id)
        if proc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure {procedure_id} not found",
            )
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
        proc = await db.get(Procedure, procedure_id)
        if proc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure {procedure_id} not found",
            )
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
        proc = await db.get(Procedure, procedure_id)
        if proc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure {procedure_id} not found",
            )
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
        procedure_id, success, proc.success_rate,
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
            Procedure.status == "active",
            Procedure.trigger.ilike(f"%{query}%"),
        )
        .order_by(Procedure.confidence.desc())
        .limit(limit)
    )

    async with async_session() as db:
        result = await db.execute(stmt)
        procedures = result.scalars().all()

    return success_response(
        data=[ProcedureResponse.model_validate(p) for p in procedures]
    )
