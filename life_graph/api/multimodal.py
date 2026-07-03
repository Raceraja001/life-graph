"""Multi-modal ingest endpoints (T-077, T-078).

Provides file-upload routes for ingesting voice recordings, images,
and documents into the Life Graph. Each endpoint stores the original
in MinIO, extracts text, runs the extraction pipeline, and returns
processing results.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, status

from life_graph.api.dependencies import get_extraction_pipeline
from life_graph.core.events import event_bus
from life_graph.storage.minio_client import MinIOStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["multi-modal"])


def _get_multimodal_service():
    """Lazy-build the MultiModalService singleton."""
    from life_graph.services.multimodal import MultiModalService

    if not hasattr(_get_multimodal_service, "_instance"):
        try:
            minio = MinIOStorage()
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MinIO client (minio package) is not installed",
            )
        _get_multimodal_service._instance = MultiModalService(
            minio=minio,
            event_bus=event_bus,
            pipeline=get_extraction_pipeline(),
        )
    return _get_multimodal_service._instance


@router.post(
    "/voice",
    summary="Ingest a voice recording",
    response_model=dict,
)
async def ingest_voice(file: UploadFile = File(...)) -> dict:
    """Upload an audio file for transcription and memory extraction.

    Supported formats: WAV, MP3, OGG, M4A, FLAC, WebM.

    Returns the transcript, number of memories created, and the
    MinIO storage key.
    """
    service = _get_multimodal_service()
    audio_bytes = await file.read()

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    filename = file.filename or "recording.wav"
    try:
        result = await service.process_voice(audio_bytes, filename)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Voice processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice processing failed",
        )
    return result


@router.post(
    "/image",
    summary="Ingest an image for OCR",
    response_model=dict,
)
async def ingest_image(file: UploadFile = File(...)) -> dict:
    """Upload an image for OCR text extraction and memory creation.

    Supported formats: PNG, JPEG, GIF, BMP, TIFF, WebP.

    Returns the extracted OCR text, number of memories created, and
    the MinIO storage key.
    """
    service = _get_multimodal_service()
    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    filename = file.filename or "image.png"
    try:
        result = await service.process_image(image_bytes, filename)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Image processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image processing failed",
        )
    return result


@router.post(
    "/document",
    summary="Ingest a document",
    response_model=dict,
)
async def ingest_document(file: UploadFile = File(...)) -> dict:
    """Upload a document (PDF, Markdown, or plain text) for extraction.

    The document is split into chunks and each chunk is processed
    through the extraction pipeline.

    Supported formats: PDF, Markdown (.md), plain text (.txt).

    Returns the text length, number of chunks, memories created,
    and the MinIO storage key.
    """
    service = _get_multimodal_service()
    doc_bytes = await file.read()

    if not doc_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    filename = file.filename or "document.txt"
    try:
        result = await service.process_document(doc_bytes, filename)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Document processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed",
        )
    return result
