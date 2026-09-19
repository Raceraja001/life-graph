"""Google People API source (OAuth, ``contacts.readonly`` + ``contacts.other.readonly``).

Two lists: the user's saved contacts (``people/me/connections``) and "Other
contacts", the addresses Google keeps from mail (``otherContacts``). Both
support sync tokens; deleted people then come back with ``metadata.deleted``.

A missing or expired sync token on either list means a full listing of both,
returned as the complete set, so the runtime drops anything no longer there.
Read-only twice over: the scopes cannot write, and only GET requests are made.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from life_graph.connectors.base import (
    DIR_INBOUND,
    DIR_OWN,
    Account,
    ConnectorError,
    Item,
    ReauthRequiredError,
)
from plugins.contacts.common import Person, to_item

logger = logging.getLogger(__name__)

API = "https://people.googleapis.com/v1"
PAGE_SIZE = 1000
MAX_PAGES = 50
PERSON_FIELDS = (
    "names,emailAddresses,phoneNumbers,organizations,birthdays,addresses,"
    "biographies,relations,memberships,metadata"
)
OTHER_FIELDS = "names,emailAddresses,phoneNumbers,metadata"
STARRED = "contactGroups/starred"


class ExpiredSyncTokenError(Exception):
    """The list's sync token is too old; list everything again."""


def _error_reason(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
    except ValueError:
        return resp.text[:200]
    reasons = [d.get("reason", "") for d in err.get("details", []) if isinstance(d, dict)]
    return " ".join([err.get("status", ""), err.get("message", ""), *reasons])


async def _get(http: httpx.AsyncClient, path: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        resp = await http.get(f"{API}{path}", params=params)
    except httpx.HTTPError as exc:
        raise ConnectorError(f"could not reach Google Contacts: {type(exc).__name__}") from exc
    if resp.status_code == 200:
        return resp.json()
    reason = _error_reason(resp)
    if resp.status_code == 410 or "EXPIRED_SYNC_TOKEN" in reason or "sync token" in reason.lower():
        raise ExpiredSyncTokenError
    if resp.status_code == 401:
        raise ReauthRequiredError("Google refused access (HTTP 401); reconnect")
    if resp.status_code == 403:
        if "SERVICE_DISABLED" in reason or "has not been used" in reason:
            raise ConnectorError(
                "the People API is not enabled in your Google Cloud project: enable it under"
                " APIs & Services, then sync again"
            )
        raise ReauthRequiredError("Google refused access to contacts (HTTP 403); reconnect")
    if resp.status_code == 429:
        raise ConnectorError("Google Contacts rate limit reached; will retry later")
    raise ConnectorError(f"Google Contacts error {resp.status_code}: {reason[:200]}")


async def _list(
    http: httpx.AsyncClient,
    path: str,
    key: str,
    fields: tuple[str, str],
    sync_token: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Every page of one list: (people, next sync token)."""
    people: list[dict[str, Any]] = []
    page: str | None = None
    next_token: str | None = None
    for _ in range(MAX_PAGES):
        params = {fields[0]: fields[1], "pageSize": str(PAGE_SIZE), "requestSyncToken": "true"}
        if sync_token:
            params["syncToken"] = sync_token
        if page:
            params["pageToken"] = page
        data = await _get(http, path, params)
        people.extend(data.get(key) or [])
        next_token = data.get("nextSyncToken") or next_token
        page = data.get("nextPageToken")
        if not page:
            break
    else:
        logger.warning("Google Contacts %s: stopped after %d pages", path, MAX_PAGES)
    return people, next_token


def _primary(entries: list[dict[str, Any]] | None) -> dict[str, Any]:
    entries = entries or []
    for e in entries:
        if (e.get("metadata") or {}).get("primary"):
            return e
    return entries[0] if entries else {}


def _typed(value: str | None, kind: str | None) -> str | None:
    if not value:
        return None
    return f"{value} ({kind.lower()})" if kind else value


def _updated(meta: dict[str, Any]) -> datetime | None:
    for src in meta.get("sources") or []:
        stamp = src.get("updateTime")
        if stamp:
            try:
                return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def person_item(person: dict[str, Any], direction: str) -> Item | None:
    """One People API person → an Item (None when there is nothing to show)."""
    meta = person.get("metadata") or {}
    name = _primary(person.get("names")).get("displayName") or ""
    org = _primary(person.get("organizations"))
    bday = next((b.get("date") for b in person.get("birthdays") or [] if b.get("date")), None) or {}
    p = Person(
        external_id=person["resourceName"],
        direction=direction,
        name=name,
        emails=[e.get("value", "") for e in person.get("emailAddresses") or []],
        org=org.get("name"),
        job_title=org.get("title"),
        birth_month=bday.get("month"),
        birth_day=bday.get("day"),
        birth_year=bday.get("year"),
        phones=[
            t
            for n in person.get("phoneNumbers") or []
            if (t := _typed(n.get("value"), n.get("formattedType") or n.get("type")))
        ],
        addresses=[
            t
            for a in person.get("addresses") or []
            if (t := _typed(a.get("formattedValue"), a.get("formattedType") or a.get("type")))
        ],
        notes=_primary(person.get("biographies")).get("value"),
        relations=[
            t
            for r in person.get("relations") or []
            if (t := _typed(r.get("person"), r.get("formattedType") or r.get("type")))
        ],
        starred=any(
            (m.get("contactGroupMembership") or {}).get("contactGroupResourceName") == STARRED
            for m in person.get("memberships") or []
        ),
        updated=_updated(meta),
    )
    return to_item(p)


async def sync(
    account: Account, secret: dict[str, Any], cursor: dict[str, Any]
) -> tuple[list[Item], list[str], dict[str, Any], bool]:
    """(items, deleted ids, new cursor, complete)."""
    token = secret.get("access_token")
    if not token:
        raise ReauthRequiredError("no Google access token")
    state = cursor.get("google") or {}
    lists = (
        (
            "connections",
            "/people/me/connections",
            "connections",
            ("personFields", PERSON_FIELDS),
            DIR_OWN,
        ),
        ("other", "/otherContacts", "otherContacts", ("readMask", OTHER_FIELDS), DIR_INBOUND),
    )
    async with httpx.AsyncClient(timeout=45, headers={"Authorization": f"Bearer {token}"}) as http:
        full = not all(state.get(name) for name, *_ in lists)
        try:
            fetched = {
                name: await _list(http, path, key, fields, None if full else state.get(name))
                for name, path, key, fields, _ in lists
            }
        except ExpiredSyncTokenError:
            full = True
            fetched = {
                name: await _list(http, path, key, fields, None)
                for name, path, key, fields, _ in lists
            }
    items: list[Item] = []
    deleted: list[str] = []
    new_state: dict[str, Any] = {}
    for name, _path, _key, _fields, direction in lists:
        people, next_token = fetched[name]
        new_state[name] = next_token
        for person in people:
            if not person.get("resourceName"):
                continue
            if (person.get("metadata") or {}).get("deleted"):
                deleted.append(person["resourceName"])
                continue
            item = person_item(person, direction)
            if item is not None:
                items.append(item)
            elif not full:
                # Emptied at the source (no name, address or number left).
                deleted.append(person["resourceName"])
    return items, deleted, {"google": new_state}, full
