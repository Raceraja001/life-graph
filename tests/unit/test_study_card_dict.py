import uuid
from datetime import date, datetime

import pytest

from life_graph.models.assistant import ReviewCard
from life_graph.services.study import card_dict


@pytest.fixture
def sample_card() -> ReviewCard:
    """Return a sample ReviewCard instance with realistic data."""
    return ReviewCard(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        tenant_id="tenant1",
        deck="math",
        front="What is 2+2?",
        back="4",
        source_memory_id=None,
        ease=2.5,
        interval_days=5,
        repetitions=2,
        due_on=date(2023, 1, 1),
        last_grade="good",
        reviews=3,
        dedup_key="hash",
        created_at=datetime(2023, 1, 1),
    )


def test_card_dict_basic(sample_card: ReviewCard):
    result = card_dict(sample_card)
    assert isinstance(result, dict)
    assert result["id"] == str(sample_card.id)
    assert result["deck"] == sample_card.deck
    assert result["front"] == sample_card.front
    assert result["back"] == sample_card.back
    assert result["due_on"] == sample_card.due_on.isoformat()
    assert result["interval_days"] == sample_card.interval_days
    assert result["repetitions"] == sample_card.repetitions
    assert result["ease"] == sample_card.ease
    assert result["reviews"] == sample_card.reviews
    assert result["last_grade"] == sample_card.last_grade


def test_card_dict_last_grade_none():
    card = ReviewCard(
        id=uuid.uuid4(),
        tenant_id="tenant2",
        deck="science",
        front="What is H2O?",
        back="Water",
        source_memory_id=None,
        ease=1.5,
        interval_days=0,
        repetitions=0,
        due_on=date.today(),
        last_grade=None,
        reviews=0,
        dedup_key="hash2",
        created_at=datetime.now(),
    )
    result = card_dict(card)
    assert result["last_grade"] is None
