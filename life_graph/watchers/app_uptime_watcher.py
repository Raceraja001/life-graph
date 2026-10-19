"""Uptime, TLS expiry and backups for the apps the assistant builds.

Phase E of docs/specs/assistant-capabilities.md. For every project with a
``health_url``, each hourly run records the HTTP status and latency and, for
HTTPS, how many days are left on the certificate.

- **Down**: two failed checks in a row (one blip is not an outage) raise an
  important event and queue a fix task through
  services/production_findings.py, which de-duplicates an outage that lasts
  for hours. Recovery raises one info event.
- **Certificate**: alerts at 14, 7, 3 and 1 days left, once each.
- **Backups**: ``backup_check_command`` runs in the project's directory once a
  day; a non-zero exit raises an important event, once per failing streak.

The health URL is the operator's own setting and may well be a LAN or
localhost address, so it is fetched directly rather than through the
private-address guard that protects model-chosen URLs.

State between runs (failure streaks, alerts already sent) lives in the
watcher's own config row (``watch_configs.config["state"]``), keyed by
project id.
"""

from __future__ import annotations

import asyncio
import ssl
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, update

from life_graph.watchers.base import BaseWatcher, Severity

DOWN_AFTER = 2
CERT_ALERT_DAYS = (14, 7, 3, 1)
BACKUP_EVERY = timedelta(hours=20)
BACKUP_TIMEOUT = 300
HTTP_TIMEOUT = 15.0


async def probe_http(url: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    own = client is None
    http = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True)
    start = time.monotonic()
    try:
        resp = await http.get(url)
        ms = int((time.monotonic() - start) * 1000)
        return {"ok": 200 <= resp.status_code < 400, "status": resp.status_code, "latency_ms": ms}
    except Exception as exc:  # noqa: BLE001 — every failure is an observation
        return {"ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
    finally:
        if own:
            await http.aclose()


async def cert_days_left(url: str, now: datetime | None = None) -> int | None:
    """Days until the server certificate expires; None for http or on failure."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return None
    try:
        ctx = ssl.create_default_context()
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                parts.hostname, parts.port or 443, ssl=ctx, server_hostname=parts.hostname
            ),
            timeout=HTTP_TIMEOUT,
        )
        cert = writer.get_extra_info("peercert") or {}
        writer.close()
        expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), tz=UTC)
    except Exception:  # noqa: BLE001 — an invalid cert also shows as an HTTP failure
        return None
    return (expires - (now or datetime.now(UTC))).days


def cert_alert(days: int | None, sent: list[int]) -> int | None:
    """The tightest certificate threshold crossed and not yet alerted."""
    if days is None:
        return None
    crossed = [t for t in CERT_ALERT_DAYS if days <= t and t not in sent]
    return min(crossed) if crossed else None


def next_state(state: dict[str, Any], probe: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """(new state, "down" | "up" | None) after one probe. Pure."""
    failures = 0 if probe["ok"] else int(state.get("failures", 0)) + 1
    was_down = bool(state.get("down"))
    new = {**state, "failures": failures, "last": probe}
    if failures >= DOWN_AFTER and not was_down:
        new["down"] = True
        return new, "down"
    if probe["ok"] and was_down:
        new["down"] = False
        return new, "up"
    return new, None


class AppUptimeWatcher(BaseWatcher):
    name = "app_uptime"
    display_name = "App uptime"
    default_schedule = "0 * * * *"

    async def execute(self) -> None:
        from life_graph.models.db import Project
        from life_graph.watchers.models import WatchConfig

        now = datetime.now(UTC)
        async with self.session_factory() as session:
            projects = (
                (
                    await session.execute(
                        select(Project).where(
                            Project.tenant_id == self.tenant_id, Project.is_active.is_(True)
                        )
                    )
                )
                .scalars()
                .all()
            )
            config = (
                await session.execute(
                    select(WatchConfig).where(
                        WatchConfig.tenant_id == self.tenant_id,
                        WatchConfig.watcher_name == self.name,
                    )
                )
            ).scalar_one_or_none()
        states: dict[str, Any] = dict(((config.config if config else None) or {}).get("state", {}))

        for project in projects:
            meta = project.scan_metadata or {}
            if not (meta.get("health_url") or meta.get("backup_check_command")):
                continue
            pid = str(project.id)
            state = dict(states.get(pid, {}))
            pdict = {
                "id": pid,
                "name": project.name,
                "path": project.path,
                "scan_metadata": meta,
            }
            if meta.get("health_url"):
                state = await self._check_health(pdict, meta["health_url"], state, now)
            if meta.get("backup_check_command"):
                state = await self._check_backups(pdict, meta["backup_check_command"], state, now)
            states[pid] = state

        if config is not None:
            async with self.session_factory() as session:
                await session.execute(
                    update(WatchConfig)
                    .where(WatchConfig.id == config.id)
                    .values(config={**(config.config or {}), "state": states})
                )
                await session.commit()

    async def _check_health(
        self, project: dict[str, Any], url: str, state: dict[str, Any], now: datetime
    ) -> dict[str, Any]:
        probe = await probe_http(url)
        state, change = next_state(state, probe)
        details = {"project_id": project["id"], "url": url, **probe}
        if change == "down":
            what = (
                f"HTTP {probe['status']}"
                if probe.get("status")
                else probe.get("error", "no answer")
            )
            title = f"{project['name']} is down ({what})"
            self.emit_event(Severity.IMPORTANT, title, details=details, summary=url)
            await self._file_fix(
                project, title, f"{url} failed {DOWN_AFTER} checks in a row: {what}.", what
            )
        elif change == "up":
            self.emit_event(
                Severity.INFO, f"{project['name']} is back up", details=details, summary=url
            )

        days = await cert_days_left(url, now)
        if days is not None:
            state["cert_days"] = days
            sent = [int(x) for x in state.get("cert_alerts", [])]
            if days > max(CERT_ALERT_DAYS):
                sent = []  # renewed: the next expiry gets its own alerts
            level = cert_alert(days, sent)
            if level is not None:
                self.emit_event(
                    Severity.IMPORTANT if days <= 7 else Severity.INFO,
                    f"{project['name']}: TLS certificate expires in {days} days",
                    details={"project_id": project["id"], "url": url, "days_left": days},
                    summary="Renew the certificate (or check that auto-renewal is running).",
                )
                sent = sorted({*sent, *[t for t in CERT_ALERT_DAYS if days <= t]})
            state["cert_alerts"] = sent
        return state

    async def _check_backups(
        self, project: dict[str, Any], command: str, state: dict[str, Any], now: datetime
    ) -> dict[str, Any]:
        from life_graph.services.approvals import _run_shell

        last = state.get("backup_checked_at")
        if last and now - datetime.fromisoformat(last) < BACKUP_EVERY:
            return state
        code, output = await _run_shell(command, project["path"], BACKUP_TIMEOUT)
        failing = code != 0
        state = {**state, "backup_checked_at": now.isoformat(), "backup_exit": code}
        if failing and not state.get("backup_failing"):
            self.emit_event(
                Severity.IMPORTANT,
                f"{project['name']}: backup check failed (exit {code})",
                details={"project_id": project["id"], "exit_code": code, "output": output[-1500:]},
                summary=output.strip().splitlines()[-1][:200] if output.strip() else None,
            )
        state["backup_failing"] = failing
        return state

    async def _file_fix(
        self, project: dict[str, Any], title: str, detail: str, signature: str
    ) -> None:
        from life_graph.services.production_findings import file_fix_task

        try:
            await file_fix_task(
                self.session_factory,
                self.tenant_id,
                project,
                kind="uptime",
                title=title,
                detail=detail,
                signature=f"down:{signature}",
            )
        except Exception:
            self.logger.warning("Could not file a fix task for %s", project["name"], exc_info=True)
