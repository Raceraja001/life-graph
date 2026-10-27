import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from life_graph.services.nudges import as_listed


def test_as_listed_full_context_and_trigger():
    """Test as_listed with full context_match and a trigger_time."""
    # Create a fake row with all fields populated.
    row_id = uuid.uuid4()
    content = "Buy milk"
    status = "open"
    # Use a timezone-aware datetime for trigger_time.
    trigger = datetime.now(tz=UTC)
    context = {
        "when": "today",
        "due_by": "tomorrow",
        "said_at": "2023-01-01T00:00:00Z",
    }
    row = SimpleNamespace(
        id=row_id,
        content=content,
        status=status,
        trigger_time=trigger,
        context_match=context,
    )

    result = as_listed(row)

    assert result["id"] == str(row_id)
    assert result["what"] == content
    assert result["status"] == status
    # Trigger time should be ISO formatted.
    assert result["next_nudge_at"] == trigger.isoformat()
    # Context values should be propagated.
    assert result["when"] == context["when"]
    assert result["due_by"] == context["due_by"]
    assert result["said_at"] == context["said_at"]


def test_as_listed_missing_context_keys_and_trigger():
    """Test as_listed when context_match is missing keys and trigger_time is present."""
    row_id = uuid.uuid4()
    content = "Read book"
    status = "completed"
    trigger = datetime.now(tz=UTC)
    # Empty context: no keys.
    row = SimpleNamespace(
        id=row_id,
        content=content,
        status=status,
        trigger_time=trigger,
        context_match={},
    )

    result = as_listed(row)

    # All keys should be present.
    assert set(result.keys()) == {
        "id",
        "what",
        "when",
        "due_by",
        "status",
        "next_nudge_at",
        "said_at",
    }
    # Missing keys default to None.
    assert result["when"] is None
    assert result["due_by"] is None
    assert result["said_at"] is None
    # Trigger time formatted.
    assert result["next_nudge_at"] == trigger.isoformat()


def test_as_listed_context_none_and_no_trigger():
    """Test as_listed when context_match is None and trigger_time is None."""
    row_id = 123
    content = "Exercise"
    status = "pending"
    row = SimpleNamespace(
        id=row_id,
        content=content,
        status=status,
        trigger_time=None,
        context_match=None,
    )

    result = as_listed(row)

    assert result["id"] == str(row_id)
    assert result["what"] == content
    assert result["status"] == status
    # Trigger time is None.
    assert result["next_nudge_at"] is None
    # Context keys are None.
    assert result["when"] is None
    assert result["due_by"] is None
    assert result["said_at"] is None
