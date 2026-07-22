"""Multi-modal input processing: voice, images, documents (T-077, T-078).

Provides a unified service for ingesting non-text content into the
Life Graph. Each modality follows the same pattern:

1. Store the original file in MinIO.
2. Extract text (transcribe / OCR / parse).
3. Run extracted text through the extraction pipeline.
4. Emit the appropriate event.

Heavy dependencies (faster-whisper, pytesseract, pymupdf) are
imported lazily so the module can be loaded even when they are
not installed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from life_graph.core.memory_manager import MemoryManager

from life_graph.core.events import EventBus, EventType
from life_graph.extraction.pipeline import ExtractionPipeline
from life_graph.models.schemas import MemoryCreate
from life_graph.storage.minio_client import MinIOStorage

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────

_CF_WHISPER_MODEL = "@cf/openai/whisper-large-v3-turbo"
_VOICE_BUCKET = "voice-notes"
_IMAGE_BUCKET = "images"
_DOCUMENT_BUCKET = "documents"
_MAX_CHUNK_WORDS = 500
_OCR_LANGUAGES = "eng+tam"


def _content_type_for(filename: str) -> str:
    """Guess MIME type from file extension."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    return mime_map.get(ext, "application/octet-stream")


class MultiModalService:
    """Process voice, image, and document inputs into Life Graph memories.

    Args:
        minio: MinIO storage client for persisting originals.
        event_bus: Event bus for emitting processing events.
        pipeline: Extraction pipeline for turning text into memories.
    """

    def __init__(
        self,
        minio: MinIOStorage,
        event_bus: EventBus,
        pipeline: ExtractionPipeline | None = None,
    ) -> None:
        self.minio = minio
        self.event_bus = event_bus
        self.pipeline = pipeline or ExtractionPipeline()
        self._whisper_model: Any = None

    @staticmethod
    async def _ingest_or_fallback(
        manager: "MemoryManager", text: str, source: str
    ) -> list[Any]:
        """Run text through the ingestion pipeline; if nothing was extracted,
        persist the raw text directly so it isn't silently dropped.

        Mirrors the fallback in ``life_graph.api.memories.create_memory``:
        when the extraction pipeline finds no facts, store the original
        text as-is rather than lose the user's input.
        """
        memories = await manager.ingest(text, source=source)
        if not memories:
            row = await manager.store.store(MemoryCreate(content=text, source_type=source))
            memories = [row]
        return memories

    # ── Voice ─────────────────────────────────────────────────

    def _get_whisper_model(self) -> Any:
        """Lazy-load the faster-whisper model on first use."""
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ImportError(
                    "The 'faster-whisper' package is required for voice transcription. "
                    "Install it with: pip install faster-whisper"
                ) from exc

            model_name = os.environ.get("WHISPER_MODEL", None)
            if model_name is None:
                from life_graph.config import settings
                model_name = settings.whisper_model
            logger.info("Loading Whisper model: %s (this may take a moment)", model_name)
            self._whisper_model = WhisperModel(model_name, compute_type="int8")
            logger.info("Whisper model loaded: %s", model_name)
        return self._whisper_model

    async def _transcribe_cloudflare(self, audio_bytes: bytes, filename: str) -> str:
        """Transcribe audio via Cloudflare Workers AI (whisper-large-v3-turbo).

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Original filename (for logging only).

        Returns:
            The transcript text (stripped).

        Raises:
            RuntimeError: If the API reports failure.
            httpx.HTTPStatusError: On non-2xx responses.
        """
        import base64

        import httpx

        from life_graph.config import settings

        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{settings.cf_account_id}/ai/run/{_CF_WHISPER_MODEL}"
        )
        payload = {"audio": base64.b64encode(audio_bytes).decode("ascii")}
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.cf_ai_token}"},
            )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success", False):
            raise RuntimeError(f"Cloudflare AI transcription failed: {body.get('errors')}")
        text = str((body.get("result") or {}).get("text", ""))
        logger.info("Cloudflare transcribed %s: %d characters", filename, len(text))
        return text.strip()

    async def process_voice(
        self, audio_bytes: bytes, filename: str, manager: "MemoryManager"
    ) -> dict[str, Any]:
        """Transcribe audio, store the original in MinIO, persist memories.

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Original filename (used for content type and key).
            manager: Tenant-scoped memory manager that persists the transcript.

        Returns:
            Dict with ``transcript``, ``memories_created``, and ``minio_key``.

        Raises:
            ValueError: If transcription produces no text (nothing persisted).
        """
        # 1. Store original in MinIO
        key = f"{uuid.uuid4()}/{filename}"
        content_type = _content_type_for(filename)
        self.minio.upload(_VOICE_BUCKET, key, audio_bytes, content_type)

        # 2. Transcribe — Cloudflare Workers AI when configured (better
        #    Tamil/English code-switching), else local faster-whisper.
        from life_graph.config import settings

        if settings.cf_account_id and settings.cf_ai_token:
            transcript = await self._transcribe_cloudflare(audio_bytes, filename)
        else:
            transcript = await asyncio.to_thread(self._transcribe_audio, audio_bytes, filename)
        if not transcript.strip():
            raise ValueError("Transcription produced no text — nothing to remember")

        # 3. Persist through the full ingestion pipeline (extraction →
        #    scoring → dedup → embedding → storage). NOTE: pipeline.extract
        #    alone does NOT persist — that was the pre-existing bug here.
        # If nothing was extracted, fall back to storing the raw transcript
        # so the user's voice note isn't silently dropped.
        memories = await self._ingest_or_fallback(manager, transcript, "voice")
        memories_created = len(memories)

        # 4. Emit event
        await self.event_bus.emit(
            EventType.VOICE_TRANSCRIBED,
            {
                "filename": filename,
                "minio_key": key,
                "transcript_length": len(transcript),
                "memories_created": memories_created,
            },
            source="multimodal",
        )

        return {
            "transcript": transcript,
            "memories_created": memories_created,
            "minio_key": key,
        }

    def _transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Synchronous transcription helper (runs in a thread)."""
        import tempfile

        model = self._get_whisper_model()

        # faster-whisper needs a file path, so write to a temp file
        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            segments, _info = model.transcribe(tmp_path)
            transcript = " ".join(segment.text.strip() for segment in segments)
        finally:
            os.unlink(tmp_path)

        logger.info("Transcribed %s: %d characters", filename, len(transcript))
        return transcript

    # ── Image ─────────────────────────────────────────────────

    async def process_image(
        self, image_bytes: bytes, filename: str, manager: "MemoryManager"
    ) -> dict[str, Any]:
        """OCR an image, store the original in MinIO, persist memories.

        Args:
            image_bytes: Raw image file bytes.
            filename: Original filename.
            manager: Tenant-scoped memory manager that persists the OCR text.

        Returns:
            Dict with ``ocr_text``, ``memories_created``, and ``minio_key``.

        Raises:
            ValueError: If OCR finds no text (nothing persisted).
        """
        key = f"{uuid.uuid4()}/{filename}"
        content_type = _content_type_for(filename)
        self.minio.upload(_IMAGE_BUCKET, key, image_bytes, content_type)

        ocr_text = await asyncio.to_thread(self._ocr_image, image_bytes)
        if not ocr_text.strip():
            raise ValueError("No text found in the image — nothing to remember")

        # If nothing was extracted, fall back to storing the raw OCR text
        # so the captured text isn't silently dropped.
        memories = await self._ingest_or_fallback(manager, ocr_text, "image")
        memories_created = len(memories)

        await self.event_bus.emit(
            EventType.IMAGE_PROCESSED,
            {
                "filename": filename,
                "minio_key": key,
                "ocr_text_length": len(ocr_text),
                "memories_created": memories_created,
            },
            source="multimodal",
        )

        return {
            "ocr_text": ocr_text,
            "memories_created": memories_created,
            "minio_key": key,
        }

    @staticmethod
    def _ocr_image(image_bytes: bytes) -> str:
        """Synchronous OCR helper (runs in a thread)."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "The 'pytesseract' and 'Pillow' packages are required for image OCR. "
                "Install them with: pip install pytesseract Pillow"
            ) from exc

        import io

        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang=_OCR_LANGUAGES)
        return text.strip()

    # ── Document ──────────────────────────────────────────────

    async def process_document(
        self, doc_bytes: bytes, filename: str, manager: "MemoryManager"
    ) -> dict[str, Any]:
        """Extract text from a document, store the original, persist memories.

        Args:
            doc_bytes: Raw document bytes.
            filename: Original filename.
            manager: Tenant-scoped memory manager that persists each chunk.

        Returns:
            Dict with ``text_length``, ``chunks``, ``memories_created``,
            and ``minio_key``.

        Raises:
            ValueError: If no text could be extracted (nothing persisted).
        """
        key = f"{uuid.uuid4()}/{filename}"
        content_type = _content_type_for(filename)
        self.minio.upload(_DOCUMENT_BUCKET, key, doc_bytes, content_type)

        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            text = await asyncio.to_thread(self._extract_pdf_text, doc_bytes)
        else:
            text = doc_bytes.decode("utf-8", errors="replace")

        chunks = self._split_into_chunks(text, max_words=_MAX_CHUNK_WORDS)
        if not chunks:
            raise ValueError("No text found in the document — nothing to remember")

        # If a chunk yields no extracted facts, fall back to storing the
        # raw chunk text so no part of the document is silently dropped.
        total_memories = 0
        for chunk in chunks:
            memories = await self._ingest_or_fallback(manager, chunk, "document")
            total_memories += len(memories)

        await self.event_bus.emit(
            EventType.DOCUMENT_IMPORTED,
            {
                "filename": filename,
                "minio_key": key,
                "text_length": len(text),
                "chunks": len(chunks),
                "memories_created": total_memories,
            },
            source="multimodal",
        )

        return {
            "text_length": len(text),
            "chunks": len(chunks),
            "memories_created": total_memories,
            "minio_key": key,
        }

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes) -> str:
        """Extract text from a PDF using pymupdf (runs in a thread)."""
        try:
            import pymupdf  # noqa: F811
        except ImportError as exc:
            raise ImportError(
                "The 'pymupdf' package is required for PDF text extraction. "
                "Install it with: pip install pymupdf"
            ) from exc

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages).strip()

    @staticmethod
    def _split_into_chunks(text: str, max_words: int = _MAX_CHUNK_WORDS) -> list[str]:
        """Split text into chunks of at most *max_words* words.

        Splits on paragraph boundaries (double newlines) first, then
        falls back to word-level splitting for very long paragraphs.

        Args:
            text: The full text to split.
            max_words: Maximum words per chunk.

        Returns:
            List of text chunks.
        """
        text = text.strip()
        if not text:
            return []

        words = text.split()
        if len(words) <= max_words:
            return [text]

        # Try paragraph-aware splitting first
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_word_count = 0

        for para in paragraphs:
            para_words = len(para.split())
            if current_word_count + para_words > max_words and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_word_count = 0

            # Handle paragraphs longer than max_words
            if para_words > max_words:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_word_count = 0
                # Word-level splitting for very long paragraphs
                para_word_list = para.split()
                for i in range(0, len(para_word_list), max_words):
                    chunks.append(" ".join(para_word_list[i : i + max_words]))
            else:
                current_chunk.append(para)
                current_word_count += para_words

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks
