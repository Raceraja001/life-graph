"""Unit tests for correction-triple export shaping (Capture Spine).

Pure logic — no DB. Verifies the (original, corrected, context) training
triple shape and the exportability filter.
"""

from __future__ import annotations

import types
from datetime import UTC

from life_graph.services.capture import CaptureService


def _correction(**kw):
    """Lightweight stand-in for a Correction ORM row."""
    from datetime import datetime

    defaults = dict(
        original="git push",
        corrected="git push --force-with-lease",
        context={},
        domain_tags=["git"],
        kind="edit",
        created_at=datetime(2026, 7, 12, tzinfo=UTC),
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def test_to_triple_shape():
    c = _correction()
    t = CaptureService.to_triple(c)
    assert t["original"] == "git push"
    assert t["corrected"] == "git push --force-with-lease"
    assert t["context"] == {}
    assert t["domain_tags"] == ["git"]
    assert t["kind"] == "edit"
    assert t["created_at"].startswith("2026-07-12")


def test_to_triple_handles_null_created_at():
    t = CaptureService.to_triple(_correction(created_at=None))
    assert t["created_at"] is None


def test_exportable_default_true_when_both_sides_present():
    assert CaptureService.is_exportable(_correction()) is True


def test_not_exportable_when_opted_out():
    c = _correction(context={"exportable": False})
    assert CaptureService.is_exportable(c) is False


def test_not_exportable_when_missing_a_side():
    assert CaptureService.is_exportable(_correction(corrected=None)) is False
    assert CaptureService.is_exportable(_correction(original="")) is False
