"""life_graph/core/utils: one copy of the small helpers (audit L18).

The modules that had their own copy keep the private name as an alias of the
shared function, so behaviour, imports and monkeypatch targets are unchanged.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest

from life_graph.core import utils

ALIASES = [
    ("life_graph.models.base", "_utcnow", utils.utcnow),
    ("life_graph.services.memory.metamemory", "_utcnow", utils.utcnow),
    ("life_graph.services.intentions", "_utcnow", utils.utcnow),
    ("life_graph.services.workflow_engine", "_utcnow", utils.utcnow),
    ("life_graph.services.shared_context", "_utcnow", utils.utcnow),
    ("life_graph.extraction.intentions", "_utcnow", utils.utcnow),
    ("life_graph.connectors.models", "_utcnow", utils.utcnow),
    (
        "life_graph.services.memory.micro_consolidation",
        "_cosine_similarity",
        utils.cosine_similarity,
    ),
    ("life_graph.jobs.consolidation", "_cosine_similarity", utils.cosine_similarity),
    ("life_graph.services.memory.page", "_iso", utils.iso_or_none),
    ("life_graph.services.jarvis.memory", "_iso", utils.iso_or_none),
    ("life_graph.scoring.ranking", "_set_overlap_ratio", utils.set_overlap_ratio),
    ("life_graph.services.context", "_set_overlap_ratio", utils.set_overlap_ratio),
]


@pytest.mark.parametrize(("module", "name", "shared"), ALIASES)
def test_each_old_copy_is_now_the_shared_helper(module, name, shared):
    assert getattr(importlib.import_module(module), name) is shared


def test_utcnow_is_timezone_aware():
    assert utils.utcnow().tzinfo is UTC


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 2.0], [-1.0, -2.0], -1.0),
        ([], [1.0], 0.0),
        ([1.0], [1.0, 2.0], 0.0),
        ([0.0, 0.0], [1.0, 1.0], 0.0),
    ],
)
def test_cosine_similarity(a, b, expected):
    assert utils.cosine_similarity(a, b) == pytest.approx(expected)


def test_iso_or_none():
    when = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
    assert utils.iso_or_none(when) == "2026-11-20T09:30:00+00:00"
    assert utils.iso_or_none(None) is None


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(set(), set(), 0.0), ({"x"}, set(), 0.0), ({"x", "y"}, {"y"}, 0.5), ({"x"}, {"x"}, 1.0)],
)
def test_set_overlap_ratio(a, b, expected):
    assert utils.set_overlap_ratio(a, b) == expected
