"""Job 7 — app health at a glance: the uptime watcher's state, per app.

docs/specs/money-checkin-and-app-health.md. The hourly ``app_uptime`` watcher
(watchers/app_uptime_watcher.py) already probes every project with a
``health_url``, tracks its certificate and runs its ``backup_check_command``;
it keeps what it saw in its config row. This reads that state back, so the
dashboard and Jarvis can answer "are my apps up?" without probing again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _status(state: dict[str, Any], has_url: bool) -> str:
    if not has_url:
        return "not watched"
    if not state:
        return "not checked yet"
    if state.get("down"):
        return "down"
    last = state.get("last") or {}
    return "up" if last.get("ok") else "failing"  # one failed check, not yet an outage


async def report(session: AsyncSession, tenant_id: str) -> list[dict[str, Any]]:
    """One entry per project that has a health URL or a backup check."""
    from life_graph.models.db import Project
    from life_graph.watchers.models import WatchConfig

    projects = (
        (
            await session.execute(
                select(Project).where(Project.tenant_id == tenant_id, Project.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    config = (
        await session.execute(
            select(WatchConfig).where(
                WatchConfig.tenant_id == tenant_id, WatchConfig.watcher_name == "app_uptime"
            )
        )
    ).scalar_one_or_none()
    states = ((config.config if config else None) or {}).get("state", {})
    out = []
    for p in projects:
        meta = p.scan_metadata or {}
        url, backup = meta.get("health_url"), meta.get("backup_check_command")
        if not (url or backup):
            continue
        state = states.get(str(p.id), {})
        last = state.get("last") or {}
        out.append(
            {
                "project": p.name,
                "health_url": url,
                "status": _status(state, bool(url)),
                "http_status": last.get("status"),
                "latency_ms": last.get("latency_ms"),
                "error": last.get("error"),
                "cert_days_left": state.get("cert_days"),
                "backup": None
                if not backup
                else (
                    "not checked yet"
                    if "backup_exit" not in state
                    else "failing"
                    if state.get("backup_failing")
                    else "ok"
                ),
                "backup_checked_at": state.get("backup_checked_at"),
                "watcher_enabled": bool(config and config.enabled),
            }
        )
    return sorted(out, key=lambda a: (a["status"] != "down", a["project"]))


def lines(apps: list[dict[str, Any]]) -> list[str]:
    """One line per app, problems first."""
    out = []
    for a in apps:
        bits = [a["status"]]
        if a["status"] == "down":
            bits.append(f"HTTP {a['http_status']}" if a["http_status"] else a["error"] or "")
        if a["cert_days_left"] is not None and a["cert_days_left"] <= 14:
            bits.append(f"TLS expires in {a['cert_days_left']} days")
        if a["backup"] == "failing":
            bits.append("backup failing")
        out.append(f"{a['project']}: " + ", ".join(b for b in bits if b))
    return out
