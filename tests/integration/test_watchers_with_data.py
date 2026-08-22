"""Watcher endpoints exercised against rows, not an empty table.

The existing watcher suite runs each request against a fresh tenant, so every
list endpoint was only ever asked to serialize nothing. Two response schemas
named columns their model does not have; with no rows the endpoints returned
an empty 200 and the tests passed:

    GET /watchers/tech-radar   200 empty, 500 with one row (created_at was a
                               required field with no counterpart)
    GET /watchers/events       acknowledged always false; 500 on any event
                               whose JSONB details hold a dict, which is what
                               BaseWatcher.emit_event() produces

Each test here inserts a row first. That is the whole point of the file.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from life_graph.main import app
from life_graph.storage.database import async_session
from life_graph.watchers.models import (
    NotificationChannel,
    TechRadarItem,
    WatcherRun,
    WatchEvent,
)
from tests.integration.conftest import skip_on_db_error


@pytest_asyncio.fixture
async def tenant():
    tid = f"watch-data-{uuid.uuid4().hex[:8]}"
    yield tid
    async with async_session() as session:
        for model in (TechRadarItem, WatchEvent, WatcherRun, NotificationChannel):
            await session.execute(delete(model).where(model.tenant_id == tid))
        await session.commit()


@pytest_asyncio.fixture
async def client(tenant):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Tenant-ID": tenant}
    ) as c:
        yield c


async def _seed_event(tid: str, *, details, acknowledged: bool = False):
    run_id, evt_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    async with async_session() as session:
        session.add(
            WatcherRun(
                id=run_id,
                tenant_id=tid,
                watcher_name="code_quality",
                status="success",
                started_at=now,
            )
        )
        await session.commit()
        session.add(
            WatchEvent(
                id=evt_id,
                tenant_id=tid,
                watcher_name="code_quality",
                run_id=run_id,
                severity="critical",
                title="disk full",
                details=details,
                created_at=now,
                acknowledged_at=now if acknowledged else None,
                acknowledged_by="raja" if acknowledged else None,
            )
        )
        await session.commit()
    return evt_id


class TestTechRadarWithData:
    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_serializes_a_row(self, client: AsyncClient, tenant: str):
        async with async_session() as session:
            session.add(
                TechRadarItem(
                    id=uuid.uuid4(),
                    tenant_id=tenant,
                    # ck_tech_radar_source allows only hn | reddit | github_trending
                    source="hn",
                    title="Rust 2.0",
                    url="http://example.test/rust",
                    score=97,
                    scraped_at=datetime.now(UTC),
                )
            )
            await session.commit()

        response = await client.get("/api/v1/watchers/tech-radar")
        assert response.status_code == 200, response.text

        item = response.json()["data"][0]
        assert item["title"] == "Rust 2.0"
        assert item["relevance_score"] == 97.0, "relevance_score must read the score column"
        assert item["created_at"], "created_at must read scraped_at"
        assert "published_at" not in item, (
            "published_at was removed: TechRadarItem never records a publication time"
        )


class TestWatchEventsWithData:
    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_acknowledged_is_derived_from_acknowledged_at(
        self, client: AsyncClient, tenant: str
    ):
        evt_id = await _seed_event(tenant, details="82% -> 61%", acknowledged=True)

        response = await client.get("/api/v1/watchers/events")
        assert response.status_code == 200, response.text

        event = next(e for e in response.json()["data"] if e["id"] == str(evt_id))
        assert event["acknowledged"] is True
        assert event["acknowledged_by"] == "raja"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_unacknowledged_event_reports_false(self, client: AsyncClient, tenant: str):
        evt_id = await _seed_event(tenant, details="still open", acknowledged=False)

        response = await client.get("/api/v1/watchers/events")
        event = next(e for e in response.json()["data"] if e["id"] == str(evt_id))
        assert event["acknowledged"] is False
        assert event["acknowledged_at"] is None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dict_details_do_not_break_serialization(
        self, client: AsyncClient, tenant: str
    ):
        """BaseWatcher.emit_event() stores a dict in the JSONB column."""
        evt_id = await _seed_event(tenant, details={"pct": 99, "mount": "/"})

        response = await client.get("/api/v1/watchers/events")
        assert response.status_code == 200, response.text

        event = next(e for e in response.json()["data"] if e["id"] == str(evt_id))
        assert isinstance(event["details"], str)
        assert "99" in event["details"]

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_string_details_pass_through(self, client: AsyncClient, tenant: str):
        evt_id = await _seed_event(tenant, details="plain text")

        response = await client.get("/api/v1/watchers/events")
        event = next(e for e in response.json()["data"] if e["id"] == str(evt_id))
        assert event["details"] == "plain text"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_retry_count_is_gone(self, client: AsyncClient, tenant: str):
        """WatchEvent has no retry counter; it always reported 0."""
        await _seed_event(tenant, details="x")
        response = await client.get("/api/v1/watchers/events")
        assert "retry_count" not in response.json()["data"][0]


class TestNotificationChannelName:
    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_name_survives_a_round_trip(self, client: AsyncClient):
        """The create API always accepted `name` and silently discarded it."""
        created = await client.post(
            "/api/v1/watchers/notification-channels",
            json={"channel_type": "terminal", "name": "My Terminal", "priority": 5},
        )
        assert created.status_code == 201, created.text
        assert created.json()["data"]["name"] == "My Terminal"

        listed = await client.get("/api/v1/watchers/notification-channels")
        assert listed.status_code == 200
        names = [c["name"] for c in listed.json()["data"]]
        assert "My Terminal" in names

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_name_is_optional(self, client: AsyncClient):
        created = await client.post(
            "/api/v1/watchers/notification-channels",
            json={"channel_type": "webhook"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["data"]["name"] is None
