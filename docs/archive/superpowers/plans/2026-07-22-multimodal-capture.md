# Multimodal Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Voice, camera, and file capture in the Life Graph mobile PWA — Tanglish voice notes transcribed by Cloudflare Workers AI (local Whisper fallback), photos OCR'd (eng+tam), PDFs extracted, originals kept in MinIO, everything landing as real, embedded, searchable memories.

**Architecture:** The backend `/api/v1/ingest/{voice,image,document}` endpoints already exist but (a) only support local Whisper and (b) call `ExtractionPipeline.extract()`, which **does not persist anything** — the counts they return are fiction. We add a pluggable Cloudflare transcription backend and reroute all three endpoints through `MemoryManager.ingest()` (the same persistence path `POST /memories/` uses: extraction → scoring → dedup → **inline embedding** → storage). The PWA capture card gains mic/camera/attach buttons that multipart-POST to these endpoints.

**Tech Stack:** FastAPI + httpx (backend), Cloudflare Workers AI `@cf/openai/whisper-large-v3-turbo`, faster-whisper (fallback), pytesseract eng+tam, pymupdf, MinIO, Next.js 16 / React 19 PWA (`MediaRecorder`, `FormData`).

## Global Constraints

- Python: async everywhere, type hints + docstrings on public APIs, ruff line-length 100, double quotes.
- Every DB-touching operation is tenant-scoped via the contextvar set by `TenantMiddleware` — never pass tenant ids manually; `MemoryManager` handles it.
- Frontend: match the existing uzhavu-token inline-style approach used in `components/mobile/*` (CSS vars like `var(--accent)`, no new CSS frameworks).
- Commits end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Work happens in the worktree at `<scratchpad>/hotfix-wt` on branch `feat/multimodal-capture` (already created, spec committed).
- On Windows: ruff binary is blocked by App Control — verify Python with `python -m py_compile <files>` + pytest instead. Global `python` (C:\Python314) has the project deps.
- Unit tests must run without Postgres (repo's `tests/conftest.py` mocks pgvector). New tests mock MinIO/EventBus/MemoryManager — no network, no DB.
- Secrets (`LIFE_GRAPH_CF_ACCOUNT_ID`, `LIFE_GRAPH_CF_AI_TOKEN`) go **only** in the VM's `.env.production`, never in git. `.env.example` documents names only.
- Deploy target: GCP VM `deploy@34.14.194.65` (key `D:\DevTools\gcloud-config\lg_deploy`). PowerShell→SSH quoting is hell: base64-encode remote bash (`$b64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash)); ssh ... "echo $b64 | base64 -d | bash"`). After any `--force-recreate` of `app`: `docker network connect web life_graph_app` or Caddy 502s. Avoid literal `rm -f` in commands (harness-blocked) — swap containers via `docker stop` + `docker rename` + `docker run`.

---

### Task 1: Cloudflare transcription backend (config + service)

**Files:**
- Modify: `life_graph/config.py` (Multi-Modal section, ~line 79)
- Modify: `life_graph/services/multimodal.py`
- Test: `tests/unit/test_multimodal_service.py` (new)

**Interfaces:**
- Consumes: existing `MultiModalService` (`__init__(minio, event_bus, pipeline)`), `settings` from `life_graph.config`.
- Produces: `MultiModalService._transcribe_cloudflare(audio_bytes: bytes, filename: str) -> str` (async); `process_voice` now selects Cloudflare when `settings.cf_account_id` and `settings.cf_ai_token` are both non-empty, else local; raises `ValueError` on empty transcript. New settings: `cf_account_id: str = ""`, `cf_ai_token: str = ""`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_multimodal_service.py`:

```python
"""Unit tests for MultiModalService: transcription backend selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.config import settings
from life_graph.services.multimodal import MultiModalService


def _service() -> tuple[MultiModalService, MagicMock, AsyncMock]:
    minio = MagicMock()
    bus = AsyncMock()
    svc = MultiModalService(minio=minio, event_bus=bus, pipeline=MagicMock())
    return svc, minio, bus


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class _FakeAsyncClient:
    last_request: dict | None = None
    body: dict = {"success": True, "result": {"text": "vanakkam hello"}}

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        _FakeAsyncClient.last_request = {"url": url, "json": json, "headers": headers}
        return _FakeResponse(_FakeAsyncClient.body)


@pytest.mark.asyncio
async def test_cloudflare_backend_used_when_configured(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "vanakkam hello"}}

    transcript = await svc._transcribe_cloudflare(b"RIFFfake", "note.webm")

    assert transcript == "vanakkam hello"
    req = _FakeAsyncClient.last_request
    assert "acct123" in req["url"]
    assert "whisper-large-v3-turbo" in req["url"]
    assert req["headers"]["Authorization"] == "Bearer tok"
    assert "audio" in req["json"]  # base64 payload


@pytest.mark.asyncio
async def test_cloudflare_error_body_raises(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": False, "errors": [{"message": "boom"}]}

    with pytest.raises(RuntimeError):
        await svc._transcribe_cloudflare(b"x", "note.webm")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_multimodal_service.py -v`
Expected: FAIL / ERROR with `AttributeError: ... has no attribute '_transcribe_cloudflare'`

- [ ] **Step 3: Add settings**

In `life_graph/config.py`, replace:

```python
    # ── Multi-Modal (Voice / Whisper) ──────────────────
    whisper_model: str = "small"
```

with:

```python
    # ── Multi-Modal (Voice / Whisper) ──────────────────
    whisper_model: str = "small"
    # Cloudflare Workers AI transcription — preferred when BOTH are set
    # (handles Tamil/English code-switching via whisper-large-v3-turbo);
    # otherwise falls back to local faster-whisper. Token needs only the
    # "Workers AI" permission.
    cf_account_id: str = ""  # Set LIFE_GRAPH_CF_ACCOUNT_ID
    cf_ai_token: str = ""  # Set LIFE_GRAPH_CF_AI_TOKEN
```

- [ ] **Step 4: Implement `_transcribe_cloudflare` and backend selection**

In `life_graph/services/multimodal.py`, add near the top constants:

```python
_CF_WHISPER_MODEL = "@cf/openai/whisper-large-v3-turbo"
```

Add this method to `MultiModalService` (after `_get_whisper_model`):

```python
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
```

In `process_voice`, replace the transcription step (step 2 comment block):

```python
        # 2. Transcribe — Cloudflare Workers AI when configured (better
        #    Tamil/English code-switching), else local faster-whisper.
        from life_graph.config import settings

        if settings.cf_account_id and settings.cf_ai_token:
            transcript = await self._transcribe_cloudflare(audio_bytes, filename)
        else:
            transcript = await asyncio.to_thread(self._transcribe_audio, audio_bytes, filename)
        if not transcript.strip():
            raise ValueError("Transcription produced no text — nothing to remember")
```

*Implementation note:* the request/response shape above (JSON `{"audio": <base64>}` → `{"result": {"text": ...}}`) matches current Workers AI docs for `whisper-large-v3-turbo`. Verify once against the live API in Task 6 before the phone test; if the live shape differs, fix here and in the fake-client test.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_multimodal_service.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add life_graph/config.py life_graph/services/multimodal.py tests/unit/test_multimodal_service.py
git commit -m "feat(multimodal): pluggable Cloudflare Workers AI transcription backend

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Persist ingested text through MemoryManager

**Files:**
- Modify: `life_graph/services/multimodal.py` (`process_voice`, `process_image`, `process_document`)
- Modify: `life_graph/api/multimodal.py` (all three endpoints)
- Test: `tests/unit/test_multimodal_service.py` (extend)

**Interfaces:**
- Consumes: `MemoryManager.ingest(text: str, context: dict | None = None, source: str | None = None, skip_dedup: bool = False, trust_tier: str | None = None) -> list[Memory]`; FastAPI dependency `get_memory_manager` from `life_graph.api.dependencies` (same as `api/memories.py` uses).
- Produces: `process_voice(audio_bytes, filename, manager) -> dict`, `process_image(image_bytes, filename, manager) -> dict`, `process_document(doc_bytes, filename, manager) -> dict` — each now takes a `MemoryManager` as third positional arg and **persists** extracted text; `memories_created` counts really-stored memories. Endpoints translate `ValueError` → HTTP 422.

**Background (why):** `ExtractionPipeline.extract()` returns facts but persists nothing — the endpoints' current `memories_created` counts are fiction. `MemoryManager.ingest` is the real path (extraction → scoring → dedup → inline embedding → storage) and reads the tenant from the request contextvar.

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/test_multimodal_service.py`)

```python
@pytest.mark.asyncio
async def test_process_voice_persists_via_manager(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "call amma tonight"}}
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]

    result = await svc.process_voice(b"RIFFfake", "note.webm", manager)

    assert result["transcript"] == "call amma tonight"
    assert result["memories_created"] == 1
    manager.ingest.assert_awaited_once_with("call amma tonight", source="voice")
    minio.upload.assert_called_once()


@pytest.mark.asyncio
async def test_process_voice_empty_transcript_raises_and_persists_nothing(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "   "}}
    manager = AsyncMock()

    with pytest.raises(ValueError):
        await svc.process_voice(b"x", "note.webm", manager)
    manager.ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_image_persists_ocr_text():
    svc, minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="Receipt total Rs 450")
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock(), MagicMock()]

    result = await svc.process_image(b"pngbytes", "receipt.png", manager)

    assert result["memories_created"] == 2
    manager.ingest.assert_awaited_once_with("Receipt total Rs 450", source="image")


@pytest.mark.asyncio
async def test_process_image_empty_ocr_raises():
    svc, _minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="")
    manager = AsyncMock()

    with pytest.raises(ValueError):
        await svc.process_image(b"pngbytes", "blank.png", manager)
    manager.ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_document_persists_each_chunk():
    svc, _minio, _bus = _service()
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]

    result = await svc.process_document(b"hello world text", "note.txt", manager)

    assert result["memories_created"] == 1
    manager.ingest.assert_awaited_once_with("hello world text", source="document")
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/unit/test_multimodal_service.py -v`
Expected: Task-1 tests pass; new tests FAIL with `TypeError: process_voice() takes 3 positional arguments but 4 were given` (and similar).

- [ ] **Step 3: Change the service methods**

In `life_graph/services/multimodal.py`:

Add the import at the top with the other project imports:

```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from life_graph.core.memory_manager import MemoryManager
```

(Replace the existing `from typing import Any` line.)

`process_voice` — new signature and persistence (full replacement of the method's signature line and steps 3–4; keep MinIO upload and transcription steps from Task 1):

```python
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
        memories = await manager.ingest(transcript, source="voice")
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
```

`process_image` — same pattern (full replacement):

```python
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

        memories = await manager.ingest(ocr_text, source="image")
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
```

`process_document` — same pattern; chunks each go through `manager.ingest` (full replacement of steps 4–5):

```python
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

        total_memories = 0
        for chunk in chunks:
            memories = await manager.ingest(chunk, source="document")
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
```

The `pipeline` constructor arg stays (unused by these paths now) to avoid breaking `_get_multimodal_service`; it is removed from use, not from the signature.

- [ ] **Step 4: Change the endpoints**

In `life_graph/api/multimodal.py`:

Change the imports block:

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from life_graph.api.dependencies import get_extraction_pipeline, get_memory_manager
from life_graph.api.responses import success_response
from life_graph.core.events import event_bus
from life_graph.core.memory_manager import MemoryManager
from life_graph.storage.minio_client import MinIOStorage
```

Replace all three endpoint functions:

```python
@router.post(
    "/voice",
    summary="Ingest a voice recording",
)
async def ingest_voice(
    file: UploadFile = File(...),
    manager: MemoryManager = Depends(get_memory_manager),
) -> dict:
    """Upload an audio file for transcription and memory extraction.

    Supported formats: WAV, MP3, OGG, M4A, FLAC, WebM.

    Returns the transcript, number of memories created, and the
    MinIO storage key.
    """
    service = _get_multimodal_service()
    audio_bytes = await file.read()
    filename = _validate_upload(file, audio_bytes, ALLOWED_AUDIO, "audio")

    try:
        result = await service.process_voice(audio_bytes, filename, manager)
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
    manager: MemoryManager = Depends(get_memory_manager),
) -> dict:
    """Upload an image for OCR text extraction and memory creation.

    Supported formats: PNG, JPEG, GIF, BMP, TIFF, WebP.

    Returns the extracted OCR text, number of memories created, and
    the MinIO storage key.
    """
    service = _get_multimodal_service()
    image_bytes = await file.read()
    filename = _validate_upload(file, image_bytes, ALLOWED_IMAGE, "image")

    try:
        result = await service.process_image(image_bytes, filename, manager)
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
    manager: MemoryManager = Depends(get_memory_manager),
) -> dict:
    """Upload a document (PDF, Markdown, or plain text) for extraction.

    The document is split into chunks and each chunk is processed
    through the extraction pipeline.

    Supported formats: PDF, Markdown (.md), plain text (.txt).

    Returns the text length, number of chunks, memories created,
    and the MinIO storage key.
    """
    service = _get_multimodal_service()
    doc_bytes = await file.read()
    filename = _validate_upload(file, doc_bytes, ALLOWED_DOCUMENT, "document")

    try:
        result = await service.process_document(doc_bytes, filename, manager)
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
```

*Implementation check:* confirm `get_memory_manager` exists in `life_graph/api/dependencies.py` (it is what `api/memories.py:35` injects). If its import path differs, match whatever `api/memories.py` imports.

- [ ] **Step 5: Run the full unit test file + compile check**

Run: `python -m pytest tests/unit/test_multimodal_service.py -v`
Expected: 7 passed

Run: `python -m py_compile life_graph/services/multimodal.py life_graph/api/multimodal.py life_graph/config.py`
Expected: no output (success)

- [ ] **Step 6: Commit**

```bash
git add life_graph/services/multimodal.py life_graph/api/multimodal.py tests/unit/test_multimodal_service.py
git commit -m "fix(multimodal): actually persist ingested text via MemoryManager

pipeline.extract() never stored anything - the memories_created counts
were fiction. Voice/image/document now flow through manager.ingest()
(extraction, scoring, dedup, inline embedding, storage), and empty
transcript/OCR raises 422 instead of silently storing nothing.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Tamil+English OCR and image dependencies

**Files:**
- Modify: `life_graph/services/multimodal.py` (`_ocr_image`)
- Modify: `Dockerfile` (two lines)

**Interfaces:**
- Consumes: nothing new.
- Produces: OCR runs with `lang="eng+tam"`; production image contains `[multimodal]` extras + tesseract binaries with English and Tamil language data.

- [ ] **Step 1: OCR language constant + usage**

In `life_graph/services/multimodal.py`, add with the other constants:

```python
_OCR_LANGUAGES = "eng+tam"
```

In `_ocr_image`, change:

```python
        text = pytesseract.image_to_string(image)
```

to:

```python
        text = pytesseract.image_to_string(image, lang=_OCR_LANGUAGES)
```

- [ ] **Step 2: Dockerfile — install extras and tesseract**

In `Dockerfile`, change the builder pip install line from:

```dockerfile
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://pypi.org/simple \
    --index-url https://download.pytorch.org/whl/cpu \
    . psycopg2-binary
```

to:

```dockerfile
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://pypi.org/simple \
    --index-url https://download.pytorch.org/whl/cpu \
    ".[multimodal]" psycopg2-binary
```

And the production-stage apt line from:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 bash && \
    rm -rf /var/lib/apt/lists/*
```

to:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 bash tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam && \
    rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 3: Verify unit tests still pass** (OCR path is mocked in tests)

Run: `python -m pytest tests/unit/test_multimodal_service.py -v`
Expected: 7 passed

- [ ] **Step 4: Update `.env.example`** — after the existing embeddings block, add:

```bash
# Multi-modal capture
# Cloudflare Workers AI transcription for Tanglish voice notes (free tier).
# Leave both empty to use local faster-whisper instead (private, weaker Tamil).
LIFE_GRAPH_CF_ACCOUNT_ID=
LIFE_GRAPH_CF_AI_TOKEN=
```

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/multimodal.py Dockerfile .env.example
git commit -m "feat(multimodal): eng+tam OCR, ship multimodal deps in the image

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Frontend multipart ingest API

**Files:**
- Modify: `dashboard/lib/api.ts`

**Interfaces:**
- Consumes: existing `API_BASE` constant and localStorage tenant/key conventions in `dashboard/lib/api.ts`.
- Produces: `api.ingest.voice(blob: Blob, filename: string)`, `api.ingest.image(file: File)`, `api.ingest.document(file: File)` — each returns the parsed JSON envelope (`{data: {transcript|ocr_text|..., memories_created, minio_key}}`). Task 5 calls these.

- [ ] **Step 1: Add the multipart helper** (below the existing `request` function in `dashboard/lib/api.ts`)

```typescript
// Multipart upload — mirrors request()'s auth headers but lets the browser
// set the multipart boundary (no explicit Content-Type).
async function uploadRequest<T>(path: string, file: Blob, filename: string): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  const form = new FormData();
  form.append("file", file, filename);
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const tenantId = localStorage.getItem("lg_tenant_id") || process.env.NEXT_PUBLIC_TENANT_ID || "default";
    const apiKey = localStorage.getItem("lg_api_key") || "";
    headers["X-Tenant-ID"] = tenantId;
    if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;
  }
  const res = await fetch(url.toString(), { method: "POST", headers, body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}
```

- [ ] **Step 2: Add the `ingest` group to the exported `api` object** (alongside `memories`, `kernel`, …)

```typescript
  // ── Multi-modal ingest ──────────────────────────
  ingest: {
    voice: (blob: Blob, filename: string) => uploadRequest<any>("/ingest/voice", blob, filename),
    image: (file: File) => uploadRequest<any>("/ingest/image", file, file.name),
    document: (file: File) => uploadRequest<any>("/ingest/document", file, file.name),
  },
```

- [ ] **Step 3: Verify it compiles**

Run (in `dashboard/`): `npm run lint`
Expected: no new errors (pre-existing warnings acceptable)

- [ ] **Step 4: Commit**

```bash
git add dashboard/lib/api.ts
git commit -m "feat(dashboard): multipart ingest API helpers (voice/image/document)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Recorder hook + three-button capture UI

**Files:**
- Create: `dashboard/components/mobile/use-recorder.ts`
- Modify: `dashboard/components/mobile/mobile-capture.tsx`

**Interfaces:**
- Consumes: `api.ingest.voice/image/document` (Task 4), `useMobileState()` (`online`), existing `Result` chip state in `mobile-capture.tsx`, uzhavu CSS vars.
- Produces: user-visible mic/camera/attach buttons; recorder hook `useRecorder(): { recording, seconds, error, start(): Promise<void>, stop(): Promise<Blob | null>, mimeExt: string }`.

- [ ] **Step 1: Create the recorder hook** — `dashboard/components/mobile/use-recorder.ts`:

```typescript
"use client";
// MediaRecorder wrapper: start() asks for the mic, stop() resolves the
// recorded Blob. Chrome/Android records audio/webm; Safari records
// audio/mp4 — mimeExt tracks the right file extension for the backend.
import { useCallback, useEffect, useRef, useState } from "react";

const MIME = typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported?.("audio/webm")
  ? { type: "audio/webm", ext: "webm" }
  : { type: "audio/mp4", ext: "m4a" };

export function useRecorder() {
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: MIME.type });
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.start();
      mediaRef.current = rec;
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setError("Microphone unavailable — allow mic access in your browser's site settings.");
    }
  }, []);

  const stop = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const rec = mediaRef.current;
      clearInterval(timerRef.current);
      setRecording(false);
      setSeconds(0);
      if (!rec || rec.state === "inactive") {
        resolve(null);
        return;
      }
      rec.onstop = () => {
        rec.stream.getTracks().forEach((t) => t.stop());
        resolve(new Blob(chunksRef.current, { type: MIME.type }));
      };
      rec.stop();
    });
  }, []);

  useEffect(() => () => clearInterval(timerRef.current), []);

  return { recording, seconds, error, start, stop, mimeExt: MIME.ext };
}
```

- [ ] **Step 2: Wire the three buttons into `mobile-capture.tsx`**

Add imports at the top:

```typescript
import { useRef } from "react";
import { Mic, Square, Camera, Paperclip, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useRecorder } from "./use-recorder";
```

(Merge `useRef` into the existing react import; keep existing imports.)

Inside `MobileCapture()`, after the existing state hooks, add:

```typescript
  const recorder = useRecorder();
  const [busy, setBusy] = useState<null | "voice" | "file">(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const MAX_FILE_BYTES = 20 * 1024 * 1024; // stay far below Cloudflare's 100MB

  const afterIngest = (label: string) => {
    setResult({ kind: "captured", routedTo: label });
    qc.invalidateQueries({ queryKey: ["memories"] });
    qc.invalidateQueries({ queryKey: ["tasks"] });
  };

  const onMicTap = async () => {
    if (recorder.recording) {
      const blob = await recorder.stop();
      if (!blob || blob.size === 0) return;
      setBusy("voice");
      try {
        await api.ingest.voice(blob, `note.${recorder.mimeExt}`);
        afterIngest("voice memory");
      } catch {
        setResult({ kind: "error" });
      } finally {
        setBusy(null);
      }
    } else {
      void recorder.start();
    }
  };

  const onFilePicked = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > MAX_FILE_BYTES) {
      setResult({ kind: "error" });
      return;
    }
    setBusy("file");
    try {
      if (f.type === "application/pdf") {
        await api.ingest.document(f);
        afterIngest("document");
      } else {
        await api.ingest.image(f);
        afterIngest("photo memory");
      }
    } catch {
      setResult({ kind: "error" });
    } finally {
      setBusy(null);
    }
  };
```

In the JSX, below the existing kind-chips row (inside the capture `<section>`), add the actions row and hidden inputs:

```tsx
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px" }}>
        <button
          type="button"
          onClick={onMicTap}
          disabled={!online || busy !== null}
          aria-label={recorder.recording ? "Stop recording" : "Record a voice note"}
          style={{
            ...chipBase,
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            ...(recorder.recording
              ? { background: "var(--danger-soft, #fee)", borderColor: "var(--danger, #d33)", color: "var(--danger, #d33)" }
              : {}),
            opacity: !online || busy !== null ? 0.5 : 1,
          }}
        >
          {recorder.recording ? <Square width={14} height={14} /> : <Mic width={14} height={14} />}
          {recorder.recording ? `Stop · ${recorder.seconds}s` : "Voice"}
        </button>

        <button
          type="button"
          onClick={() => cameraInputRef.current?.click()}
          disabled={!online || busy !== null || recorder.recording}
          aria-label="Capture a photo"
          style={{ ...chipBase, display: "inline-flex", alignItems: "center", gap: "6px", opacity: !online || busy !== null ? 0.5 : 1 }}
        >
          <Camera width={14} height={14} /> Camera
        </button>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={!online || busy !== null || recorder.recording}
          aria-label="Attach a photo or PDF"
          style={{ ...chipBase, display: "inline-flex", alignItems: "center", gap: "6px", opacity: !online || busy !== null ? 0.5 : 1 }}
        >
          <Paperclip width={14} height={14} /> Attach
        </button>

        {busy !== null && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            <Loader2 width={13} height={13} className="animate-spin" />
            {busy === "voice" ? "Transcribing…" : "Uploading…"}
          </span>
        )}
      </div>

      {!online && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", marginTop: "6px" }}>
          Voice, camera, and attachments need a connection — text capture still queues offline.
        </p>
      )}
      {recorder.error && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--danger, #d33)", marginTop: "6px" }}>{recorder.error}</p>
      )}

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => { void onFilePicked(e.target.files?.[0]); e.target.value = ""; }}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,application/pdf"
        hidden
        onChange={(e) => { void onFilePicked(e.target.files?.[0]); e.target.value = ""; }}
      />
```

Style note: `chipBase` already exists in this file — reuse it. If `var(--danger)`/`var(--danger-soft)` tokens don't exist in `tokens.css`, the inline fallbacks (`#d33`, `#fee`) apply — check `tokens.css` and use the real token names if present (the mobile board uses a `danger` tone, so tokens likely exist).

- [ ] **Step 3: Build check**

Run (in `dashboard/`): `npm run build`
Expected: compiles clean (warnings OK, no errors)

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/mobile/use-recorder.ts dashboard/components/mobile/mobile-capture.tsx
git commit -m "feat(dashboard): mic, camera, and attach capture buttons in the PWA

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Deploy to the VM

**Files:** none in-repo (VM operations + user-provided secrets)

**Interfaces:**
- Consumes: merged/pushed `feat/multimodal-capture` branch on the VM; user-provided `LIFE_GRAPH_CF_ACCOUNT_ID` + `LIFE_GRAPH_CF_AI_TOKEN`.
- Produces: running stack with MinIO, rebuilt app/worker images (multimodal deps), rebuilt dashboard, Cloudflare transcription configured.

- [ ] **Step 1: Ask the user for Cloudflare credentials.** They need (dashboard, one-time): **Account ID** (Cloudflare dashboard → any zone → right sidebar, or Workers & Pages overview) and an **API token** (My Profile → API Tokens → Create Token → "Workers AI" template → read+run). Append to `~/life-graph/.env.production` on the VM (never git):

```bash
LIFE_GRAPH_CF_ACCOUNT_ID=<from user>
LIFE_GRAPH_CF_AI_TOKEN=<from user>
```

- [ ] **Step 2: Sanity-check the Workers AI API shape with the real token** (from the VM):

```bash
python3 - <<'EOF'  # inside the app container OR via curl on the VM
# curl variant:
EOF
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/ai/run/@cf/openai/whisper-large-v3-turbo" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"audio":"'"$(base64 -w0 /tmp/tiny.m4a 2>/dev/null || echo dGVzdA==)"'"}' | head -c 400
```

Expected: JSON with `"success": true` and a `result.text` field (possibly empty for junk audio) — or a clear error whose shape tells you what to adjust in `_transcribe_cloudflare`. **If the request/response shape differs from Task 1's implementation, fix the code + fake-client test now and commit.**

- [ ] **Step 3: On the VM — fetch branch, start MinIO, rebuild backend**

```bash
cd ~/life-graph
git fetch origin feat/multimodal-capture
git checkout feat/multimodal-capture
docker compose -f docker-compose.production.yml --env-file .env.production up -d minio
docker compose -f docker-compose.production.yml --env-file .env.production build app
docker compose -f docker-compose.production.yml --env-file .env.production up -d --force-recreate --no-deps app worker
docker network connect web life_graph_app
```

Wait for `docker inspect -f '{{.State.Health.Status}}' life_graph_app` = `healthy`.

- [ ] **Step 4: Rebuild + swap the dashboard**

```bash
cd ~/life-graph/dashboard
docker build --build-arg NEXT_PUBLIC_API_URL=https://brain.raceraja001.in/api/v1 \
  --build-arg NEXT_PUBLIC_TENANT_ID=personal -t life_graph_dashboard:latest .
docker stop life_graph_dashboard
docker rename life_graph_dashboard life_graph_dashboard_prev
docker run -d --name life_graph_dashboard --restart unless-stopped --network web \
  -e NODE_ENV=production life_graph_dashboard:latest
```

- [ ] **Step 5: Smoke-check routes through Caddy**

```bash
R() { curl -sk --resolve brain.raceraja001.in:443:127.0.0.1 -o /dev/null -w "$1=%{http_code}\n" "https://brain.raceraja001.in$2"; }
R m /m
R api /api/v1/memories/
```

Expected: both 200.

---

### Task 7: End-to-end verification + PR

**Files:** none (verification + PR)

- [ ] **Step 1: Image OCR E2E** — generate a text-bearing PNG inside the app container and POST it through Caddy:

```bash
docker exec life_graph_app python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (600, 120), 'white')
d = ImageDraw.Draw(img)
d.text((10, 40), 'Electricity bill due August 30', fill='black')
img.save('/tmp/testocr.png')
"
docker cp life_graph_app:/tmp/testocr.png /tmp/testocr.png
curl -sk --resolve brain.raceraja001.in:443:127.0.0.1 -F "file=@/tmp/testocr.png;type=image/png" \
  https://brain.raceraja001.in/api/v1/ingest/image
```

Expected: `{"data": {"ocr_text": "...Electricity bill due August 30...", "memories_created": >=1, ...}}`, then `GET /api/v1/memories/` contains the text **with an embedding** (check DB: `SELECT embedding IS NOT NULL FROM memories ORDER BY created_at DESC LIMIT 1;` → `t`).

- [ ] **Step 2: Document E2E** — POST a small `.txt` (also exercises chunk path):

```bash
printf "Passport renewal needs form 49A and two photos." > /tmp/note.txt
curl -sk --resolve brain.raceraja001.in:443:127.0.0.1 -F "file=@/tmp/note.txt;type=text/plain" \
  https://brain.raceraja001.in/api/v1/ingest/document
```

Expected: `memories_created >= 1`.

- [ ] **Step 3: Voice negative-path E2E** — junk audio must NOT create a memory:

```bash
head -c 2048 /dev/urandom > /tmp/noise.webm
curl -sk --resolve brain.raceraja001.in:443:127.0.0.1 -F "file=@/tmp/noise.webm;type=audio/webm" \
  -w "\nHTTP=%{http_code}\n" https://brain.raceraja001.in/api/v1/ingest/voice
```

Expected: HTTP 422 (empty transcript) or a clean 4xx/5xx from Cloudflare rejecting junk — and memory count unchanged. (Real-voice happy path is the user's phone test.)

- [ ] **Step 4: MinIO originals sanity**

```bash
docker exec life_graph_minio ls -R /data 2>/dev/null | head -20
```

Expected: `images/` and `documents/` bucket dirs with stored objects.

- [ ] **Step 5: Phone test (user)** — record a Tanglish voice note via 🎤; snap text via 📷; confirm both appear in Memories and semantic search finds the voice note's meaning. Airplane mode disables all three buttons.

- [ ] **Step 6: Open the PR**

```bash
git push "https://x-access-token:$(gh auth token)@github.com/Raceraja001/life-graph.git" feat/multimodal-capture:feat/multimodal-capture
gh pr create --repo Raceraja001/life-graph --base master --head feat/multimodal-capture \
  --title "feat: multimodal capture — voice (Cloudflare Whisper), camera OCR, documents" \
  --body "Voice/camera/file capture per docs/superpowers/specs/2026-07-22-multimodal-capture-design.md. Fixes the pre-existing ingest bug where extracted text was never persisted."
```

User merges via GitHub UI; then sync the VM clone back onto `master` (`git checkout master && git pull`).

---

## Self-review notes

- Spec coverage: pluggable CF transcription (T1), persistence + tenant + embedding (T2), eng+tam OCR + deps + MinIO (T3, T6), three-button UI + offline + size caps + failure copy (T5), env docs (T3), deploy (T6), verification incl. negative paths (T7). Camera button uses `capture="environment"` (spec §Decisions). ✅
- Types consistent: `process_*(bytes, str, manager) -> dict`; `api.ingest.*` names match between Tasks 4 and 5. ✅
- Known judgment call: `_get_multimodal_service` singleton keeps the (now-unused) pipeline arg to minimize churn; whisper model cache preserved for local-fallback mode.
