"""Turn an advisory persona's finished run into notifications.

scout/admin/tutor end their reply with a JSON array of findings; this module
extracts them and creates a Notification per finding, pushing urgent ones
immediately. Malformed/absent JSON falls back to a single digest so a finding
is never silently dropped.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select

from life_graph.core.events import Event, EventType, event_bus
from life_graph.kernel.ambient import AMBIENT_ADVISORY

logger = logging.getLogger(__name__)

_VALID_URGENCY = {"now", "brief"}


def _extract_json_array(text: str) -> list[Any] | None:
    """Return the trailing JSON array from text, or None if there is none.

    Prefers the array whose parse reaches end-of-text (the contract: the
    reply ends with the findings array). Falls back to the widest array
    found, so an embedded ``[]``/``[1]`` inside a string value can never
    steal the match from the real, outer findings array.
    """
    dec = json.JSONDecoder()
    best: tuple[int, list[Any]] | None = None  # (consumed_span, array)
    for idx in (i for i, c in enumerate(text) if c == "["):
        try:
            obj, end = dec.raw_decode(text, idx)
        except ValueError:
            continue
        if not isinstance(obj, list):
            continue
        if text[end:].strip() == "":  # nothing but whitespace after → trailing array
            return obj
        span = end - idx
        if best is None or span > best[0]:
            best = (span, obj)
    return best[1] if best else None


def parse_findings(result_text: str) -> list[dict[str, Any]]:
    """Extract the trailing JSON findings array from a persona's reply.

    Returns a list of ``{"title","detail","urgency"}`` dicts. Unknown urgency
    values coerce to ``"brief"``. Returns ``[]`` when no valid findings are
    extracted (even if a JSON array was present).
    """
    raw = _extract_json_array(result_text)
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    findings: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or "title" not in item:
            continue
        urgency = item.get("urgency", "brief")
        if urgency not in _VALID_URGENCY:
            urgency = "brief"
        findings.append(
            {
                "title": str(item["title"])[:200],
                "detail": str(item.get("detail", "")),
                "urgency": urgency,
            }
        )
    return findings


_PRIORITY = {"now": "important", "brief": "info"}


class FindingsBridge:
    """Convert an advisory run's findings into notifications (+ urgent push)."""

    def __init__(self, notification_engine: Any, push_service: Any) -> None:
        self._notifications = notification_engine
        self._push = push_service

    async def process_result(
        self, tenant_id: str, agent_name: str, task_id: str, result_text: str
    ) -> int:
        """Parse findings and create a notification per finding.

        Urgent (``urgency="now"``) findings are created at ``important`` and
        pushed to the phone immediately; the rest are held for the daily brief.
        Malformed/absent JSON becomes one held digest notification. Returns the
        number of notifications created.
        """
        raw_array = _extract_json_array(result_text)
        findings = parse_findings(result_text)

        # Fallback logic: create digest only if conditions apply
        if raw_array is None:
            # No JSON array found at all - fallback to digest if text exists
            if result_text.strip():
                findings = [
                    {
                        "title": f"{agent_name} update",
                        "detail": result_text.strip(),
                        "urgency": "brief",
                    }
                ]
        elif raw_array == []:
            # Explicit empty array - create nothing
            findings = []
        elif not findings and result_text.strip():
            # Non-empty array but no valid findings - fallback to digest
            findings = [
                {
                    "title": f"{agent_name} update",
                    "detail": result_text.strip(),
                    "urgency": "brief",
                }
            ]

        created = 0
        for f in findings:
            urgent = f["urgency"] == "now"
            try:
                await self._notifications.create(
                    tenant_id,
                    f["title"],
                    body=f["detail"] or None,
                    priority=_PRIORITY[f["urgency"]],
                    source_type=agent_name,
                    source_id=task_id,
                    deliver_at_brief=not urgent,
                )
                created += 1
            except Exception:  # one bad finding must not drop the rest
                logger.warning("Findings bridge: notification create failed", exc_info=True)
                continue
            if urgent:
                try:
                    await self._push.send_to_tenant(tenant_id, f["title"], f["detail"], "/m")
                except Exception:  # delivery must never break the flow
                    logger.warning("Findings bridge: urgent push failed", exc_info=True)
        return created


async def _load_task_result(tenant_id: str, task_id: str) -> str | None:
    """Load a completed AgentTask's response text, tenant-scoped."""
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.id == uuid.UUID(task_id),
                    AgentTask.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    if row is None or not isinstance(row.result, dict):
        return None
    return row.result.get("response")


class FindingsBridgeHandler:
    """Subscribes TASK_COMPLETED and bridges advisory runs to notifications."""

    def __init__(self) -> None:
        self._subscribed = False
        self._bridge: FindingsBridge | None = None

    def _get_bridge(self) -> FindingsBridge:
        if self._bridge is None:
            from life_graph.api.dependencies import get_notification_engine
            from life_graph.services.webpush import PushService
            from life_graph.storage.database import async_session

            self._bridge = FindingsBridge(
                notification_engine=get_notification_engine(),
                push_service=PushService(async_session),
            )
        return self._bridge

    def subscribe(self) -> None:
        """Subscribe the handler to TASK_COMPLETED (idempotent)."""
        if self._subscribed:
            return
        event_bus.subscribe(EventType.TASK_COMPLETED, self._on_task_completed)
        self._subscribed = True

    async def _on_task_completed(self, event: Event) -> None:
        try:
            data = event.payload
            agent_name = data.get("agent_name", "")
            if agent_name not in AMBIENT_ADVISORY:
                return
            tenant_id = data.get("tenant_id")
            task_id = data.get("task_id")
            if not tenant_id or not task_id:
                return
            result_text = await _load_task_result(tenant_id, task_id)
            if result_text is None:
                return
            await self._get_bridge().process_result(tenant_id, agent_name, task_id, result_text)
        except Exception:  # a bridge failure must never break task completion
            logger.warning("FindingsBridge handler failed", exc_info=True)


findings_bridge_handler = FindingsBridgeHandler()
