"""Production failures become fix tasks (docs/specs/autonomous-app-development.md, item 11).

One entry point, :func:`file_fix_task`, for anything that learns a deployed
app is broken:
- the post-deploy smoke check (services/approvals.py, after deploy_command);
- an external monitor, through ``POST /kernel/drivers/projects/{id}/findings``.
  Uptime checks, Sentry and the like are third parties; that endpoint is
  their stub-free integration point.

The task is queued, not started: the queue runner works it under the same
budget, verification and PR/merge approvals as any dev task, so a fix never
reaches production without passing the same gates. Duplicates are refused:
the same failure reported again while its fix is still open (or within a
week) does not pile up tasks.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.models.db import AgentTask

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

ORIGIN = "production"
DEFAULT_FIX_PERSONA = "code-fixer-local"
DEDUPE_DAYS = 7


def finding_key(project_id: str, kind: str, signature: str) -> str:
    """A stable key for one failure: same project, kind and signature, same key."""
    return hashlib.sha1(f"{project_id}|{kind}|{signature}".encode()).hexdigest()[:16]


def fix_instruction(kind: str, title: str, detail: str) -> str:
    return (
        f"A production check failed ({kind}): {title}\n\n"
        f"What was observed:\n{detail.strip()[:4000]}\n\n"
        "Find the cause in the code and fix it. Add or extend a test that would "
        "have caught this failure before it was deployed, so it cannot come back "
        "unnoticed. Make the smallest change that fixes it."
    )


async def file_fix_task(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    project: dict[str, Any],
    *,
    kind: str,
    title: str,
    detail: str,
    signature: str | None = None,
) -> dict[str, Any]:
    """Queue a fix task for a production failure, unless this one is already open.

    *project* is a registry project dict (``id``, ``name``, ``path``,
    ``scan_metadata``). *signature* identifies the failure for de-duplication
    (defaults to the title). Returns ``{"queued": id}`` or
    ``{"deduplicated": existing_id}``.
    """
    from life_graph.services import dev_tasks

    project_id = str(project["id"])
    key = finding_key(project_id, kind, signature or title)
    since = datetime.now(UTC) - timedelta(days=DEDUPE_DAYS)
    async with session_factory() as session:
        existing = (
            (
                await session.execute(
                    select(AgentTask.id)
                    .where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.project_id == uuid.UUID(project_id),
                        AgentTask.properties["finding_key"].astext == key,
                        AgentTask.created_at >= since,
                    )
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
    if existing is not None:
        logger.info("Production finding %s already has fix task %s", key, existing)
        return {"deduplicated": str(existing), "finding_key": key}

    meta = project.get("scan_metadata") or {}
    task = await dev_tasks.create_dev_task(
        session_factory,
        tenant_id,
        instruction=fix_instruction(kind, title, detail),
        project=project,
        persona_name=meta.get("fix_persona") or DEFAULT_FIX_PERSONA,
        start=False,
        properties={"origin": ORIGIN, "finding_key": key, "finding_kind": kind},
    )
    logger.warning("Queued fix task %s for production finding %s (%s)", task["id"], key, title)
    return {"queued": task["id"], "finding_key": key}
