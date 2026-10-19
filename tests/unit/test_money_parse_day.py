from datetime import UTC, date, datetime

from life_graph.services.money import parse_day

# Test numeric format


def test_parse_day_numeric():
    raw = "12/10/2023"
    expected = date(2023, 10, 12)
    assert parse_day(raw) == expected


# Test month name format with full name


def test_parse_day_month_name():
    raw = "12 Oct 2023"
    expected = date(2023, 10, 12)
    assert parse_day(raw) == expected


# Test month name format without spaces (e.g., "12Oct2023")


def test_parse_day_month_abbrev():
    raw = "12Oct2023"
    expected = date(2023, 10, 12)
    assert parse_day(raw) == expected


# Test dash-separated month format


def test_parse_day_dash_separated():
    raw = "12-Oct-2023"
    expected = date(2023, 10, 12)
    assert parse_day(raw) == expected


# Test format without year, anchored to next year if needed


def test_parse_day_no_year_next_year():
    raw = "01 Jan"
    # Provide a date in the past, so the day is considered next year
    now = datetime(2022, 12, 15, tzinfo=UTC)
    expected = date(2023, 1, 1)
    assert parse_day(raw, now) == expected


# Test that invalid strings return None


def test_parse_day_invalid():
    raw = "invalid"
    assert parse_day(raw) is None


# Test empty string returns None


def test_parse_day_empty():
    raw = ""
    assert parse_day(raw) is None
