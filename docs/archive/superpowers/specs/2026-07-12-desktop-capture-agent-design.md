# Desktop Capture Agent — Design Spec

> **Date:** 2026-07-12
> **Status:** Approved design — ready for implementation planning
> **Author:** Life Graph (with Raja)
> **Topic:** First native capture surface for the multi-surface "memory intake" path

---

## 1. Context & Vision

Life Graph's long-term vision is a Jarvis/Friday-style ambient assistant fed by
**many capture surfaces** — Chrome extension, VS Code extension, mobile, desktop —
all pouring into the existing **Capture Spine** (`POST /api/v1/capture/`, which
handles dedup, fan-out, and extraction).

Every surface is a thin client on that one endpoint. The surfaces will be built
as **layers of capture mode** (deliberate → conversational → ambient) on a small
number of clients, not all at once.

**Architecture decision (from this brainstorm):** the primary rich surface is a
**PWA** (installable on desktop *and* mobile; carries dashboard + chat +
in-app/deliberate capture). But a PWA is sandboxed and **cannot** register a
system-wide hotkey, read another app's selection, or know the active window. The
one capability the web can't provide — *capture from any app* — needs a small
native process.

This spec covers **only that native process: the Desktop Capture Agent.** The PWA
capture surface is a separate sub-project with its own spec.

### Non-goals for this spec

- The PWA (dashboard, chat, in-app capture) — separate spec.
- Chrome / VS Code / mobile surfaces — separate specs.
- Ambient/passive observation, screenshot+OCR, voice capture — v2+.

---

## 2. Scope

### In scope (v1)

- A **system-tray agent** (Windows 11 first) that runs on login.
- **Two global hotkeys:**
  - **Popup capture** (`Ctrl+Alt+Space`): an always-on-top box pre-filled with the
    current selection; editable; optional tags; Enter saves, Esc cancels.
  - **Instant grab** (`Ctrl+Alt+C`): current selection → capture immediately with a
    "✓ Saved" toast, no box.
- **Auto-context**: active app name, window title, and capture source attached to
  every capture.
- **The shared capture-client contract** (§5): auth, payload, offline queue,
  redaction — defined here because the agent is the reference implementation the
  PWA and later surfaces reuse.
- **Offline resilience**: local queue with automatic replay.
- **Light secret redaction** before send.

### Out of scope (v1 → deferred)

- Screenshot + OCR capture.
- Voice-note capture.
- Ambient/passive observation (active-window streaming, clipboard streaming).
- Handoff to the PWA to render the popup (agent renders its own minimal popup and
  stands alone).
- Cross-platform (macOS/Linux) — keep the code portable but only ship/verify
  Windows in v1.

---

## 3. Success Criteria

v1 is done when, on Windows 11:

1. Pressing `Ctrl+Alt+Space` from **any** foreground app opens the popup pre-filled
   with the current text selection; Enter creates a capture in Life Graph within
   ~2 seconds.
2. Pressing `Ctrl+Alt+C` captures the selection instantly with a toast, no window.
3. Each capture carries `surface="desktop"` and `properties` with the source app +
   window title + source type.
4. With the backend unreachable, captures **queue locally** and **replay
   automatically** when it returns — no data loss, no duplicates.
5. Obvious secrets in captured text are redacted before leaving the machine.
6. The agent starts on login and lives in the system tray (menu: Pause, Settings,
   Quit).

---

## 4. Architecture

```
                any foreground app (VS Code, browser, PDF, terminal)
                                  │  user selects text
                        ┌─────────▼─────────┐
                        │  global hotkey    │  Ctrl+Alt+Space / Ctrl+Alt+C
                        └─────────┬─────────┘
        ┌─────────────────────────┼─────────────────────────┐
        │              Desktop Capture Agent (Python, tray)   │
        │  hotkeys → grab → [popup?] → client → queue         │
        └─────────────────────────┬─────────────────────────┘
                                   │  POST /api/v1/capture/
                                   │  Authorization: Bearer <key>
                                   │  X-Tenant-ID: <tenant>
                        ┌──────────▼───────────┐
                        │  Life Graph backend   │  Capture Spine
                        │  (FastAPI /capture)   │  dedup · fan-out · extract
                        └───────────────────────┘
```

The **same HTTP contract** is later implemented by the PWA and other surfaces
(different languages, identical payload).

---

## 5. The Shared Capture-Client Contract

This is the reusable core. Both the agent and (later) the PWA implement it.

### 5.1 Endpoint & payload

`POST {backend_url}/api/v1/capture/`

Body (`CaptureEventCreate`):

```json
{
  "surface": "desktop",
  "content": "<captured text or note>",
  "modality": "text",
  "properties": {
    "app": "Code.exe",
    "window_title": "dispatcher.py — life-graph",
    "source": "selection",              // selection | clipboard | note
    "client_capture_id": "<uuid4>",     // client-generated, for dedup on replay
    "tags": ["security", "deps"],       // optional, from popup
    "captured_at": "2026-07-12T09:03:00Z"
  }
}
```

`surface="desktop"` is a new value (existing set: orchestrator|mcp|cli|voice|tool|
watcher|git). No backend change required — `surface` is a free-form string.

### 5.2 Auth

- Header `Authorization: Bearer <SERVICE_API_KEY>` (validated by `AuthMiddleware`
  against `LIFE_GRAPH_SERVICE_API_KEYS`).
- Header `X-Tenant-ID: <tenant>` (required by `TenantMiddleware`).
- The API key is stored in the **Windows Credential Manager** via `keyring`
  (never plaintext on disk). `backend_url` and `tenant_id` live in the config file.

### 5.3 Offline queue & idempotency

- On send failure (network/timeout/5xx), the capture is written to a local
  **SQLite** queue (`%APPDATA%/LifeGraph/queue.db`).
- A background worker retries queued items on an interval and after each new
  capture; items are deleted only on a 2xx response.
- Every payload includes a client-generated `client_capture_id`. The server's
  existing content-hash dedup (10-min window per surface) absorbs fast retries;
  `client_capture_id` lets us also skip re-enqueuing an item already accepted.
  Known edge: an offline gap > the server dedup window could re-store identical
  content — accepted for v1 (rare; harmless; the spine dedups exact hashes anyway).

### 5.4 Client-side redaction

Before send, run the captured text through a redaction pass reusing the patterns
from `life_graph/core/redaction.py` (API keys, tokens, `key=secret` pairs, Bearer
headers). Since the popup shows the user exactly what will be sent, this is a
safety net rather than the primary control.

---

## 6. Components (modules under `clients/desktop/`)

Each is small, single-purpose, and independently testable.

| Module | Responsibility | Key interface | Depends on |
|---|---|---|---|
| `config.py` | Load `config.toml` + API key from keyring; validate | `load_config() -> Config` | `keyring`, `tomllib` |
| `hotkeys.py` | Register/unregister the two global hotkeys | `HotkeyManager(bindings).start()` | `pynput` |
| `grab.py` | Get current selection (simulate copy → read clipboard, restore prior clipboard), active-window app + title | `grab_selection() -> Grab`, `active_window() -> WindowInfo` | `pynput`/`pyperclip`, `pygetwindow`/win32 |
| `popup.py` | Minimal always-on-top capture window (text + tags), returns edited content or None | `show_popup(prefill) -> CaptureDraft \| None` | `tkinter` (stdlib) |
| `redact.py` | Client-side secret scrub (mirror of core patterns) | `redact(text) -> str` | stdlib `re` |
| `client.py` | Build payload, POST with auth, map errors | `async send(draft) -> Result` | `httpx` |
| `queue.py` | SQLite offline buffer + replay worker | `enqueue(payload)`, `replay_pending()` | `sqlite3` (stdlib) |
| `tray.py` | Tray icon + menu (Pause / Settings / Quit); pause disables hotkeys | `Tray(controller).run()` | `pystray`, `Pillow` |
| `app.py` | Wire everything; entry point; login autostart install | `main()` | all above |

**The reusable contract lives in `client.py` + `queue.py` + `redact.py` + the
payload schema** — documented so the PWA re-creates it in TypeScript.

---

## 7. Interaction Flows

### 7.1 Popup capture (`Ctrl+Alt+Space`)

1. Hotkey fires → `grab.grab_selection()` (save clipboard, send Ctrl+C, read
   clipboard, restore clipboard) + `grab.active_window()`.
2. `popup.show_popup(prefill=selection)` → user edits text, adds tags, Enter.
   (Esc → abort, nothing sent.)
3. `client.send(draft)` builds payload (`source="selection"` or `"note"` if the
   selection was empty and the user typed) → redact → POST.
4. Success → brief toast. Failure → `queue.enqueue(payload)` + toast "Queued
   (offline)".

### 7.2 Instant grab (`Ctrl+Alt+C`)

1. Hotkey fires → grab selection + active window.
2. If selection is empty → toast "Nothing selected", stop.
3. `client.send` directly (no popup). Success → "✓ Saved" toast; failure → queue +
   "Queued".

### 7.3 Replay

- On startup, on interval (e.g. 30s), and after each successful send, the replay
  worker drains `queue.db` in FIFO order, stopping on the first failure.

---

## 8. Configuration

`%APPDATA%/LifeGraph/config.toml`:

```toml
backend_url = "http://localhost:8000"   # VPS URL in prod
tenant_id   = "default"

[hotkeys]
popup   = "<ctrl>+<alt>+space"
instant = "<ctrl>+<alt>+c"

[behavior]
replay_interval_seconds = 30
redact = true
```

API key: stored under keyring service `"life-graph-capture"`, username =
`tenant_id`. First run: if missing, a small dialog (or documented CLI:
`python -m clients.desktop.app --set-key`) prompts once.

---

## 9. Error Handling

| Condition | Behavior |
|---|---|
| No text selected (instant) | Toast "Nothing selected"; no capture |
| Backend unreachable / 5xx / timeout | Enqueue locally; toast "Queued (offline)" |
| 401/403 (bad/missing key) | Toast "Auth failed — check settings"; do **not** enqueue (config error, not transient) |
| 422 (bad payload) | Log + drop the item (bug, not transient); never infinite-retry |
| Clipboard grab fails | Fall back to existing clipboard contents; note `source="clipboard"` |
| Hotkey registration conflict | Log which binding failed; tray shows a warning; other binding still works |

---

## 10. Testing Strategy

Pure/unit-testable (no OS, no network) is the priority:

- `redact.py` — secret patterns (reuse/mirror `test_redaction.py` cases).
- `client.py` — payload construction, header assembly, error→outcome mapping
  (with a fake transport).
- `queue.py` — enqueue/replay ordering, stop-on-failure, dedup by
  `client_capture_id`, against a temp SQLite file.
- `grab.py` — window-info parsing and selection/clipboard fallback logic
  (OS calls behind a thin seam that can be stubbed).

Manual/integration checklist (documented, run on Windows):

- Selection capture from 3+ app types (browser, VS Code, PDF viewer).
- Offline → online replay (stop backend, capture 3×, start backend, confirm 3
  land, no dupes).
- Auth failure surfaces a clear toast and does not queue.

---

## 11. Dependencies & Packaging

- Runtime deps: `pynput`, `pystray`, `Pillow`, `pyperclip` (or win32 clipboard),
  `pygetwindow` (or `pywin32`), `httpx`, `keyring`. (`tkinter`, `sqlite3`,
  `tomllib` are stdlib.)
- Packaged in the monorepo at `clients/desktop/` with its own `pyproject.toml` /
  requirements (kept separate from the backend's deps).
- v1 run: `pythonw -m clients.desktop.app`, with a login autostart shortcut the app
  can install (Startup folder / registry `Run` key). A single-file PyInstaller
  `.exe` is a v1.1 nicety, not required.

---

## 12. Open Questions / Future

- **PWA handoff (v2):** optionally, the instant-grab could deep-link into the PWA
  to show a richer editor instead of the tkinter popup — once the PWA exists.
- **v2 capture types:** screenshot+OCR, voice note (add as new `modality` values +
  a capture menu).
- **Ambient (v3):** opt-in active-window / clipboard streaming with heavy sampling
  + redaction, reusing the daily-cap discipline already in the tool-observation
  hook.
- **macOS/Linux:** the `grab`/`hotkeys`/`tray` seams are the only OS-specific parts;
  keep them behind interfaces so a second platform is an adapter, not a rewrite.

---

## 13. Relationship to Existing Code

- **Reuses:** `POST /api/v1/capture/` (unchanged), `AuthMiddleware`/`TenantMiddleware`
  contract, and the redaction *patterns* from `life_graph/core/redaction.py`
  (mirrored client-side — the agent is a separate process and won't import the
  backend package).
- **Adds:** a new `surface="desktop"` value (no schema change), and a new
  top-level `clients/desktop/` package.
- **No backend changes required for v1.**
