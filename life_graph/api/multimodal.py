"""Multi-modal ingest endpoints (T-077, T-078).

Provides file-upload routes for ingesting voice recordings, images,
and documents into the Life Graph. Each endpoint stores the original
in MinIO, extracts text, runs the extraction pipeline, and returns
processing results.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from life_graph.api.dependencies import get_extraction_pipeline
from life_graph.api.responses import success_response
from life_graph.core.events import event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.minio_client import MinIOStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["multi-modal"])

# ── Upload security constraints ──────────────────────────────

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_AUDIO = {"audio/wav", "audio/mpeg", "audio/ogg", "audio/mp4", "audio/flac", "audio/webm", "audio/x-wav"}
ALLOWED_IMAGE = {"image/png", "image/jpeg", "image/gif", "image/bmp", "image/tiff", "image/webp"}
ALLOWED_DOCUMENT = {"application/pdf", "text/plain", "text/markdown", "application/octet-stream"}


def _validate_upload(file: UploadFile, data: bytes, allowed_types: set[str], label: str) -> str:
    """Validate uploaded file size, type, and sanitize filename."""
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB.",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )
    # Content type check
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported {label} type: {content_type}. Allowed: {', '.join(sorted(allowed_types))}",
        )
    # Sanitize filename — strip path components to prevent traversal
    import os
    filename = os.path.basename(file.filename or f"upload.{label}")
    # Remove any non-alphanumeric chars except dots, hyphens, underscores
    import re
    filename = re.sub(r"[^\w.\-]", "_", filename)
    return filename


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
)
async def ingest_voice(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
) -> dict:
    """Upload an audio file for transcription; ingestion runs in the background.

    Supported formats: WAV, MP3, OGG, M4A, FLAC, WebM.

    Transcription happens inline and is returned immediately. The slow
    extraction/scoring/dedup/embedding work is queued to the ARQ worker
    (see ``ingest`` field in the response — ``"queued"``).
    """
    service = _get_multimodal_service()
    audio_bytes = await file.read()
    filename = _validate_upload(file, audio_bytes, ALLOWED_AUDIO, "audio")

    try:
        result = await service.process_voice(audio_bytes, filename, tenant_id)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Voice processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice processing failed",
        )
    return success_response(data=result)


@router.post(
    "/image",
    summary="Ingest an image for OCR",
)
async def ingest_image(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
) -> dict:
    """Upload an image for OCR; ingestion runs in the background.

    Supported formats: PNG, JPEG, GIF, BMP, TIFF, WebP.

    OCR happens inline and is returned immediately. The slow
    extraction/scoring/dedup/embedding work is queued to the ARQ worker
    (see ``ingest`` field in the response — ``"queued"``).
    """
    service = _get_multimodal_service()
    image_bytes = await file.read()
    filename = _validate_upload(file, image_bytes, ALLOWED_IMAGE, "image")

    try:
        result = await service.process_image(image_bytes, filename, tenant_id)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Image processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image processing failed",
        )
    return success_response(data=result)


@router.post(
    "/document",
    summary="Ingest a document",
)
async def ingest_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
) -> dict:
    """Upload a document (PDF, Markdown, or plain text); ingestion runs in the background.

    Text extraction and chunk-count happen inline and are returned
    immediately. The per-chunk extraction/scoring/dedup/embedding work
    is queued as a single ARQ job that loops over the chunks (see
    ``ingest`` field in the response — ``"queued"``).

    Supported formats: PDF, Markdown (.md), plain text (.txt).
    """
    service = _get_multimodal_service()
    doc_bytes = await file.read()
    filename = _validate_upload(file, doc_bytes, ALLOWED_DOCUMENT, "document")

    try:
        result = await service.process_document(doc_bytes, filename, tenant_id)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Document processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed",
        )
    return success_response(data=result)
