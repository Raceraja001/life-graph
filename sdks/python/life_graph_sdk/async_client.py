"""Asynchronous Life Graph SDK client."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import BinaryIO

import httpx

from .errors import raise_for_status
from .types import GraphEntity, IngestResult, Memory, SearchResult, Stats


class AsyncLifeGraph:
    """Asynchronous client for the Life Graph API.

    Usage::

        async with AsyncLifeGraph() as brain:
            await brain.remember("I prefer Python over Java")
            results = await brain.search("programming language preference")
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialise the async client.

        Args:
            api_url: Base URL of the Life Graph API.
            api_key: Optional Bearer token for authentication.
            timeout: Request timeout in seconds.
        """
        self.base_url = api_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        if api_key:
            self._client.headers["Authorization"] = f"Bearer {api_key}"

    # -- Context manager --------------------------------------------------

    async def __aenter__(self) -> AsyncLifeGraph:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    # -- Internal helpers -------------------------------------------------

    async def _get(self, path: str, **kwargs) -> httpx.Response:
        resp = await self._client.get(path, **kwargs)
        raise_for_status(resp)
        return resp

    async def _post(self, path: str, **kwargs) -> httpx.Response:
        resp = await self._client.post(path, **kwargs)
        raise_for_status(resp)
        return resp

    async def _delete(self, path: str, **kwargs) -> httpx.Response:
        resp = await self._client.delete(path, **kwargs)
        raise_for_status(resp)
        return resp

    @staticmethod
    def _open_file(file_path: str | Path | BinaryIO) -> tuple[str, BinaryIO, str]:
        """Return ``(filename, file_obj, content_type)`` for upload."""
        if isinstance(file_path, (str, Path)):
            p = Path(file_path)
            ct = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
            return p.name, open(p, "rb"), ct  # noqa: SIM115
        name = getattr(file_path, "name", "upload")
        return name, file_path, "application/octet-stream"

    # -- Health -----------------------------------------------------------

    async def health(self) -> dict:
        """Return the raw health-check payload from the API.

        Returns:
            A dict with health status information.
        """
        return (await self._get("/health")).json()

    async def ping(self) -> bool:
        """Check whether the API is reachable and healthy.

        Returns:
            ``True`` if the API responds with a success status.
        """
        try:
            await self._get("/health")
            return True
        except Exception:
            return False

    # -- Memory CRUD ------------------------------------------------------

    async def memories(self) -> list[Memory]:
        """List all stored memories.

        Returns:
            A list of :class:`Memory` objects.
        """
        data = (await self._get("/memories/")).json()
        return [Memory.from_dict(m) for m in data]

    async def memory(self, id: str) -> Memory:
        """Retrieve a single memory by ID.

        Args:
            id: The memory identifier.

        Returns:
            The requested :class:`Memory`.

        Raises:
            NotFoundError: If no memory with the given ID exists.
        """
        data = (await self._get(f"/memories/{id}")).json()
        return Memory.from_dict(data)

    async def delete_memory(self, id: str) -> None:
        """Delete a memory by ID.

        Args:
            id: The memory identifier.

        Raises:
            NotFoundError: If no memory with the given ID exists.
        """
        await self._delete(f"/memories/{id}")

    # -- Ingestion --------------------------------------------------------

    async def remember(self, text: str) -> list[Memory]:
        """Ingest free-form text and create memories from it.

        This is the primary way to store information in Life Graph.

        Args:
            text: The text to remember.

        Returns:
            A list of :class:`Memory` objects that were created.
        """
        resp = await self._post("/admin/ingest", json={"text": text})
        return [Memory.from_dict(m) for m in resp.json()]

    async def ingest_voice(self, file_path: str | Path | BinaryIO) -> IngestResult:
        """Ingest an audio file (voice memo, recording, etc.).

        Args:
            file_path: Path to the audio file, or an open file-like object.

        Returns:
            An :class:`IngestResult` with transcription details.
        """
        name, fobj, ct = self._open_file(file_path)
        try:
            resp = await self._post("/ingest/voice", files={"file": (name, fobj, ct)})
        finally:
            if isinstance(file_path, (str, Path)):
                fobj.close()
        return IngestResult.from_dict(resp.json())

    async def ingest_image(self, file_path: str | Path | BinaryIO) -> IngestResult:
        """Ingest an image file for OCR and analysis.

        Args:
            file_path: Path to the image file, or an open file-like object.

        Returns:
            An :class:`IngestResult` with OCR details.
        """
        name, fobj, ct = self._open_file(file_path)
        try:
            resp = await self._post("/ingest/image", files={"file": (name, fobj, ct)})
        finally:
            if isinstance(file_path, (str, Path)):
                fobj.close()
        return IngestResult.from_dict(resp.json())

    async def ingest_document(self, file_path: str | Path | BinaryIO) -> IngestResult:
        """Ingest a document file (PDF, DOCX, etc.).

        Args:
            file_path: Path to the document file, or an open file-like object.

        Returns:
            An :class:`IngestResult` with extraction details.
        """
        name, fobj, ct = self._open_file(file_path)
        try:
            resp = await self._post(
                "/ingest/document", files={"file": (name, fobj, ct)}
            )
        finally:
            if isinstance(file_path, (str, Path)):
                fobj.close()
        return IngestResult.from_dict(resp.json())

    # -- Search -----------------------------------------------------------

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Semantic search across all memories.

        Args:
            query: Natural-language search query.
            limit: Maximum number of results to return (default 10).

        Returns:
            A list of :class:`SearchResult` objects ranked by relevance.
        """
        resp = await self._post("/search/", json={"query": query, "limit": limit})
        return [SearchResult.from_dict(r) for r in resp.json()]

    # -- Graph ------------------------------------------------------------

    async def entities(self, label: str | None = None) -> list[GraphEntity]:
        """List entities in the knowledge graph.

        Args:
            label: Optional label to filter entities by (e.g. ``"Person"``).

        Returns:
            A list of :class:`GraphEntity` objects.
        """
        params = {}
        if label is not None:
            params["label"] = label
        data = (await self._get("/graph/entities", params=params)).json()
        return [GraphEntity.from_dict(e) for e in data]

    async def entity(self, name: str) -> dict:
        """Get full details for a single graph entity.

        Args:
            name: The entity name.

        Returns:
            A dict containing the entity and its relationships.

        Raises:
            NotFoundError: If the entity does not exist.
        """
        return (await self._get(f"/graph/entity/{name}")).json()

    async def graph_query(
        self, cypher: str, columns: list[str] | None = None
    ) -> list[dict]:
        """Execute a raw Cypher query against the knowledge graph.

        Args:
            cypher: A Cypher query string.
            columns: Optional list of column names to extract.

        Returns:
            A list of result dicts.
        """
        body: dict = {"query": cypher}
        if columns is not None:
            body["columns"] = columns
        return (await self._post("/graph/query", json=body)).json()

    async def graph_path(self, from_name: str, to_name: str) -> dict:
        """Find the shortest path between two entities.

        Args:
            from_name: Starting entity name.
            to_name: Ending entity name.

        Returns:
            A dict describing the path (nodes and relationships).
        """
        return (
            await self._get(
                "/graph/path",
                params={"from_name": from_name, "to_name": to_name},
            )
        ).json()

    async def graph_search(
        self,
        query: str,
        graph_filter: dict | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Hybrid search combining vector similarity with graph context.

        Args:
            query: Natural-language search query.
            graph_filter: Optional graph-level filter constraints.
            limit: Maximum number of results to return.

        Returns:
            A list of :class:`SearchResult` objects.
        """
        body: dict = {"query": query, "limit": limit}
        if graph_filter is not None:
            body["graph_filter"] = graph_filter
        resp = await self._post("/graph/search", json=body)
        return [SearchResult.from_dict(r) for r in resp.json()]

    # -- Stats ------------------------------------------------------------

    async def stats(self) -> Stats:
        """Retrieve system statistics.

        Returns:
            A :class:`Stats` object with counts of memories, intentions, etc.
        """
        return Stats.from_dict((await self._get("/admin/stats")).json())
