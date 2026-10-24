"""Declarative base and the two helpers every model module shares."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase

from life_graph.config import settings

# Embedding vector dimension — single source of truth (config-driven). The
# null-and-rebuild migration alters the pgvector columns to match this.
_EMBED_DIM = settings.embedding_dimension


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all Life Graph models."""

    pass
