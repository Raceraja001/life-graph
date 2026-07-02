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

    def __init__(self, model_name: str = "all-mpnet-base-v2") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._dimension: int = 768
        self._available: bool = True

        # Quick availability check without loading the model
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            self._available = False
            logger.warning(
                "sentence-transformers not installed — "
                "EmbeddingService will return empty vectors"
            )

    # ── Public API ────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a 768-dim vector.

        Returns an empty list if sentence-transformers is unavailable
        or the model fails to load.
        """
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
