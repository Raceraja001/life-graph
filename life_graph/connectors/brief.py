"""Daily-brief sections from connectors: **Today**, **Waiting on you**, **You promised**, **Birthdays**, **Code**.

Rendered twice. The brief's stored ``body`` is what Telegram and Web Push send
off the machine, so it gets the CLOUD view (redacted, ``local_only`` accounts as
counts). The LOCAL view goes into the brief's metadata for the dashboard.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from life_graph.connectors import store
from life_graph.connectors.exposure import view_items
from life_graph.connectors.locality import CLOUD, LOCAL
from life_graph.connectors.tools import day_bounds, user_tz
from life_graph.storage.database import async_session

MAX_WAITING = 5
EARLY_TOMORROW_HOUR = 10
BIRTHDAY_DAYS = 4  # today and the next three days


async def collect(tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Raw rows: today's events, tomorrow's early start, mail waiting on the user,
    promises, upcoming birthdays, and the contacts behind the addresses in them."""
    now = now or datetime.now(UTC)
    today = now.astimezone(user_tz()).date()
    start, end = day_bounds(today)
    t_start, t_end = day_bounds(today + timedelta(days=1))
    async with async_session() as session:
        events = await store.events_between(session, tenant_id, start, end)
        tomorrow = await store.events_between(session, tenant_id, t_start, t_end, limit=5)
        waiting = await store.waiting_on_me(session, tenant_id, now)
        promises = await store.open_promises(session, tenant_id, now)
        birthdays = await store.birthdays_between(session, tenant_id, today, BIRTHDAY_DAYS)
        code = await store.code_items(session, tenant_id)
        addrs = {m["sender_addr"] for m in waiting if m.get("sender_addr")}
        addrs.update(a for e in events for a in e["emails"])
        people = await store.people_by_address(session, tenant_id, addrs)
    early = [
        e
        for e in tomorrow
        if e["starts_at"]
        and not (e.get("flags") or {}).get("all_day")
        and e["starts_at"].astimezone(user_tz()).hour < EARLY_TOMORROW_HOUR
    ][:1]
    return {
        "today": events,
        "tomorrow_early": early,
        "waiting": waiting,
        "promises": promises,
        "birthdays": birthdays,
        "code": code,
        "people": people,
    }


def _hm(iso: str | None) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).astimezone(user_tz()).strftime("%H:%M")


def _conflicts(events: list[dict[str, Any]]) -> set[str]:
    timed = [e for e in events if not e["all_day"] and e["starts_at"] and e["ends_at"]]
    clash: set[str] = set()
    for i, a in enumerate(timed):
        for b in timed[i + 1 :]:
            if a["starts_at"] < b["ends_at"] and b["starts_at"] < a["ends_at"]:
                clash.update((a["id"], b["id"]))
    return clash


def _event_line(e: dict[str, Any], clash: set[str]) -> str:
    when = "all day" if e["all_day"] else f"{_hm(e['starts_at'])}–{_hm(e['ends_at'])}"
    where = f" @ {e['location']}" if e.get("location") else ""
    flag = "  ⚠ overlaps" if e["id"] in clash else ""
    return f"- {when} {e['title']}{where} ({e['account']}){flag}"


def _age(iso: str | None, now: datetime) -> str:
    if not iso:
        return ""
    hours = (now - datetime.fromisoformat(iso)).total_seconds() / 3600
    return f"{int(hours // 24)}d" if hours >= 24 else f"{int(hours)}h"


def _birthday_lines(shown: dict[str, Any], now: datetime) -> list[str]:
    today = now.astimezone(user_tz()).date()
    lines = []
    for c in shown["items"]:
        d = date.fromisoformat(c["on"])
        if d == today:
            when = "today"
        elif d == today + timedelta(days=1):
            when = "tomorrow"
        else:
            when = f"{d:%a %d %b}"
        lines.append(f"- {c['name']} — {when}")
    for account, n in shown["withheld"].items():
        lines.append(f"- +{n} in {account} (details on the dashboard)")
    return lines


MAX_CODE = 3


def _ref(c: dict[str, Any]) -> str:
    agent = " (dev agent)" if c.get("dev_agent") else ""
    return f"{(c.get('repo') or '').split('/')[-1]}#{c.get('number')}{agent}"


def pr_state(c: dict[str, Any]) -> tuple[int, str]:
    """(urgency rank, label) for one of the user's own pull requests; lower is more urgent."""
    if c.get("review") == "CHANGES_REQUESTED":
        return 0, "changes requested"
    if c.get("ci") in ("FAILURE", "ERROR"):
        return 1, "CI failing"
    if c.get("mergeable") == "CONFLICTING":
        return 2, "merge conflict"
    if c.get("review") == "APPROVED" and c.get("ci") in (None, "SUCCESS"):
        return 3, "approved, ready to merge"
    return 9, "waiting on reviewers"


def _code_lines(code: dict[str, Any], now: datetime) -> list[str]:
    items = code["items"]
    reviews = sorted(
        (c for c in items if c.get("sub") == "pr_review" and not c.get("draft")),
        key=lambda c: c.get("created") or "",
    )
    mine = sorted(
        (c for c in items if c.get("sub") == "pr_mine" and not c.get("draft")),
        key=lambda c: pr_state(c)[0],
    )
    issues = [c for c in items if c.get("sub") == "issue"]
    lines: list[str] = []
    if reviews:
        shown = "; ".join(
            f"{_ref(c)} {c['title']} ({c.get('author') or '?'}, {_age(c.get('created'), now)})"
            for c in reviews[:MAX_CODE]
        )
        more = f"; +{len(reviews) - MAX_CODE} more" if len(reviews) > MAX_CODE else ""
        lines.append(f"- Review requested ({len(reviews)}): {shown}{more}")
    acting = [c for c in mine if pr_state(c)[0] < 9]
    waiting = len(mine) - len(acting)
    if acting or waiting:
        parts = [f"{_ref(c)} — {pr_state(c)[1]}" for c in acting[:MAX_CODE]]
        if len(acting) > MAX_CODE:
            parts.append(f"+{len(acting) - MAX_CODE} more")
        if waiting:
            parts.append(f"{waiting} waiting on reviewers")
        lines.append("- Your PRs: " + " · ".join(parts))
    if issues:
        shown = "; ".join(f"{_ref(c)} {c['title']}" for c in issues[:MAX_CODE])
        more = f"; +{len(issues) - MAX_CODE} more" if len(issues) > MAX_CODE else ""
        lines.append(f"- Assigned issues ({len(issues)}): {shown}{more}")
    for account, n in code["withheld"].items():
        lines.append(f"- +{n} in {account} (details on the dashboard)")
    return lines


def render(raw: dict[str, Any], audience: str, now: datetime) -> dict[str, Any]:
    """Views + markdown text for one audience."""
    people = raw.get("people") or {}
    today = view_items(raw["today"], audience, people)
    early = view_items(raw["tomorrow_early"], audience, people)
    waiting = view_items(raw["waiting"], audience, people)
    promises = view_items(raw.get("promises", []), audience, people)
    birthday_rows = raw.get("birthdays", [])
    # Birthdays need the birthday field as well as the name.
    birthdays = view_items(birthday_rows, audience)
    for c in list(birthdays["items"]):
        if not c.get("birthday"):
            birthdays["items"].remove(c)
            birthdays["withheld"][c["account"]] = birthdays["withheld"].get(c["account"], 0) + 1
    for c in birthdays["items"]:
        c["on"] = next(r["birthday_on"] for r in birthday_rows if r["id"] == c["id"]).isoformat()
    lines: list[str] = []
    day_label = now.astimezone(user_tz()).strftime("%a %d %b")

    if today["items"] or today["withheld"]:
        lines.append(f"## Today ({day_label})")
        clash = _conflicts(today["items"])
        lines.extend(_event_line(e, clash) for e in today["items"])
        for account, n in today["withheld"].items():
            lines.append(
                f"- +{n} event{'s' if n > 1 else ''} in {account} (details on the dashboard)"
            )
        if early["items"]:
            e = early["items"][0]
            lines.append(f"- Tomorrow starts early: {_hm(e['starts_at'])} {e['title']}")
        lines.append("")

    shown = waiting["items"][:MAX_WAITING]
    total = len(waiting["items"]) + sum(waiting["withheld"].values())
    if total:
        lines.append(f"## Waiting on you ({total})")
        for m in shown:
            who = m.get("sender_name") or m.get("sender_addr") or "someone"
            gist = f" — {m['summary']}" if m.get("summary") else ""
            lines.append(f"- {_age(m['date'], now)} · {who}: {m['subject']}{gist}")
        if len(waiting["items"]) > MAX_WAITING:
            lines.append(f"- …and {len(waiting['items']) - MAX_WAITING} more")
        for account, n in waiting["withheld"].items():
            lines.append(f"- +{n} in {account} (details on the dashboard)")
        lines.append("")

    open_count = len(promises["items"]) + sum(promises["withheld"].values())
    if open_count:
        lines.append(f"## You promised ({open_count})")
        for p in promises["items"][:MAX_WAITING]:
            # A promise in a sensitive thread shows only as such off the machine.
            due = _due_label(p.get("commitment_due"), now)
            if p.get("commitment"):
                topic = re.sub(r"(?i)^(?:(?:re|fwd?|aw)\s*:\s*)+", "", p.get("subject") or "")
                lines.append(f"- {p['commitment']}{due} (re: {topic})")
            else:
                lines.append(f"- A promise in a sensitive email{due}")
        for account, n in promises["withheld"].items():
            lines.append(f"- +{n} in {account} (details on the dashboard)")
        lines.append("")

    if birthdays["items"] or birthdays["withheld"]:
        lines.append("## Birthdays")
        lines.extend(_birthday_lines(birthdays, now))
        lines.append("")

    code = view_items(raw.get("code", []), audience)
    code_lines = _code_lines(code, now)
    if code_lines:
        lines.append("## Code")
        lines.extend(code_lines)
        lines.append("")

    return {
        "text": "\n".join(lines).strip(),
        "today": today,
        "tomorrow_early": early,
        "waiting": waiting,
        "promises": promises,
        "birthdays": birthdays,
        "code": code,
    }


def _due_label(due: str | None, now: datetime) -> str:
    if not due:
        return ""
    try:
        d = date.fromisoformat(due)
    except ValueError:
        return ""
    today = now.astimezone(user_tz()).date()
    if d < today:
        return " — overdue"
    if d == today:
        return " — due today"
    return f" — due {d:%a %d %b}"


async def brief_sections(tenant_id: str, now: datetime | None = None) -> dict[str, Any] | None:
    """Both renderings, or None when there is nothing to say."""
    now = now or datetime.now(UTC)
    raw = await collect(tenant_id, now)
    if not any(raw.values()):
        return None
    return {"external": render(raw, CLOUD, now), "local": render(raw, LOCAL, now)}
