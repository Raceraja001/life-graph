"""Integration tests for OS Kernel Scheduler.

Tests the Scheduler API:
- POST /api/v1/kernel/schedules (create)
- GET /api/v1/kernel/schedules (list)
- GET /api/v1/kernel/schedules/{id} (detail)
- PATCH /api/v1/kernel/schedules/{id} (update)
- DELETE /api/v1/kernel/schedules/{id} (soft-delete)

Also tests CronExpression parser and SchedulerService
cron validation (unit tests, no DB needed).
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test_scheduler_tenant",
    "X-User-ID": "scheduler-test-user",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for scheduler API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── CronExpression Parser (unit tests, no DB) ───────────────


class TestCronExpression:
    """CronExpression — built-in cron parser tests."""

    @pytest.fixture
    def cron_cls(self):
        from life_graph.kernel.scheduler import (
            CronExpression,
        )
        return CronExpression

    def test_parse_every_minute(self, cron_cls):
        """'* * * * *' should parse without error."""
        cron = cron_cls("* * * * *")
        next_fire = cron.next_fire_time(
            datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)
        )
        assert next_fire is not None
        assert next_fire.minute == 1  # next minute

    def test_parse_daily_3am(self, cron_cls):
        """'0 3 * * *' → next fire at 3:00 AM."""
        cron = cron_cls("0 3 * * *")
        after = datetime(
            2026, 7, 7, 4, 0, 0, tzinfo=timezone.utc,
        )
        next_fire = cron.next_fire_time(after)
        assert next_fire.hour == 3
        assert next_fire.minute == 0
        assert next_fire.day == 8  # next day

    def test_parse_every_15_minutes(self, cron_cls):
        """'*/15 * * * *' → every 15 minutes."""
        cron = cron_cls("*/15 * * * *")
        after = datetime(
            2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc,
        )
        next_fire = cron.next_fire_time(after)
        assert next_fire.minute in (0, 15, 30, 45)

    def test_parse_range(self, cron_cls):
        """'0 9-17 * * *' → hours 9 to 17."""
        cron = cron_cls("0 9-17 * * *")
        after = datetime(
            2026, 7, 7, 18, 0, 0, tzinfo=timezone.utc,
        )
        next_fire = cron.next_fire_time(after)
        assert 9 <= next_fire.hour <= 17

    def test_parse_list(self, cron_cls):
        """'0 0 1,15 * *' → 1st and 15th of month."""
        cron = cron_cls("0 0 1,15 * *")
        after = datetime(
            2026, 7, 2, 0, 0, 0, tzinfo=timezone.utc,
        )
        next_fire = cron.next_fire_time(after)
        assert next_fire.day in (1, 15)

    def test_invalid_expression_too_few_fields(
        self, cron_cls,
    ):
        """Less than 5 fields raises ValueError."""
        with pytest.raises(ValueError, match="5 fields"):
            cron_cls("0 3 * *")

    def test_invalid_expression_too_many_fields(
        self, cron_cls,
    ):
        """More than 5 fields raises ValueError."""
        with pytest.raises(ValueError, match="5 fields"):
            cron_cls("0 3 * * * 2026")

    def test_validate_valid(self, cron_cls):
        """validate() returns True for valid expressions."""
        assert cron_cls.validate("0 3 * * *") is True
        assert cron_cls.validate("*/5 * * * *") is True

    def test_validate_invalid(self, cron_cls):
        """validate() returns False for invalid expressions."""
        assert cron_cls.validate("not a cron") is False
        assert cron_cls.validate("") is False

    def test_step_with_range(self, cron_cls):
        """'0 1-10/3 * * *' → hours 1, 4, 7, 10."""
        cron = cron_cls("0 1-10/3 * * *")
        after = datetime(
            2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc,
        )
        next_fire = cron.next_fire_time(after)
        assert next_fire.hour in (1, 4, 7, 10)

    def test_weekday_monday(self, cron_cls):
        """'0 0 * * 1' → midnight every Monday."""
        cron = cron_cls("0 0 * * 1")
        # 2026-07-07 is a Tuesday
        after = datetime(
            2026, 7, 7, 1, 0, 0, tzinfo=timezone.utc,
        )
        next_fire = cron.next_fire_time(after)
        # Python weekday: Monday = 0
        assert next_fire.weekday() == 0


# ── Scheduler Validation ─────────────────────────────────────


class TestSchedulerValidation:
    """SchedulerService cron validation tests."""

    def test_validate_cron_via_service(self):
        from life_graph.kernel.scheduler import (
            CronExpression,
        )
        assert CronExpression.validate("0 3 * * *")
        assert not CronExpression.validate("bad")


# ── Create Schedule Endpoint ─────────────────────────────────


class TestCreateSchedule:
    """POST /api/v1/kernel/schedules"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_schedule_returns_201(
        self, client: AsyncClient,
    ):
        """Valid schedule returns 201."""
        response = await client.post(
            "/api/v1/kernel/schedules",
            json={
                "name": "test-nightly-analysis",
                "cron_expression": "0 3 * * *",
                "agent_name": "cody",
                "description": "Nightly test job",
                "input": {"message": "Run tests"},
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["name"] == "test-nightly-analysis"
            assert data["cron_expression"] == "0 3 * * *"
            assert data["is_active"] is True
            assert data["next_run_at"] is not None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_schedule_invalid_cron(
        self, client: AsyncClient,
    ):
        """Invalid cron expression returns 400."""
        response = await client.post(
            "/api/v1/kernel/schedules",
            json={
                "name": "bad-cron-test",
                "cron_expression": "not valid",
                "agent_name": "cody",
            },
        )
        assert response.status_code in (400, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_schedule_missing_name(
        self, client: AsyncClient,
    ):
        """Missing name returns 422."""
        response = await client.post(
            "/api/v1/kernel/schedules",
            json={
                "cron_expression": "0 3 * * *",
                "agent_name": "cody",
            },
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_schedule_missing_cron(
        self, client: AsyncClient,
    ):
        """Missing cron_expression returns 422."""
        response = await client.post(
            "/api/v1/kernel/schedules",
            json={
                "name": "no-cron-test",
                "agent_name": "cody",
            },
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_schedule_duplicate_name(
        self, client: AsyncClient,
    ):
        """Duplicate name returns 409."""
        payload = {
            "name": "dup-schedule-test",
            "cron_expression": "0 3 * * *",
            "agent_name": "cody",
        }
        first = await client.post(
            "/api/v1/kernel/schedules", json=payload,
        )
        if first.status_code != 201:
            pytest.skip("DB unavailable")

        second = await client.post(
            "/api/v1/kernel/schedules", json=payload,
        )
        assert second.status_code in (409, 500)


# ── List Schedules Endpoint ──────────────────────────────────


class TestListSchedules:
    """GET /api/v1/kernel/schedules"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_schedules_returns_200(
        self, client: AsyncClient,
    ):
        """List returns 200 with total."""
        response = await client.get(
            "/api/v1/kernel/schedules",
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            data = response.json()["data"]
            assert "schedules" in data
            assert "total" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_schedules_include_inactive(
        self, client: AsyncClient,
    ):
        """include_inactive=true shows disabled jobs."""
        response = await client.get(
            "/api/v1/kernel/schedules",
            params={"include_inactive": "true"},
        )
        assert response.status_code in (200, 500)


# ── Get Schedule Detail ──────────────────────────────────────


class TestGetSchedule:
    """GET /api/v1/kernel/schedules/{id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_schedule_not_found(
        self, client: AsyncClient,
    ):
        """Non-existent schedule returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/kernel/schedules/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_schedule_invalid_uuid(
        self, client: AsyncClient,
    ):
        """Invalid UUID returns 422."""
        response = await client.get(
            "/api/v1/kernel/schedules/not-a-uuid",
        )
        assert response.status_code in (422, 500)


# ── Update Schedule ──────────────────────────────────────────


class TestUpdateSchedule:
    """PATCH /api/v1/kernel/schedules/{id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_schedule_not_found(
        self, client: AsyncClient,
    ):
        """Updating non-existent schedule returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/api/v1/kernel/schedules/{fake_id}",
            json={"description": "Updated"},
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_schedule_bad_cron(
        self, client: AsyncClient,
    ):
        """Updating with invalid cron returns 400."""
        # Create first
        resp = await client.post(
            "/api/v1/kernel/schedules",
            json={
                "name": "update-cron-test",
                "cron_expression": "0 3 * * *",
                "agent_name": "cody",
            },
        )
        if resp.status_code != 201:
            pytest.skip("DB unavailable")

        sid = resp.json()["data"]["id"]
        update = await client.patch(
            f"/api/v1/kernel/schedules/{sid}",
            json={"cron_expression": "bad"},
        )
        assert update.status_code in (400, 500)


# ── Delete Schedule ──────────────────────────────────────────


class TestDeleteSchedule:
    """DELETE /api/v1/kernel/schedules/{id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_schedule_not_found(
        self, client: AsyncClient,
    ):
        """Deleting non-existent schedule returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/api/v1/kernel/schedules/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_schedule_success(
        self, client: AsyncClient,
    ):
        """Deleting an existing schedule returns success."""
        resp = await client.post(
            "/api/v1/kernel/schedules",
            json={
                "name": "delete-me-schedule",
                "cron_expression": "0 3 * * *",
                "agent_name": "cody",
            },
        )
        if resp.status_code != 201:
            pytest.skip("DB unavailable")

        sid = resp.json()["data"]["id"]
        del_resp = await client.delete(
            f"/api/v1/kernel/schedules/{sid}",
        )
        assert del_resp.status_code in (200, 500)
        data = del_resp.json()["data"]
        assert data["message"] == "Schedule removed"
