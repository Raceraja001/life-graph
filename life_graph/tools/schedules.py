"""ask_schedule: Jarvis takes on a recurring ask when the owner sets one.

"Every Monday at 9, summarise my week" becomes a scheduled ask
(services/scheduled_asks.py): it runs on its own at that time, on the local
model, and the answer arrives in this chat and as a notification.

Like reminder_set, after a run has read outside content it refuses unless the
owner's own typed words ask for something recurring (core/run_taint.py): a
page or an email must not be able to set Jarvis jobs in the owner's name.
"""

from __future__ import annotations

import json
import logging
import re

from life_graph.core.run_taint import TAINTED_REFUSAL, outside_content_seen
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

#: The owner asking for something recurring in their own typed message.
RECURRING_INTENT = re.compile(
    r"\b(every|each|daily|weekly|monthly|hourly|weekdays?|weekends?)\b", re.IGNORECASE
)


@tool(
    name="ask_schedule",
    description=(
        "Take on a recurring ask when the user wants something done on a schedule"
        " ('every Monday at 9 summarise my week', 'each evening tell me what is due"
        " tomorrow'). `ask` is what to do each time, in the user's words; `when` is"
        " the repeating time as they said it ('every Monday at 9', 'every weekday at"
        " 8:30', 'every day at 7 pm'). For a one-off use reminder_set instead. If"
        " the time is unclear, ask; never guess. Tell the user in a few words what"
        " will happen and when."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "ask": {
                "type": "string",
                "description": "What to do each time, e.g. 'Summarise my week'.",
            },
            "when": {
                "type": "string",
                "description": "The repeating time, e.g. 'every Monday at 9'.",
            },
        },
        "required": ["ask", "when"],
    },
)
async def ask_schedule(ask: str, when: str) -> str:
    """Store one scheduled ask for the current tenant. Never raises."""
    from life_graph.api.dependencies import get_scheduler_service
    from life_graph.config import settings
    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.services import scheduled_asks
    from life_graph.storage.database import async_session

    ctx = get_current_task_context()
    if has_tenant_context():
        tenant_id = get_current_tenant_id()
    elif ctx is not None:
        tenant_id = ctx.tenant_id
    else:
        return json.dumps({"error": "ask_schedule has no tenant context."})
    from life_graph.tools.memory_search import _owner_message

    owner = await _owner_message(ctx)
    if outside_content_seen() and not RECURRING_INTENT.search(owner):
        return json.dumps({"error": TAINTED_REFUSAL})
    session_id, origin = await _session_of(ctx)
    if origin == "scheduled":
        # A firing ask runs with no one typing: it never sets up more of itself.
        return json.dumps({"error": "A scheduled ask cannot set up another one."})
    try:
        job = await scheduled_asks.create(
            get_scheduler_service(),
            async_session,
            tenant_id,
            ask=ask,
            when=when,
            tz=settings.user_timezone or "UTC",
            session_id=session_id,
        )
    except scheduled_asks.AskError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        # Never the ask: it is personal.
        logger.warning("ask_schedule failed: %s", exc)
        return json.dumps({"error": f"Could not set it up: {exc}"})
    props = job.get("properties") or {}
    return json.dumps(
        {
            "scheduled": True,
            "id": str(job["id"]),
            "ask": props.get("ask"),
            "when": props.get("when"),
            "next_run_at": job.get("next_run_at"),
        },
        ensure_ascii=False,
    )


async def _session_of(ctx) -> tuple[str | None, str | None]:
    """The chat this run belongs to (so each answer lands there) and its origin."""
    if ctx is None:
        return None, None
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as session:
        task = await session.get(AgentTask, ctx.root_task_id or ctx.task_id)
    if task is None:
        return None, None
    return (str(task.session_id) if task.session_id else None), (task.input or {}).get("origin")
