"""Pattern-based query router — zero-LLM query classification.

Routes incoming queries to the appropriate retrieval backend
(graph, relational, vector, reasoning, intentions) using compiled
regex patterns. Falls back to 'hybrid' for unmatched queries.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Route definitions: (route_name, list_of_regex_patterns)
# Patterns are compiled at module load for performance.
# ---------------------------------------------------------------------------

_ROUTE_DEFINITIONS: list[tuple[str, list[str]]] = [
    ("graph", [
        r"what\s+do\s+i\s+(?:prefer|use|like)",
        r"what\s+(?:tools?|frameworks?|languages?|databases?)",
        r"what\s+is\s+my\s+(?:preferred|favorite|go[- ]?to)",
    ]),
    ("relational", [
        r"when\s+did\s+i",
        r"last\s+time\s+i",
        r"history\s+of",
        r"how\s+many\s+times",
        r"how\s+often",
    ]),
    ("reasoning", [
        r"why\s+did\s+i",
        r"why\s+do\s+i",
        r"reason\s+for",
        r"explain\s+my",
    ]),
    ("vector", [
        r"similar\s+to",
        r"related\s+to",
        r"like\s+this",
        r"find.*similar",
        r"anything\s+like",
    ]),
    ("intentions", [
        r"\btodo\b",
        r"\bremind\b",
        r"\bplan\b",
        r"what\s+should\s+i\s+do",
        r"\bpending\b",
        r"\bupcoming\b",
    ]),
]


class _CompiledRoute:
    """A single route with its pre-compiled regex patterns."""

    __slots__ = ("name", "patterns")

    def __init__(self, name: str, raw_patterns: list[str]) -> None:
        self.name = name
        self.patterns: list[re.Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in raw_patterns
        ]

    def match(self, query: str) -> re.Match[str] | None:
        """Return the first matching pattern, or None."""
        for pattern in self.patterns:
            m = pattern.search(query)
            if m is not None:
                return m
        return None


class QueryRouter:
    """Routes queries to the appropriate retrieval backend.

    All patterns are compiled once at instantiation. Matching is
    deterministic and requires zero LLM calls.

    Route types:
    - **graph**: preference/tool/stack queries → Apache AGE graph
    - **relational**: temporal/history queries → PostgreSQL relational
    - **reasoning**: 'why' queries → multi-hop retrieval + reasoning
    - **vector**: similarity queries → pgvector cosine search
    - **intentions**: TODO/reminder queries → intentions store
    - **hybrid**: everything else → combined retrieval
    """

    def __init__(self) -> None:
        self._routes: list[_CompiledRoute] = [
            _CompiledRoute(name, patterns)
            for name, patterns in _ROUTE_DEFINITIONS
        ]

    def route(self, query: str) -> str:
        """Classify a query and return the route name.

        Args:
            query: The user's query string.

        Returns:
            Route type: 'graph', 'relational', 'reasoning',
            'vector', 'intentions', or 'hybrid'.
        """
        for compiled_route in self._routes:
            if compiled_route.match(query) is not None:
                return compiled_route.name
        return "hybrid"

    def route_detailed(self, query: str) -> dict[str, Any]:
        """Classify a query and return detailed routing metadata.

        Args:
            query: The user's query string.

        Returns:
            Dict with 'route', 'confidence', and 'matched_pattern'.
        """
        for compiled_route in self._routes:
            m = compiled_route.match(query)
            if m is not None:
                return {
                    "route": compiled_route.name,
                    "confidence": 1.0,
                    "matched_pattern": m.re.pattern,
                }

        return {
            "route": "hybrid",
            "confidence": 0.5,
            "matched_pattern": "default",
        }
