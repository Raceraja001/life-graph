# Jarvis push-to-talk voice — design

## Purpose

Let the user talk to Jarvis (or any persona) on `/m/chat` instead of typing: tap a mic
button, speak, get a spoken reply back. Push-to-talk, not wake-word — the browser can't
keep a mic hot in the background, so every turn is explicitly started by the user.

## Non-goals

- No always-listening / wake-word activation (not feasible in a PWA — see prior
  discussion; would need a native app if ever pursued).
- No new conversation/turn model — voice is a second way to produce the same kind of
  turn `persona-chat.tsx` already renders and streams.
- Recordings made in voice mode are **not** saved as memories. That's the existing
  `/ingest/voice` capture flow's job; this is a live chat input, not a capture surface.

## Architecture

```
[Mic tap]        useRecorder.start()
[Mic tap again]  useRecorder.stop() -> Blob
                 -> POST /api/v1/ingest/transcribe (new)
                 -> { transcript }
                 -> send(transcript, viaVoice=true)     <- same code path as typing, plus a tag
                 -> existing chatStream turn renders + streams, unchanged
                 -> on turn.done (if turn.viaVoice) -> speechSynthesis.speak(turn.synthesis)
```

## Backend: `POST /api/v1/ingest/transcribe`

New, additive endpoint in `life_graph/api/multimodal.py`. Factored out of
`MultimodalService.process_voice()`: keeps the transcription branch (Groq
whisper-large-v3-turbo when configured, else Cloudflare Workers AI, else local
faster-whisper) unchanged, but drops the two capture-specific side effects:

- No MinIO upload of the audio.
- No `_enqueue_ingest_job` call (no memory is queued).

Returns `{"transcript": "<text>"}`. Raises the same `ValueError("Transcription produced
no text")` as `process_voice` on silence/empty audio, mapped to a 4xx by the route the
same way the existing `/ingest/voice` route does.

The existing `/ingest/voice` route and `process_voice()` are untouched — this is a
sibling code path sharing the private transcription helpers, not a modification.

## Frontend: `persona-chat.tsx`

- Add `const recorder = useRecorder()` (already exists, unchanged) plus two new local
  states: `transcribing: boolean`, `speaking: boolean`.
- Add a mic button next to the existing text input. Its visual state follows
  `recorder.recording` (pulsing + `recorder.seconds` timer) → `transcribing` (spinner) →
  idle. Text input stays usable throughout — voice is additive, not a modal takeover.
- `Turn` gains `viaVoice?: boolean`, set true only for turns produced by the voice flow.
- Mic tap while idle: `recorder.start()`.
- Mic tap while recording: `recorder.stop()` → Blob → `POST /ingest/transcribe`. On
  success, call `send(transcript, true)`. On failure (empty transcript, network error),
  show a small inline error near the mic and do not create a turn.
- **Small refactor to `send()` and `newTurn()`:**
  - `send()` today takes no arguments and reads `input` state directly. It gains two
    optional parameters: `send(message?: string, viaVoice = false)`. When `message` is
    passed, it's used in place of `input.trim()` (still clearing `input` and pushing the
    turn exactly as today). Typed sends are unaffected — the existing send button and
    Enter-to-send still call `send()` with no arguments, identical behavior to now.
  - `newTurn(user: string)` gains a second parameter: `newTurn(user: string, viaVoice =
    false)`, setting the new `Turn.viaVoice` field. `send()` passes its own `viaVoice`
    argument through to `newTurn`.
- Mic tap while `speaking`: `speechSynthesis.cancel()` (barge-in), then start recording
  immediately, per the flow above.
- `useEffect` watching the last turn: when it becomes `done` and `viaVoice`, call
  `speechSynthesis.speak(new SpeechSynthesisUtterance(turn.synthesis))`, tracking
  `speaking` via the utterance's `onstart`/`onend`. Typed turns never trigger this.
- The existing Stop button additionally calls `speechSynthesis.cancel()`.
- If `window.speechSynthesis` is undefined, the speak step is skipped silently — the
  turn still renders as text, matching the typed-message experience.
- After a spoken reply ends, nothing auto-restarts. The user taps the mic again for the
  next turn (explicit push-to-talk, no auto-continuous-listening mode).

## Error handling

| Failure | Behavior |
|---|---|
| Mic permission denied | `useRecorder`'s existing `error` state, surfaced inline near the mic button. |
| Empty/silent recording | Transcribe endpoint's `ValueError` → inline error, no turn created, mic re-enabled. |
| Transcribe network/backend failure | Inline error ("couldn't transcribe"), no turn created. |
| All transcription backends (Groq/Cloudflare/local) fail | Same as above — the fallback chain's own failure surfaces as one generic error. |
| `speechSynthesis` unsupported | Silent degrade to text-only turn — never blocks the conversation. |

None of this touches the existing text-chat error paths (`connection lost`,
`child_error`, etc.) — voice failures are caught before `send()` is ever invoked, so a
bad recording can never produce a broken turn.

## Testing

- Backend: unit test on `/ingest/transcribe` mirroring the existing `/ingest/voice`
  test's mocking pattern, specifically asserting it does **not** touch MinIO and does
  **not** enqueue an ingest job — the one behavioral difference from the sibling route.
- Frontend: `MediaRecorder`/`SpeechSynthesis` aren't meaningfully unit-testable in
  jsdom. Verification is manual, in a real browser (same approach already used for the
  existing recorder/capture flow) — mic tap records, transcript appears as a sent
  message, reply streams and is spoken, barge-in interrupts speech and starts a new
  recording, Stop silences an in-progress reply.

## Open items intentionally deferred

- Auto-stop-on-silence (vs. manual tap-to-stop) — manual for v1, per YAGNI; revisit if
  tap-to-stop feels awkward in practice.
- Paid TTS (e.g. ElevenLabs) for higher voice quality — browser TTS for v1, swappable
  later without touching the rest of this design.
- Continuous/hands-free mode (auto-relisten after each reply) — explicitly rejected for
  v1 in favor of manual push-to-talk per turn.
