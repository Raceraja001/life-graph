"""Life Graph SDK — Python client for the Life Graph v1 memory system.

Quick start::

    from life_graph_sdk import LifeGraph

    brain = LifeGraph("https://api.example.com", api_key="sk-...", tenant_id="t-123")
    brain.remember("I prefer Python over Java")
    results = brain.search("programming language preference")

For async usage::

    from life_graph_sdk import AsyncLifeGraph

    async with AsyncLifeGraph("https://api.example.com", api_key="sk-...", tenant_id="t-123") as brain:
        await brain.remember("Async memory")
"""

from .async_client import AsyncLifeGraph
from .client import LifeGraph
from .errors import (
    AuthenticationError,
    LifeGraphError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .types import (
    ApiResponse,
    AskResult,
    GraphEntity,
    IngestResult,
    Intention,
    JobRun,
    KnowledgeGap,
    Memory,
    RateLimitInfo,
    RecallContext,
    SearchResult,
    Session,
    StaleBelief,
    Stats,
    TimelineChapter,
)

__all__ = [
    # Clients
    "LifeGraph",
    "AsyncLifeGraph",
    # Types
    "ApiResponse",
    "AskResult",
    "GraphEntity",
    "IngestResult",
    "Intention",
    "JobRun",
    "KnowledgeGap",
    "Memory",
    "RateLimitInfo",
    "RecallContext",
    "SearchResult",
    "Session",
    "StaleBelief",
    "Stats",
    "TimelineChapter",
    # Errors
    "AuthenticationError",
    "LifeGraphError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]

__version__ = "1.0.0"
