# Desktop Capture Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows system-tray agent that captures text from any app via global hotkeys and POSTs it to Life Graph's Capture Spine, with offline queuing and secret redaction.

**Architecture:** A standalone Python process (`clients/desktop/`) separate from the backend. A testable core (redaction, config, HTTP client, offline SQLite queue, grab-logic seams) is built TDD-first; OS-glue modules (popup, global hotkeys, tray, wiring) are built on top with manual verification. Everything funnels into the existing `POST /api/v1/capture/` endpoint — no backend changes.

**Tech Stack:** Python 3.11+, `httpx` (sync), `pynput` (global hotkeys), `pystray` + `Pillow` (tray), `tkinter` (stdlib popup), `keyring` (Windows Credential Manager), `pyperclip` + `pygetwindow` (clipboard/window), `sqlite3`/`tomllib` (stdlib).

## Global Constraints

- Python 3.11+ (uses stdlib `tomllib`).
- Windows 11 is the only shipped/verified platform for v1; keep OS calls behind seams but do not build/verify macOS/Linux.
- No backend changes. Capture goes to `POST {backend_url}/api/v1/capture/` with headers `Authorization: Bearer <api_key>` and `X-Tenant-ID: <tenant_id>`.
- Capture payload `surface` value is exactly `"desktop"`; `modality` is `"text"`.
- API key is read from the OS keyring (service `"life-graph-capture"`, username = `tenant_id`) — never stored in the config file or logged.
- HTTP client is **synchronous** (`httpx.Client`) — the agent is a threaded GUI/tray process with no asyncio event loop. (This refines the spec's `async send` interface.)
- Ruff line-length 100 (repo convention).
- New code lives under `clients/desktop/`; tests under `clients/desktop/tests/`. Run tests from repo root: `python -m pytest clients/desktop/tests/ -v`.

---

## File Structure

- `clients/__init__.py` — namespace package marker.
- `clients/desktop/__init__.py` — package marker.
- `clients/desktop/requirements.txt` — runtime deps (separate from backend).
- `clients/desktop/redact.py` — `redact(text)` secret scrub (mirrors `life_graph/core/redaction.py`).
- `clients/desktop/config.py` — `Config`, `HotkeyConfig`, `load_config()`, `default_config_path()`, `set_api_key()`, `ConfigError`.
- `clients/desktop/client.py` — `SendStatus`, `SendResult`, `build_payload()`, `CaptureClient`.
- `clients/desktop/queue.py` — `CaptureQueue` (SQLite enqueue/replay/dedup).
- `clients/desktop/grab.py` — `WindowInfo`, `normalize_window()`, `grab_selection()` (logic seam) + real OS wiring.
- `clients/desktop/popup.py` — `CaptureDraft`, `show_popup()` (tkinter).
- `clients/desktop/hotkeys.py` — `HotkeyManager` (pynput).
- `clients/desktop/tray.py` — `Tray` (pystray).
- `clients/desktop/app.py` — `main()`, `--set-key` CLI, autostart install, wiring.
- `clients/desktop/README.md` — setup + manual integration checklist.
- `clients/desktop/tests/` — `__init__.py`, `test_redact.py`, `test_config.py`, `test_client.py`, `test_queue.py`, `test_grab.py`.

---

### Task 1: Package scaffold + dependencies

**Files:**
- Create: `clients/__init__.py`
- Create: `clients/desktop/__init__.py`
- Create: `clients/desktop/requirements.txt`
- Create: `clients/desktop/tests/__init__.py`
- Test: `clients/desktop/tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `clients.desktop`.

- [ ] **Step 1: Write the failing test**

`clients/desktop/tests/test_smoke.py`:
```python
def test_package_imports():
    import clients.desktop  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest clients/desktop/tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clients'`

- [ ] **Step 3: Create the package files**

`clients/__init__.py`: (empty file)

`clients/desktop/__init__.py`:
```python
"""Life Graph Desktop Capture Agent."""
```

`clients/desktop/tests/__init__.py`: (empty file)

`clients/desktop/requirements.txt`:
```
httpx>=0.27
pynput>=1.7
pystray>=0.19
Pillow>=10.0
keyring>=25.0
pyperclip>=1.8
pygetwindow>=0.0.9
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest clients/desktop/tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add clients/
git commit -m "feat(desktop): scaffold capture agent package"
```

---

### Task 2: Secret redaction

**Files:**
- Create: `clients/desktop/redact.py`
- Test: `clients/desktop/tests/test_redact.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `redact(text: str) -> str` — replaces secret-looking substrings with `[REDACTED]`; returns falsy input unchanged.

- [ ] **Step 1: Write the failing test**

`clients/desktop/tests/test_redact.py`:
```python
from clients.desktop.redact import redact


def test_redacts_key_value_secret():
    assert "hunter2" not in redact("password=hunter2")
    assert "abc123" not in redact("API_KEY: abc123")


def test_keeps_key_name_hides_value():
    out = redact("api_key=sk-abcdefghijklmnop1234")
    assert "api_key" in out and "[REDACTED]" in out
    assert "sk-abcdefghijklmnop1234" not in out


def test_redacts_token_shapes():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("k AKIAIOSFODNN7EXAMPLE")
    assert "ghp_" not in redact("t ghp_0123456789abcdefghijklmnopqrstuv")


def test_plain_text_untouched():
    assert redact("git commit -m 'fix'") == "git commit -m 'fix'"


def test_empty_is_safe():
    assert redact("") == ""
    assert redact(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest clients/desktop/tests/test_redact.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clients.desktop.redact'`

- [ ] **Step 3: Write the implementation**

`clients/desktop/redact.py`:
```python
"""Client-side secret redaction — mirrors life_graph/core/redaction.py.

Kept in sync manually: the agent is a separate process and must not import
the backend package (it would drag in backend dependencies).
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_KV_SECRET = re.compile(
    r"(?i)([\w.-]*(?:api[_-]?key|secret|token|password|passwd|pwd|"
    r"access[_-]?key|auth)[\w.-]*)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER = re.compile(r"(?i)\b(bearer|authorization\s*:?)\s+\S+")
_TOKEN_SHAPES = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]{8,}\b"),
]


def redact(text: str) -> str:
    """Replace secret-looking substrings with ``[REDACTED]``."""
    if not text:
        return text
    text = _KV_SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    for pat in _TOKEN_SHAPES:
        text = pat.sub(REDACTED, text)
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest clients/desktop/tests/test_redact.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add clients/desktop/redact.py clients/desktop/tests/test_redact.py
git commit -m "feat(desktop): client-side secret redaction"
```

---

### Task 3: Config loading

**Files:**
- Create: `clients/desktop/config.py`
- Test: `clients/desktop/tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ConfigError(Exception)`
  - `HotkeyConfig(popup: str, instant: str)`
  - `Config(backend_url: str, tenant_id: str, api_key: str, hotkeys: HotkeyConfig, replay_interval_seconds: int, redact: bool)`
  - `load_config(path=None, *, keyring_module=keyring) -> Config`
  - `default_config_path() -> Path`
  - `set_api_key(tenant_id, api_key, *, keyring_module=keyring) -> None`
  - constant `KEYRING_SERVICE = "life-graph-capture"`

- [ ] **Step 1: Write the failing test**

`clients/desktop/tests/test_config.py`:
```python
import pytest

from clients.desktop.config import Config, ConfigError, load_config


class FakeKeyring:
    def __init__(self, secret=None):
        self._secret = secret
        self.set_calls = []

    def get_password(self, service, user):
        return self._secret

    def set_password(self, service, user, secret):
        self.set_calls.append((service, user, secret))


def _write(tmp_path, body):
    p = tmp_path / "config.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_minimal_config(tmp_path):
    p = _write(tmp_path, 'backend_url = "http://localhost:8000"\ntenant_id = "default"\n')
    cfg = load_config(p, keyring_module=FakeKeyring(secret="key-123"))
    assert isinstance(cfg, Config)
    assert cfg.backend_url == "http://localhost:8000"
    assert cfg.tenant_id == "default"
    assert cfg.api_key == "key-123"
    # defaults
    assert cfg.hotkeys.popup == "<ctrl>+<alt>+space"
    assert cfg.hotkeys.instant == "<ctrl>+<alt>+c"
    assert cfg.replay_interval_seconds == 30
    assert cfg.redact is True


def test_overrides_hotkeys_and_behavior(tmp_path):
    p = _write(
        tmp_path,
        'backend_url = "http://x"\ntenant_id = "t"\n'
        '[hotkeys]\npopup = "<ctrl>+1"\ninstant = "<ctrl>+2"\n'
        '[behavior]\nreplay_interval_seconds = 5\nredact = false\n',
    )
    cfg = load_config(p, keyring_module=FakeKeyring(secret="k"))
    assert cfg.hotkeys.popup == "<ctrl>+1"
    assert cfg.replay_interval_seconds == 5
    assert cfg.redact is False


def test_missing_api_key_raises(tmp_path):
    p = _write(tmp_path, 'backend_url = "http://x"\ntenant_id = "t"\n')
    with pytest.raises(ConfigError):
        load_config(p, keyring_module=FakeKeyring(secret=None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest clients/desktop/tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clients.desktop.config'`

- [ ] **Step 3: Write the implementation**

`clients/desktop/config.py`:
```python
"""Config loading for the desktop capture agent.

Non-secret settings live in a TOML file; the API key is read from the OS
keyring so it never touches disk in plaintext.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import keyring

KEYRING_SERVICE = "life-graph-capture"


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class HotkeyConfig:
    popup: str = "<ctrl>+<alt>+space"
    instant: str = "<ctrl>+<alt>+c"


@dataclass
class Config:
    backend_url: str
    tenant_id: str
    api_key: str
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    replay_interval_seconds: int = 30
    redact: bool = True


def default_config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "LifeGraph" / "config.toml"


def set_api_key(tenant_id: str, api_key: str, *, keyring_module=keyring) -> None:
    keyring_module.set_password(KEYRING_SERVICE, tenant_id, api_key)


def load_config(path=None, *, keyring_module=keyring) -> Config:
    path = Path(path) if path else default_config_path()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e

    try:
        backend_url = data["backend_url"]
        tenant_id = data["tenant_id"]
    except KeyError as e:
        raise ConfigError(f"Missing required config key: {e}") from e

    api_key = keyring_module.get_password(KEYRING_SERVICE, tenant_id)
    if not api_key:
        raise ConfigError(
            f"No API key in keyring for tenant {tenant_id!r}. "
            f"Run: python -m clients.desktop.app --set-key"
        )

    hk = data.get("hotkeys", {})
    beh = data.get("behavior", {})
    return Config(
        backend_url=backend_url,
        tenant_id=tenant_id,
        api_key=api_key,
        hotkeys=HotkeyConfig(
            popup=hk.get("popup", "<ctrl>+<alt>+space"),
            instant=hk.get("instant", "<ctrl>+<alt>+c"),
        ),
        replay_interval_seconds=beh.get("replay_interval_seconds", 30),
        redact=beh.get("redact", True),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest clients/desktop/tests/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add clients/desktop/config.py clients/desktop/tests/test_config.py
git commit -m "feat(desktop): config loading with keyring-backed API key"
```

---

### Task 4: HTTP capture client

**Files:**
- Create: `clients/desktop/client.py`
- Test: `clients/desktop/tests/test_client.py`

**Interfaces:**
- Consumes: `redact()` from `clients.desktop.redact`.
- Produces:
  - `SendStatus` (Enum: `SENT`, `TRANSIENT`, `AUTH`, `BAD`)
  - `SendResult(status: SendStatus, detail: str = "")`
  - `build_payload(*, content, app, window_title, source, tags=None, client_capture_id=None, captured_at=None, do_redact=True) -> dict`
  - `CaptureClient(base_url, api_key, tenant_id, *, transport=None, timeout=5.0)` with `.send(payload: dict) -> SendResult`

- [ ] **Step 1: Write the failing test**

`clients/desktop/tests/test_client.py`:
```python
import httpx

from clients.desktop.client import (
    CaptureClient,
    SendStatus,
    build_payload,
)


def test_build_payload_shape():
    p = build_payload(
        content="urllib3 CVE",
        app="Code.exe",
        window_title="dispatcher.py",
        source="selection",
        tags=["security"],
        client_capture_id="cid-1",
        captured_at="2026-07-12T00:00:00Z",
    )
    assert p["surface"] == "desktop"
    assert p["modality"] == "text"
    assert p["content"] == "urllib3 CVE"
    assert p["properties"]["app"] == "Code.exe"
    assert p["properties"]["source"] == "selection"
    assert p["properties"]["client_capture_id"] == "cid-1"
    assert p["properties"]["tags"] == ["security"]


def test_build_payload_redacts_content():
    p = build_payload(
        content="token ghp_0123456789abcdefghij0123456789",
        app="x", window_title="y", source="note",
    )
    assert "ghp_0123456789abcdefghij0123456789" not in p["content"]


def test_build_payload_generates_id_when_absent():
    p = build_payload(content="x", app="a", window_title="b", source="note")
    assert p["properties"]["client_capture_id"]


def _client_with(handler):
    transport = httpx.MockTransport(handler)
    return CaptureClient("http://x", "key", "tenant", transport=transport)


def test_send_success():
    c = _client_with(lambda req: httpx.Response(201, json={"ok": True}))
    assert c.send({"surface": "desktop"}).status == SendStatus.SENT


def test_send_auth_failure():
    c = _client_with(lambda req: httpx.Response(401, text="bad key"))
    assert c.send({}).status == SendStatus.AUTH


def test_send_server_error_is_transient():
    c = _client_with(lambda req: httpx.Response(503, text="down"))
    assert c.send({}).status == SendStatus.TRANSIENT


def test_send_bad_request_is_bad():
    c = _client_with(lambda req: httpx.Response(422, text="nope"))
    assert c.send({}).status == SendStatus.BAD


def test_send_network_error_is_transient():
    def boom(req):
        raise httpx.ConnectError("refused")
    assert _client_with(boom).send({}).status == SendStatus.TRANSIENT


def test_send_sets_auth_and_tenant_headers():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers.get("authorization")
        seen["tenant"] = req.headers.get("x-tenant-id")
        return httpx.Response(201)

    _client_with(handler).send({"surface": "desktop"})
    assert seen["auth"] == "Bearer key"
    assert seen["tenant"] == "tenant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest clients/desktop/tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clients.desktop.client'`

- [ ] **Step 3: Write the implementation**

`clients/desktop/client.py`:
```python
"""Synchronous HTTP client for the Capture Spine + payload builder."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx

from clients.desktop.redact import redact


class SendStatus(str, Enum):
    SENT = "sent"            # 2xx — delete from queue
    TRANSIENT = "transient"  # network / timeout / 5xx — enqueue / stop replay
    AUTH = "auth"            # 401/403 — config error, do not enqueue, stop replay
    BAD = "bad"              # other 4xx (e.g. 422) — drop, do not retry


@dataclass
class SendResult:
    status: SendStatus
    detail: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_payload(
    *,
    content: str,
    app: str,
    window_title: str,
    source: str,
    tags=None,
    client_capture_id: str | None = None,
    captured_at: str | None = None,
    do_redact: bool = True,
) -> dict:
    """Assemble the /capture payload. Redacts content unless disabled."""
    text = redact(content) if do_redact else content
    return {
        "surface": "desktop",
        "content": text,
        "modality": "text",
        "properties": {
            "app": app,
            "window_title": window_title,
            "source": source,
            "client_capture_id": client_capture_id or str(uuid.uuid4()),
            "tags": list(tags or []),
            "captured_at": captured_at or _now_iso(),
        },
    }


class CaptureClient:
    """Posts capture payloads to POST {base_url}/api/v1/capture/."""

    def __init__(self, base_url, api_key, tenant_id, *, transport=None, timeout=5.0):
        self._url = base_url.rstrip("/") + "/api/v1/capture/"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(headers=headers, timeout=timeout, transport=transport)

    def send(self, payload: dict) -> SendResult:
        try:
            resp = self._client.post(self._url, json=payload)
        except httpx.RequestError as e:
            return SendResult(SendStatus.TRANSIENT, str(e))
        if resp.status_code < 300:
            return SendResult(SendStatus.SENT)
        if resp.status_code in (401, 403):
            return SendResult(SendStatus.AUTH, resp.text[:200])
        if resp.status_code >= 500:
            return SendResult(SendStatus.TRANSIENT, f"server {resp.status_code}")
        return SendResult(SendStatus.BAD, f"{resp.status_code}: {resp.text[:200]}")

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest clients/desktop/tests/test_client.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add clients/desktop/client.py clients/desktop/tests/test_client.py
git commit -m "feat(desktop): sync capture client + payload builder"
```

---

### Task 5: Offline queue

**Files:**
- Create: `clients/desktop/queue.py`
- Test: `clients/desktop/tests/test_queue.py`

**Interfaces:**
- Consumes: `SendStatus`, `SendResult` from `clients.desktop.client`.
- Produces:
  - `CaptureQueue(db_path)` with `.enqueue(payload: dict) -> None`, `.pending_count() -> int`, `.replay(send_fn) -> int` where `send_fn(payload: dict) -> SendResult`.
  - Dedup: enqueuing a payload whose `properties.client_capture_id` is already pending is a no-op.
  - Replay: FIFO; on `SENT`/`BAD` delete the row (and count `SENT`); on `TRANSIENT`/`AUTH` stop and keep the row. Returns number successfully sent.

- [ ] **Step 1: Write the failing test**

`clients/desktop/tests/test_queue.py`:
```python
from clients.desktop.client import SendResult, SendStatus
from clients.desktop.queue import CaptureQueue


def _payload(cid, content="x"):
    return {"surface": "desktop", "content": content,
            "properties": {"client_capture_id": cid}}


def test_enqueue_and_count(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    assert q.pending_count() == 2


def test_enqueue_dedupes_by_capture_id(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("a"))
    assert q.pending_count() == 1


def test_replay_sends_all_on_success(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    sent = q.replay(lambda p: SendResult(SendStatus.SENT))
    assert sent == 2
    assert q.pending_count() == 0


def test_replay_stops_on_transient_and_keeps_rest(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    calls = []

    def send_fn(p):
        calls.append(p["properties"]["client_capture_id"])
        return SendResult(SendStatus.TRANSIENT)

    sent = q.replay(send_fn)
    assert sent == 0
    assert calls == ["a"]           # stopped after first failure
    assert q.pending_count() == 2   # nothing removed


def test_replay_drops_bad_items(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    sent = q.replay(lambda p: SendResult(SendStatus.BAD))
    assert sent == 0
    assert q.pending_count() == 0   # both dropped, not retried forever
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest clients/desktop/tests/test_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clients.desktop.queue'`

- [ ] **Step 3: Write the implementation**

`clients/desktop/queue.py`:
```python
"""SQLite-backed offline queue for captures that failed to send."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from clients.desktop.client import SendStatus


class CaptureQueue:
    def __init__(self, db_path) -> None:
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS pending (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_capture_id TEXT UNIQUE,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    def enqueue(self, payload: dict) -> None:
        cid = payload["properties"]["client_capture_id"]
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO pending(client_capture_id, payload, created_at) "
                "VALUES (?, ?, ?)",
                (cid, json.dumps(payload), time.time()),
            )

    def pending_count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM pending").fetchone()[0]

    def replay(self, send_fn) -> int:
        """Drain FIFO. Returns count SENT. Stops on TRANSIENT/AUTH."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, payload FROM pending ORDER BY id ASC"
            ).fetchall()

        sent = 0
        for row_id, payload_json in rows:
            result = send_fn(json.loads(payload_json))
            if result.status in (SendStatus.SENT, SendStatus.BAD):
                with self._conn() as c:
                    c.execute("DELETE FROM pending WHERE id = ?", (row_id,))
                if result.status == SendStatus.SENT:
                    sent += 1
            else:  # TRANSIENT or AUTH — keep row, stop draining
                break
        return sent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest clients/desktop/tests/test_queue.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add clients/desktop/queue.py clients/desktop/tests/test_queue.py
git commit -m "feat(desktop): SQLite offline queue with replay + dedup"
```

---

### Task 6: Selection + active-window grab

**Files:**
- Create: `clients/desktop/grab.py`
- Test: `clients/desktop/tests/test_grab.py`

**Interfaces:**
- Consumes: nothing (OS libs behind seams).
- Produces:
  - `WindowInfo(app: str, title: str)`
  - `normalize_window(title, app) -> WindowInfo` — trims/defaults; `title`/`app` may be None → `""`.
  - `grab_selection(*, copy_fn, read_clipboard, write_clipboard, sleep_fn) -> tuple[str, str]` — returns `(selection_text, source)` where source is `"selection"` if the copy changed the clipboard, else `"clipboard"`. Saves and restores the prior clipboard.
  - `read_active_window() -> WindowInfo` — real OS wiring (pygetwindow), untested.
  - `grab_current() -> tuple[str, str]` — real OS wiring, untested.

- [ ] **Step 1: Write the failing test**

`clients/desktop/tests/test_grab.py`:
```python
from clients.desktop.grab import WindowInfo, grab_selection, normalize_window


def test_normalize_window_defaults_none():
    assert normalize_window(None, None) == WindowInfo(app="", title="")


def test_normalize_window_trims():
    assert normalize_window("  Title  ", " Code.exe ") == WindowInfo(
        app="Code.exe", title="Title"
    )


def test_grab_selection_returns_copied_text_as_selection():
    clip = {"v": "OLD"}
    copied = {"done": False}

    def copy_fn():
        clip["v"] = "SELECTED TEXT"  # simulate Ctrl+C replacing clipboard
        copied["done"] = True

    text, source = grab_selection(
        copy_fn=copy_fn,
        read_clipboard=lambda: clip["v"],
        write_clipboard=lambda v: clip.__setitem__("v", v),
        sleep_fn=lambda _s: None,
    )
    assert text == "SELECTED TEXT"
    assert source == "selection"
    assert clip["v"] == "OLD"  # prior clipboard restored


def test_grab_selection_falls_back_to_clipboard_when_no_selection():
    clip = {"v": "CLIP ONLY"}

    def copy_fn():
        pass  # nothing selected → clipboard unchanged

    text, source = grab_selection(
        copy_fn=copy_fn,
        read_clipboard=lambda: clip["v"],
        write_clipboard=lambda v: clip.__setitem__("v", v),
        sleep_fn=lambda _s: None,
    )
    assert text == "CLIP ONLY"
    assert source == "clipboard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest clients/desktop/tests/test_grab.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clients.desktop.grab'`

- [ ] **Step 3: Write the implementation**

`clients/desktop/grab.py`:
```python
"""Grab the current selection and active-window context.

The pure logic (clipboard save/restore, selection-vs-clipboard decision,
window normalization) is separated from OS calls so it is unit-testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    app: str
    title: str


def normalize_window(title, app) -> WindowInfo:
    return WindowInfo(app=(app or "").strip(), title=(title or "").strip())


def grab_selection(*, copy_fn, read_clipboard, write_clipboard, sleep_fn) -> tuple[str, str]:
    """Copy the current selection to the clipboard, read it, then restore.

    Returns (text, source). source is "selection" if the copy changed the
    clipboard, else "clipboard" (nothing was selected; we use prior contents).
    """
    prior = read_clipboard() or ""
    # Sentinel so we can detect whether Ctrl+C actually replaced the clipboard.
    write_clipboard("")
    copy_fn()
    sleep_fn(0.12)  # give the foreground app time to service the copy
    grabbed = read_clipboard() or ""

    if grabbed:
        source = "selection"
        text = grabbed
    else:
        source = "clipboard"
        text = prior

    write_clipboard(prior)  # always restore the user's clipboard
    return text, source


# ── Real OS wiring (Windows; manual verification) ─────────────────────


def read_active_window() -> WindowInfo:  # pragma: no cover - OS call
    import pygetwindow

    win = pygetwindow.getActiveWindow()
    title = getattr(win, "title", "") if win else ""
    app = _active_process_name()
    return normalize_window(title, app)


def _active_process_name() -> str:  # pragma: no cover - OS call
    try:
        import win32gui
        import win32process
        import psutil

        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return ""


def grab_current() -> tuple[str, str]:  # pragma: no cover - OS call
    import pyperclip
    from pynput.keyboard import Controller, Key

    kb = Controller()

    def copy_fn():
        with kb.pressed(Key.ctrl):
            kb.press("c")
            kb.release("c")

    return grab_selection(
        copy_fn=copy_fn,
        read_clipboard=pyperclip.paste,
        write_clipboard=pyperclip.copy,
        sleep_fn=time.sleep,
    )
```

Note: `_active_process_name` uses `pywin32` + `psutil`. Add `pywin32` and `psutil` to `clients/desktop/requirements.txt` in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest clients/desktop/tests/test_grab.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Add the two OS deps and commit**

Append to `clients/desktop/requirements.txt`:
```
pywin32>=306; sys_platform == "win32"
psutil>=5.9
```

```bash
git add clients/desktop/grab.py clients/desktop/tests/test_grab.py clients/desktop/requirements.txt
git commit -m "feat(desktop): selection + active-window grab with testable seams"
```

---

### Task 7: Capture popup (tkinter)

**Files:**
- Create: `clients/desktop/popup.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `CaptureDraft(content: str, tags: list[str])`
  - `show_popup(prefill: str = "") -> CaptureDraft | None` — modal always-on-top window; returns the draft on save (Enter / Save), `None` on cancel (Esc / close). Tags are parsed from a comma-separated field.

**Note:** tkinter UI — no unit test; verified manually in Task 10's checklist.

- [ ] **Step 1: Write the implementation**

`clients/desktop/popup.py`:
```python
"""Minimal always-on-top capture window built on tkinter (stdlib)."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass


@dataclass
class CaptureDraft:
    content: str
    tags: list[str]


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def show_popup(prefill: str = "") -> CaptureDraft | None:
    """Show the capture popup. Returns a CaptureDraft or None if cancelled."""
    result: dict[str, CaptureDraft | None] = {"draft": None}

    root = tk.Tk()
    root.title("Capture to Life Graph")
    root.attributes("-topmost", True)
    root.geometry("460x220")
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Capture").pack(anchor="w", padx=8, pady=(8, 0))
    text = tk.Text(root, height=6, wrap="word")
    text.insert("1.0", prefill)
    text.pack(fill="both", expand=True, padx=8)
    text.focus_set()

    tag_frame = tk.Frame(root)
    tag_frame.pack(fill="x", padx=8, pady=4)
    tk.Label(tag_frame, text="tags:").pack(side="left")
    tag_entry = tk.Entry(tag_frame)
    tag_entry.pack(side="left", fill="x", expand=True)

    def save(_event=None):
        content = text.get("1.0", "end").strip()
        if content:
            result["draft"] = CaptureDraft(content, _parse_tags(tag_entry.get()))
        root.destroy()

    def cancel(_event=None):
        root.destroy()

    btns = tk.Frame(root)
    btns.pack(fill="x", padx=8, pady=(0, 8))
    tk.Button(btns, text="Save  (Ctrl+Enter)", command=save).pack(side="right")
    tk.Button(btns, text="Cancel  (Esc)", command=cancel).pack(side="right", padx=6)

    root.bind("<Control-Return>", save)
    root.bind("<Escape>", cancel)

    root.mainloop()
    return result["draft"]
```

Note: multi-line captures use **Ctrl+Enter** to save (plain Enter inserts a newline in the text box).

- [ ] **Step 2: Manual smoke check**

Run: `python -c "from clients.desktop.popup import show_popup; print(show_popup('hello'))"`
Expected: window appears with "hello"; Ctrl+Enter prints `CaptureDraft(content='hello', tags=[])`; Esc prints `None`.

- [ ] **Step 3: Commit**

```bash
git add clients/desktop/popup.py
git commit -m "feat(desktop): tkinter capture popup"
```

---

### Task 8: Global hotkeys (pynput)

**Files:**
- Create: `clients/desktop/hotkeys.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `HotkeyManager(bindings: dict[str, callable])` where keys are pynput hotkey strings and values are zero-arg callbacks.
  - `.start() -> None` (non-blocking; spawns the listener thread), `.stop() -> None`, `.set_enabled(bool)` (pause/resume without unregistering).

**Note:** pynput global listener — no unit test; verified in Task 10.

- [ ] **Step 1: Write the implementation**

`clients/desktop/hotkeys.py`:
```python
"""Global hotkey registration via pynput."""

from __future__ import annotations

import logging

from pynput import keyboard

logger = logging.getLogger("desktop.hotkeys")


class HotkeyManager:
    def __init__(self, bindings: dict) -> None:
        self._bindings = bindings
        self._enabled = True
        self._listener: keyboard.GlobalHotKeys | None = None

    def _wrap(self, fn):
        def handler():
            if self._enabled:
                try:
                    fn()
                except Exception:
                    logger.exception("Hotkey handler failed")
        return handler

    def start(self) -> None:
        wrapped = {combo: self._wrap(fn) for combo, fn in self._bindings.items()}
        self._listener = keyboard.GlobalHotKeys(wrapped)
        self._listener.start()
        logger.info("Hotkeys active: %s", list(self._bindings))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
```

- [ ] **Step 2: Manual smoke check**

Run this snippet, press Ctrl+Alt+Space, confirm it prints, then Ctrl+C to exit:
```bash
python -c "import time; from clients.desktop.hotkeys import HotkeyManager; m=HotkeyManager({'<ctrl>+<alt>+space': lambda: print('HIT')}); m.start(); time.sleep(30)"
```
Expected: pressing the combo prints `HIT`.

- [ ] **Step 3: Commit**

```bash
git add clients/desktop/hotkeys.py
git commit -m "feat(desktop): global hotkey manager"
```

---

### Task 9: System tray (pystray)

**Files:**
- Create: `clients/desktop/tray.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Tray(on_pause_toggle: callable, on_quit: callable, on_settings: callable)` with `.run() -> None` (blocking; owns the main thread) and `.notify(title, message) -> None` (toast).
  - Menu items: "Pause/Resume" (calls `on_pause_toggle(is_paused: bool)`), "Open settings folder" (`on_settings`), "Quit" (`on_quit`).

**Note:** pystray UI — no unit test; verified in Task 10.

- [ ] **Step 1: Write the implementation**

`clients/desktop/tray.py`:
```python
"""System tray icon + menu via pystray."""

from __future__ import annotations

from PIL import Image, ImageDraw
import pystray


def _icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), (30, 30, 40))
    d = ImageDraw.Draw(img)
    d.ellipse((14, 14, 50, 50), fill=(90, 200, 160))
    return img


class Tray:
    def __init__(self, on_pause_toggle, on_quit, on_settings) -> None:
        self._on_pause_toggle = on_pause_toggle
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._paused = False
        self._icon = pystray.Icon(
            "life-graph-capture", _icon_image(), "Life Graph Capture",
            menu=self._menu(),
        )

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: "Resume" if self._paused else "Pause",
                self._toggle_pause,
            ),
            pystray.MenuItem("Open settings folder", lambda: self._on_settings()),
            pystray.MenuItem("Quit", self._quit),
        )

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._on_pause_toggle(self._paused)

    def _quit(self) -> None:
        self._on_quit()
        self._icon.stop()

    def notify(self, title: str, message: str) -> None:
        try:
            self._icon.notify(message, title)
        except Exception:
            pass

    def run(self) -> None:
        self._icon.run()
```

- [ ] **Step 2: Manual smoke check**

Run and confirm a tray icon appears with Pause / Open settings folder / Quit:
```bash
python -c "from clients.desktop.tray import Tray; Tray(lambda p: print('pause',p), lambda: print('quit'), lambda: print('settings')).run()"
```

- [ ] **Step 3: Commit**

```bash
git add clients/desktop/tray.py
git commit -m "feat(desktop): system tray icon + menu"
```

---

### Task 10: Wiring, CLI, autostart + README

**Files:**
- Create: `clients/desktop/app.py`
- Create: `clients/desktop/README.md`

**Interfaces:**
- Consumes: `load_config`, `set_api_key`, `default_config_path` (config); `CaptureClient`, `build_payload`, `SendStatus` (client); `CaptureQueue` (queue); `read_active_window`, `grab_current` (grab); `show_popup` (popup); `HotkeyManager` (hotkeys); `Tray` (tray).
- Produces: `main()` entry point; `--set-key` CLI; `install_autostart()`.

**Note:** wiring + OS integration — verified via the manual checklist in the README.

- [ ] **Step 1: Write the app wiring**

`clients/desktop/app.py`:
```python
"""Desktop Capture Agent entry point — wires all modules together."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import subprocess
import sys
import threading
import time

from clients.desktop.client import CaptureClient, SendStatus, build_payload
from clients.desktop.config import (
    default_config_path,
    load_config,
    set_api_key,
)
from clients.desktop.grab import grab_current, read_active_window
from clients.desktop.hotkeys import HotkeyManager
from clients.desktop.popup import show_popup
from clients.desktop.queue import CaptureQueue
from clients.desktop.tray import Tray

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("desktop.app")


class Agent:
    def __init__(self, config) -> None:
        self._cfg = config
        self._client = CaptureClient(
            config.backend_url, config.api_key, config.tenant_id
        )
        self._queue = CaptureQueue(default_config_path().parent / "queue.db")
        self._tray: Tray | None = None

    # ── capture flows ────────────────────────────────────────
    def _deliver(self, payload: dict, ok_msg: str) -> None:
        result = self._client.send(payload)
        if result.status == SendStatus.SENT:
            self._notify("Life Graph", ok_msg)
            self._queue.replay(self._client.send)
        elif result.status == SendStatus.AUTH:
            self._notify("Life Graph", "Auth failed — check settings")
        elif result.status == SendStatus.BAD:
            logger.warning("Dropped bad capture: %s", result.detail)
        else:  # TRANSIENT
            self._queue.enqueue(payload)
            self._notify("Life Graph", "Queued (offline)")

    def capture_popup(self) -> None:
        text, source = grab_current()
        draft = show_popup(prefill=text)
        if draft is None:
            return
        win = read_active_window()
        payload = build_payload(
            content=draft.content, app=win.app, window_title=win.title,
            source=source if draft.content == text else "note",
            tags=draft.tags, do_redact=self._cfg.redact,
        )
        self._deliver(payload, "Saved")

    def capture_instant(self) -> None:
        text, source = grab_current()
        if not text.strip():
            self._notify("Life Graph", "Nothing selected")
            return
        win = read_active_window()
        payload = build_payload(
            content=text, app=win.app, window_title=win.title,
            source=source, do_redact=self._cfg.redact,
        )
        self._deliver(payload, "✓ Saved")

    # ── infra ────────────────────────────────────────────────
    def _notify(self, title: str, msg: str) -> None:
        if self._tray:
            self._tray.notify(title, msg)
        logger.info("%s: %s", title, msg)

    def _replay_loop(self) -> None:
        while True:
            time.sleep(self._cfg.replay_interval_seconds)
            try:
                self._queue.replay(self._client.send)
            except Exception:
                logger.exception("Replay loop error")

    def run(self) -> None:
        hotkeys = HotkeyManager({
            self._cfg.hotkeys.popup: self.capture_popup,
            self._cfg.hotkeys.instant: self.capture_instant,
        })
        hotkeys.start()
        threading.Thread(target=self._replay_loop, daemon=True).start()

        self._tray = Tray(
            on_pause_toggle=hotkeys.set_enabled_inverted,
            on_quit=lambda: os._exit(0),
            on_settings=lambda: _open_folder(default_config_path().parent),
        )
        self._tray.run()  # blocks


def _open_folder(path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 - Windows only
    except Exception:
        subprocess.Popen(["explorer", str(path)])


def install_autostart() -> None:
    """Register the agent to launch on login via the Startup folder shortcut."""
    startup = os.path.join(
        os.environ["APPDATA"],
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    target = f'"{sys.executable}" -m clients.desktop.app'
    bat = os.path.join(startup, "life-graph-capture.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f"@echo off\nstart \"\" {target}\n")
    logger.info("Autostart installed: %s", bat)


def _cmd_set_key() -> None:
    cfg_path = default_config_path()
    tenant = input("tenant_id [default]: ").strip() or "default"
    key = getpass.getpass("service API key: ").strip()
    set_api_key(tenant, key)
    print(f"Stored API key for tenant {tenant!r}. Ensure {cfg_path} sets tenant_id = \"{tenant}\".")


def main() -> None:
    parser = argparse.ArgumentParser(prog="clients.desktop.app")
    parser.add_argument("--set-key", action="store_true", help="store API key in keyring")
    parser.add_argument("--install-autostart", action="store_true")
    args = parser.parse_args()

    if args.set_key:
        _cmd_set_key()
        return
    if args.install_autostart:
        install_autostart()
        return

    config = load_config()
    Agent(config).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add the pause helper to HotkeyManager**

The tray toggles pause with `is_paused: bool`; add an inverted setter to `clients/desktop/hotkeys.py` (enabled = not paused). Insert after `set_enabled`:
```python
    def set_enabled_inverted(self, is_paused: bool) -> None:
        """Tray passes is_paused; enabled is the inverse."""
        self.set_enabled(not is_paused)
```

- [ ] **Step 3: Run the full unit suite (regression)**

Run: `python -m pytest clients/desktop/tests/ -v`
Expected: PASS (all tests from Tasks 2–6 green)

- [ ] **Step 4: Write the README with the manual checklist**

`clients/desktop/README.md`:
```markdown
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
```

- [ ] **Step 5: Commit**

```bash
git add clients/desktop/app.py clients/desktop/hotkeys.py clients/desktop/README.md
git commit -m "feat(desktop): wire agent, CLI, autostart, README + manual checklist"
```

- [ ] **Step 6: Full manual integration pass**

Follow every item in `clients/desktop/README.md` → "Manual verification checklist" against a running backend. Fix any failures before considering v1 done.

---

## Self-Review

**1. Spec coverage:**
- Two hotkeys (popup + instant) → Tasks 7/8/10. ✓
- Auto-context (app, window title, source) → Task 6 `read_active_window` + Task 4 `build_payload`. ✓
- Shared contract: payload → Task 4; auth headers → Task 4; keyring key → Task 3; offline queue + dedup → Task 5; redaction → Task 2. ✓
- Config file format → Task 3. ✓
- Error-handling table (nothing selected / offline / auth / bad / clipboard fallback) → Task 10 `_deliver` + `capture_instant`, Task 6 grab fallback. ✓
- Tray (pause/settings/quit) + autostart → Tasks 9/10. ✓
- Success criteria (2s, offline replay, source app, login start) → Task 10 checklist. ✓
- Out-of-scope (screenshot/OCR/voice/ambient/PWA-handoff) → correctly absent. ✓

**2. Placeholder scan:** No TBD/TODO; every code step contains complete code. ✓

**3. Type consistency:** `SendStatus`/`SendResult` defined in Task 4, consumed identically in Tasks 5 & 10. `build_payload` signature in Task 4 matches its calls in Task 10. `grab_current()`/`read_active_window()` defined in Task 6, called in Task 10. `HotkeyManager.set_enabled_inverted` added in Task 10 Step 2, referenced by `Tray(on_pause_toggle=...)` in Task 10 Step 1. `show_popup`/`CaptureDraft` defined Task 7, used Task 10. All consistent. ✓
```
