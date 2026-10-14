"""Page monitors: tell the user when a page changes, a price drops or text appears.

Phase D of docs/specs/assistant-capabilities.md. A monitor names a URL, an
optional part of the page and a mode:

- ``change``: the watched text changed since the last check;
- ``price_below``: the first price in the watched text is under ``threshold``;
- ``contains``: ``pattern`` appeared (case-insensitive) where it was absent.

The part of the page is a **simple CSS selector** (``tag``, ``#id``,
``.class``, ``[attr=value]`` or a combination such as
``span.price[itemprop=price]``, no descendant combinators) or
``regex:<pattern>`` over the page text. Selectors are matched with the
standard library's HTML parser, so no new dependency is needed. ``meta``
elements yield their ``content`` attribute, which is where many shops put
the machine-readable price.

Fetches go through services/safe_fetch.py. A monitor checks no more often
than its ``interval_minutes``. After ``MAX_FAILURES`` failures in a row it
pauses itself, with one event saying so, instead of failing every hour.
``price_below`` and ``contains`` alert on the transition only (not below →
below, absent → present), so a price that stays low is reported once.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.models.assistant import PageMonitor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MODES = ("change", "price_below", "contains")
MAX_FAILURES = 5
MIN_INTERVAL_MINUTES = 30
EXCERPT_CHARS = 300

_SELECTOR = re.compile(
    r"^(?P<tag>[a-zA-Z][a-zA-Z0-9-]*)?(?P<rest>(?:[#.][\w-]+|\[[\w:-]+(?:=[\"']?[^\]\"']*[\"']?)?\])*)$"
)
_PART = re.compile(r"([#.])([\w-]+)|\[([\w:-]+)(?:=[\"']?([^\]\"']*)[\"']?)?\]")
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


class SelectorError(ValueError):
    """The selector is not one this module understands."""


def parse_selector(selector: str) -> dict[str, Any]:
    m = _SELECTOR.match(selector.strip())
    if not m or not selector.strip():
        raise SelectorError(
            "use a simple selector: tag, #id, .class, [attr=value] or a combination"
            " like span.price (no spaces)"
        )
    want: dict[str, Any] = {
        "tag": (m.group("tag") or "").lower() or None,
        "id": None,
        "classes": [],
        "attrs": {},
    }
    for sym, name, attr, value in _PART.findall(m.group("rest") or ""):
        if sym == "#":
            want["id"] = name
        elif sym == ".":
            want["classes"].append(name)
        else:
            want["attrs"][attr.lower()] = value if value != "" else None
    return want


def _matches(want: dict[str, Any], tag: str, attrs: dict[str, str]) -> bool:
    if want["tag"] and tag != want["tag"]:
        return False
    if want["id"] and attrs.get("id") != want["id"]:
        return False
    classes = (attrs.get("class") or "").split()
    if any(c not in classes for c in want["classes"]):
        return False
    for key, value in want["attrs"].items():
        if key not in attrs or (value is not None and attrs[key] != value):
            return False
    return True


class _Select(HTMLParser):
    """Text of the first element matching a simple selector."""

    def __init__(self, want: dict[str, Any]) -> None:
        super().__init__(convert_charrefs=True)
        self.want = want
        self.depth = 0  # >0 while inside the matched element
        self.parts: list[str] = []
        self.done = False
        self.skip = 0  # inside <script>/<style>

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        if self.done:
            return
        attrs = {k.lower(): (v or "") for k, v in attrs_list}
        if tag in ("script", "style"):
            self.skip += 1
        if self.depth:
            if tag not in _VOID:
                self.depth += 1
            return
        if _matches(self.want, tag, attrs):
            if tag == "meta" or (tag in _VOID and "content" in attrs):
                self.parts.append(attrs.get("content", ""))
                self.done = True
            elif tag in _VOID:
                self.parts.append(attrs.get("value", "") or attrs.get("alt", ""))
                self.done = True
            else:
                self.depth = 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if self.depth and not self.done:
            self.depth -= 1
            if self.depth == 0:
                self.done = True

    def handle_data(self, data: str) -> None:
        if self.depth and not self.done and not self.skip:
            self.parts.append(data)


def select_text(markup: str, selector: str | None) -> str | None:
    """The watched text: a selector's element, a regex match, or the whole page."""
    from life_graph.tools.browser import page_text

    if not selector:
        return page_text(markup)
    if selector.startswith("regex:"):
        try:
            m = re.search(selector[6:], page_text(markup), re.I | re.S)
        except re.error as exc:
            raise SelectorError(f"bad regex: {exc}") from exc
        if not m:
            return None
        return (m.group(1) if m.groups() else m.group(0)).strip()
    parser = _Select(parse_selector(selector))
    parser.feed(markup)
    parser.close()
    if not parser.parts:
        return None
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


_PRICE = re.compile(
    r"(?:₹|rs\.?|inr|\$|usd|€|£)?\s*(\d{1,3}(?:[,\s]\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)", re.I
)


def parse_price(text: str | None) -> Decimal | None:
    """The first price in ``text``: "₹1,24,999.00" → 124999.00."""
    for m in _PRICE.finditer(text or ""):
        raw = re.sub(r"[,\s]", "", m.group(1))
        try:
            value = Decimal(raw)
        except InvalidOperation:
            continue
        if value > 0:
            return value
    return None


def evaluate(
    monitor: PageMonitor, watched: str | None
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """(event or None, column updates) for one successful fetch. Pure."""
    excerpt = (watched or "")[:EXCERPT_CHARS]
    digest = hashlib.sha256((watched or "").encode()).hexdigest()
    updates: dict[str, Any] = {"last_hash": digest, "last_excerpt": excerpt}
    event = None
    if monitor.mode == "change":
        if watched is None:
            event = None
        elif monitor.last_hash and digest != monitor.last_hash:
            event = {
                "title": f"{monitor.name} changed",
                "summary": f"Now: {excerpt[:200]}",
                "details": {"before": monitor.last_excerpt, "after": excerpt, "url": monitor.url},
            }
    elif monitor.mode == "price_below":
        price = parse_price(watched)
        updates["last_value"] = price
        was_below = monitor.last_value is not None and monitor.last_value < monitor.threshold
        if (
            price is not None
            and monitor.threshold is not None
            and price < monitor.threshold
            and not was_below
        ):
            event = {
                "title": f"{monitor.name}: {price:,.2f} (under {monitor.threshold:,.2f})",
                "summary": f"Price dropped below your threshold at {monitor.url}",
                "details": {
                    "price": float(price),
                    "threshold": float(monitor.threshold),
                    "previous": float(monitor.last_value)
                    if monitor.last_value is not None
                    else None,
                    "url": monitor.url,
                },
            }
    elif monitor.mode == "contains":
        present = bool(watched and monitor.pattern and monitor.pattern.lower() in watched.lower())
        updates["last_value"] = Decimal(1) if present else Decimal(0)
        was_present = monitor.last_value is not None and monitor.last_value > 0
        if present and not was_present:
            event = {
                "title": f"{monitor.name}: “{monitor.pattern}” appeared",
                "summary": excerpt[:200],
                "details": {"pattern": monitor.pattern, "url": monitor.url},
            }
    return event, updates


def due(monitor: PageMonitor, now: datetime) -> bool:
    if monitor.paused:
        return False
    if monitor.last_checked_at is None:
        return True
    return now - monitor.last_checked_at >= timedelta(
        minutes=max(MIN_INTERVAL_MINUTES, monitor.interval_minutes)
    )


async def check(monitor: PageMonitor, now: datetime, fetch=None) -> dict[str, Any] | None:
    """Fetch and evaluate one monitor, updating it in place; returns an event."""
    from life_graph.services import safe_fetch

    fetch = fetch or safe_fetch.fetch
    monitor.last_checked_at = now
    try:
        page = await fetch(monitor.url)
        watched = select_text(page.text, monitor.selector)
    except Exception as exc:  # noqa: BLE001 — a monitor failure is data, not a crash
        monitor.consecutive_failures = (monitor.consecutive_failures or 0) + 1
        monitor.last_error = f"{type(exc).__name__}: {exc}"[:300]
        if monitor.consecutive_failures >= MAX_FAILURES:
            monitor.paused = True
            return {
                "title": f"{monitor.name}: paused after {MAX_FAILURES} failed checks",
                "summary": monitor.last_error,
                "details": {"url": monitor.url, "error": monitor.last_error},
                "severity": "important",
            }
        return None
    monitor.consecutive_failures = 0
    monitor.last_error = None
    if watched is None and monitor.selector:
        monitor.last_error = "the selector matched nothing on the page"
    event, updates = evaluate(monitor, watched)
    for key, value in updates.items():
        setattr(monitor, key, value)
    return event


async def due_monitors(session: AsyncSession, tenant_id: str, now: datetime) -> list[PageMonitor]:
    rows = (
        (
            await session.execute(
                select(PageMonitor).where(
                    PageMonitor.tenant_id == tenant_id, PageMonitor.paused.is_(False)
                )
            )
        )
        .scalars()
        .all()
    )
    return [m for m in rows if due(m, now)]


async def ensure_watcher_config(session: AsyncSession, tenant_id: str) -> None:
    """The hourly watcher cron runs only watchers with a config row for the tenant."""
    from sqlalchemy.dialects.postgresql import insert

    from life_graph.watchers.models import WatchConfig

    await session.execute(
        insert(WatchConfig)
        .values(
            tenant_id=tenant_id,
            watcher_name="page_monitor",
            display_name="Page monitors",
            description="Pages the user asked to watch (docs/specs/assistant-capabilities.md, Phase D)",
            schedule="0 * * * *",
            enabled=True,
            config={},
            consecutive_failures=0,
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "watcher_name"])
    )


def validate(mode: str, threshold: float | None, pattern: str | None, selector: str | None) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    if mode == "price_below" and (threshold is None or threshold <= 0):
        raise ValueError("price_below needs a positive threshold")
    if mode == "contains" and not (pattern or "").strip():
        raise ValueError("contains needs a pattern")
    if selector and not selector.startswith("regex:"):
        parse_selector(selector)
    elif selector:
        try:
            re.compile(selector[6:])
        except re.error as exc:
            raise SelectorError(f"bad regex: {exc}") from exc


async def create(
    session: AsyncSession,
    tenant_id: str,
    *,
    url: str,
    name: str | None = None,
    mode: str = "change",
    selector: str | None = None,
    threshold: float | None = None,
    pattern: str | None = None,
    interval_minutes: int = 180,
) -> PageMonitor:
    from life_graph.services.safe_fetch import check_url

    validate(mode, threshold, pattern, selector)
    await check_url(url)  # refuse private addresses at creation, not only at fetch
    monitor = PageMonitor(
        tenant_id=tenant_id,
        name=(name or url)[:120],
        url=url,
        mode=mode,
        selector=selector or None,
        threshold=Decimal(str(threshold)) if threshold is not None else None,
        pattern=pattern or None,
        interval_minutes=max(MIN_INTERVAL_MINUTES, int(interval_minutes)),
        paused=False,
        consecutive_failures=0,
    )
    session.add(monitor)
    await ensure_watcher_config(session, tenant_id)
    await session.flush()
    return monitor


def to_dict(m: PageMonitor) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "name": m.name,
        "url": m.url,
        "mode": m.mode,
        "selector": m.selector,
        "threshold": float(m.threshold) if m.threshold is not None else None,
        "pattern": m.pattern,
        "interval_minutes": m.interval_minutes,
        "paused": m.paused,
        "last_checked_at": m.last_checked_at.isoformat() if m.last_checked_at else None,
        "last_value": float(m.last_value) if m.last_value is not None else None,
        "last_excerpt": m.last_excerpt,
        "last_error": m.last_error,
        "consecutive_failures": m.consecutive_failures,
    }


def now_utc() -> datetime:
    return datetime.now(UTC)
