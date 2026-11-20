"""Which embedding model is current: the name stamped on ``embedding_model`` columns.

Lives in core, not services/embeddings.py, because the storage layer stamps it
on every row it writes with a vector, and storage must not import services
(audit M12). ``life_graph.services.embeddings`` re-exports it.
"""

from __future__ import annotations

from life_graph.config import settings


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
    return settings.lm_embedding_model if settings.use_local_llm else settings.embedding_model
