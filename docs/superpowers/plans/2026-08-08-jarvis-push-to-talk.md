# Jarvis Push-to-Talk Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user talk to any persona on `/m/chat` — tap a mic, speak, get a spoken reply back — without typing.

**Architecture:** A new transcribe-only backend endpoint (sibling to the existing `/ingest/voice` capture route, sharing its transcription backend chain but with no MinIO/memory side effects) feeds transcribed text into `persona-chat.tsx`'s existing `send()`/`chatStream` pipeline unchanged; a completed voice-originated turn is spoken back via the browser's built-in `speechSynthesis`.

**Tech Stack:** FastAPI + existing `MultiModalService` (Groq/Cloudflare/local Whisper fallback chain), Next.js/React (`persona-chat.tsx`), browser `MediaRecorder` (via existing `useRecorder` hook), Web Speech API (`SpeechSynthesisUtterance`).

## Global Constraints

- Push-to-talk only — no wake-word/always-listening (not feasible in a PWA).
- Voice-mode recordings are never stored as memories — that stays `/ingest/voice`'s job.
- Typed messages never trigger spoken replies — only turns produced via the mic.
- No new conversation/turn model — voice produces the same `Turn` shape `persona-chat.tsx` already renders and streams.
- `send()` signature change must be backward compatible — existing typed-send call sites (button click, Enter key) keep working with zero changes.

---

### Task 1: `MultiModalService.transcribe_only()` — factor out the transcription chain

**Files:**
- Modify: `life_graph/services/multimodal.py`
- Test: `tests/unit/test_multimodal_service.py`

**Interfaces:**
- Produces: `MultiModalService.transcribe_only(audio_bytes: bytes, filename: str) -> dict[str, Any]` — returns `{"transcript": str}`. Raises `ValueError` if transcription produces no text (same message as `process_voice`'s existing check).
- Produces (internal, used by Task 2 indirectly via `process_voice`/`transcribe_only`): `MultiModalService._transcribe(audio_bytes: bytes, filename: str) -> str` — the Groq→Cloudflare→local-Whisper fallback chain, extracted from `process_voice`'s current inline logic.

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_multimodal_service.py`, near the existing `test_process_voice_*` tests:

```python
@pytest.mark.asyncio
async def test_transcribe_only_returns_text_without_storing_or_queuing(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "what's on my calendar"}}
    enqueue = _mock_enqueue(monkeypatch)

    result = await svc.transcribe_only(b"RIFFfake", "clip.webm")

    assert result == {"transcript": "what's on my calendar"}
    minio.upload.assert_not_called()
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_transcribe_only_empty_transcript_raises(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "   "}}

    with pytest.raises(ValueError):
        await svc.transcribe_only(b"x", "clip.webm")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_multimodal_service.py -k transcribe_only -v`
Expected: FAIL with `AttributeError: 'MultiModalService' object has no attribute 'transcribe_only'`

- [ ] **Step 3: Extract `_transcribe()` and add `transcribe_only()`**

In `life_graph/services/multimodal.py`, find `process_voice`'s current transcription block:

```python
        # 2. Transcribe — Groq when configured (fastest), else Cloudflare
        #    Workers AI when configured (better Tamil/English code-switching),
        #    else local faster-whisper.
        from life_graph.config import settings

        if settings.groq_api_key:
            transcript = await self._transcribe_groq(audio_bytes, filename)
        elif settings.cf_account_id and settings.cf_ai_token:
            transcript = await self._transcribe_cloudflare(audio_bytes, filename)
        else:
            transcript = await asyncio.to_thread(self._transcribe_audio, audio_bytes, filename)
        if not transcript.strip():
            raise ValueError("Transcription produced no text — nothing to remember")
```

Replace it with a call to a new shared helper:

```python
        # 2. Transcribe
        transcript = await self._transcribe(audio_bytes, filename)
```

Add the new `_transcribe` and `transcribe_only` methods directly above `process_voice` (same class, `MultiModalService`):

```python
    async def _transcribe(self, audio_bytes: bytes, filename: str) -> str:
        """Transcribe audio via the configured backend, in priority order.

        Groq when configured (fastest), else Cloudflare Workers AI (better
        Tamil/English code-switching), else local faster-whisper.

        Raises:
            ValueError: If transcription produces no text.
        """
        from life_graph.config import settings

        if settings.groq_api_key:
            transcript = await self._transcribe_groq(audio_bytes, filename)
        elif settings.cf_account_id and settings.cf_ai_token:
            transcript = await self._transcribe_cloudflare(audio_bytes, filename)
        else:
            transcript = await asyncio.to_thread(self._transcribe_audio, audio_bytes, filename)
        if not transcript.strip():
            raise ValueError("Transcription produced no text — nothing to remember")
        return transcript

    async def transcribe_only(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        """Transcribe audio without storing it or queuing memory ingestion.

        Used by live chat voice input (push-to-talk), which needs the text
        immediately and must not silently create a memory as a side effect
        — unlike :meth:`process_voice`.

        Raises:
            ValueError: If transcription produces no text.
        """
        transcript = await self._transcribe(audio_bytes, filename)
        return {"transcript": transcript}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_multimodal_service.py -v`
Expected: PASS — all tests in the file, including the two new ones and the pre-existing `test_process_voice_*` ones (confirms the refactor didn't change `process_voice`'s behavior).

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/multimodal.py tests/unit/test_multimodal_service.py
git commit -m "feat(voice-chat): extract MultiModalService.transcribe_only()"
```

---

### Task 2: `POST /api/v1/ingest/transcribe` route

**Files:**
- Modify: `life_graph/api/multimodal.py`
- Test: `tests/unit/test_multimodal_router.py`

**Interfaces:**
- Consumes: `MultiModalService.transcribe_only(audio_bytes: bytes, filename: str) -> dict[str, Any]` (Task 1).
- Produces: `POST /api/v1/ingest/transcribe` (multipart `file` upload, same `ALLOWED_AUDIO` types as `/ingest/voice`) → `200 {"data": {"transcript": str}}`, or `422` on empty transcript, or `503`/`500` on backend failure — same error-mapping pattern as the existing `/ingest/voice` route.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_multimodal_router.py`, add a `transcribe_only` method to both existing fake service classes:

```python
class _RaisingService:
    """Fake MultiModalService that always raises ValueError, like an
    empty-transcript / no-text-found failure."""

    async def process_voice(self, audio_bytes, filename, tenant_id):
        raise ValueError("Transcription produced no text — nothing to remember")

    async def transcribe_only(self, audio_bytes, filename):
        raise ValueError("Transcription produced no text — nothing to remember")
```

```python
class _QueuingService:
    """Fake MultiModalService that mimics the queued-ingestion response
    shape and records the tenant_id it was called with."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def process_voice(self, audio_bytes, filename, tenant_id):
        self.calls.append((audio_bytes, filename, tenant_id))
        return {"transcript": "hello", "ingest": "queued", "minio_key": "k/note.wav"}

    async def transcribe_only(self, audio_bytes, filename):
        self.calls.append((audio_bytes, filename))
        return {"transcript": "hello"}

    async def process_image(self, image_bytes, filename, tenant_id):
        self.calls.append((image_bytes, filename, tenant_id))
        return {"ocr_text": "hello", "ingest": "queued", "minio_key": "k/receipt.png"}

    async def process_document(self, doc_bytes, filename, tenant_id):
        self.calls.append((doc_bytes, filename, tenant_id))
        return {
            "text_length": 5,
            "chunks": 1,
            "ingest": "queued",
            "minio_key": "k/note.txt",
        }
```

(Only the two new `transcribe_only` methods are additions — the rest of both classes is shown so the diff is unambiguous; `process_image`/`process_document` are unchanged.)

Add the new tests, near the existing `test_ingest_voice_*` tests:

```python
@pytest.mark.asyncio
async def test_ingest_transcribe_value_error_maps_to_422(client: AsyncClient, monkeypatch):
    """A ValueError raised by the service surfaces as HTTP 422, not 500."""
    monkeypatch.setattr(multimodal_api, "_get_multimodal_service", lambda: _RaisingService())

    response = await client.post(
        "/api/v1/ingest/transcribe",
        files={"file": ("clip.webm", b"RIFFfakeaudiodata", "audio/webm")},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_transcribe_returns_transcript_only(client: AsyncClient, monkeypatch):
    """Unlike /ingest/voice, the response body is just {"transcript": ...} —
    no ingest/minio_key fields, since nothing was stored or queued."""
    fake_service = _QueuingService()
    monkeypatch.setattr(multimodal_api, "_get_multimodal_service", lambda: fake_service)

    response = await client.post(
        "/api/v1/ingest/transcribe",
        files={"file": ("clip.webm", b"RIFFfakeaudiodata", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"transcript": "hello"}
    assert len(fake_service.calls) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_multimodal_router.py -k transcribe -v`
Expected: FAIL with 404 (route doesn't exist yet) — `assert 404 == 422` / `assert 404 == 200`.

- [ ] **Step 3: Add the route**

In `life_graph/api/multimodal.py`, add this route (after `ingest_voice`, before `ingest_image` — grouping stays in the same order as the file's existing routes):

```python
@router.post(
    "/transcribe",
    summary="Transcribe a voice recording without storing it as a memory",
)
async def ingest_transcribe(
    file: UploadFile = File(...),
) -> dict:
    """Upload an audio clip and get back its transcript only.

    Used by live chat voice input (push-to-talk) — unlike ``/ingest/voice``,
    nothing is stored in MinIO and no memory is queued. Same accepted
    audio formats and transcription backend chain as ``/ingest/voice``.
    """
    service = _get_multimodal_service()
    audio_bytes = await file.read()
    filename = _validate_upload(file, audio_bytes, ALLOWED_AUDIO, "audio")

    try:
        result = await service.transcribe_only(audio_bytes, filename)
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
        logger.exception("Transcription failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed",
        )
    return success_response(data=result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_multimodal_router.py -v`
Expected: PASS — all tests in the file, including the pre-existing `/ingest/voice`, `/ingest/image`, `/ingest/document` tests (confirms the new route and fake-class additions didn't break anything).

- [ ] **Step 5: Commit**

```bash
git add life_graph/api/multimodal.py tests/unit/test_multimodal_router.py
git commit -m "feat(voice-chat): add POST /ingest/transcribe route"
```

---

### Task 3: `api.ingest.transcribe()` client method

**Files:**
- Modify: `dashboard/lib/api.ts`

**Interfaces:**
- Consumes: `POST /api/v1/ingest/transcribe` (Task 2).
- Produces: `api.ingest.transcribe(blob: Blob, filename: string) => Promise<any>` — resolves to `{"data": {"transcript": string}, "meta": ...}`, same response envelope shape as `api.ingest.voice`.

- [ ] **Step 1: Add the method**

In `dashboard/lib/api.ts`, find the `ingest` section:

```ts
  // ── Multi-modal ingest ──────────────────────────
  ingest: {
    voice: (blob: Blob, filename: string) => uploadRequest<any>("/ingest/voice", blob, filename),
    image: (file: File) => uploadRequest<any>("/ingest/image", file, file.name),
    document: (file: File) => uploadRequest<any>("/ingest/document", file, file.name),
  },
```

Replace with:

```ts
  // ── Multi-modal ingest ──────────────────────────
  ingest: {
    voice: (blob: Blob, filename: string) => uploadRequest<any>("/ingest/voice", blob, filename),
    transcribe: (blob: Blob, filename: string) => uploadRequest<any>("/ingest/transcribe", blob, filename),
    image: (file: File) => uploadRequest<any>("/ingest/image", file, file.name),
    document: (file: File) => uploadRequest<any>("/ingest/document", file, file.name),
  },
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new errors (this file has no existing test suite — `uploadRequest` is already exercised indirectly by `api.ingest.voice`'s existing usage in `mobile-capture.tsx`, so the new method follows an already-proven pattern).

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/api.ts
git commit -m "feat(voice-chat): add api.ingest.transcribe() client method"
```

---

### Task 4: Push-to-talk UI in `persona-chat.tsx`

**Files:**
- Modify: `dashboard/components/persona-chat.tsx`

**Interfaces:**
- Consumes: `useRecorder()` from `@/components/mobile/use-recorder` (existing, unchanged — `{ recording, seconds, error, start, stop, mimeExt }`, `stop()` resolves to `Blob | null`). `api.ingest.transcribe(blob, filename)` (Task 3).
- Produces: no new exports — this is the terminal UI task.

- [ ] **Step 1: Update imports**

Find:

```tsx
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Check, ChevronRight, Loader2, Send, Square, X } from "lucide-react";
import { api } from "@/lib/api";
import { useMobileState } from "@/components/mobile/mobile-state";
```

Replace with:

```tsx
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Check, ChevronRight, Loader2, Mic, Send, Square, X } from "lucide-react";
import { api } from "@/lib/api";
import { useMobileState } from "@/components/mobile/mobile-state";
import { useRecorder } from "@/components/mobile/use-recorder";
```

- [ ] **Step 2: Add `viaVoice` to the `Turn` type and `newTurn()`**

Find:

```tsx
type Turn = {
  user: string;
  synthesis: string;
  steps: Record<string, Step>;
  order: string[];
  done: boolean;
  errored: boolean;
};
```

Replace with:

```tsx
type Turn = {
  user: string;
  synthesis: string;
  steps: Record<string, Step>;
  order: string[];
  done: boolean;
  errored: boolean;
  viaVoice?: boolean;
};
```

Find:

```tsx
function newTurn(user: string): Turn {
  return { user, synthesis: "", steps: {}, order: [], done: false, errored: false };
}
```

Replace with:

```tsx
function newTurn(user: string, viaVoice = false): Turn {
  return { user, synthesis: "", steps: {}, order: [], done: false, errored: false, viaVoice };
}
```

- [ ] **Step 3: Add voice-related state**

Find:

```tsx
export function PersonaChat() {
  const { online } = useMobileState();
  const [persona, setPersona] = useState("jarvis");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const abort = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
```

Replace with:

```tsx
export function PersonaChat() {
  const { online } = useMobileState();
  const [persona, setPersona] = useState("jarvis");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const abort = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const recorder = useRecorder();
  const [transcribing, setTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
```

- [ ] **Step 4: Make `send()` accept an optional message + voice tag**

Find:

```tsx
  async function send() {
    const msg = input.trim();
    if (!msg || streaming || !online) return;
    setInput("");
    setTurns((ts) => [...ts, newTurn(msg)]);
```

Replace with:

```tsx
  async function send(message?: string, viaVoice = false) {
    const msg = (message ?? input).trim();
    if (!msg || streaming || !online) return;
    setInput("");
    setTurns((ts) => [...ts, newTurn(msg, viaVoice)]);
```

(Everything below this in `send()` — the `chatStream` call and its event handling — is unchanged. Existing call sites, `void send()` on Enter and on the send button's `onClick`, keep working identically since both new parameters are optional.)

- [ ] **Step 5: Cancel speech in `stop()`**

Find:

```tsx
  function stop() {
    abort.current?.abort();
    // Best-effort: also ask the backend to cancel the task so Jarvis stops
    // burning model quota. Ignore failures (task may already be done, or
    // the cancel endpoint may 409 on a task that just completed).
    const taskId = currentTaskId.current;
    if (taskId) {
      void api.kernel.tasks.cancel(taskId).catch(() => {});
    }
  }
```

Replace with:

```tsx
  function stop() {
    abort.current?.abort();
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setSpeaking(false);
    // Best-effort: also ask the backend to cancel the task so Jarvis stops
    // burning model quota. Ignore failures (task may already be done, or
    // the cancel endpoint may 409 on a task that just completed).
    const taskId = currentTaskId.current;
    if (taskId) {
      void api.kernel.tasks.cancel(taskId).catch(() => {});
    }
  }
```

- [ ] **Step 6: Add `onMicTap()` and the speak-on-done effect**

Find:

```tsx
  const lastIdx = turns.length - 1;
```

Replace with:

```tsx
  const lastIdx = turns.length - 1;
  const lastTurn = turns[lastIdx];

  const MAX_VOICE_BYTES = 20 * 1024 * 1024; // stay far below Cloudflare's 100MB

  async function onMicTap() {
    if (speaking && typeof window !== "undefined") {
      // Barge-in: interrupt a spoken reply and start listening immediately,
      // rather than making the user wait it out.
      window.speechSynthesis.cancel();
      setSpeaking(false);
    }
    if (recorder.recording) {
      const blob = await recorder.stop();
      if (!blob || blob.size === 0) return;
      if (blob.size > MAX_VOICE_BYTES) {
        setMicError("Recording too large — try a shorter clip.");
        return;
      }
      setTranscribing(true);
      setMicError(null);
      try {
        const res = (await api.ingest.transcribe(blob, `voice.${recorder.mimeExt}`)) as {
          data?: { transcript?: string };
        };
        const transcript = res?.data?.transcript?.trim();
        if (!transcript) {
          setMicError("Didn't catch that — try again.");
          return;
        }
        await send(transcript, true);
      } catch {
        setMicError("Couldn't transcribe — try again.");
      } finally {
        setTranscribing(false);
      }
    } else {
      setMicError(null);
      void recorder.start();
    }
  }

  // Speak a voice-originated turn's reply once it finishes streaming. Typed
  // turns (viaVoice falsy) never trigger this. Guarded on lastTurn?.done so
  // this only fires once per turn, when it actually completes.
  useEffect(() => {
    if (!lastTurn || !lastTurn.done || !lastTurn.viaVoice) return;
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(lastTurn.synthesis || "");
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastTurn?.done, lastTurn?.viaVoice]);
```

- [ ] **Step 7: Add the mic button and inline error**

Find:

```tsx
        {streaming ? (
          <button
            onClick={stop}
            aria-label="Stop streaming"
```

Replace with (inserting the mic button immediately before the existing streaming/send conditional):

```tsx
        <button
          onClick={() => void onMicTap()}
          disabled={!online || transcribing}
          aria-label={recorder.recording ? "Stop recording" : "Record a voice message"}
          style={{
            flexShrink: 0,
            width: "42px",
            height: "42px",
            border: "1px solid var(--border-strong)",
            borderRadius: "50%",
            background: recorder.recording ? "var(--danger-soft, #fee)" : "var(--surface)",
            color: recorder.recording ? "var(--danger, #d33)" : "var(--text)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: !online || transcribing ? "not-allowed" : "pointer",
            opacity: !online || transcribing ? 0.5 : 1,
          }}
        >
          {transcribing ? (
            <Loader2 width={16} height={16} className="animate-spin" />
          ) : recorder.recording ? (
            <Square width={15} height={15} fill="currentColor" />
          ) : (
            <Mic width={17} height={17} />
          )}
        </button>
        {streaming ? (
          <button
            onClick={stop}
            aria-label="Stop streaming"
```

Find:

```tsx
      {!online && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", textAlign: "center", margin: "6px 0 0" }}>
          You’re offline — chat needs a connection.
        </p>
      )}
```

Replace with:

```tsx
      {!online && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", textAlign: "center", margin: "6px 0 0" }}>
          You’re offline — chat needs a connection.
        </p>
      )}
      {(recorder.error || micError) && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--danger)", textAlign: "center", margin: "6px 0 0" }}>
          {recorder.error || micError}
        </p>
      )}
```

- [ ] **Step 8: Verify it builds and lints**

Run: `cd dashboard && npx tsc --noEmit && npm run lint`
Expected: no new errors or warnings introduced by this file's changes.

- [ ] **Step 9: Manual verification in a real browser**

`npm run dev` in `dashboard/`, open `/m/chat` on a device/browser with mic support (Chrome/Edge desktop or Android):

1. Tap the mic — browser prompts for mic permission (first time), button turns red/pulsing.
2. Speak a short question, tap the mic again — button shows a spinner briefly, then your words appear as a sent user turn (same bubble style as typing).
3. Jarvis's reply streams in as normal, then is read aloud once it finishes.
4. While it's speaking, tap the mic again — speech stops immediately and recording starts (barge-in).
5. Type a message instead of using the mic — confirm it does **not** get read aloud (only voice-originated turns speak).
6. Deny mic permission (or test on a browser without `MediaRecorder`) — confirm `recorder.error` shows inline and nothing crashes.
7. Tap the mic and stay silent, then tap again — confirm the "Didn't catch that" error shows and no turn is created.
8. Send a message that produces a long, multi-paragraph reply — confirm it's spoken to completion, not cut off partway (Chrome has a known ~15s ceiling on a single utterance).
9. Start a voice turn, then navigate away from `/m/chat` while the reply is still being spoken — confirm speech stops (it should not keep talking after the screen changes).
10. Repeat the full walkthrough on the actual primary target device/browser (not just desktop Chrome) — in particular test on iOS Safari if that's a supported target, since it requires a user gesture to start speech and this reply is triggered from an async callback, not a direct tap.
11. Tap the mic in the brief instant right after a reply finishes streaming but before it visibly starts speaking — confirm this reliably stops/prevents that reply's speech rather than letting it start anyway.

- [ ] **Step 10: Commit**

```bash
git add dashboard/components/persona-chat.tsx
git commit -m "feat(voice-chat): push-to-talk voice mode on /m/chat"
```

---

## Self-Review Notes

- **Spec coverage:** backend transcribe-only endpoint (Task 1+2) ✅; `api.ts` client method (Task 3) ✅; mic button + `viaVoice` tagging + speak-on-done + barge-in + Stop-cancels-speech + graceful `speechSynthesis`-unsupported degrade + all 5 error-handling rows from the spec's table (Task 4) ✅; deferred items (auto-stop-on-silence, paid TTS, continuous mode) intentionally not built, per spec's "Open items intentionally deferred" ✅.
- **Placeholder scan:** none found — every step has real code, real test bodies, real manual-verification steps.
- **Type consistency:** `transcribe_only` (service) → `ingest_transcribe` (route) → `api.ingest.transcribe` (client) → `onMicTap` (component) all agree on the `{"transcript": string}` shape. `Turn.viaVoice`, `newTurn(user, viaVoice)`, and `send(message, viaVoice)` use the same name and boolean type throughout Task 4 — no renaming drift between steps.
