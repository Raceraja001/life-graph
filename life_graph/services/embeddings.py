"""Local embedding service using sentence-transformers.

Provides lazy-loaded, 768-dimensional embeddings via all-mpnet-base-v2.
When sentence-transformers is not installed and no remote backend is
configured, :attr:`available` is False and embedding calls return empty
vectors. That is a genuinely degraded state — semantic search stops
working — so ``main.py`` refuses to start in it unless
``LIFE_GRAPH_REQUIRE_EMBEDDING_BACKEND=false`` is set explicitly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def current_embedding_model() -> str:
    """Name stamped on (and compared against) ``embedding_model`` columns.

    The one notion of "the embedder in use now". In local-LLM mode vectors come
    from the LM client (``lm_embedding_model``); otherwise from the in-process
    sentence-transformers model (``embedding_model``). Ingest stamped the first
    while the re-embed job compared against the second, so every locally
    embedded memory looked stale and was re-embedded on every run (code review,
    2026-10-22). Everything that writes or checks ``embedding_model`` must go
    through here.
    """
    from life_graph.config import settings

    return settings.lm_embedding_model if settings.use_local_llm else settings.embedding_model


class EmbeddingService:
    """Generate text embeddings using a local sentence-transformers model.

    The model is lazy-loaded on first call to :meth:`embed` or
    :meth:`embed_batch`, keeping startup fast and memory usage low
    until embeddings are actually needed.
    """

    def __init__(self, model_name: str | None = None, lm_client: Any = None) -> None:
        from life_graph.config import settings

        self._model_name = model_name or settings.embedding_model
        self._model: Any = None
        self._dimension: int = settings.embedding_dimension
        self._available: bool = True
        self._lm_client = lm_client

        # Quick availability check without loading the model
        if not self._use_local():
            try:
                import sentence_transformers  # noqa: F401
            except ImportError:
                self._available = False
                logger.warning(
                    "sentence-transformers not installed — "
                    "EmbeddingService will return empty vectors"
                )

    @property
    def available(self) -> bool:
        """Whether an embedding backend is reachable.

        False means every :meth:`embed` call returns an empty vector, which
        disables semantic search rather than degrading it.
        """
        return self._available

    async def probe(self) -> str:
        """Live check that the configured backend actually returns a vector.

        ``available`` is decided once, at construction, and so cannot see a
        backend that was configured and has since gone down. That failure is
        silent in the worst way for a memory system: ingestion keeps reporting
        success while every vector comes back empty and semantic search quietly
        returns nothing. ``/health`` calls this so the degradation is visible.

        Returns ``"healthy"``, ``"unavailable"`` (no backend at all) or
        ``"unreachable"`` (configured, not answering).

        The in-process sentence-transformers path is reported from the static
        flag rather than probed: a real probe would load a multi-gigabyte model
        on the first health check and block the event loop while it did.
        """
        if not self._available:
            return "unavailable"
        if not self._use_local():
            return "healthy"
        try:
            vector = await self._lm_client.embed("health")
        except Exception as e:
            logger.warning("Embedding backend probe failed: %s", e)
            return "unreachable"
        return "healthy" if vector else "unreachable"

    def _use_local(self) -> bool:
        """Check if local LM Studio should be used for embeddings."""
        from life_graph.config import settings

        return settings.use_local_llm and self._lm_client is not None

    # ── Public API ────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a 768-dim vector.

        Returns an empty list if sentence-transformers is unavailable
        or the model fails to load.

        Sync callers only. In local-LLM mode the vector comes from an async
        client, which cannot be driven from inside a running event loop, so
        there this returns ``[]`` — async code must ``await`` :meth:`embed_async`
        instead. That empty return used to be silent, and consolidation's
        distilled principles and the bulk-import worker both lost their
        vectors to it (code review, 2026-10-22); it now logs a warning.
        """
        if self._use_local():
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(self._lm_client.embed(text))
            logger.warning(
                "EmbeddingService.embed() called inside a running event loop in "
                "local-LLM mode; returning no vector. Await embed_async() instead."
            )
            return []

        if not self._available:
            return []

        model = self._load_model()
        if model is None:
            return []

        try:
            vector = model.encode(text, show_progress_bar=False)
            return vector.tolist()
        except Exception:
            logger.exception("Failed to embed text")
            return []

    async def embed_async(self, text: str) -> list[float]:
        """The embed path for async code.

        Local-LLM mode awaits the LM client. Otherwise the sentence-transformers
        ``encode`` (and, on first use, the multi-gigabyte model load) runs in a
        worker thread: calling it directly blocked the whole event loop —
        every request on the server — for the length of the encode (code
        review, 2026-10-22).
        """
        if self._use_local():
            return await self._lm_client.embed(text)
        return await asyncio.to_thread(self.embed, text)

    async def embed_batch_async(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Async batch embed; off the event loop like :meth:`embed_async`."""
        if self._use_local():
            return await self._lm_client.embed_batch(texts)
        return await asyncio.to_thread(self.embed_batch, texts, batch_size)

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed a list of texts in batches.

        Returns a list of 768-dim vectors, one per input text.
        Returns a list of empty lists if the model is unavailable.
        """
        if not texts:
            return []

        if not self._available:
            return [[] for _ in texts]

        model = self._load_model()
        if model is None:
            return [[] for _ in texts]

        try:
            vectors = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,
            )
            return [v.tolist() for v in vectors]
        except Exception:
            logger.exception("Failed to embed batch of %d texts", len(texts))
            return [[] for _ in texts]

    def get_model_info(self) -> dict:
        """Return metadata about the embedding model.

        Includes model name, vector dimension, and load status.
        """
        return {
            "model_name": self._model_name,
            "dimension": self._dimension,
            "loaded": self._model is not None,
            "available": self._available,
            "using_local": self._use_local(),
        }

    # ── Private ───────────────────────────────────────────────

    def _load_model(self) -> Any:
        """Lazy-load the sentence-transformers model on first use."""
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info("Embedding model loaded (dim=%d)", self._dimension)
            return self._model
        except Exception:
            logger.exception("Failed to load embedding model: %s", self._model_name)
            self._available = False
            return None
