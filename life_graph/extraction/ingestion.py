"""Document processing and ingestion pipeline.

Splits documents into overlapping chunks and stores them in the
memory layer for semantic retrieval.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # MemoryStore could be imported here for type checking

logger = logging.getLogger(__name__)


def _split_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks via recursive character splitting.

    Tries to split on paragraph boundaries first, then sentences,
    then words, falling back to hard character breaks if needed.

    Args:
        text: The full document text.
        chunk_size: Target maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separators = ["\n\n", "\n", ". ", " ", ""]
    return _recursive_split(text, separators, chunk_size, overlap)


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Recursively split text trying each separator in priority order.

    Args:
        text: Text to split.
        separators: Ordered list of separators to try.
        chunk_size: Target chunk size.
        overlap: Overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if not text.strip():
        return []

    separator = separators[0]
    remaining_separators = separators[1:]

    # No separator left — hard-split by character count.
    if separator == "":
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - overlap if end < len(text) else end
        return chunks

    parts = text.split(separator)
    current_chunk: list[str] = []
    current_len = 0
    chunks = []

    for part in parts:
        part_len = len(part) + len(separator)

        if current_len + part_len > chunk_size and current_chunk:
            merged = separator.join(current_chunk)
            if len(merged) > chunk_size and remaining_separators:
                chunks.extend(_recursive_split(
                    merged, remaining_separators, chunk_size, overlap,
                ))
            else:
                chunks.append(merged)

            # Retain trailing parts for overlap.
            overlap_parts: list[str] = []
            overlap_len = 0
            for prev_part in reversed(current_chunk):
                if overlap_len + len(prev_part) > overlap:
                    break
                overlap_parts.insert(0, prev_part)
                overlap_len += len(prev_part) + len(separator)
            current_chunk = overlap_parts
            current_len = overlap_len

        current_chunk.append(part)
        current_len += part_len

    # Flush remaining content.
    if current_chunk:
        merged = separator.join(current_chunk)
        if len(merged) > chunk_size and remaining_separators:
            chunks.extend(_recursive_split(
                merged, remaining_separators, chunk_size, overlap,
            ))
        else:
            chunks.append(merged)

    return [c for c in chunks if c.strip()]


async def ingest_document(
    doc_id: str,
    content: str,
    tenant_id: str,
    memory: MemoryStore,
    chunk_size: int = 500,
    overlap: int = 50,
) -> int:
    """Process and store a document in the memory layer.

    Splits the document into overlapping chunks, generates embeddings
    via the memory provider, and stores each chunk with metadata
    linking back to the source document.

    Args:
        doc_id: Unique document identifier.
        content: Full document text.
        tenant_id: Organisation/tenant identifier.
        memory: Memory provider instance to store chunks in.
        chunk_size: Target characters per chunk.
        overlap: Overlap characters between consecutive chunks.

    Returns:
        Number of chunks successfully stored.
    """
    logger.info(
        "Ingesting document doc_id=%s tenant_id=%s (%d chars)",
        doc_id, tenant_id, len(content),
    )

    chunks = _split_text(content, chunk_size, overlap)

    if not chunks:
        logger.warning("Document %s produced no chunks", doc_id)
        return 0

    stored = 0
    for i, chunk_text in enumerate(chunks):
        metadata = {"doc_id": doc_id, "chunk_index": i}
        try:
            await memory.store(
                content=chunk_text,
                tenant_id=tenant_id,
                metadata=metadata,
            )
            stored += 1
        except Exception:
            logger.exception(
                "Failed to store chunk %d of doc %s", i, doc_id,
            )

    logger.info(
        "Ingested %d/%d chunks for doc %s",
        stored, len(chunks), doc_id,
    )
    return stored
