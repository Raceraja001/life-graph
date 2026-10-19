# Tests for grade_card in life_graph.services.study

import uuid
from datetime import date, timedelta

import pytest

from life_graph.models.assistant import ReviewCard
from life_graph.services.study import grade_card

# Helper to create a ReviewCard instance with specified attributes


def make_card(**kwargs) -> ReviewCard:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": "tenant1",
        "deck": "deck1",
        "front": "What is X?",
        "back": "Answer X.",
        "source_memory_id": None,
        "ease": 2.5,
        "interval_days": 5,
        "repetitions": 3,
        "due_on": date(2023, 1, 1),
        "last_grade": None,
        "reviews": 0,
        "dedup_key": "key1",
    }
    defaults.update(kwargs)
    return ReviewCard(**defaults)


@pytest.mark.parametrize(
    "grade,expected_reps,expected_interval",
    [
        ("again", 0, 1),
        ("hard", 4, 12),
    ],
)
def test_grade_card_basic(grade, expected_reps, expected_interval):
    card = make_card()
    today = date(2023, 1, 1)
    old_ease = card.ease
    # old_due was unused; removed to satisfy lint

    result = grade_card(card, grade, today)

    # grade_card returns the same object
    assert result is card
    # Ensure ease updated and stays >= 1.3
    assert card.ease >= 1.3
    # Repetitions and interval
    assert card.repetitions == expected_reps
    assert card.interval_days == expected_interval
    # Due date advanced by interval days
    assert card.due_on == today + timedelta(days=expected_interval)
    # last_grade set
    assert card.last_grade == grade
    # reviews incremented
    assert card.reviews == 1
    # ease changed
    assert card.ease != old_ease


def test_grade_card_invalid_grade():
    card = make_card()
    today = date(2023, 1, 1)
    with pytest.raises(ValueError) as exc:
        grade_card(card, "invalid", today)
    assert "grade must be one of" in str(exc.value)


def test_grade_card_none_reviews():
    card = make_card(reviews=None)
    today = date(2023, 1, 1)
    grade_card(card, "good", today)
    assert card.reviews == 1
    assert card.last_grade == "good"
