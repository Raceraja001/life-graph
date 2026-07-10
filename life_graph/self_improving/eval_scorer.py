"""Evaluation scorer — dispatches scoring for eval cases.

Supports exact_match, contains, regex, and semantic_similarity.
Semantic similarity uses sentence_transformers lazily.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class ScoringType(str, Enum):
    """Supported scoring methods."""

    EXACT_MATCH = "exact_match"
    CONTAINS = "contains"
    REGEX = "regex"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    LLM_JUDGE = "llm_judge"


class EvalScorer:
    """Stateless scorer for eval cases."""

    def __init__(self) -> None:
        self._embedding_model = None

    def _get_embedding_model(self):
        """Lazily load the sentence transformer model."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedding_model

    def score(
        self,
        scoring_type: str,
        expected: str,
        actual: str,
        config: dict[str, Any] | None = None,
    ) -> tuple[bool, float, str | None]:
        """Score an actual output against the expected output.

        Returns:
            (passed, score, failure_reason)
            - passed: True if the output meets the threshold
            - score: Numeric score between 0.0 and 1.0
            - failure_reason: Human-readable explanation if failed, else None
        """
        config = config or {}

        try:
            st = ScoringType(scoring_type)
        except ValueError:
            return False, 0.0, f"Unknown scoring type: {scoring_type}"

        if st == ScoringType.EXACT_MATCH:
            return self._score_exact_match(expected, actual, config)
        elif st == ScoringType.CONTAINS:
            return self._score_contains(expected, actual, config)
        elif st == ScoringType.REGEX:
            return self._score_regex(expected, actual, config)
        elif st == ScoringType.SEMANTIC_SIMILARITY:
            return self._score_semantic(expected, actual, config)
        elif st == ScoringType.LLM_JUDGE:
            # LLM judge requires async LLM call — return placeholder
            return False, 0.0, "LLM judge not yet implemented"
        else:
            return False, 0.0, f"Unsupported scoring type: {scoring_type}"

    def _score_exact_match(
        self, expected: str, actual: str, config: dict[str, Any],
    ) -> tuple[bool, float, str | None]:
        """Case-insensitive exact match by default."""
        case_sensitive = config.get("case_sensitive", False)
        strip_whitespace = config.get("strip_whitespace", True)

        e = expected.strip() if strip_whitespace else expected
        a = actual.strip() if strip_whitespace else actual

        if not case_sensitive:
            e = e.lower()
            a = a.lower()

        passed = e == a
        return passed, 1.0 if passed else 0.0, (
            None if passed else f"Expected '{expected[:100]}', got '{actual[:100]}'"
        )

    def _score_contains(
        self, expected: str, actual: str, config: dict[str, Any],
    ) -> tuple[bool, float, str | None]:
        """Check if expected text is contained in actual output."""
        case_sensitive = config.get("case_sensitive", False)
        e = expected if case_sensitive else expected.lower()
        a = actual if case_sensitive else actual.lower()

        passed = e in a
        return passed, 1.0 if passed else 0.0, (
            None if passed else f"Expected output to contain '{expected[:100]}'"
        )

    def _score_regex(
        self, expected: str, actual: str, config: dict[str, Any],
    ) -> tuple[bool, float, str | None]:
        """Match actual output against an expected regex pattern."""
        flags = 0 if config.get("case_sensitive", False) else re.IGNORECASE

        try:
            match = re.search(expected, actual, flags)
        except re.error as exc:
            return False, 0.0, f"Invalid regex pattern: {exc}"

        passed = match is not None
        return passed, 1.0 if passed else 0.0, (
            None if passed else f"Output did not match pattern '{expected[:100]}'"
        )

    def _score_semantic(
        self, expected: str, actual: str, config: dict[str, Any],
    ) -> tuple[bool, float, str | None]:
        """Cosine similarity via sentence-transformers."""
        threshold = config.get("threshold", 0.8)
        model = self._get_embedding_model()

        embeddings = model.encode([expected, actual], normalize_embeddings=True)
        # Cosine similarity of normalized vectors = dot product
        similarity = float(embeddings[0] @ embeddings[1])

        passed = similarity >= threshold
        return passed, round(similarity, 4), (
            None if passed
            else f"Semantic similarity {similarity:.4f} below threshold {threshold}"
        )
