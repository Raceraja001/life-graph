"""Data types for the Life Graph SDK."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Memory:
    """A single memory stored in Life Graph."""

    id: str
    content: str
    tags: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    importance: float = 0.0
    confidence: float = 0.0
    reasoning: str | None = None
    source_type: str | None = None
    created_at: str | None = None
    access_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Memory:
        """Create a Memory from an API response dict."""
        return cls(
            id=str(data.get("id", "")),
            content=data.get("content", ""),
            tags=data.get("tags", []),
            properties=data.get("properties", {}),
            importance=float(data.get("importance", 0.0)),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning"),
            source_type=data.get("source_type"),
            created_at=data.get("created_at"),
            access_count=int(data.get("access_count", 0)),
        )


@dataclass
class SearchResult:
    """A single search result from Life Graph."""

    content: str
    tags: list[str] = field(default_factory=list)
    score: float | None = None
    importance: float = 0.0
    properties: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> SearchResult:
        """Create a SearchResult from an API response dict."""
        return cls(
            content=data.get("content", ""),
            tags=data.get("tags", []),
            score=data.get("score"),
            importance=float(data.get("importance", 0.0)),
            properties=data.get("properties", {}),
        )


@dataclass
class IngestResult:
    """Result of a multi-modal ingestion operation."""

    memories_created: int
    minio_key: str
    transcript: str | None = None
    ocr_text: str | None = None
    text_length: int | None = None
    chunks: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> IngestResult:
        """Create an IngestResult from an API response dict."""
        return cls(
            memories_created=int(data.get("memories_created", 0)),
            minio_key=data.get("minio_key", ""),
            transcript=data.get("transcript"),
            ocr_text=data.get("ocr_text"),
            text_length=data.get("text_length"),
            chunks=data.get("chunks"),
        )


@dataclass
class GraphEntity:
    """An entity in the knowledge graph."""

    name: str
    label: str | None = None
    properties: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> GraphEntity:
        """Create a GraphEntity from an API response dict."""
        return cls(
            name=data.get("name", ""),
            label=data.get("label"),
            properties=data.get("properties", {}),
        )


@dataclass
class Stats:
    """System statistics from Life Graph."""

    memory_count: int
    intention_count: int
    gap_count: int
    session_count: int

    @classmethod
    def from_dict(cls, data: dict) -> Stats:
        """Create a Stats from an API response dict."""
        return cls(
            memory_count=int(data.get("memory_count", 0)),
            intention_count=int(data.get("intention_count", 0)),
            gap_count=int(data.get("gap_count", 0)),
            session_count=int(data.get("session_count", 0)),
        )
