"""Google Tasks API source (OAuth, ``tasks.readonly``).

Every task list, then each list's tasks. The first sync of a day lists
everything open plus what was completed in the last week, returned as the
complete set so the runtime drops anything gone; later syncs ask only for what
changed since (``updatedMin``), including deletions. Read-only twice over: the
scope cannot write, and only GET requests are made.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from life_graph.config import settings
from life_graph.connectors.base import (
    DIR_OWN,
    KIND_TASK,
    Account,
    ConnectorError,
    Item,
    ReauthRequiredError,
)

logger = logging.getLogger(__name__)

API = "https://tasks.googleapis.com/tasks/v1"
PAGE_SIZE = 100
MAX_PAGES = 30
DONE_KEEP_DAYS = 7
FULL_EVERY = timedelta(hours=24)
# Overlap between incremental syncs, so an update written as a sync ran is not missed.
MARGIN = timedelta(minutes=5)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.user_timezone)
    except Exception:
        return ZoneInfo("UTC")


def _reason(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
    except ValueError:
        return resp.text[:200]
    parts = [err.get("status", ""), err.get("message", "")]
    parts += [d.get("reason", "") for d in err.get("details", []) or [] if isinstance(d, dict)]
    parts += [e.get("reason", "") for e in err.get("errors", []) or [] if isinstance(e, dict)]
    return " ".join(p for p in parts if p)


async def _get(http: httpx.AsyncClient, path: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        resp = await http.get(f"{API}{path}", params=params)
    except httpx.HTTPError as exc:
        raise ConnectorError(f"could not reach Google Tasks: {type(exc).__name__}") from exc
    if resp.status_code == 200:
        return resp.json()
    reason = _reason(resp)
    if resp.status_code == 401:
        raise ReauthRequiredError("Google refused access (HTTP 401); reconnect")
    if resp.status_code == 403:
        if any(
            s in reason for s in ("SERVICE_DISABLED", "accessNotConfigured", "has not been used")
        ):
            raise ConnectorError(
                "the Google Tasks API is not enabled in your Google Cloud project: enable it"
                " under APIs & Services, then sync again"
            )
        raise ReauthRequiredError("Google refused access to tasks (HTTP 403); reconnect")
    if resp.status_code == 429:
        raise ConnectorError("Google Tasks rate limit reached; will retry later")
    raise ConnectorError(f"Google Tasks error {resp.status_code}: {reason[:200]}")


async def _paged(http: httpx.AsyncClient, path: str, params: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    page = None
    for _ in range(MAX_PAGES):
        data = await _get(http, path, {**params, **({"pageToken": page} if page else {})})
        out.extend(data.get("items") or [])
        page = data.get("nextPageToken")
        if not page:
            break
    return out


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def task_item(list_id: str, list_title: str, task: dict[str, Any]) -> Item | None:
    """One task → an Item. Google keeps only the date of ``due``; its time is always 00:00Z."""
    if not task.get("id") or task.get("deleted"):
        return None
    title = " ".join((task.get("title") or "").split())
    if not title:
        return None  # an empty placeholder row
    due_at: datetime | None = None
    due_day: date | None = None
    if parsed := _when(task.get("due")):
        due_day = parsed.date()
        due_at = datetime.combine(due_day, time.min, tzinfo=_tz()).astimezone(UTC)
    completed = task.get("status") == "completed"
    flags: dict[str, Any] = {
        "list": list_title,
        "status": task.get("status") or "needsAction",
        "due": due_day.isoformat() if due_day else None,
        "completed_at": task.get("completed") if completed else None,
        "parent": f"{list_id}:{task['parent']}" if task.get("parent") else None,
        "url": task.get("webViewLink"),
    }
    return Item(
        kind=KIND_TASK,
        external_id=f"{list_id}:{task['id']}",
        direction=DIR_OWN,
        occurred_at=_when(task.get("updated")) or datetime.now(UTC),
        title=title[:300],
        starts_at=due_at,
        detail=(task.get("notes") or "").strip()[:2000] or None,
        flags={k: v for k, v in flags.items() if v is not None},
    )


async def sync(
    account: Account, secret: dict[str, Any], cursor: dict[str, Any]
) -> tuple[list[Item], list[str], dict[str, Any], bool]:
    """(items, deleted ids, new cursor, complete)."""
    token = secret.get("access_token")
    if not token:
        raise ReauthRequiredError("no Google access token")
    now = datetime.now(UTC)
    state = cursor.get("tasks") or {}
    last_full = _when(state.get("full_at"))
    since = _when(state.get("updated_min"))
    full = not since or not last_full or now - last_full >= FULL_EVERY
    params = {"showCompleted": "true", "showHidden": "true", "maxResults": str(PAGE_SIZE)}
    if not full:
        params["updatedMin"] = (since - MARGIN).isoformat()
        params["showDeleted"] = "true"
    # Old completed tasks are dropped here rather than with ``completedMin``,
    # so a filter on completion date can never hide an open task.
    done_cut = now - timedelta(days=DONE_KEEP_DAYS)
    items: list[Item] = []
    deleted: list[str] = []
    async with httpx.AsyncClient(timeout=45, headers={"Authorization": f"Bearer {token}"}) as http:
        lists = await _paged(http, "/users/@me/lists", {"maxResults": "100"})
        for lst in lists:
            list_id, list_title = lst.get("id"), lst.get("title") or "Tasks"
            if not list_id:
                continue
            for task in await _paged(http, f"/lists/{list_id}/tasks", params):
                if task.get("deleted"):
                    deleted.append(f"{list_id}:{task.get('id')}")
                    continue
                done_at = _when(task.get("completed"))
                if task.get("status") == "completed" and done_at and done_at < done_cut:
                    deleted.append(f"{list_id}:{task.get('id')}")
                    continue
                item = task_item(list_id, list_title, task)
                if item is not None:
                    items.append(item)
    new_state = {
        "updated_min": now.isoformat(),
        "full_at": (now if full else last_full).isoformat(),
    }
    return items, deleted, {"tasks": new_state}, full
