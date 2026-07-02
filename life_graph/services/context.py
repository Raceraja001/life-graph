"""Context fingerprint builder for proactive recall (T-021).

Builds a structured fingerprint from raw session context dicts
and computes similarity between two fingerprints using weighted
field matching. Zero LLM calls — all rule-based.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextFingerprint:
    """Structured representation of the current working context.

    Captures project, module, tools, open files, git branch,
    and topic keywords for context-aware memory retrieval.
    """

    project: str | None = None
    module: str | None = None
    tools: list[str] = field(default_factory=list)
    files_open: list[str] = field(default_factory=list)
    git_branch: str | None = None
    topics: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serialize fingerprint to a plain dict for storage or logging."""
        return {
            "project": self.project,
            "module": self.module,
            "tools": self.tools,
            "files_open": self.files_open,
            "git_branch": self.git_branch,
            "topics": self.topics,
        }

    @property
    def is_empty(self) -> bool:
        """Return True if no context fields are populated."""
        return (
            not self.project
            and not self.module
            and not self.tools
            and not self.files_open
            and not self.git_branch
            and not self.topics
        )


def _set_overlap_ratio(a: set[str], b: set[str]) -> float:
    """Compute overlap ratio between two sets.

    Returns intersection / max(len(a), len(b)), or 0.0 when both empty.
    """
    if not a and not b:
        return 0.0
    max_size = max(len(a), len(b))
    if max_size == 0:
        return 0.0
    return len(a & b) / max_size


class ContextBuilder:
    """Builds context fingerprints and computes similarity scores.

    Usage::

        builder = ContextBuilder()
        fp = builder.build({"project": "life_graph", "tools": ["pytest"]})
        score = builder.similarity(fp, other_fp)
    """

    def build(self, context_dict: dict[str, Any]) -> ContextFingerprint:
        """Create a ContextFingerprint from a raw context dict.

        Handles missing keys gracefully — unknown keys are ignored.

        Args:
            context_dict: Raw dict with optional keys matching
                ContextFingerprint fields.

        Returns:
            Populated ContextFingerprint instance.
        """
        if not context_dict:
            return ContextFingerprint()

        return ContextFingerprint(
            project=context_dict.get("project"),
            module=context_dict.get("module"),
            tools=_to_str_list(context_dict.get("tools")),
            files_open=_to_str_list(context_dict.get("files_open", context_dict.get("files", []))),
            git_branch=context_dict.get("git_branch"),
            topics=_to_str_list(context_dict.get("topics")),
        )

    def similarity(self, a: ContextFingerprint, b: ContextFingerprint) -> float:
        """Compute weighted similarity between two fingerprints.

        Scoring breakdown:
            - Project match: +0.3
            - Module match:  +0.2
            - Tools overlap: +0.2 × (intersection / max(len))
            - Files overlap: +0.3 × (intersection / max(len))

        Args:
            a: First context fingerprint.
            b: Second context fingerprint.

        Returns:
            Similarity score in [0.0, 1.0].
        """
        score = 0.0

        # Project match: +0.3
        if a.project and b.project and a.project == b.project:
            score += 0.3

        # Module match: +0.2
        if a.module and b.module and a.module == b.module:
            score += 0.2

        # Tools overlap: +0.2 × ratio
        tools_a = set(a.tools)
        tools_b = set(b.tools)
        if tools_a or tools_b:
            score += 0.2 * _set_overlap_ratio(tools_a, tools_b)

        # Files overlap: +0.3 × ratio
        files_a = set(a.files_open)
        files_b = set(b.files_open)
        if files_a or files_b:
            score += 0.3 * _set_overlap_ratio(files_a, files_b)

        return round(score, 6)


def _to_str_list(value: Any) -> list[str]:
    """Coerce a value to list[str], handling None and non-list inputs."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []
