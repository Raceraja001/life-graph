"""Proactive recall unit tests (T-025).

Tests for ContextFingerprint, ContextBuilder, and RecallRanker — all
rule-based, no database or external services required.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from life_graph.scoring.ranking import (
    RecallRanker,
    context_similarity,
)
from life_graph.services.context import ContextBuilder, ContextFingerprint


# ── ContextFingerprint ────────────────────────────────────────────────────


class TestContextFingerprint:
    """Tests for the ContextFingerprint dataclass."""

    def test_create_empty_fingerprint(self) -> None:
        fp = ContextFingerprint()
        assert fp.project is None
        assert fp.module is None
        assert fp.tools == []
        assert fp.files_open == []
        assert fp.git_branch is None
        assert fp.topics == []

    def test_create_full_fingerprint(self) -> None:
        fp = ContextFingerprint(
            project="life-graph",
            module="api",
            tools=["python", "docker"],
            files_open=["main.py", "config.py"],
            git_branch="feature/recall",
            topics=["memory", "search"],
        )
        assert fp.project == "life-graph"
        assert fp.module == "api"
        assert len(fp.tools) == 2
        assert len(fp.files_open) == 2
        assert fp.git_branch == "feature/recall"
        assert fp.topics == ["memory", "search"]

    def test_is_empty_when_nothing_set(self) -> None:
        fp = ContextFingerprint()
        assert fp.is_empty is True

    def test_is_empty_false_when_project_set(self) -> None:
        fp = ContextFingerprint(project="foo")
        assert fp.is_empty is False

    def test_is_empty_false_when_tools_set(self) -> None:
        fp = ContextFingerprint(tools=["python"])
        assert fp.is_empty is False

    def test_as_dict_round_trips_all_fields(self) -> None:
        fp = ContextFingerprint(
            project="x",
            module="y",
            tools=["a"],
            files_open=["f.py"],
            git_branch="main",
            topics=["t1"],
        )
        d = fp.as_dict()
        assert d["project"] == "x"
        assert d["module"] == "y"
        assert d["tools"] == ["a"]
        assert d["files_open"] == ["f.py"]
        assert d["git_branch"] == "main"
        assert d["topics"] == ["t1"]

    def test_as_dict_empty_fingerprint(self) -> None:
        d = ContextFingerprint().as_dict()
        assert d["project"] is None
        assert d["tools"] == []

    def test_independent_list_instances(self) -> None:
        """Each fingerprint should have its own list objects."""
        fp1 = ContextFingerprint()
        fp2 = ContextFingerprint()
        fp1.tools.append("x")
        assert fp2.tools == []


# ── ContextBuilder ────────────────────────────────────────────────────────


class TestContextBuilder:
    """Tests for ContextBuilder.build() and similarity()."""

    def setup_method(self) -> None:
        self.builder = ContextBuilder()

    # -- build() -----------------------------------------------------------

    def test_build_from_dict(self) -> None:
        ctx = self.builder.build(
            {"project": "life-graph", "module": "api", "tools": ["python"]}
        )
        assert isinstance(ctx, ContextFingerprint)
        assert ctx.project == "life-graph"
        assert ctx.module == "api"
        assert ctx.tools == ["python"]

    def test_build_handles_missing_keys(self) -> None:
        ctx = self.builder.build({})
        assert ctx.project is None
        assert ctx.tools == []

    def test_build_handles_none_values(self) -> None:
        ctx = self.builder.build({"project": None, "tools": None})
        assert ctx.project is None
        assert ctx.tools == []

    def test_build_handles_empty_dict(self) -> None:
        ctx = self.builder.build({})
        assert ctx.is_empty is True

    def test_build_coerces_tool_strings(self) -> None:
        """A single string for 'tools' should still produce a list."""
        ctx = self.builder.build({"tools": "python"})
        assert ctx.tools == ["python"]

    def test_build_accepts_files_alias(self) -> None:
        """The builder accepts 'files' as an alias for 'files_open'."""
        ctx = self.builder.build({"files": ["app.py"]})
        assert ctx.files_open == ["app.py"]

    def test_build_prefers_files_open_over_files(self) -> None:
        """When both 'files_open' and 'files' are present, 'files_open' wins."""
        ctx = self.builder.build({"files_open": ["a.py"], "files": ["b.py"]})
        assert ctx.files_open == ["a.py"]

    def test_build_ignores_extra_keys(self) -> None:
        ctx = self.builder.build({"project": "x", "unknown_key": "y"})
        assert ctx.project == "x"

    # -- similarity() ------------------------------------------------------

    def test_similarity_identical(self) -> None:
        a = ContextFingerprint(
            project="x", module="y", tools=["a", "b"], files_open=["f1"]
        )
        b = ContextFingerprint(
            project="x", module="y", tools=["a", "b"], files_open=["f1"]
        )
        sim = self.builder.similarity(a, b)
        assert sim == 1.0

    def test_similarity_completely_different(self) -> None:
        a = ContextFingerprint(project="x", tools=["a"])
        b = ContextFingerprint(project="y", tools=["b"])
        sim = self.builder.similarity(a, b)
        # Project mismatch → 0, tools 0/1 → 0 → total 0.0
        assert sim == 0.0

    def test_similarity_partial_overlap(self) -> None:
        a = ContextFingerprint(project="x", tools=["a", "b", "c"])
        b = ContextFingerprint(project="x", tools=["a", "d", "e"])
        sim = self.builder.similarity(a, b)
        # Project +0.3, tools overlap 1/3 → 0.2*(1/3) ≈ 0.0667 → total ~0.367
        assert 0.3 < sim < 0.7

    def test_similarity_empty_fingerprints(self) -> None:
        a = ContextFingerprint()
        b = ContextFingerprint()
        sim = self.builder.similarity(a, b)
        assert sim == 0.0

    def test_similarity_project_only_match(self) -> None:
        a = ContextFingerprint(project="x")
        b = ContextFingerprint(project="x")
        sim = self.builder.similarity(a, b)
        assert sim == 0.3  # exactly the project weight

    def test_similarity_module_only_match(self) -> None:
        a = ContextFingerprint(module="api")
        b = ContextFingerprint(module="api")
        sim = self.builder.similarity(a, b)
        assert sim == 0.2  # exactly the module weight

    def test_similarity_tools_only_full_match(self) -> None:
        a = ContextFingerprint(tools=["python", "docker"])
        b = ContextFingerprint(tools=["python", "docker"])
        sim = self.builder.similarity(a, b)
        assert sim == 0.2  # 0.2 × (2/2)

    def test_similarity_files_only_full_match(self) -> None:
        a = ContextFingerprint(files_open=["main.py", "config.py"])
        b = ContextFingerprint(files_open=["main.py", "config.py"])
        sim = self.builder.similarity(a, b)
        assert sim == 0.3  # 0.3 × (2/2)

    def test_similarity_is_symmetric(self) -> None:
        a = ContextFingerprint(project="x", tools=["a", "b"])
        b = ContextFingerprint(project="x", tools=["b", "c"])
        assert self.builder.similarity(a, b) == self.builder.similarity(b, a)

    def test_similarity_project_none_vs_set(self) -> None:
        """One side having project=None means no project match bonus."""
        a = ContextFingerprint(project="x")
        b = ContextFingerprint()
        sim = self.builder.similarity(a, b)
        assert sim == 0.0


# ── RecallRanker ──────────────────────────────────────────────────────────


class TestRecallRanker:
    """Tests for multi-signal ranking and diversity reranking."""

    def setup_method(self) -> None:
        self.ranker = RecallRanker()

    # -- rank() ------------------------------------------------------------

    def test_rank_single_candidate(self) -> None:
        candidates = [
            {
                "semantic_score": 0.9,
                "importance": 0.8,
                "trust_score": 0.7,
                "access_count": 5,
                "days_since_access": 1.0,
            },
        ]
        result = self.ranker.rank(candidates)
        assert len(result) == 1
        assert "final_score" in result[0]
        assert "_sub_scores" in result[0]
        assert result[0]["final_score"] > 0

    def test_rank_orders_by_final_score_descending(self) -> None:
        candidates = [
            {"semantic_score": 0.1, "importance": 0.1},
            {"semantic_score": 0.9, "importance": 0.9},
            {"semantic_score": 0.5, "importance": 0.5},
        ]
        result = self.ranker.rank(candidates)
        scores = [c["final_score"] for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_rank_preserves_original_fields(self) -> None:
        candidates = [{"semantic_score": 0.5, "custom_field": "hello"}]
        result = self.ranker.rank(candidates)
        assert result[0]["custom_field"] == "hello"

    def test_rank_handles_empty_candidates(self) -> None:
        result = self.ranker.rank([])
        assert result == []

    def test_rank_with_context_boosts_matching(self) -> None:
        candidates = [
            {"semantic_score": 0.5, "project": "life_graph"},
            {"semantic_score": 0.5, "project": "other"},
        ]
        result = self.ranker.rank(
            candidates, current_context={"project": "life_graph"}
        )
        # First result should be the context-matching one
        assert result[0]["project"] == "life_graph"
        assert result[0]["final_score"] > result[1]["final_score"]

    def test_rank_sub_scores_present(self) -> None:
        candidates = [{"semantic_score": 0.7, "importance": 0.6}]
        result = self.ranker.rank(candidates)
        sub = result[0]["_sub_scores"]
        expected_keys = {"semantic", "context", "importance", "recency", "frequency", "trust", "impact"}
        assert set(sub.keys()) == expected_keys

    def test_rank_with_last_accessed_datetime(self) -> None:
        """days_since_access can be derived from a 'last_accessed' datetime."""
        now = datetime.now(timezone.utc)
        candidates = [
            {
                "semantic_score": 0.5,
                "last_accessed": now - timedelta(days=1),
            },
            {
                "semantic_score": 0.5,
                "last_accessed": now - timedelta(days=30),
            },
        ]
        result = self.ranker.rank(candidates)
        # Recent memory should rank higher due to recency
        recent = [c for c in result if (now - c["last_accessed"]).days <= 2][0]
        old = [c for c in result if (now - c["last_accessed"]).days >= 29][0]
        assert recent["final_score"] > old["final_score"]

    # -- rerank() ----------------------------------------------------------

    def test_rerank_limits_results(self) -> None:
        candidates = [
            {"final_score": 0.9 - i * 0.1, "tags": [f"t{i}"], "type": f"type{i}"}
            for i in range(10)
        ]
        result = self.ranker.rerank(candidates, max_results=3)
        assert len(result) <= 3

    def test_rerank_topic_cap(self) -> None:
        """At most max_per_topic memories per topic cluster."""
        candidates = [
            {"final_score": 0.9, "tags": ["python"], "type": "fact"},
            {"final_score": 0.8, "tags": ["python"], "type": "preference"},
            {"final_score": 0.7, "tags": ["python"], "type": "decision"},
            {"final_score": 0.6, "tags": ["docker"], "type": "fact"},
        ]
        result = self.ranker.rerank(candidates, max_results=10, max_per_topic=2)
        python_count = sum(
            1 for c in result if c.get("tags", [None])[0] == "python"
        )
        assert python_count <= 2

    def test_rerank_cooldown_filter(self) -> None:
        """Memories surfaced recently should be filtered out."""
        now = datetime.now(timezone.utc)
        candidates = [
            {
                "final_score": 0.9,
                "tags": ["a"],
                "type": "fact",
                "last_surfaced": now - timedelta(days=1),  # too recent
            },
            {
                "final_score": 0.7,
                "tags": ["b"],
                "type": "fact",
                "last_surfaced": now - timedelta(days=30),  # ok
            },
        ]
        result = self.ranker.rerank(candidates, cooldown_days=7.0)
        assert len(result) == 1
        assert result[0]["tags"] == ["b"]

    def test_rerank_no_cooldown_when_no_last_surfaced(self) -> None:
        candidates = [
            {"final_score": 0.9, "tags": ["a"], "type": "fact"},
        ]
        result = self.ranker.rerank(candidates)
        assert len(result) == 1

    def test_rerank_preserves_score_order(self) -> None:
        candidates = [
            {"final_score": 0.9, "tags": ["a"], "type": "fact"},
            {"final_score": 0.8, "tags": ["b"], "type": "preference"},
            {"final_score": 0.7, "tags": ["c"], "type": "decision"},
        ]
        result = self.ranker.rerank(candidates, max_results=3)
        scores = [c["final_score"] for c in result]
        assert scores == sorted(scores, reverse=True)


# ── context_similarity (standalone function) ──────────────────────────────


class TestContextSimilarity:
    """Tests for the standalone context_similarity function from ranking.py."""

    def test_identical_contexts(self) -> None:
        ctx = {"project": "x", "module": "y", "tools": ["a"], "files": ["f"]}
        assert context_similarity(ctx, ctx) == 1.0

    def test_empty_contexts(self) -> None:
        assert context_similarity({}, {}) == 0.0

    def test_project_match_only(self) -> None:
        score = context_similarity({"project": "x"}, {"project": "x"})
        assert score == pytest.approx(0.3)

    def test_tools_partial_overlap(self) -> None:
        score = context_similarity(
            {"tools": ["a", "b"]},
            {"tools": ["b", "c"]},
        )
        # overlap 1 / max(2,2) = 0.5 → 0.2 * 0.5 = 0.1
        assert score == pytest.approx(0.1)
