"""Unit tests for the `user_today` helper.

The helper is very small but it relies on the global `settings.user_timezone` and on
`datetime.now`/`ZoneInfo`.  The tests patch those values so that the behaviour can be
verified without touching the real system clock or timezone database.
"""

import datetime

import pytest

from life_graph.config import settings
from life_graph.services.assistant_daily import user_today


@pytest.fixture
def patch_datetime_now(monkeypatch):
    """Patch ``datetime.now`` to return a deterministic datetime.

    The patched function accepts an optional ``tz`` argument, mimicking the real
    ``datetime.now`` signature used in :func:`user_today`.
    """

    class DummyDatetime:
        @staticmethod
        def now(tz=None):  # pragma: no cover - trivial helper
            # Return a fixed point in time. ``tz`` is passed through to keep
            # the signature compatible with ``datetime.now(ZoneInfo(...))``.
            return datetime.datetime(2023, 3, 15, 12, 0, tzinfo=tz)

    monkeypatch.setattr("life_graph.services.assistant_daily.datetime", DummyDatetime, raising=True)
    return DummyDatetime.now


def test_user_today_valid_timezone(patch_datetime_now, monkeypatch):
    """When the timezone is valid, ``user_today`` returns the correct date."""

    monkeypatch.setattr(settings, "user_timezone", "Europe/Berlin")

    # ``datetime.now`` will be called twice: first with ZoneInfo, then (on error) with UTC.
    # Our fixture provides a deterministic value.
    result = user_today()
    assert result == datetime.date(2023, 3, 15)


def test_user_today_invalid_timezone_fallback(patch_datetime_now, monkeypatch):
    """An invalid timezone string causes a fallback to UTC."""

    monkeypatch.setattr(settings, "user_timezone", "Invalid/Zone")
    result = user_today()
    assert result == datetime.date(2023, 3, 15)


def test_user_today_empty_timezone_fallback(patch_datetime_now, monkeypatch):
    """An empty timezone string also falls back to UTC."""

    monkeypatch.setattr(settings, "user_timezone", "")
    result = user_today()
    assert result == datetime.date(2023, 3, 15)


# The following test demonstrates that the helper can handle timezones with
# offsets.  ``ZoneInfo('UTC+2')`` is not a valid IANA name and therefore falls
# back to UTC.  The test is kept for completeness.


def test_user_today_offset_timezone_fallback(patch_datetime_now, monkeypatch):
    monkeypatch.setattr(settings, "user_timezone", "UTC+2")
    result = user_today()
    assert result == datetime.date(2023, 3, 15)
