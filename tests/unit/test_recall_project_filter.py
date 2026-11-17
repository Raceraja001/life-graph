"""Recall must not pre-filter candidates by project.

`_retrieve_candidates` ANDed `properties->>'project' = <session project>` into
the SQL. That is the same mistake the candidate pool made once before — a
pre-filter deciding what the ranker exists to decide — and it had a worse
failure mode, because nothing was writing a project onto capture-derived
memories. Every session that reported a project (every session, since the hook
derives one from cwd) therefore matched zero candidates, and proactive recall
returned empty buckets on an instance with hundreds of active memories.

The ranker already prefers a same-project memory inside its context signal,
and unlike the filter it degrades to "no preference" when the project is
unknown instead of eliminating everything.
"""

from __future__ import annotations

import ast
import pathlib

from life_graph.scoring.ranking import context_similarity

RECALL_PY = pathlib.Path(__file__).resolve().parents[2] / "life_graph" / "services" / "recall.py"


def _retrieve_candidates_source() -> str:
    tree = ast.parse(RECALL_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_retrieve_candidates":
            return ast.get_source_segment(RECALL_PY.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("recall.py has no _retrieve_candidates()")


def test_the_candidate_query_filters_on_status_only():
    """A project predicate here eliminates candidates the ranker should weigh."""
    source = _retrieve_candidates_source()
    assert '"status": "active"' in source
    assert "fingerprint.project" not in source, (
        "filtering candidates by project returns nothing whenever the session's "
        "project is absent from the stored properties"
    )


def test_the_ranker_is_where_project_preference_lives():
    """The behaviour the filter was reaching for, kept where it belongs."""
    same = context_similarity({"project": "life-graph"}, {"project": "life-graph"})
    different = context_similarity({"project": "life-graph"}, {"project": "uzhavu"})
    unknown = context_similarity({}, {"project": "life-graph"})

    assert same > different
    # The important half: an unknown project is a neutral score, not a zero
    # that removes the candidate from consideration altogether.
    assert unknown == different
