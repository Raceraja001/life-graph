"""Autonomy policy API — the owner's auto-approval conditions, daily cap,
review stages and fix rounds (docs/specs/agent-drivers.md, "Autonomy policy").

Prefix: /autonomy/policy. Reading is open to the tenant; every write is the
owner's alone (api/approval_identity.py ``owner_only``), like trust overrides
and autonomy levels: the policy decides how much lands without a person.
``updated_by`` is who the server saw calling, never a body field.

Validation (422) is the pydantic models in services/dev/autonomy_policy.py,
answered in the app-wide envelope (main.py ``validation_exception_handler``:
``error.code = "VALIDATION_ERROR"``, ``error.details``, string ``detail``).
An unknown or inactive project is 404 ``error.code = "PROJECT_NOT_FOUND"``
(main.py ``domain_error_handler``); a known one without a policy is 200.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.approval_identity import owner_only, resolver
from life_graph.api.responses import success_response
from life_graph.core.errors import NotFoundError
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


class ProjectNotFoundError(NotFoundError):
    """No active project with this id for the tenant (not "no policy")."""

    code = "PROJECT_NOT_FOUND"


async def _project_or_404(
    session: AsyncSession, tenant_id: str, project_id: str
) -> tuple[str, str]:
    """``(project_id, name)`` of an active project of this tenant, else a 404
    whose ``error.code`` is ``PROJECT_NOT_FOUND`` (not "no policy": a known
    project without one answers 200 with ``override: null``)."""
    try:
        pk = uuid.UUID(project_id)
    except ValueError:
        raise ProjectNotFoundError("Project not found") from None
    found = (
        await session.execute(
            select(Project.id, Project.name).where(
                Project.id == pk, Project.tenant_id == tenant_id, Project.is_active.is_(True)
            )
        )
    ).first()
    if found is None:
        raise ProjectNotFoundError("Project not found")
    return str(pk), found[1]


async def _project_names(session: AsyncSession, tenant_id: str, scopes: list[str]) -> dict:
    """``{project_id: (name, active)}`` for the scopes that are this tenant's projects."""
    ids = []
    for scope in scopes:
        try:
            ids.append(uuid.UUID(scope))
        except ValueError:
            continue
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Project.id, Project.name, Project.is_active).where(
                Project.tenant_id == tenant_id, Project.id.in_(ids)
            )
        )
    ).all()
    return {str(r[0]): (r[1], bool(r[2])) for r in rows}


async def _global_view(session: AsyncSession, tenant_id: str) -> dict:
    rows = (
        (await session.execute(select(AutonomyPolicy).where(AutonomyPolicy.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    by_scope = {r.scope: r for r in rows}
    glob = by_scope.pop(ap.GLOBAL_SCOPE, None)
    names = await _project_names(session, tenant_id, list(by_scope))
    projects = []
    for scope, row in sorted(by_scope.items()):
        name, active = names.get(scope, (None, False))
        # Every row here is an override; ``active`` false = the project is
        # gone or archived (its row no longer applies to any task).
        projects.append(
            {"project_id": scope, "name": name, "active": active, "override": True, **_row(row)}
        )
    return {
        "global": _row(glob),
        "projects": projects,
        "auto_approvals_today": await ap.auto_approvals_today(session, tenant_id),
        "limits": ap.limits(),
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
    """``override`` is the project's own row (null when none; ``policy`` is the
    same value under its original name); ``effective`` is what a task in this
    project gets, global and project merged. 404 ``PROJECT_NOT_FOUND`` only
    for an unknown or inactive project."""
    scope, name = await _project_or_404(session, tenant_id, project_id)
    rows = await ap.load_rows(session, tenant_id, scope)
    g, p = rows.get(ap.GLOBAL_SCOPE), rows.get(scope)
    effective = ap.merge(g.policy if g else None, p.policy if p else None)
    return success_response(
        {
            "project_id": scope,
            "name": name,
            "has_override": p is not None,
            "override": _row(p),
            "policy": _row(p),
            "effective": ap.describe(effective),
        }
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
    scope, _name = await _project_or_404(session, tenant_id, project_id)
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
    scope, _name = await _project_or_404(session, tenant_id, project_id)
    removed = await ap.delete(session, tenant_id, scope)
    await session.commit()
    return success_response({"project_id": scope, "removed": removed})
