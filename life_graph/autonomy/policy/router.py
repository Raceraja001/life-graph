"""Autonomy policy API — the owner's auto-approval conditions, daily cap,
review stages and fix rounds (docs/specs/agent-drivers.md, "Autonomy policy").

Prefix: /autonomy/policy. Reading is open to the tenant; every write is the
owner's alone (api/approval_identity.py ``owner_only``), like trust overrides
and autonomy levels: the policy decides how much lands without a person.
``updated_by`` is who the server saw calling, never a body field.

Validation (422) is the pydantic models in services/dev/autonomy_policy.py.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.approval_identity import owner_only, resolver
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import AutonomyPolicy, Project
from life_graph.services.dev import autonomy_policy as ap
from life_graph.storage.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policy", tags=["autonomy-policy"])

_WHAT = "Changing the autonomy policy"


def _row(row: AutonomyPolicy | None) -> dict | None:
    if row is None:
        return None
    return {
        "policy": row.policy,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _limits() -> dict:
    return {
        "max_fix_rounds": ap.MAX_FIX_ROUNDS,
        "max_review_stages": ap.MAX_STAGES,
        "max_globs": ap.MAX_GLOBS,
        "reviewers": [ap.HUMAN_REVIEWER, ap.PR_AGENT_REVIEWER, f"{ap.MODEL_PREFIX}<model id>"],
    }


async def _project_or_404(session: AsyncSession, tenant_id: str, project_id: str) -> str:
    try:
        pk = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    found = (
        await session.execute(
            select(Project.id).where(
                Project.id == pk, Project.tenant_id == tenant_id, Project.is_active.is_(True)
            )
        )
    ).first()
    if found is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return str(pk)


async def _global_view(session: AsyncSession, tenant_id: str) -> dict:
    rows = (
        (await session.execute(select(AutonomyPolicy).where(AutonomyPolicy.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    by_scope = {r.scope: r for r in rows}
    glob = by_scope.pop(ap.GLOBAL_SCOPE, None)
    return {
        "global": _row(glob),
        "projects": [{"project_id": scope, **_row(row)} for scope, row in sorted(by_scope.items())],
        "auto_approvals_today": await ap.auto_approvals_today(session, tenant_id),
        "limits": _limits(),
    }


@router.get("", summary="The global autonomy policy, every project policy, today's count")
async def get_policy(
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """``global`` is null when no global policy is stored (today's behaviour)."""
    return success_response(await _global_view(session, tenant_id))


@router.put("", summary="Replace the global autonomy policy (owner only)")
async def put_policy(
    body: ap.GlobalAutonomyPolicy,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Replaces the whole global policy; omitted fields take their neutral default."""
    owner_only(request, _WHAT)
    await ap.save(session, tenant_id, ap.GLOBAL_SCOPE, body, resolver(request))
    await session.commit()
    logger.info("Global autonomy policy set by %s", resolver(request))
    return success_response(await _global_view(session, tenant_id))


@router.delete("", summary="Remove the global autonomy policy (owner only)")
async def delete_policy(
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Back to no global policy. Project policies stay."""
    owner_only(request, _WHAT)
    removed = await ap.delete(session, tenant_id, ap.GLOBAL_SCOPE)
    await session.commit()
    return success_response({"removed": removed})


@router.get("/projects/{project_id}", summary="A project's stored policy and the effective policy")
async def get_project_policy(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """``policy`` is the project's own row (null when none); ``effective`` is
    what a task in this project gets, global and project merged."""
    scope = await _project_or_404(session, tenant_id, project_id)
    rows = await ap.load_rows(session, tenant_id, scope)
    g, p = rows.get(ap.GLOBAL_SCOPE), rows.get(scope)
    effective = ap.merge(g.policy if g else None, p.policy if p else None)
    return success_response(
        {"project_id": scope, "policy": _row(p), "effective": ap.describe(effective)}
    )


@router.put("/projects/{project_id}", summary="Replace a project's autonomy policy (owner only)")
async def put_project_policy(
    project_id: str,
    body: ap.ProjectAutonomyPolicy,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """A project's conditions are checked on top of the global ones (both must
    hold); its stages and rounds, when not null, replace the global ones."""
    owner_only(request, _WHAT)
    scope = await _project_or_404(session, tenant_id, project_id)
    await ap.save(session, tenant_id, scope, body, resolver(request))
    await session.commit()
    return await get_project_policy(project_id, session, tenant_id)


@router.delete("/projects/{project_id}", summary="Remove a project's autonomy policy (owner only)")
async def delete_project_policy(
    project_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    owner_only(request, _WHAT)
    scope = await _project_or_404(session, tenant_id, project_id)
    removed = await ap.delete(session, tenant_id, scope)
    await session.commit()
    return success_response({"project_id": scope, "removed": removed})
