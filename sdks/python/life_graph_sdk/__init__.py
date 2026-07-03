"""Life Graph SDK — Python client for the Life Graph memory system.

Quick start::

    from life_graph_sdk import LifeGraph

    brain = LifeGraph("http://localhost:8000")
    brain.remember("I prefer Python over Java")
    results = brain.search("programming language preference")

For async usage::

    from life_graph_sdk import AsyncLifeGraph

    async with AsyncLifeGraph() as brain:
        await brain.remember("Async memory")
"""

from .async_client import AsyncLifeGraph
from .client import LifeGraph
from .errors import LifeGraphError, NotFoundError, ServerError, ValidationError
from .types import GraphEntity, IngestResult, Memory, SearchResult, Stats

__all__ = [
    # Clients
    "LifeGraph",
    "AsyncLifeGraph",
    # Types
    "Memory",
    "SearchResult",
    "IngestResult",
    "GraphEntity",
    "Stats",
    # Errors
    "LifeGraphError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
]

__version__ = "0.1.0"
