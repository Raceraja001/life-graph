# Multimodal Capture — Voice, Camera, and Files in the Mobile PWA

> **Date:** 2026-07-22
> **Status:** Approved design — ready for implementation planning
> **Scope:** `life_graph/services/multimodal.py`, `life_graph/api/multimodal.py` (small changes), `dashboard/` capture UI, Dockerfile, production compose/env. Deployed at `brain.raceraja001.in`.

## Problem

The mobile PWA captures text only. The user wants to capture the way life actually
happens: speak a thought while walking, photograph a receipt or whiteboard, upload a
bill PDF. The backend already has a full multimodal subsystem (`/api/v1/ingest/voice`,
`/ingest/image`, `/ingest/document` — T-077/T-078) built around faster-whisper,
pytesseract, and pymupdf, storing originals in MinIO — but none of it is deployed
(optional deps not installed, MinIO container never started) and the phone UI has no
way to reach it.

**Voice notes are Tamil + English mixed (Tanglish).** This is the binding constraint:
Whisper models small enough for the 8 GB VM transcribe Tanglish poorly, and models
that do it well (large-v3 class) cannot run there.

## Decisions (locked with user)

- **All three modes ship together:** voice, camera, file upload.
- **Approach A — cloud transcription, pluggable.** Voice audio is transcribed by
  **Cloudflare Workers AI** (`@cf/openai/whisper-large-v3-turbo`, free tier ~10k
  neurons/day) when Cloudflare credentials are configured; otherwise the existing
  local faster-whisper path is the fallback. One env flip returns to fully-private
  local mode. The user accepts audio transiting Cloudflare (which already fronts all
  traffic for the domain).
- **OCR and PDF extraction stay fully on-VM** (tesseract with **eng + tam** language
  packs; pymupdf).
- **Originals are kept:** deploy the MinIO container (already defined in
  `docker-compose.production.yml`; credentials already in `.env.production`).
- **Dedicated camera button** in addition to the file picker (`capture="environment"`
  hint opens the rear camera directly on phones; degrades to a picker on desktop).

## Non-goals (v1)

- No offline queueing of audio/files — mic/camera/attach are disabled offline with a
  hint; only text capture queues offline (existing behaviour).
- No in-app viewer for stored originals (MinIO keeps them; UI comes later).
- No streaming/live transcription; record → stop → transcribe.
- No image *understanding* (captioning); OCR text extraction only.

## Architecture

```
Phone PWA capture card
├─ 🎤 Mic     MediaRecorder → audio/webm ─┐
├─ 📷 Camera  <input capture=environment> ├─ multipart POST /api/v1/ingest/…
└─ 📎 Attach  <input image/*,pdf>        ─┘        (Caddy injects API key)
                                          │
                              api/multimodal.py
                                          │
                     ┌────────────────────┼──────────────────┐
                voice│               image│             document│
        TranscriptionBackend      pytesseract (eng+tam)   pymupdf
        ├─ cloudflare: Workers AI         │                  │
        │  whisper-large-v3-turbo         │                  │
        └─ local: faster-whisper          │                  │
                     └────────────────────┴──────────────────┘
                          original file → MinIO bucket
                          extracted text → memory pipeline
                          (dedup → embedding inline → searchable)
```

## Components

### 1. Pluggable transcription backend (`services/multimodal.py`)

- New settings: `cf_account_id: str = ""` (`LIFE_GRAPH_CF_ACCOUNT_ID`) and
  `cf_ai_token: str = ""` (`LIFE_GRAPH_CF_AI_TOKEN`).
- Selection: both set → Cloudflare Workers AI REST call
  (`POST https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/openai/whisper-large-v3-turbo`,
  bearer token, audio payload); else → existing `_get_whisper_model()` local path.
  *Exact request/response shape to be verified against current Workers AI docs during
  implementation.*
- Empty/whitespace transcript → raise; endpoint returns an error and **no memory is
  created** (the original audio is already in MinIO either way).

### 2. Image + document extraction (existing code, new deps)

- Dockerfile: install `.[multimodal]` extras plus apt packages `tesseract-ocr`,
  `tesseract-ocr-eng`, `tesseract-ocr-tam`. OCR configured for `eng+tam`.
- Image growth (~300–500 MB) is acceptable; faster-whisper ships as the fallback but
  downloads no model unless local mode is used.

### 3. MinIO deployment

- `docker compose … up -d minio` on the VM; buckets are created by the existing
  client code. Disk budget fine (50 GB disk, personal volumes).

### 4. Phone UI (`dashboard/components/mobile/mobile-capture.tsx` + small additions)

- Three buttons in the capture card, uzhavu design system / emerald accents:
  - **Mic:** tap → recording state (pulsing indicator + elapsed timer + Stop) →
    "Transcribing…" → existing success chip ("captured → memory"). `MediaRecorder`,
    `audio/webm` (backend already whitelists it).
  - **Camera:** `<input type="file" accept="image/*" capture="environment">` → upload
    state → success chip.
  - **Attach:** `<input type="file" accept="image/*,application/pdf">`; images →
    `/ingest/image`, PDFs → `/ingest/document`.
- `lib/api.ts` gains multipart helpers (`api.ingest.voice/image/document`); the
  existing memories/tasks query invalidation runs on success.
- Client-side size cap ~20 MB per file (Cloudflare proxy limit is 100 MB; stay far
  below). Oversize → inline error, no request.

### 5. Failure handling

| Case | Behaviour |
|---|---|
| Offline | Mic/camera/attach disabled + "needs connection" hint; text capture still queues |
| Mic permission denied | Message pointing at browser site settings |
| Transcription API error/empty | "Couldn't transcribe — try again"; no memory created |
| OCR finds no text | Same pattern: clear error, original still stored |
| Oversize file | Client-side inline error before any upload |

## Deployment / config changes (committed via PR, per project convention)

1. Dockerfile: multimodal extras + tesseract packages.
2. `.env.production` (VM only): `LIFE_GRAPH_CF_ACCOUNT_ID`, `LIFE_GRAPH_CF_AI_TOKEN`
   (user creates a Workers AI token in the Cloudflare dashboard — one-time step).
3. Compose: start `minio`.
4. `.env.example`: document the new variables.

*Implementation-time verifications:* the `/ingest/*` endpoints' tenant handling and
that their output flows through the standard memory pipeline (inline embedding) —
believed true from code reading, verify with a live curl before UI work.

## Verification

1. `curl` a small webm to `/ingest/voice` → transcript memory exists **with embedding**.
2. Photo containing mixed Tamil/English text → OCR memory contains both scripts.
3. Small PDF → extracted memory.
4. Phone E2E: record a Tanglish voice note → appears in Memories, semantically searchable;
   snap a receipt via the camera button → OCR memory.
5. Negative: airplane mode disables the three buttons; empty-audio clip creates no memory.
