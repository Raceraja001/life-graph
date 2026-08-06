"""Turn an advisory persona's finished run into notifications.

scout/admin/tutor end their reply with a JSON array of findings; this module
extracts them and (Task 2) creates a Notification per finding, pushing urgent
ones immediately. Malformed/absent JSON falls back to a single digest so a
finding is never silently dropped.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_VALID_URGENCY = {"now", "brief"}
# Last ``[ ... ]`` block in the text, across newlines.
_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def parse_findings(result_text: str) -> list[dict[str, Any]]:
    """Extract the trailing JSON findings array from a persona's reply.

    Returns a list of ``{"title","detail","urgency"}`` dicts. Unknown urgency
    values coerce to ``"brief"``. Returns ``[]`` when no valid array is found.
    """
    if not result_text:
        return []
    match = _ARRAY_RE.search(result_text)
    if not match:
        return []
    try:
        raw = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
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


def _json_array_found(result_text: str) -> bool:
    """Check if a JSON array was found in the text."""
    if not result_text:
        return False
    match = _ARRAY_RE.search(result_text)
    if not match:
        return False
    try:
        raw = json.loads(match.group(0))
        return isinstance(raw, list)
    except (json.JSONDecodeError, ValueError):
        return False


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
        findings = parse_findings(result_text)
        # Fallback to digest only if no JSON array was found and text is not empty
        if not findings and result_text.strip() and not _json_array_found(result_text):
            findings = [{"title": f"{agent_name} update", "detail": result_text.strip(), "urgency": "brief"}]

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
