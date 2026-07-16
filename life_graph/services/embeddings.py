"""Local embedding service using sentence-transformers.

Provides lazy-loaded, 768-dimensional embeddings via all-mpnet-base-v2.
Falls back gracefully (empty vectors) when sentence-transformers is not
installed, so the rest of the system keeps working.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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

    def _use_local(self) -> bool:
        """Check if local LM Studio should be used for embeddings."""
        from life_graph.config import settings
        return settings.use_local_llm and self._lm_client is not None

    # ── Public API ────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a 768-dim vector.

        Returns an empty list if sentence-transformers is unavailable
        or the model fails to load.
        """
        if self._use_local():
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside an async context, can't use run()
                    # Return empty and let async callers use embed_async
                    return []
            except RuntimeError:
                pass
            return asyncio.run(self._lm_client.embed(text))

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
        """Async embed using LM Studio. Falls back to sync embed."""
        if self._use_local():
            return await self._lm_client.embed(text)
        return self.embed(text)

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """Async batch embed using LM Studio. Falls back to sync embed_batch."""
        if self._use_local():
            return await self._lm_client.embed_batch(texts)
        return self.embed_batch(texts)

    def embed_batch(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]]:
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
            logger.info(
                "Embedding model loaded (dim=%d)", self._dimension
            )
            return self._model
        except Exception:
            logger.exception("Failed to load embedding model: %s", self._model_name)
            self._available = False
            return None
