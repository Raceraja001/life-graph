"""Shadow-mode policy — the graduation bar for the autonomy ladder.

A new autonomous actor runs in dry-run ("shadow"): the pipeline records what it
*would have done* instead of executing. The user grades each would-have-done;
an actor graduates to acting for real only once it has soaked long enough, been
graded enough times, and been graded well enough. This module holds that pure
decision; ``autonomy/shadow/service.py`` wraps it with persistence.

No DB, no I/O (mirrors ``core/trust.py`` and ``core/budget.py``).
"""

from __future__ import annotations

from enum import Enum

DEFAULT_MIN_DAYS = 14
DEFAULT_MIN_SAMPLES = 5
DEFAULT_GOOD_RATE_THRESHOLD = 0.8


class ShadowGrade(str, Enum):
    """A one-tap grade on a would-have-done shadow run."""

    GOOD = "good"
    BAD = "bad"


def good_rate(graded_good: int, graded_bad: int) -> float:
    """Fraction of graded runs marked good. 0.0 when nothing has been graded."""
    total = graded_good + graded_bad
    if total <= 0:
        return 0.0
    return graded_good / total


def should_graduate(
    days_enrolled: float,
    graded_good: int,
    graded_bad: int,
    *,
    min_days: int = DEFAULT_MIN_DAYS,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    good_rate_threshold: float = DEFAULT_GOOD_RATE_THRESHOLD,
) -> bool:
    """Decide whether a shadowed actor may graduate to acting for real.

    Graduates only when ALL three hold — calendar soak, enough graded samples,
    and a good-enough good-rate:

        days_enrolled >= min_days
        AND graded_good >= min_samples
        AND good_rate(good, bad) >= good_rate_threshold

    A run graded ``bad`` lowers the good-rate and can keep the actor in shadow.
    """
    if days_enrolled < min_days:
        return False
    if graded_good < min_samples:
        return False
    return good_rate(graded_good, graded_bad) >= good_rate_threshold
