"""Turn an advisory persona's finished run into notifications.

scout/admin/tutor end their reply with a JSON array of findings; this module
extracts them and creates a Notification per finding, pushing urgent ones
immediately. Malformed/absent JSON falls back to a single digest so a finding
is never silently dropped.
"""

from __future__ import annotations

import json
import logging
from typing import Any

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
