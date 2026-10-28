"""Unit tests for day_row in life_graph.services.jarvis_memory.

Tests cover the three decision points in day_row:
1. with_source parameter (True/False)
2. source property in memory (present/missing)
3. content parameter (with/without episode prefix)
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from life_graph.services import jarvis_memory as jm

NOW = None  # Not needed for day_row tests


def _m(*, content=None, props=None, tags=None, source_type="capture", status="active"):
    """Create a mock memory object for testing."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        properties=props or {},
        tags=tags,
        source_type=source_type,
        status=status,
        created_at=NOW,
    )


def test_day_row_with_source_true():
    """Test day_row when with_source=True includes source field."""
    m = _m(
        content="Conversations with Jarvis on Sunday 25 October 2026: Talked about the school app.",
        props={"source": "jarvis", "date": "2026-10-24"},
    )
    result = jm.day_row(m, with_source=True)
    assert result["id"] == str(m.id)
    assert result["date"] == "2026-10-24"
    assert result["summary"] == "Talked about the school app."
    assert result["source"] == "Jarvis"


def test_day_row_with_source_false():
    """Test day_row when with_source=False excludes source field."""
    m = _m(
        content="Conversations with Jarvis on Sunday 25 October 2026: Talked about the school app.",
        props={"source": "jarvis", "date": "2026-10-24"},
    )
    result = jm.day_row(m, with_source=False)
    assert result["id"] == str(m.id)
    assert result["date"] == "2026-10-24"
    assert result["summary"] == "Talked about the school app."
    assert "source" not in result


def test_day_row_missing_source_property():
    """Test day_row when source property is missing defaults to 'Life Graph'."""
    m = _m(
        content="Conversations with Jarvis on Sunday 25 October 2026: Talked about the school app.",
        props={"date": "2026-10-24"},  # No source property
    )
    result = jm.day_row(m, with_source=True)
    assert result["source"] == "Life Graph"


def test_day_row_empty_content():
    """Test day_row when content is None or empty."""
    m = _m(content=None, props={"date": "2026-10-24"})
    result = jm.day_row(m, with_source=True)
    assert result["summary"] == ""

    m2 = _m(content="", props={"date": "2026-10-24"})
    result2 = jm.day_row(m2, with_source=True)
    assert result2["summary"] == ""


def test_day_row_non_episode_content():
    """Test day_row when content doesn't have episode prefix."""
    m = _m(
        content="Just a regular memory content.",
        props={"date": "2026-10-24"},
    )
    result = jm.day_row(m, with_source=True)
    assert result["summary"] == "Just a regular memory content."


def test_day_row_work_source():
    """Test day_row with work source mapping."""
    m = _m(
        content="Conversations with Jarvis on Sunday 25 October 2026: Talked about the school app.",
        props={"source": "work", "date": "2026-10-24"},
    )
    result = jm.day_row(m, with_source=True)
    assert result["source"] == "Claude Code"


def test_day_row_unknown_source():
    """Test day_row when source is not in _DAY_SOURCE mapping."""
    m = _m(
        content="Conversations with Jarvis on Sunday 25 October 2026: Talked about the school app.",
        props={"source": "unknown", "date": "2026-10-24"},
    )
    result = jm.day_row(m, with_source=True)
    assert result["source"] == "Life Graph"
