"""The real ports: dev tasks, the start gate, notices, ``gh``/``git``, intentions.

- :class:`DevTasks` creates tasks through ``services/dev/tasks.create_dev_task``
  (its duplicate check, the runner's queue, the normal approvals) and cancels
  through ``request_cancel``; views are ``tasks.serialize``.
- :class:`StartGate` is what every **automatic** start asks first, failing
  closed: the kill switch (``autonomy_stopped``); the subscription share (D4,
  ``accounts_hook.preview`` with ``unattended=True``: every account over its
  plan-window share, cooling down or unreadable → refused); and the Governor
  for api-billed runs (refused when it refuses, or when it could not check —
  the Governor itself fails open, the automation does not).
- :class:`EventNotifier` emits ``dev:automation:notice`` (CHARTER invariant 3);
  :class:`NoticeHandler`, subscribed in the API and the worker, turns it into
  a notification, a Web Push and a Telegram message.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.autonomy import kill_switch
from life_graph.config import settings
from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventType, event_bus
from life_graph.drivers import accounts_hook
from life_graph.models.db import AgentTask, Intention
from life_graph.runtime import get_notification_engine, get_persona_service, get_project_registry
from life_graph.services import governor as governor_mod
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.automation.ports import ExecResult
from life_graph.services.notifications.webpush import PushService
from life_graph.storage.database import async_session
from life_graph.watchers.channels.telegram_channel import TelegramChannel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from life_graph.core.events import Event

logger = logging.getLogger(__name__)

NOTICE_URL = "/m"


class DevTasks:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def project(self, tenant_id: str, project_id: str) -> dict[str, Any] | None:
        try:
            uuid.UUID(str(project_id))
        except ValueError:
            return None
        return await get_project_registry().get_by_id(tenant_id, project_id)

    async def persona_driver(self, tenant_id: str, persona: str) -> str | None:
        row = await get_persona_service().get_by_name(tenant_id, persona)
        if not row or not row.get("is_active", True):
            return None
        return row.get("driver") or None

    async def create(
        self,
        tenant_id: str,
        *,
        project: dict[str, Any],
        instruction: str,
        persona: str,
        mode: str,
        start_now: bool,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        if not await self.persona_driver(tenant_id, persona):
            raise ValueError(f"Persona {persona!r} not found or has no driver")
        plan = mode == "plan"
        return await dev_tasks.create_dev_task(
            self._sf,
            tenant_id,
            instruction=instruction,
            project=project,
            persona_name=persona,
            task_type="plan" if plan else "code_change",
            spec_first=plan,
            verify_chain=["no_diff_in_plan"] if plan else None,
            start=start_now,
            properties=properties,
        )

    async def cancel(self, tenant_id: str, task_id: str) -> dict[str, Any] | None:
        return await dev_tasks.request_cancel(self._sf, tenant_id, task_id)

    async def views(self, tenant_id: str, task_ids: list[str]) -> dict[str, dict[str, Any]]:
        pks = []
        for t in task_ids:
            try:
                pks.append(uuid.UUID(str(t)))
            except ValueError:
                continue
        if not pks:
            return {}
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(AgentTask).where(
                            AgentTask.tenant_id == tenant_id,
                            AgentTask.id.in_(pks),
                            AgentTask.properties["kind"].astext == dev_tasks.KIND,
                        )
                    )
                )
                .scalars()
                .all()
            )
            approvals = await dev_tasks._approvals_by_task(
                session, tenant_id, [str(r.id) for r in rows]
            )
            return {str(r.id): dev_tasks.serialize(r, approvals.get(str(r.id), [])) for r in rows}


class StartGate:
    async def paused(self, tenant_id: str) -> bool:
        return await kill_switch.autonomy_stopped(tenant_id)

    async def blockers(self, tenant_id: str, driver: str | None) -> list[str]:
        """Plain reasons automated work may not start now; [] = go. Fails closed."""
        reasons: list[str] = []
        try:
            if await self.paused(tenant_id):
                return [kill_switch.PAUSED_REFUSAL]
            if driver is None:
                return ["The persona has no driver."]
            preview = await accounts_hook.preview(driver, tenant_id, unattended=True)
            state = (preview or {}).get("state")
            if state == "over_budget":
                reasons.append("Every agent account is over its plan-window share.")
            elif state == "cooling":
                reasons.append("Every agent account is cooling down after a rate limit.")
            elif state == "error":
                reasons.append("The agent account pool could not be read.")
            subscription = state == "selected" and (preview or {}).get("kind") == "subscription"
            if not reasons and not subscription:
                decision = await governor_mod.governor.authorize(
                    tenant_id, BudgetCategory.DRIVER, 0.0, interactive=False
                )
                if not decision.allowed:
                    reasons.append(f"Budget: {decision.reason}")
                elif "failed open" in (decision.reason or ""):
                    reasons.append("The budget could not be checked.")
        except Exception as exc:  # noqa: BLE001 — fail closed (CHARTER invariant 5)
            logger.warning("Automation start gate failed for %s", tenant_id, exc_info=True)
            reasons.append(f"The start gate could not be checked: {str(exc)[:200]}")
        return reasons


class EventNotifier:
    """Publish an automation notice on the EventBus (``dev:automation:notice``)."""

    async def publish(
        self,
        tenant_id: str,
        *,
        kind: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        try:
            await event_bus.emit(
                EventType.AUTOMATION_NOTICE,
                {
                    "tenant_id": tenant_id,
                    "kind": kind,
                    "title": title,
                    "body": body,
                    **(data or {}),
                },
                source="dev_automation",
            )
        except Exception:  # noqa: BLE001 — a notice must never break the tick
            logger.warning("Could not publish the automation notice", exc_info=True)


class NoticeHandler:
    """``dev:automation:notice`` → notification + Web Push + Telegram."""

    def __init__(
        self, session_factory: Any = None, engine: Any = None, push: Any = None, channel: Any = None
    ) -> None:
        self._sf = session_factory
        self._engine = engine
        self._push = push
        self._channel = channel
        self._subscribed = False

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.AUTOMATION_NOTICE, self.on_notice)
        self._subscribed = True

    def _deps(self) -> tuple[Any, Any, Any]:
        sf = self._sf or async_session
        if self._engine is None:
            self._engine = get_notification_engine()
        if self._push is None:
            self._push = PushService(sf)
        if self._channel is None:
            self._channel = TelegramChannel(session_factory=sf)
        return self._engine, self._push, self._channel

    async def on_notice(self, event: Event) -> None:
        data = event.payload or {}
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            return
        kind = str(data.get("kind") or "notice")
        title = str(data.get("title") or "Automation")[:500]
        body = str(data.get("body") or "")
        engine, push, channel = self._deps()
        meta = {k: v for k, v in data.items() if k not in ("tenant_id", "title", "body")}
        try:
            await engine.create(
                tenant_id,
                title,
                body=body,
                priority="important" if kind == "breaker" else "info",
                source_type=f"dev_automation_{kind}",
                metadata=meta,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Automation notification create failed", exc_info=True)
        try:
            await push.send_to_tenant(tenant_id, title, body[:500], NOTICE_URL)
        except Exception:  # noqa: BLE001
            logger.warning("Automation notice push failed", exc_info=True)
        try:
            await channel.send(
                config={},
                tenant_id=tenant_id,
                severity="important",
                title=title,
                details=body[:1500],
                watcher_name=None,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Automation notice Telegram delivery failed", exc_info=True)


notice_handler = NoticeHandler()


async def run_command(
    argv: list[str], *, cwd: str | None = None, timeout: float = 30.0
) -> ExecResult:
    """Run ``gh`` / ``git`` without a prompt; ``gh`` is ``settings.driver_gh_bin``."""
    if argv and argv[0] == "gh":
        argv = [settings.driver_gh_bin, *argv[1:]]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd or None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GH_PROMPT_DISABLED": "1",
                "LC_ALL": "C",
            },
        )
    except (FileNotFoundError, NotADirectoryError) as exc:
        return ExecResult(code=127, stderr=f"{argv[0]}: {exc}")
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return ExecResult(code=-1, timed_out=True)
    return ExecResult(
        code=proc.returncode if proc.returncode is not None else -1,
        stdout=out.decode(errors="replace"),
        stderr=err.decode(errors="replace"),
    )


class NativeIntentions:
    """Active intentions straight from the ``intentions`` table (tenant-scoped)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def active(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(
                        Intention.id,
                        Intention.content,
                        Intention.status,
                        Intention.context_match,
                    )
                    .where(
                        Intention.tenant_id == tenant_id,
                        Intention.status.in_(("pending", "triggered")),
                    )
                    .order_by(Intention.created_at)
                    .limit(500)
                )
            ).all()
        return [
            {"id": str(r[0]), "content": r[1], "status": r[2], "context_match": r[3] or {}}
            for r in rows
        ]
