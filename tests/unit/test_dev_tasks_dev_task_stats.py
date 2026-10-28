import pytest
import pytest_asyncio

from life_graph.services.dev_tasks import dev_task_stats

# Monkeypatch list_dev_tasks in tests


@pytest_asyncio.fixture
async def fake_session():
    """A dummy async session that is ignored by dev_task_stats because we patch list_dev_tasks."""

    class Dummy:
        async def close(self):
            pass

    return Dummy()


# Helper to patch list_dev_tasks
async def _patch_list_dev_tasks(monkeypatch, return_value):
    async def fake_list_dev_tasks(session, tenant_id, limit=2000):  # noqa: D401
        return return_value

    monkeypatch.setattr("life_graph.services.dev_tasks.list_dev_tasks", fake_list_dev_tasks)


@pytest.mark.asyncio
async def test_empty_tasks(fake_session, monkeypatch):
    await _patch_list_dev_tasks(monkeypatch, [])
    result = await dev_task_stats(fake_session, "tenant1")
    assert result == []


@pytest.mark.asyncio
async def test_persona_none_replaced(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": None,
                "project_id": "proj1",
                "project_name": "Project 1",
                "stage": "merged",
                "duration_ms": 1000,
                "cost_usd": 1.5,
            }
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["persona"] == "?"
    assert result[0]["project_id"] == "proj1"


@pytest.mark.asyncio
async def test_project_id_none(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "agent1",
                "project_id": None,
                "project_name": "Unnamed",
                "stage": "merged",
                "duration_ms": 2000,
                "cost_usd": 2.0,
            }
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["project_id"] is None


@pytest.mark.asyncio
async def test_in_flight_count(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "queued",
                "duration_ms": 10,
                "cost_usd": 0.1,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "running",
                "duration_ms": 20,
                "cost_usd": 0.2,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": 30,
                "cost_usd": 0.3,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["in_flight"] == 2


@pytest.mark.asyncio
async def test_merged_count(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": 10,
                "cost_usd": 0.1,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": 20,
                "cost_usd": 0.2,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["merged"] == 2


@pytest.mark.asyncio
async def test_needs_review_count(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "needs_review",
                "duration_ms": 10,
                "cost_usd": 0.1,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "needs_review",
                "duration_ms": 20,
                "cost_usd": 0.2,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["needs_review"] == 2


@pytest.mark.asyncio
async def test_merge_rate_none_when_settled_zero(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "queued",
                "duration_ms": 10,
                "cost_usd": 0.1,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "running",
                "duration_ms": 20,
                "cost_usd": 0.2,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["merge_rate"] is None


@pytest.mark.asyncio
async def test_avg_duration_ms_none_when_empty(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": None,
                "cost_usd": 0.1,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["avg_duration_ms"] is None


@pytest.mark.asyncio
async def test_avg_cost_usd_none_when_empty(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": 10,
                "cost_usd": None,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    assert result[0]["avg_cost_usd"] is None


@pytest.mark.asyncio
async def test_sorting_by_total(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p1",
                "project_id": "a",
                "project_name": "A",
                "stage": "merged",
                "duration_ms": 10,
                "cost_usd": 1.0,
            },
            {
                "persona": "p1",
                "project_id": "b",
                "project_name": "B",
                "stage": "merged",
                "duration_ms": 20,
                "cost_usd": 2.0,
            },
            {
                "persona": "p1",
                "project_id": "b",
                "project_name": "B",
                "stage": "merged",
                "duration_ms": 30,
                "cost_usd": 3.0,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    # project b has 2 tasks, a has 1
    assert result[0]["project_id"] == "b"
    assert result[1]["project_id"] == "a"


@pytest.mark.asyncio
async def test_merge_rate_and_averages_calculated(fake_session, monkeypatch):
    await _patch_list_dev_tasks(
        monkeypatch,
        [
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": 100,
                "cost_usd": 1.0,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "merged",
                "duration_ms": 200,
                "cost_usd": 2.0,
            },
            {
                "persona": "p",
                "project_id": "proj",
                "project_name": "P",
                "stage": "queued",
                "duration_ms": 300,
                "cost_usd": 3.0,
            },
        ],
    )
    result = await dev_task_stats(fake_session, "tenant1")
    group = result[0]
    # settled = total - in_flight = 3 - 1 = 2
    assert group["merge_rate"] == round(2 / 2, 3)
    assert group["avg_duration_ms"] == round((100 + 200 + 300) / 3)
    assert group["avg_cost_usd"] == round((1.0 + 2.0 + 3.0) / 3, 4)
