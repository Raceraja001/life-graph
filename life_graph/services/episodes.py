"""Conversation memory: one dated summary per day of what the owner talked about.

Facts alone cannot answer "what did we talk about on Tuesday?" or "what was I
working on last week?": the extractor keeps lasting facts and, by design,
drops the conversation around them (2026-10-22). So once a day the local
model writes a short summary of the previous day, kept as an ordinary active
memory with ``properties.kind = "episode"`` and the day it covers:

* ``jarvis`` — the owner's conversations with Jarvis (questions and replies);
* ``work`` — what the owner asked for in their Claude Code sessions (their
  own prompts only, never the assistant's replies).

Questions about a time ("yesterday", "last week", "on Monday") fetch that
period's summaries directly (:func:`time_window`, :func:`episodes_between`):
search cannot guess which dates "last week" means.

Local model only: these are the owner's conversations. Idempotent per
(day, source), so the hourly job can run as often as it likes.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select, text

from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

KIND = "episode"
SOURCES = ("jarvis", "work")
MAX_TURNS = 60
MAX_TURN_CHARS = 500
MAX_PROMPTS = 80
MACHINE_PREFIXES = (
    "<task-notification>",
    "<agent-message",
    "<cross-session-message",
    "<local-command",
    "<command-",
    "<system-reminder>",
)

PROMPT = """\
You keep one person's memory (the owner). Below is one day of their {what}.
Write 1-6 plain sentences: what they asked about or worked on, what they
decided or planned, and anything they said about themselves. Name the projects
and topics. A thin day gets one sentence.
Never: describe their mood or attitude ("focused", "determined"), say what they
did not mention, add a "Topics:" list, or include anything that is not in the
text. Start directly with the content, no heading."""

WHAT = {
    "jarvis": "conversations with their assistant Jarvis (their messages and its replies)",
    "work": "requests to their coding assistant (their own messages only)",
}
LABEL = {"jarvis": "Conversations with Jarvis", "work": "Work with the coding assistant"}


def _tz():
    from life_graph.connectors.tools import user_tz

    return user_tz()


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """The day in UTC; it starts no earlier than ``memory_start_at`` (a fresh
    start), so a day before it is empty and one it falls in is cut short."""
    from life_graph.config import settings

    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = (start + timedelta(days=1)).astimezone(UTC)
    start = start.astimezone(UTC)
    floor = settings.memory_start()
    if floor is not None:
        start = min(max(start, floor), end)
    return start, end


async def _jarvis_turns(tenant_id: str, day: date) -> tuple[list[str], list[str]]:
    from life_graph.models.db import AgentTask

    start, end = _day_bounds(day)
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.agent_name == "jarvis",
                        AgentTask.parent_task_id.is_(None),
                        AgentTask.status == "completed",
                        AgentTask.created_at >= start,
                        AgentTask.created_at < end,
                    )
                    .order_by(AgentTask.created_at)
                    .limit(MAX_TURNS)
                )
            )
            .scalars()
            .all()
        )
    lines, sessions = [], []
    for t in rows:
        asked = str((t.input or {}).get("message") or "").strip()
        answered = str((t.result or {}).get("response") or "").strip()
        if not asked:
            continue
        lines.append(f"Owner: {' '.join(asked.split())[:MAX_TURN_CHARS]}")
        if answered:
            lines.append(f"Jarvis: {' '.join(answered.split())[:MAX_TURN_CHARS]}")
        if t.session_id and str(t.session_id) not in sessions:
            sessions.append(str(t.session_id))
    return lines, sessions


async def _work_prompts(tenant_id: str, day: date) -> tuple[list[str], list[str]]:
    """The day's prompts, grouped by Claude Code session when there are several.

    Interleaved sessions (two terminals on two projects) read as one muddled
    stream otherwise; under a heading each, the model can tell the threads
    apart. One session, or prompts with no session id, stay a flat list.
    """
    from life_graph.models.db import CaptureEvent
    from life_graph.services.claude_code_sessions import claude_code_session_of

    start, end = _day_bounds(day)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(CaptureEvent.id, CaptureEvent.content, CaptureEvent.properties)
                .where(
                    CaptureEvent.tenant_id == tenant_id,
                    CaptureEvent.surface == "cli",
                    CaptureEvent.created_at >= start,
                    CaptureEvent.created_at < end,
                )
                .order_by(CaptureEvent.created_at)
                .limit(MAX_PROMPTS * 2)
            )
        ).all()
    # Session key -> (project, prompts), in the order sessions first appear.
    groups: dict[str | None, tuple[str | None, list[tuple[str, str]]]] = {}
    kept = 0
    for cid, content, props in rows:
        body = (content or "").strip()
        if not body or body.startswith(MACHINE_PREFIXES):
            continue
        props = props or {}
        key = claude_code_session_of(props)
        project = props.get("project")
        groups.setdefault(key, (str(project) if project else None, []))[1].append(
            (f"- {' '.join(body.split())[:MAX_TURN_CHARS]}", str(cid))
        )
        kept += 1
        if kept >= MAX_PROMPTS:
            break
    lines, ids = [], []
    for n, (project, prompts) in enumerate(groups.values(), start=1):
        if len(groups) > 1:
            lines.append(f"Session {n}" + (f" ({project}):" if project else ":"))
        for line, cid in prompts:
            lines.append(line)
            ids.append(cid)
    return lines, ids


def episode_key(day: date, source: str) -> str:
    return f"{day.isoformat()}:{source}"


async def _exists(tenant_id: str, key: str) -> bool:
    async with async_session() as session:
        found = await session.scalar(
            # Active ones only: archiving a day's summary lets it be written again.
            text(
                "select 1 from memories where tenant_id = :t and status = 'active' "
                "and properties @> CAST(:p AS jsonb) limit 1"
            ),
            {"t": tenant_id, "p": f'{{"kind": "{KIND}", "episode_key": "{key}"}}'},
        )
    return bool(found)


async def summarize(source: str, day: date, lines: list[str]) -> str:
    """The local model's summary of one day, or "" if it gave none."""
    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings

    reply = await get_lm_client().chat_local_only(
        [
            {"role": "system", "content": PROMPT.format(what=WHAT[source])},
            {"role": "user", "content": f"{day:%A %d %B %Y}\n\n" + "\n".join(lines)},
        ],
        model=settings.lm_extraction_model,
        temperature=0.2,
        max_tokens=400,
    )
    return clean(" ".join((reply or "").split()))


#: Sentences the model adds about nothing (seen 2026-10-23 on qwen3:14b despite
#: the prompt): what was not said, mood, "showed intent to…".
_FILLER = re.compile(
    r"\b(did not|didn't|does not|no) (mention|specify|name|discuss)|"
    r"\bno (specific )?(projects?|decisions?|personal details)\b|"
    r"\b(showed|showing|expressed|showed a|displayed) (a |an )?(clear |consistent )?"
    r"(interest|intent|readiness|determination|eagerness)\b|"
    r"\b(focused and determined|appeared focused|stay productive)\b|"
    r"^topics?:|^projects?( mentioned)?:",
    re.IGNORECASE,
)


def clean(summary: str) -> str:
    """Drop filler sentences from a model summary; keep the rest in order."""
    sentences = re.split(r"(?<=[.!?])\s+", summary.strip())
    kept = [s for s in sentences if s and not _FILLER.search(s)]
    return " ".join(kept).strip()


async def write_day(tenant_id: str, day: date) -> list[str]:
    """Write the day's episodes that are missing; return the keys written."""
    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.schemas import MemoryCreate

    written = []
    for source in SOURCES:
        key = episode_key(day, source)
        if await _exists(tenant_id, key):
            continue
        if source == "jarvis":
            lines, refs = await _jarvis_turns(tenant_id, day)
        else:
            lines, refs = await _work_prompts(tenant_id, day)
        if not lines:
            continue
        summary = await summarize(source, day, lines)
        if not summary:
            logger.warning("Episode %s for %s: the model gave no summary", key, tenant_id)
            continue
        content = f"{LABEL[source]} on {day:%A %d %B %Y}: {summary}"
        with tenant_scope(tenant_id):
            embedding = await get_memory_manager().generate_embedding(content)
            row = await get_store().store(
                MemoryCreate(
                    content=content,
                    tags=["episode", source],
                    source_type="episode",
                    importance=0.5,
                    properties={
                        "kind": KIND,
                        "source": source,
                        "date": day.isoformat(),
                        "episode_key": key,
                        "refs": refs[:50],
                    },
                ),
                embedding=embedding or None,
                trust_tier="verified",
                # A summary of what was said, not a new claim about the owner:
                # it does not wait in the review queue.
                status="active",
            )
        # Linked to the people and projects it names, so "everything about X"
        # includes the days X came up (services/entities.py).
        try:
            from life_graph.services import entities

            named = await entities.known_in_text(tenant_id, summary)
            await entities.link(tenant_id, row.id, [name for _, name in named])
        except Exception:
            logger.warning("Entity linking failed for episode %s", key, exc_info=True)
        written.append(key)
    return written


async def write_recent(tenant_id: str, days: int = 1, today: date | None = None) -> list[str]:
    """Episodes for the last *days* full days (not today: it is not over)."""
    today = today or datetime.now(_tz()).date()
    written: list[str] = []
    for back in range(days, 0, -1):
        written += await write_day(tenant_id, today - timedelta(days=back))
    return written


# ── Questions about a time ───────────────────────────────────────────

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def time_window(question: str, today: date) -> tuple[date, date] | None:
    """The days (inclusive) a question is about, if it names a time; else None."""
    q = question.lower()
    if re.search(r"\bday before yesterday\b", q):
        d = today - timedelta(days=2)
        return d, d
    if re.search(r"\byesterday\b", q):
        d = today - timedelta(days=1)
        return d, d
    if m := re.search(r"\b(\d{1,2}) days? ago\b", q):
        d = today - timedelta(days=int(m.group(1)))
        return d, d
    if re.search(r"\blast week\b", q):
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if re.search(r"\bthis week\b", q):
        return today - timedelta(days=today.weekday()), today
    if re.search(r"\blast month\b", q):
        first = today.replace(day=1)
        end = first - timedelta(days=1)
        return end.replace(day=1), end
    if re.search(r"\b(today|this morning)\b", q):
        return today, today
    for i, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b(on |last )?{name}\b", q):
            back = (today.weekday() - i) % 7 or 7
            d = today - timedelta(days=back)
            return d, d
    return None


async def episodes_between(tenant_id: str, start: date, end: date, limit: int = 8) -> list[Any]:
    """Active episode memories covering days start..end (inclusive), oldest first."""
    from life_graph.models.db import Memory

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                        Memory.properties["kind"].astext == KIND,
                        Memory.properties["date"].astext >= start.isoformat(),
                        Memory.properties["date"].astext <= end.isoformat(),
                    )
                    .order_by(Memory.properties["date"].astext)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return list(rows)
