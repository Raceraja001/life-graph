"""The archive-proposal horizon is a six-month policy, not an accident.

Two constants decide when a memory becomes a candidate for a removal
proposal: ``memories.decay_rate`` (the lambda) and
``settings.decay_archive_threshold`` (the floor). Neither is legible on its
own -- the horizon only appears after taking a logarithm, which is exactly
how the old 39-day cliff went unnoticed. These tests assert the horizon in
days so a change to either constant has to be deliberate.
"""

import math

import pytest
from sqlalchemy import inspect as sa_inspect

from life_graph.config import settings
from life_graph.models.db import Memory
from life_graph.scoring.decay import DecayCalculator


def _column_default(name: str) -> float:
    """The Python-side default the ORM applies on insert."""
    col = sa_inspect(Memory).columns[name]
    return float(col.default.arg)


def _horizon_days(importance: float) -> float:
    """Days until ``importance`` decays below the proposal threshold."""
    rate = _column_default("decay_rate")
    return math.log(importance / settings.decay_archive_threshold) / rate


@pytest.mark.parametrize(
    ("importance", "low", "high"),
    [
        (0.5, 170.0, 190.0),  # the mid-importance case: ~180 days
        (1.0, 200.0, 225.0),  # maximum importance buys ~a month more
    ],
)
def test_proposal_horizon_is_about_six_months(importance, low, high):
    assert low < _horizon_days(importance) < high


def test_horizon_is_not_the_old_forty_day_cliff():
    """Regression: rate 0.1 proposed removal 39 days after last activity."""
    assert _horizon_days(0.5) > 150.0


def test_importance_still_orders_the_horizon():
    """A more important memory must survive longer, or the dial is inert."""
    assert _horizon_days(1.0) > _horizon_days(0.5) > _horizon_days(0.2)


def test_calculator_default_matches_the_column_default():
    """A drifting fallback would score unsaved memories on the old curve."""
    calc = DecayCalculator()
    column_rate = _column_default("decay_rate")
    explicit = calc.calculate(
        importance=0.6, access_count=1, days_since_access=30.0, decay_rate=column_rate
    )
    implied = calc.calculate(importance=0.6, access_count=1, days_since_access=30.0)
    assert implied == pytest.approx(explicit)


def test_a_memory_untouched_one_month_is_not_a_candidate():
    """The behaviour the horizon exists to guarantee."""
    calc = DecayCalculator()
    score = calc.calculate(
        importance=0.5,
        access_count=1,
        days_since_access=30.0,
        decay_rate=_column_default("decay_rate"),
    )
    assert not calc.should_archive(score, "normal", threshold=settings.decay_archive_threshold)
