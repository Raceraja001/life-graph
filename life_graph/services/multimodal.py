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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from life_graph.core.events import EventBus, EventType
from life_graph.extraction.pipeline import ExtractionPipeline
from life_graph.storage.minio_client import MinIOStorage

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────

_VOICE_BUCKET = "voice-notes"
_IMAGE_BUCKET = "images"
_DOCUMENT_BUCKET = "documents"
_MAX_CHUNK_WORDS = 500


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

    async def process_voice(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        """Transcribe audio using faster-whisper, store in MinIO, extract memories.

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Original filename (used for content type and key).

        Returns:
            Dict with ``transcript``, ``memories_created``, and ``minio_key``.
        """
        # 1. Store original in MinIO
        key = f"{uuid.uuid4()}/{filename}"
        content_type = _content_type_for(filename)
        self.minio.upload(_VOICE_BUCKET, key, audio_bytes, content_type)

        # 2. Transcribe using faster-whisper (run in thread to avoid blocking)
        transcript = await asyncio.to_thread(self._transcribe_audio, audio_bytes, filename)

        # 3. Run transcription through extraction pipeline
        result = await self.pipeline.extract(transcript)
        memories_created = len(result.facts)

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

    async def process_image(self, image_bytes: bytes, filename: str) -> dict[str, Any]:
        """OCR an image using pytesseract, store in MinIO, extract memories.

        Args:
            image_bytes: Raw image file bytes.
            filename: Original filename.

        Returns:
            Dict with ``ocr_text``, ``memories_created``, and ``minio_key``.
        """
        # 1. Store original in MinIO
        key = f"{uuid.uuid4()}/{filename}"
        content_type = _content_type_for(filename)
        self.minio.upload(_IMAGE_BUCKET, key, image_bytes, content_type)

        # 2. OCR using pytesseract (run in thread)
        ocr_text = await asyncio.to_thread(self._ocr_image, image_bytes)

        # 3. Run extracted text through extraction pipeline
        result = await self.pipeline.extract(ocr_text)
        memories_created = len(result.facts)

        # 4. Emit event
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
        text = pytesseract.image_to_string(image)
        return text.strip()

    # ── Document ──────────────────────────────────────────────

    async def process_document(self, doc_bytes: bytes, filename: str) -> dict[str, Any]:
        """Extract text from PDF/markdown/text, store in MinIO, extract memories.

        Args:
            doc_bytes: Raw document bytes.
            filename: Original filename.

        Returns:
            Dict with ``text_length``, ``chunks``, ``memories_created``,
            and ``minio_key``.
        """
        # 1. Store original in MinIO
        key = f"{uuid.uuid4()}/{filename}"
        content_type = _content_type_for(filename)
        self.minio.upload(_DOCUMENT_BUCKET, key, doc_bytes, content_type)

        # 2. Extract text
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            text = await asyncio.to_thread(self._extract_pdf_text, doc_bytes)
        else:
            # .md, .txt, and other text formats
            text = doc_bytes.decode("utf-8", errors="replace")

        # 3. Split into chunks if long
        chunks = self._split_into_chunks(text, max_words=_MAX_CHUNK_WORDS)

        # 4. Run each chunk through extraction pipeline
        total_memories = 0
        for chunk in chunks:
            result = await self.pipeline.extract(chunk)
            total_memories += len(result.facts)

        # 5. Emit event
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
