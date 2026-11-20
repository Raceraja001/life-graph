"""Small pure helpers that several modules had each written for themselves.

Audit L18: ``_utcnow`` had seven identical copies, ``_cosine_similarity``,
``_iso`` and ``_set_overlap_ratio`` two each. The modules keep their private
names as aliases of these (``from life_graph.core.utils import utcnow as
_utcnow``), so existing imports and monkeypatches still work. Copies that
behave differently (``services/memory/recall._cosine`` returns None on an
unusable vector; ``connectors/exposure._iso`` tests ``is not None``;
``services/reminders._iso`` parses) were left alone on purpose.

Standard library only: ``models/base.py`` imports this.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(UTC)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity of two vectors.

    Returns 0.0 when either vector is empty, the lengths differ, or either has
    zero magnitude.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    # Annotated: mypy types float ** float as Any. Same arithmetic as the copies.
    norm_a: float = sum(a * a for a in vec_a) ** 0.5
    norm_b: float = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def iso_or_none(value: datetime | None) -> str | None:
    """``value.isoformat()``, or None for a missing (falsy) value."""
    return value.isoformat() if value else None


def set_overlap_ratio(a: set[str], b: set[str]) -> float:
    """``len(a & b) / max(len(a), len(b))``; 0.0 when both sets are empty."""
    if not a and not b:
        return 0.0
    max_size = max(len(a), len(b))
    if max_size == 0:
        return 0.0
    return len(a & b) / max_size
