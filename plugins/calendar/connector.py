"""Calendar connector implementation (see ``plugins/calendar/__init__.py``)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from life_graph.config import settings
from life_graph.connectors.base import (
    AUTH_NONE,
    AUTH_OAUTH,
    DIR_INVITE,
    DIR_OWN,
    KIND_EVENT,
    Account,
    ConnectorError,
    Item,
    ReauthRequiredError,
    SyncResult,
)

logger = logging.getLogger(__name__)

GOOGLE_EVENTS = "https://www.googleapis.com/calendar/v3/calendars/{cal}/events"
MAX_DETAIL = 2000
MAX_ATTENDEES = 25


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.user_timezone)
    except Exception:
        return ZoneInfo("UTC")


def _window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return (
        now - timedelta(days=settings.connector_event_past_days),
        now + timedelta(days=settings.connector_event_future_days),
    )


def _as_utc(value: Any, tz: ZoneInfo) -> tuple[datetime, bool]:
    """(UTC datetime, all_day) from an ICS/Google date or datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return value.astimezone(UTC), False
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=tz).astimezone(UTC), True
    raise ValueError(f"not a date: {value!r}")


def _addr(value: Any) -> str:
    text = str(value or "")
    return text[7:].lower() if text.lower().startswith("mailto:") else text.lower()


class CalendarConnector:
    name = "calendar"
    display_name = "Calendar"
    item_kinds = frozenset({KIND_EVENT})
    auth_methods = (AUTH_NONE, AUTH_OAUTH)
    account_fields = (
        {"name": "username", "label": "Google account (for sign-in)", "methods": [AUTH_OAUTH]},
        {
            "name": "my_addresses",
            "label": "Your email addresses (events you organise count as yours)",
            "methods": [AUTH_NONE, AUTH_OAUTH],
            "list": True,
        },
        {
            "name": "calendar_ids",
            "label": "Calendar IDs (default: primary)",
            "methods": [AUTH_OAUTH],
            "list": True,
        },
    )

    def validate_settings(self, auth_method: str, raw: dict[str, Any]) -> dict[str, Any]:
        def as_list(v: Any) -> list[str]:
            if isinstance(v, str):
                v = [p for p in v.replace(";", ",").split(",")]
            return [str(p).strip() for p in (v or []) if str(p).strip()]

        out: dict[str, Any] = {
            "my_addresses": [a.lower() for a in as_list(raw.get("my_addresses"))]
        }
        if raw.get("username"):
            out["username"] = str(raw["username"]).strip()
            if out["username"].lower() not in out["my_addresses"]:
                out["my_addresses"].append(out["username"].lower())
        if auth_method == AUTH_OAUTH:
            out["calendar_ids"] = as_list(raw.get("calendar_ids")) or ["primary"]
        return out

    async def sync(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        if account.auth_method == AUTH_OAUTH:
            return await self._sync_google(account, secret, cursor)
        return await self._sync_ics(account, secret, cursor)

    async def fetch_body(
        self, account: Account, secret: dict[str, Any], external_id: str
    ) -> str | None:
        return None  # event text is already in the index (local_detail)

    # ── ICS feed ──────────────────────────────────────────────

    async def _sync_ics(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        url = str(secret.get("url") or "").strip()
        if url.lower().startswith("webcal://"):
            url = "https://" + url[len("webcal://") :]
        if not url.lower().startswith(("https://", "http://")):
            raise ReauthRequiredError("no calendar feed link stored; paste the secret iCal address")
        headers = {}
        if cursor.get("etag"):
            headers["If-None-Match"] = cursor["etag"]
        if cursor.get("last_modified"):
            headers["If-Modified-Since"] = cursor["last_modified"]
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
                resp = await http.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"could not fetch the calendar feed: {type(exc).__name__}"
            ) from exc
        if resp.status_code == 304:
            return SyncResult(cursor=cursor)
        if resp.status_code in (401, 403, 404, 410):
            raise ReauthRequiredError(
                f"the calendar feed link was refused (HTTP {resp.status_code}); it may have been"
                " reset — paste the current secret address"
            )
        if resp.status_code >= 400:
            raise ConnectorError(f"calendar feed returned HTTP {resp.status_code}")
        items = parse_ics(resp.content, set(account.settings.get("my_addresses") or []))
        new_cursor = {
            k: v
            for k, v in (
                ("etag", resp.headers.get("etag")),
                ("last_modified", resp.headers.get("last-modified")),
            )
            if v
        }
        return SyncResult(items=items, cursor=new_cursor, complete=True)

    # ── Google Calendar API ───────────────────────────────────

    async def _sync_google(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        token = secret.get("access_token")
        if not token:
            raise ReauthRequiredError("no Google access token")
        my = set(account.settings.get("my_addresses") or [])
        cal_ids = account.settings.get("calendar_ids") or ["primary"]
        tokens = dict(cursor.get("sync_tokens") or {})
        items: list[Item] = []
        deleted: list[str] = []
        full_resync_done = False
        async with httpx.AsyncClient(
            timeout=60, headers={"Authorization": f"Bearer {token}"}
        ) as http:
            for cal in cal_ids:
                got, gone, next_token, full = await self._google_calendar(
                    http, cal, tokens.get(cal), my
                )
                items.extend(got)
                deleted.extend(gone)
                if next_token:
                    tokens[cal] = next_token
                full_resync_done = full_resync_done or full
        # A full (windowed) listing is complete only when every calendar was
        # listed in full this round; incremental rounds only report changes.
        complete = full_resync_done and all(
            c not in (cursor.get("sync_tokens") or {}) for c in cal_ids
        )
        return SyncResult(
            items=items, deleted=deleted, cursor={"sync_tokens": tokens}, complete=complete
        )

    async def _google_calendar(
        self, http: httpx.AsyncClient, cal: str, sync_token: str | None, my: set[str]
    ) -> tuple[list[Item], list[str], str | None, bool]:
        start, end = _window()
        base = {"singleEvents": "true", "maxResults": "2500", "showDeleted": "true"}
        params = (
            {**base, "syncToken": sync_token}
            if sync_token
            else {**base, "timeMin": start.isoformat(), "timeMax": end.isoformat()}
        )
        items: list[Item] = []
        deleted: list[str] = []
        page = None
        while True:
            q = {**params, **({"pageToken": page} if page else {})}
            resp = await http.get(GOOGLE_EVENTS.format(cal=cal), params=q)
            if resp.status_code == 410 and sync_token:
                # Sync token expired: start over with a full windowed listing.
                return await self._google_calendar(http, cal, None, my)
            if resp.status_code in (401, 403):
                raise ReauthRequiredError(
                    f"Google Calendar refused access (HTTP {resp.status_code}); reconnect"
                )
            if resp.status_code >= 400:
                raise ConnectorError(f"Google Calendar error {resp.status_code} for {cal}")
            data = resp.json()
            for ev in data.get("items", []):
                if ev.get("status") == "cancelled":
                    deleted.append(f"{cal}:{ev['id']}")
                    continue
                item = google_event_item(cal, ev, my)
                if item is not None:
                    items.append(item)
            page = data.get("nextPageToken")
            if not page:
                return items, deleted, data.get("nextSyncToken"), sync_token is None


def google_event_item(cal: str, ev: dict[str, Any], my: set[str]) -> Item | None:
    tz = _tz()
    start_raw, end_raw = ev.get("start") or {}, ev.get("end") or {}
    try:
        if "dateTime" in start_raw:
            starts, all_day = datetime.fromisoformat(start_raw["dateTime"]).astimezone(UTC), False
            ends = datetime.fromisoformat(
                end_raw.get("dateTime", start_raw["dateTime"])
            ).astimezone(UTC)
        else:
            starts, all_day = _as_utc(date.fromisoformat(start_raw["date"]), tz)
            ends, _ = _as_utc(date.fromisoformat(end_raw.get("date", start_raw["date"])), tz)
    except (KeyError, ValueError):
        return None
    attendees = ev.get("attendees") or []
    me = next((a for a in attendees if a.get("self")), None)
    if me and me.get("responseStatus") == "declined":
        return None
    organizer = ev.get("organizer") or {}
    own = bool(organizer.get("self")) or (organizer.get("email", "").lower() in my) or not organizer
    detail_parts = [ev.get("description") or ""]
    if ev.get("hangoutLink"):
        detail_parts.append(f"Meet: {ev['hangoutLink']}")
    return Item(
        kind=KIND_EVENT,
        external_id=f"{cal}:{ev['id']}",
        direction=DIR_OWN if own else DIR_INVITE,
        occurred_at=starts,
        title=ev.get("summary") or "(no title)",
        starts_at=starts,
        ends_at=ends,
        all_day=all_day,
        location=ev.get("location"),
        attendees=[
            a.get("displayName") or a.get("email", "") for a in attendees if not a.get("self")
        ][:MAX_ATTENDEES],
        detail="\n".join(p for p in detail_parts if p)[:MAX_DETAIL] or None,
        flags={
            "calendar": cal,
            **({"tentative": True} if me and me.get("responseStatus") == "tentative" else {}),
        },
    )


def parse_ics(content: bytes, my_addresses: set[str]) -> list[Item]:
    """Expand an ICS feed into event items within the retention window."""
    import icalendar
    import recurring_ical_events

    try:
        cal = icalendar.Calendar.from_ical(content)
    except Exception as exc:
        raise ConnectorError("the calendar feed is not valid iCalendar data") from exc
    tz = _tz()
    start, end = _window()
    items: list[Item] = []
    seen: set[str] = set()
    for ev in recurring_ical_events.of(cal).between(start, end):
        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
            continue
        uid = str(ev.get("UID") or "")
        try:
            starts, all_day = _as_utc(ev.decoded("DTSTART"), tz)
            ends = _as_utc(ev.decoded("DTEND"), tz)[0] if ev.get("DTEND") else starts
        except (KeyError, ValueError):
            continue
        external_id = (
            f"{uid}:{starts.isoformat()}"
            if uid
            else f"anon:{starts.isoformat()}:{ev.get('SUMMARY')}"
        )
        if external_id in seen:
            continue
        seen.add(external_id)
        organizer = _addr(ev.get("ORGANIZER"))
        own = not organizer or organizer in my_addresses
        attendees_raw = ev.get("ATTENDEE") or []
        if not isinstance(attendees_raw, list):
            attendees_raw = [attendees_raw]
        mine = [a for a in attendees_raw if _addr(a) in my_addresses]
        if mine and str(mine[0].params.get("PARTSTAT", "")).upper() == "DECLINED":
            continue
        attendees = [
            str(a.params.get("CN") or _addr(a))
            for a in attendees_raw
            if _addr(a) not in my_addresses
        ][:MAX_ATTENDEES]
        detail = "\n".join(
            str(p)
            for p in (ev.get("DESCRIPTION"), ev.get("URL"), ev.get("X-GOOGLE-CONFERENCE"))
            if p
        )
        items.append(
            Item(
                kind=KIND_EVENT,
                external_id=external_id,
                direction=DIR_OWN if own else DIR_INVITE,
                occurred_at=starts,
                title=str(ev.get("SUMMARY") or "(no title)"),
                starts_at=starts,
                ends_at=ends,
                all_day=all_day,
                location=str(ev.get("LOCATION")) if ev.get("LOCATION") else None,
                attendees=attendees,
                detail=detail[:MAX_DETAIL] or None,
            )
        )
    return items
