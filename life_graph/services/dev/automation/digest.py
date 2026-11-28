"""Morning digest: the night-shift report (services/night_shift.py), pushed once a day.

Replaces race-app's digest. When ``digest.enabled`` and the tenant-local time
has reached ``digest.time``, the report for the window since the previous
digest (or the last 24 h) is built, today's date is claimed in the settings
row's ``state`` (once per local day, across restarts and overlapping ticks;
a worker started after the time sends that day's digest late, once), and,
unless nothing happened and nothing waits (a quiet night), it is published as
an automation notice: a notification, Web Push and Telegram. No model call.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from life_graph.services import night_shift
from life_graph.services.dev.automation.clock import local_parts
from life_graph.services.dev.automation.settings import parse_hhmm, tenant_zone

if TYPE_CHECKING:
    from life_graph.services.dev.automation.ports import Notifier, Store
    from life_graph.services.dev.automation.settings import AutomationSettings

#: (tenant_id, since) → the night-shift report (night_shift.report's shape).
ReportFn = Callable[[str, datetime], Awaitable[dict[str, Any]]]

DIGEST_TITLE = "Night shift"
MAX_LINES = 20


def build(report: dict[str, Any], lines: list[str], *, since: datetime, to: datetime) -> dict:
    """The digest's API shape (race-app ``Digest`` where it maps)."""
    merged, waiting, failed = report["merged"], report["waiting"], report["failed"]
    quiet = not lines
    head = lines[0] if lines else "Quiet night."
    return {
        "from": since.isoformat(),
        "to": to.isoformat(),
        "merged": len(merged),
        "needsYou": len(waiting),
        "failed": len(failed),
        # Runs that finished normally with nothing to change (never "failed").
        "noChanges": len(report.get("no_changes") or []),
        "queued": report["queued"],
        "lines": lines[1 : MAX_LINES + 1],
        "summary": head[:300],
        "quiet": quiet,
        "report": report,
    }


class Digest:
    def __init__(
        self,
        *,
        tenant_id: str,
        doc: AutomationSettings,
        store: Store,
        notifier: Notifier,
        report_fn: ReportFn,
        now: datetime,
    ) -> None:
        self.tenant = tenant_id
        self.doc = doc
        self.store = store
        self.notifier = notifier
        self.report_fn = report_fn
        self.now = now

    async def _since(self) -> datetime:
        state = await self.store.get_state(self.tenant)
        last = state.get("digest_to")
        if last:
            try:
                return datetime.fromisoformat(last)
            except ValueError:
                pass
        return self.now - timedelta(hours=24)

    async def preview(self) -> dict[str, Any]:
        """What it would send now, without recording or sending."""
        since = await self._since()
        report = await self.report_fn(self.tenant, since)
        return build(report, night_shift.lines(report), since=since, to=self.now)

    async def tick(self) -> dict[str, Any] | None:
        """Send today's digest when due; None when off, not due or already handled."""
        settings = self.doc.digest
        if not settings.enabled:
            return None
        at = parse_hhmm(settings.time)
        today = local_parts(self.now, tenant_zone(self.doc.timezone))
        if at is None or today.minutes < at:
            return None
        state = await self.store.get_state(self.tenant)
        if state.get("digest_date") == today.date:
            return None
        digest = await self.preview()
        if not await self.store.claim_digest(self.tenant, today.date, self.now):
            return None  # another tick claimed today
        sent = not digest["quiet"]
        if sent:
            body = "\n".join([digest["summary"], *digest["lines"]])
            await self.notifier.publish(
                self.tenant,
                kind="digest",
                title=f"{DIGEST_TITLE}: {digest['summary']}"[:500],
                body=body,
                data={"from": digest["from"], "to": digest["to"]},
            )
        return {**digest, "sent": sent, "date": today.date}
