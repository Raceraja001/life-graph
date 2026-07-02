"""Unit tests for Life Graph query router (T-036).

Tests the pattern-based QueryRouter — zero-LLM query classification
that routes to graph, relational, reasoning, vector, intentions,
or hybrid backends.
"""

from __future__ import annotations

import pytest

from life_graph.core.router import QueryRouter


class TestQueryRouter:
    """Test pattern-based query routing."""

    def setup_method(self) -> None:
        self.router = QueryRouter()

    # -- Graph routes (preference/tool/stack queries) -----------------------

    def test_routes_preference_to_graph(self) -> None:
        assert self.router.route("what do I prefer for databases") == "graph"

    def test_routes_what_tools_to_graph(self) -> None:
        assert self.router.route("what tools do I use") == "graph"

    def test_routes_what_frameworks_to_graph(self) -> None:
        assert self.router.route("what frameworks do I use") == "graph"

    def test_routes_what_languages_to_graph(self) -> None:
        assert self.router.route("what languages do I use") == "graph"

    def test_routes_favorite_to_graph(self) -> None:
        assert self.router.route("what is my favorite framework") == "graph"

    def test_routes_preferred_to_graph(self) -> None:
        assert self.router.route("what is my preferred database") == "graph"

    def test_routes_goto_to_graph(self) -> None:
        assert self.router.route("what is my go-to language") == "graph"

    def test_routes_what_do_i_like(self) -> None:
        assert self.router.route("what do I like for testing") == "graph"

    def test_routes_what_do_i_use(self) -> None:
        assert self.router.route("what do I use for linting") == "graph"

    # -- Relational routes (temporal/history queries) -----------------------

    def test_routes_when_to_relational(self) -> None:
        assert self.router.route("when did I decide on PostgreSQL") == "relational"

    def test_routes_last_time_to_relational(self) -> None:
        assert self.router.route("last time I worked on auth") == "relational"

    def test_routes_history_to_relational(self) -> None:
        assert self.router.route("history of my database choices") == "relational"

    def test_routes_how_many_times_to_relational(self) -> None:
        assert self.router.route("how many times did I deploy") == "relational"

    def test_routes_how_often_to_relational(self) -> None:
        assert self.router.route("how often do I refactor") == "relational"

    # -- Reasoning routes ('why' queries) -----------------------------------

    def test_routes_why_did_to_reasoning(self) -> None:
        assert self.router.route("why did I choose FastAPI") == "reasoning"

    def test_routes_why_do_to_reasoning(self) -> None:
        assert self.router.route("why do I prefer async drivers") == "reasoning"

    def test_routes_reason_for_to_reasoning(self) -> None:
        assert self.router.route("reason for using PostgreSQL") == "reasoning"

    def test_routes_explain_my_to_reasoning(self) -> None:
        assert self.router.route("explain my decision about Docker") == "reasoning"

    # -- Vector routes (similarity/search queries) --------------------------

    def test_routes_similar_to_vector(self) -> None:
        assert self.router.route("find something similar to my auth pattern") == "vector"

    def test_routes_related_to_vector(self) -> None:
        assert self.router.route("anything related to caching strategies") == "vector"

    def test_routes_like_this_to_vector(self) -> None:
        assert self.router.route("something like this pattern") == "vector"

    def test_routes_find_similar_to_vector(self) -> None:
        assert self.router.route("find similar approaches to this") == "vector"

    def test_routes_anything_like_to_vector(self) -> None:
        assert self.router.route("anything like the retry pattern") == "vector"

    # -- Intention routes (TODO/reminder queries) ---------------------------

    def test_routes_todo_to_intentions(self) -> None:
        assert self.router.route("what are my pending todos") == "intentions"

    def test_routes_remind_to_intentions(self) -> None:
        assert self.router.route("remind me about the deployment") == "intentions"

    def test_routes_plan_to_intentions(self) -> None:
        assert self.router.route("what is my plan for next week") == "intentions"

    def test_routes_pending_to_intentions(self) -> None:
        assert self.router.route("show pending items") == "intentions"

    def test_routes_upcoming_to_intentions(self) -> None:
        assert self.router.route("what upcoming tasks do I have") == "intentions"

    def test_routes_what_should_i_do_to_intentions(self) -> None:
        assert self.router.route("what should I do next") == "intentions"

    # -- Hybrid default (unmatched queries) ---------------------------------

    def test_routes_ambiguous_to_hybrid(self) -> None:
        assert self.router.route("tell me about my setup") == "hybrid"

    def test_routes_generic_to_hybrid(self) -> None:
        assert self.router.route("hello how are you") == "hybrid"

    def test_routes_empty_to_hybrid(self) -> None:
        assert self.router.route("") == "hybrid"

    def test_routes_random_text_to_hybrid(self) -> None:
        assert self.router.route("some random text about nothing") == "hybrid"

    # -- Case insensitivity -------------------------------------------------

    def test_case_insensitive_graph(self) -> None:
        assert self.router.route("WHAT DO I PREFER for databases") == "graph"

    def test_case_insensitive_relational(self) -> None:
        assert self.router.route("WHEN DID I decide on PostgreSQL") == "relational"

    def test_case_insensitive_reasoning(self) -> None:
        assert self.router.route("WHY DID I choose FastAPI") == "reasoning"

    def test_case_insensitive_intentions(self) -> None:
        assert self.router.route("my TODO list") == "intentions"


# ---------------------------------------------------------------------------
# Detailed routing
# ---------------------------------------------------------------------------


class TestQueryRouterDetailed:
    """Test the route_detailed method for metadata-rich routing."""

    def setup_method(self) -> None:
        self.router = QueryRouter()

    def test_route_detailed_returns_dict(self) -> None:
        result = self.router.route_detailed("what do I prefer")
        assert isinstance(result, dict)
        assert "route" in result
        assert "confidence" in result
        assert "matched_pattern" in result

    def test_route_detailed_high_confidence_on_match(self) -> None:
        result = self.router.route_detailed("what do I prefer for APIs")
        assert result["confidence"] == 1.0
        assert result["route"] == "graph"

    def test_route_detailed_low_confidence_on_default(self) -> None:
        result = self.router.route_detailed("something random here")
        assert result["confidence"] == 0.5
        assert result["route"] == "hybrid"
        assert result["matched_pattern"] == "default"

    def test_route_detailed_includes_matched_pattern(self) -> None:
        result = self.router.route_detailed("why did I choose FastAPI")
        assert result["route"] == "reasoning"
        assert result["matched_pattern"] != "default"
        assert isinstance(result["matched_pattern"], str)

    def test_route_detailed_graph_pattern(self) -> None:
        result = self.router.route_detailed("what tools do I use")
        assert result["route"] == "graph"
        assert result["confidence"] == 1.0

    def test_route_detailed_relational_pattern(self) -> None:
        result = self.router.route_detailed("when did I start this project")
        assert result["route"] == "relational"
        assert result["confidence"] == 1.0

    def test_route_detailed_vector_pattern(self) -> None:
        result = self.router.route_detailed("find something similar to this")
        assert result["route"] == "vector"
        assert result["confidence"] == 1.0

    def test_route_detailed_intentions_pattern(self) -> None:
        result = self.router.route_detailed("show my pending tasks")
        assert result["route"] == "intentions"
        assert result["confidence"] == 1.0


# ---------------------------------------------------------------------------
# Route priority / first-match behaviour
# ---------------------------------------------------------------------------


class TestQueryRouterPriority:
    """Test that route ordering gives deterministic results for ambiguous queries."""

    def setup_method(self) -> None:
        self.router = QueryRouter()

    def test_all_valid_routes(self) -> None:
        valid_routes = {"graph", "relational", "reasoning", "vector", "intentions", "hybrid"}
        # Every query should return a valid route
        queries = [
            "what do I prefer",
            "when did I decide",
            "why did I choose",
            "find similar",
            "my todos",
            "random text",
        ]
        for q in queries:
            assert self.router.route(q) in valid_routes

    def test_deterministic_routing(self) -> None:
        query = "what do I prefer for databases"
        route1 = self.router.route(query)
        route2 = self.router.route(query)
        assert route1 == route2

    def test_detailed_matches_simple(self) -> None:
        queries = [
            "what do I prefer",
            "when did I decide",
            "why did I choose",
            "find similar",
            "my todos",
            "tell me about my setup",
        ]
        for q in queries:
            simple = self.router.route(q)
            detailed = self.router.route_detailed(q)
            assert simple == detailed["route"], f"Mismatch for query: {q}"
