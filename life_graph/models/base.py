"""Declarative base and the two helpers every model module shares."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

from life_graph.config import settings

# Re-exported: the model modules import ``_utcnow`` from here for column defaults.
from life_graph.core.utils import utcnow as _utcnow  # noqa: F401

# Embedding vector dimension — single source of truth (config-driven). The
# null-and-rebuild migration alters the pgvector columns to match this.
_EMBED_DIM = settings.embedding_dimension


class Base(DeclarativeBase):
    """Declarative base for all Life Graph models."""

    pass
