# Life Graph — Desktop Capture Agent

A system-tray app that captures text from any app via global hotkeys and sends it
to Life Graph's Capture Spine (`POST /api/v1/capture/`).

## Setup

1. `pip install -r clients/desktop/requirements.txt`
2. Create `%APPDATA%\LifeGraph\config.toml`:

   ```toml
   backend_url = "http://localhost:8000"
   tenant_id   = "default"
   ```
3. Store your service API key (from `LIFE_GRAPH_SERVICE_API_KEYS`):
   `python -m clients.desktop.app --set-key`
4. Run: `pythonw -m clients.desktop.app`  (or `python -m clients.desktop.app` to see logs)
5. Optional autostart: `python -m clients.desktop.app --install-autostart`

## Hotkeys

- `Ctrl+Alt+Space` — popup capture (edit + tags; Ctrl+Enter saves, Esc cancels)
- `Ctrl+Alt+C` — instant grab of the current selection

## Manual verification checklist

- [ ] Popup: select text in Chrome → `Ctrl+Alt+Space` → text pre-filled → Ctrl+Enter → capture appears in Life Graph within ~2s.
- [ ] Instant: select text in VS Code → `Ctrl+Alt+C` → "✓ Saved" toast → capture present.
- [ ] PDF viewer: repeat instant grab from a third, non-browser app.
- [ ] Context: a captured event's `properties` includes `app`, `window_title`, `source`.
- [ ] Offline: stop the backend, capture 3×, confirm "Queued (offline)"; start the backend, wait one replay interval, confirm all 3 land and there are no duplicates.
- [ ] Auth: set a wrong key → capture shows "Auth failed — check settings" and is NOT queued.
- [ ] Redaction: capture text containing `api_key=sk-...` → stored `content` shows `[REDACTED]`.
- [ ] Tray: Pause disables both hotkeys; Resume re-enables; Quit exits.
- [ ] Popup context: open the popup from Chrome, then VS Code, then a PDF — each capture's `app`/`window_title` reflects the SOURCE app, not the popup/python.
- [ ] Popup stability: open and save the popup 3× in a row from different apps — no hang or crash (the popup runs tkinter from the hotkey listener thread; watch for lockups).
