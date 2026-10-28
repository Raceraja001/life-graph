# tests/unit/test_episodes_write_recent.py

from datetime import date

import pytest

from life_graph.services.episodes import write_recent

# The tests monkeypatch the write_day function to isolate write_recent.


@pytest.mark.asyncio
async def test_write_recent_single_day(monkeypatch):
    """Test that write_recent writes the correct single day when days=1."""

    async def mock_write_day(tenant_id: str, day: date):
        # Return a predictable key based on the day
        return [f"key_{day.isoformat()}"]

    monkeypatch.setattr("life_graph.services.episodes.write_day", mock_write_day)

    today = date(2023, 1, 2)
    result = await write_recent("tenant1", days=1, today=today)
    # For days=1, the function should write yesterday: 2023-01-01
    assert result == ["key_2023-01-01"]


@pytest.mark.asyncio
async def test_write_recent_multiple_days(monkeypatch):
    """Test that write_recent writes days in chronological order for multiple days."""

    async def mock_write_day(tenant_id: str, day: date):
        return [f"key_{day.isoformat()}"]

    monkeypatch.setattr("life_graph.services.episodes.write_day", mock_write_day)

    today = date(2023, 1, 3)
    result = await write_recent("tenant1", days=2, today=today)
    # days 2: back=2 -> 2023-01-01, back=1 -> 2023-01-02
    assert result == ["key_2023-01-01", "key_2023-01-02"]


@pytest.mark.asyncio
async def test_write_recent_zero_days(monkeypatch):
    """Test that write_recent returns an empty list and does not call write_day when days=0."""

    def mock_write_day(tenant_id: str, day: date):
        raise AssertionError("write_day should not be called for zero days")

    monkeypatch.setattr("life_graph.services.episodes.write_day", mock_write_day)

    today = date(2023, 1, 2)
    result = await write_recent("tenant1", days=0, today=today)
    assert result == []
