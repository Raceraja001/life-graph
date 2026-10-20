"""Phase E: a project's health URL and backup check, through the watcher lifecycle."""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error


@pytest.mark.asyncio
@skip_on_db_error
async def test_down_after_two_failures_files_one_fix_task_and_recovers(monkeypatch, tmp_path):
    from sqlalchemy import select

    from life_graph.kernel.project_registry import ProjectRegistry
    from life_graph.models.db import AgentTask, Project
    from life_graph.storage.database import async_session
    from life_graph.watchers import app_uptime_watcher as up
    from life_graph.watchers.models import WatchConfig, WatchEvent

    tenant = f"uptime_{uuid.uuid4().hex[:8]}"
    async with async_session() as s:
        project = Project(
            tenant_id=tenant, name="shop-api", path=str(tmp_path), language="python", is_active=True
        )
        s.add(project)
        await s.commit()
        pid = str(project.id)

    registry = ProjectRegistry(session_factory=async_session)
    await registry.update_settings(
        tenant,
        pid,
        {"health_url": "http://shop.internal/health", "backup_check_command": "exit 3"},
    )
    async with async_session() as s:
        cfg = (
            await s.execute(
                select(WatchConfig).where(
                    WatchConfig.tenant_id == tenant, WatchConfig.watcher_name == "app_uptime"
                )
            )
        ).scalar_one()
        assert cfg.enabled

    answers = iter(
        [{"ok": False, "status": 502}] * 3 + [{"ok": True, "status": 200, "latency_ms": 5}] * 2
    )

    async def probe(url, client=None):
        return next(answers)

    monkeypatch.setattr(up, "probe_http", probe)
    monkeypatch.setattr(up, "RECHECK_SECONDS", 0)
    watcher = up.AppUptimeWatcher(tenant_id=tenant, session_factory=async_session)
    results = [await watcher.run() for _ in range(4)]
    assert all(r["status"] == "success" for r in results), results

    async with async_session() as s:
        titles = [
            e.title
            for e in (
                await s.execute(
                    select(WatchEvent)
                    .where(WatchEvent.tenant_id == tenant)
                    .order_by(WatchEvent.created_at)
                )
            ).scalars()
        ]
        fixes = (
            (
                await s.execute(
                    select(AgentTask).where(
                        AgentTask.tenant_id == tenant,
                        AgentTask.properties["origin"].astext == "production",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert "shop-api: backup check failed (exit 3)" in titles
    assert titles.count("shop-api is down (HTTP 502)") == 1
    assert titles[-1] == "shop-api is back up"
    assert titles.count("shop-api: backup check failed (exit 3)") == 1  # once per streak, daily
    assert len(fixes) == 1
