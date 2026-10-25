"""reminder_set: Jarvis sets a timed reminder when the owner asks.

"Remind me to call Murugan at 6", typed or spoken on the phone, becomes a
time ``Intention`` (services/reminders.py); when it is due,
services/due_notifications.py posts it to the phone. The chat stream shows the
result as a ``reminded`` event, and the voice reply lists it (api/jarvis.py),
from the run's task id stored with the reminder.

After a run has read outside content (an email, a web page, a worker's report)
it refuses (core/run_taint.py): that text must not be able to schedule things
in the owner's name.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from life_graph.core.run_taint import TAINTED_REFUSAL, outside_content_seen
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(
    name="reminder_set",
    description=(
        "Set a reminder when the user asks ('remind me to…', 'set a reminder…')."
        " The phone notifies them at that time. Pass `at` as ISO-8601 in the"
        " user's timezone (use get_current_datetime for now), or a simple phrase:"
        " '6 pm', 'at 18:30', 'tomorrow 9 am', 'in 2 hours'. If the user gave no"
        " clear time, ask them; never guess. Tell the user in a few words what"
        " and when."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "What to remind them of, in their words, e.g. 'Call Murugan'.",
            },
            "at": {
                "type": "string",
                "description": "When: '2026-10-25T18:00:00+05:30', '6 pm', 'tomorrow 9 am'.",
            },
        },
        "required": ["text", "at"],
    },
)
async def reminder_set(text: str, at: str) -> str:
    """Create one pending time reminder for the current tenant. Never raises."""
    from life_graph.connectors.tools import user_tz
    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.services import reminders
    from life_graph.storage.database import async_session

    ctx = get_current_task_context()
    if has_tenant_context():
        tenant_id = get_current_tenant_id()
    elif ctx is not None:
        tenant_id = ctx.tenant_id
    else:
        return json.dumps({"error": "reminder_set has no tenant context."})
    if outside_content_seen():
        return json.dumps({"error": TAINTED_REFUSAL})
    words = reminders.clean_text(text)
    if len(words) < 2:
        return json.dumps({"error": "What should the reminder say? Ask the user."})
    if len(words) > reminders.MAX_TEXT_CHARS:
        return json.dumps(
            {"error": f"Too long: keep it under {reminders.MAX_TEXT_CHARS} characters."}
        )
    tz, now = user_tz(), datetime.now(UTC)
    try:
        when = reminders.parse_when(at, now, tz)
    except reminders.WhenError as exc:
        return json.dumps({"error": str(exc)})
    problem = reminders.check_when(when, now)
    if problem:
        return json.dumps({"error": problem})
    task_id = str(ctx.root_task_id or ctx.task_id) if ctx is not None else None
    try:
        async with async_session() as session:
            row = await reminders.create(session, tenant_id, words, when, task_id=task_id)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        # Never the text: it is personal.
        logger.warning("reminder_set failed (%d chars): %s", len(words), exc)
        return json.dumps({"error": f"Could not set the reminder: {exc}"})
    # Not ASCII-escaped, as memory_save's result: the chat stream trims a tool
    # result before the phone's "reminded" event is read from it.
    return json.dumps(
        {
            "reminded": True,
            "id": str(row.id),
            "text": words,
            "at": when.isoformat(),
            "when": reminders.say_when(when, now, tz),
        },
        ensure_ascii=False,
    )
