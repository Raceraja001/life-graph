"""Phase D: a monitor created over the API is checked by the watcher lifecycle."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from life_graph.services import safe_fetch
from life_graph.services.safe_fetch import FetchResult
from tests.integration.conftest import skip_on_db_error

PAGES = {"price": "₹64,999"}


@pytest.fixture
def fake_net(monkeypatch):
    async def resolve(host, port):
        return {"127.0.0.1"} if host == "internal.test" else {"93.184.216.34"}

    async def fetch(url, **_kw):
        html = f'<html><body><span class="price">{PAGES["price"]}</span></body></html>'
        return FetchResult(
            url=url, status_code=200, content_type="text/html", text=html, truncated=False
        )

    monkeypatch.setattr(safe_fetch, "_resolve", resolve)
    monkeypatch.setattr(safe_fetch, "fetch", fetch)


@pytest.mark.asyncio
@skip_on_db_error
async def test_monitor_lifecycle_through_the_watcher(fake_net):
    from sqlalchemy import select, update

    from life_graph.models.assistant import PageMonitor
    from life_graph.storage.database import async_session
    from life_graph.watchers.models import WatchConfig, WatchEvent
    from life_graph.watchers.page_monitor_watcher import PageMonitorWatcher

    tenant = f"mon_{uuid.uuid4().hex[:8]}"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "mon-test"},
    ) as c:
        bad = await c.post("/api/v1/monitors", json={"url": "http://internal.test/admin"})
        assert bad.status_code == 422 and "private" in bad.json()["detail"]

        r = await c.post(
            "/api/v1/monitors",
            json={
                "url": "https://shop.example/p9",
                "name": "Pixel 9",
                "mode": "price_below",
                "threshold": 60000,
                "selector": "span.price",
            },
        )
        assert r.status_code == 201, r.text
        monitor_id = r.json()["data"]["id"]

    async with async_session() as s:
        cfg = (
            await s.execute(
                select(WatchConfig).where(
                    WatchConfig.tenant_id == tenant, WatchConfig.watcher_name == "page_monitor"
                )
            )
        ).scalar_one()
        assert cfg.enabled

    watcher = PageMonitorWatcher(tenant_id=tenant, session_factory=async_session)
    first = await watcher.run()
    assert first["status"] == "success" and first["events"] == 0  # baseline at ₹64,999

    PAGES["price"] = "₹58,999"
    async with async_session() as s:  # make it due again
        await s.execute(
            update(PageMonitor).where(PageMonitor.tenant_id == tenant).values(last_checked_at=None)
        )
        await s.commit()
    second = await watcher.run()
    assert second["events"] == 1

    async with async_session() as s:
        events = (
            (await s.execute(select(WatchEvent).where(WatchEvent.tenant_id == tenant)))
            .scalars()
            .all()
        )
        assert len(events) == 1 and "58,999.00" in events[0].title
        assert events[0].severity == "important" and events[0].details["monitor_id"] == monitor_id
