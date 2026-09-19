"""One contact → one ``Item``, the same way for every source.

Public-ish fields (name, organisation, addresses, birthday as month-day) go in
columns and flags, where the exposure table can release them per account.
Everything else (phone numbers, postal addresses, notes, relations, birth year)
goes in ``detail`` as JSON: ``local_detail`` in the store, which only a local
audience sees unless the account opts a group in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from life_graph.connectors.base import DIR_OWN, KIND_CONTACT, Item

MAX_FIELD = 500
MAX_NOTES = 2000
MAX_LIST = 10


@dataclass
class Person:
    external_id: str
    direction: str = DIR_OWN
    name: str = ""
    emails: list[str] = field(default_factory=list)
    org: str | None = None
    job_title: str | None = None
    birth_month: int | None = None
    birth_day: int | None = None
    birth_year: int | None = None
    phones: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    notes: str | None = None
    relations: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    starred: bool = False
    updated: datetime | None = None


def _short(value: str | None, limit: int = MAX_FIELD) -> str | None:
    value = " ".join((value or "").split())
    return value[:limit] or None


def _unique(values: list[str], *, lower: bool = False) -> list[str]:
    out: list[str] = []
    for v in values:
        v = (v or "").strip()
        if lower:
            v = v.lower()
        if v and v not in out:
            out.append(v[:MAX_FIELD])
    return out[:MAX_LIST]


def valid_birthday(month: int | None, day: int | None) -> bool:
    if not month or not day or not 1 <= month <= 12:
        return False
    # 2000 is a leap year, so 29 February is accepted.
    try:
        datetime(2000, month, day)
    except ValueError:
        return False
    return True


def to_item(p: Person) -> Item | None:
    """None for an entry with nothing to identify it by."""
    emails = [e for e in _unique(p.emails, lower=True) if "@" in e]
    phones = _unique(p.phones)
    name = _short(p.name) or (emails[0] if emails else None) or (phones[0] if phones else None)
    if not name:
        return None
    flags: dict = {}
    if p.org:
        flags["org"] = _short(p.org)
    if p.job_title:
        flags["job_title"] = _short(p.job_title)
    if valid_birthday(p.birth_month, p.birth_day):
        flags["birthday"] = f"{p.birth_month:02d}-{p.birth_day:02d}"
    groups = _unique(p.groups)
    if groups:
        flags["groups"] = groups
    if p.starred:
        flags["starred"] = True
    private = {
        "phones": phones,
        "addresses": _unique([" ".join(a.split()) for a in p.addresses]),
        "notes": (p.notes or "").strip()[:MAX_NOTES] or None,
        "relations": _unique(p.relations),
        "birth_year": p.birth_year if valid_birthday(p.birth_month, p.birth_day) else None,
    }
    private = {k: v for k, v in private.items() if v}
    return Item(
        kind=KIND_CONTACT,
        external_id=p.external_id,
        direction=p.direction,
        occurred_at=p.updated or datetime.now(UTC),
        title=name,
        emails=emails,
        detail=json.dumps(private, ensure_ascii=False) if private else None,
        flags=flags,
    )
