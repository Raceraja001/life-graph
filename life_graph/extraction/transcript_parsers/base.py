# life_graph/extraction/transcript_parsers/base.py
"""Shared types for pluggable transcript parsers.

A parser turns one tool's raw transcript lines into a common ``Turn`` list;
the distiller and endpoint stay tool-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterable


class Turn(TypedDict):
    role: str  # "user" | "assistant"
    text: str  # plain text content
    ts: str | None  # ISO8601 timestamp if available


class TranscriptParser(Protocol):
    tool: str

    def parse(self, lines: Iterable[str]) -> list[Turn]: ...
