"""Storage protocol — the contract every memory store backend must satisfy.

Using ``typing.Protocol`` means backends don't need to inherit from a
base class.  Any object that implements these async methods is a valid
``MemoryStore``, enabling easy backend swaps (Postgres → SQLite → in-memory).
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from life_graph.models.db import Memory
from life_graph.models.schemas import MemoryCreate, MemoryUpdate


@runtime_checkable
class MemoryStore(Protocol):
    """Async protocol for memory persistence operations."""

    async def store(self, memory: MemoryCreate) -> Memory:
        """Persist a new memory and return the ORM instance."""
        ...

    async def retrieve(self, memory_id: uuid.UUID) -> Memory | None:
        """Fetch a single memory by its primary key, or ``None``."""
        ...

    async def update(self, memory_id: uuid.UUID, updates: MemoryUpdate) -> Memory:
        """Apply a partial update to an existing memory and return the updated instance.

        Raises:
            ValueError: If the memory does not exist.
        """
        ...

    async def delete(self, memory_id: uuid.UUID) -> bool:
        """Delete a memory and its session associations.

        Returns ``True`` if a row was actually deleted, ``False`` otherwise.
        """
        ...

    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[Memory]:
        """Return the closest memories by cosine distance to *embedding*.

        *filters* supports the same keys as :meth:`list_memories`.
        """
        ...

    async def list_memories(
        self,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Memory], bool]:
        """Return memories matching optional filters, paginated.

        Returns a tuple of (memories, has_more).

        Supported filter keys:
        - ``status`` (str)
        - ``tags`` (list[str]) — overlap match
        - ``properties`` (dict) — JSONB containment (``@>``)
        - ``created_after`` (datetime)
        - ``created_before`` (datetime)
        - ``min_importance`` (float)
        - ``source_type`` (str)
        """
        ...

    async def touch(self, memory_id: uuid.UUID) -> None:
        """Increment ``access_count`` and set ``last_accessed`` to now.

        Silently does nothing if the memory doesn't exist.
        """
        ...
