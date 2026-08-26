"""HTTP transport + offline spool for the Claude Code hook.

Reuses the desktop capture agent's building blocks rather than growing a second
implementation of the same thing:

* :class:`clients.desktop.client.SendStatus` / ``SendResult`` — the 2xx-sent /
  401-403-auth / 5xx-network-transient / other-4xx-drop triage.
* :class:`clients.desktop.queue.CaptureQueue` — the SQLite spool, including the
  "stop draining on the first transient failure" replay discipline.

Secret redaction reuses :mod:`life_graph.core.redaction` — the backend module
that ``clients/desktop/redact.py`` is a hand-maintained mirror of. Since this
adapter already lives inside ``life_graph``, importing the original is free and
removes the mirror's drift risk from this path entirely.

``clients`` is a sibling top-level package of ``life_graph`` in the repo. An
editable install puts both on ``sys.path``; :func:`_ensure_clients_importable`
covers the plain-checkout case by adding the repo root itself.
"""

from __future__ import annotations

import contextlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from life_graph.core.redaction import redact_secrets

if TYPE_CHECKING:
    from life_graph.integrations.claude_code.config import HookConfig


def _ensure_clients_importable() -> None:
    """Put the repo root on ``sys.path`` so ``clients.desktop`` resolves."""
    repo_root = str(Path(__file__).resolve().parents[3])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


try:
    from clients.desktop.client import SendResult, SendStatus
    from clients.desktop.queue import CaptureQueue
except ImportError:  # pragma: no cover - exercised only in odd installs
    _ensure_clients_importable()
    from clients.desktop.client import SendResult, SendStatus
    from clients.desktop.queue import CaptureQueue

__all__ = [
    "CaptureQueue",
    "SendResult",
    "SendStatus",
    "build_capture_payload",
    "flush_spool",
    "post_capture",
    "post_recall",
    "spool",
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clip(text: str, limit: int) -> str:
    """Truncate with an explicit marker so downstream sees the elision."""
    if limit > 0 and len(text) > limit:
        return text[:limit] + f"… [+{len(text) - limit} chars]"
    return text


def build_capture_payload(
    *,
    surface: str,
    content: str,
    cfg: HookConfig,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a ``CaptureEventCreate`` body, redacted and clipped.

    ``modality`` is always ``"text"``: ``capture_processors`` early-returns on
    every other modality, so a ``structured`` event would be stored but never
    processed into memory.

    Redaction runs on the content *and* on every string leaf of ``properties``
    — tool arguments and prompts are exactly where a credential shows up.
    """
    props = _redact_tree(properties or {})
    props.setdefault("client_capture_id", str(uuid.uuid4()))
    props.setdefault("captured_at", _now_iso())
    props.setdefault("integration", "claude_code")
    return {
        "surface": surface,
        "content": _clip(redact_secrets(content), cfg.max_content_chars),
        "modality": "text",
        "properties": props,
    }


def _redact_tree(value: Any) -> Any:
    """Recursively redact every string in a JSON-ish structure."""
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: _redact_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_tree(v) for v in value]
    return value


def post_capture(payload: dict[str, Any], cfg: HookConfig, *, client=None) -> SendResult:
    """POST one capture event, applying the desktop agent's status triage.

    ``client`` is injectable so tests can drive this with a stub transport and
    no network.
    """
    import httpx

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=cfg.capture_timeout)
    try:
        resp = client.post(cfg.capture_url, json=payload, headers=cfg.headers)
    except Exception as exc:  # httpx.RequestError, timeouts, DNS, …
        return SendResult(SendStatus.TRANSIENT, str(exc))
    finally:
        if owns_client:
            with contextlib.suppress(Exception):
                client.close()

    if resp.status_code < 300:
        return SendResult(SendStatus.SENT)
    if resp.status_code in (401, 403):
        return SendResult(SendStatus.AUTH, resp.text[:200])
    if resp.status_code >= 500:
        return SendResult(SendStatus.TRANSIENT, f"server {resp.status_code}")
    return SendResult(SendStatus.BAD, f"{resp.status_code}: {resp.text[:200]}")


def spool(payload: dict[str, Any], cfg: HookConfig) -> None:
    """Persist an undelivered capture for a later flush. Best-effort."""
    with contextlib.suppress(Exception):
        CaptureQueue(cfg.spool_path).enqueue(payload)


def deliver(payload: dict[str, Any], cfg: HookConfig, *, client=None) -> SendResult:
    """Send a capture; spool it if the backend was unreachable or 5xx.

    ``AUTH`` and ``BAD`` are *not* spooled — a misconfigured key or a payload
    the API rejects would otherwise retry forever.
    """
    result = post_capture(payload, cfg, client=client)
    if result.status == SendStatus.TRANSIENT:
        spool(payload, cfg)
    return result


def flush_spool(cfg: HookConfig, *, client=None, limit_seconds: float | None = None) -> int:
    """Drain the offline spool. Returns the number of events delivered.

    Replay stops at the first transient/auth failure (``CaptureQueue.replay``
    semantics), so a still-dead backend costs one request, not one per row.
    """
    try:
        queue = CaptureQueue(cfg.spool_path)
    except Exception:
        return 0
    deadline = _monotonic() + limit_seconds if limit_seconds is not None else None

    def send_fn(payload: dict[str, Any]) -> SendResult:
        if deadline is not None and _monotonic() > deadline:
            return SendResult(SendStatus.TRANSIENT, "flush budget exhausted")
        return post_capture(payload, cfg, client=client)

    try:
        return queue.replay(send_fn)
    except Exception:
        return 0


def _monotonic() -> float:
    import time

    return time.monotonic()


def post_recall(context: dict[str, Any], cfg: HookConfig, *, client=None) -> dict[str, Any] | None:
    """POST session-start proactive recall. Returns the RecallContext or None.

    Never raises: recall is a nicety, and a slow or missing backend must cost
    the developer nothing but the configured timeout.
    """
    import httpx

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=cfg.recall_timeout)
    try:
        resp = client.post(cfg.recall_url, json={"context": context}, headers=cfg.headers)
        if resp.status_code >= 300:
            return None
        body = resp.json()
    except Exception:
        return None
    finally:
        if owns_client:
            with contextlib.suppress(Exception):
                client.close()

    if not isinstance(body, dict):
        return None
    data = body.get("data", body)
    return data if isinstance(data, dict) else None


def log_debug(cfg: HookConfig, message: str, **fields: Any) -> None:
    """Append a debug line when ``LIFE_GRAPH_HOOK_DEBUG`` is set.

    Never stdout — stray stdout corrupts the hook output contract.
    """
    if not cfg.debug:
        return
    try:
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": _now_iso(), "msg": message, **fields}, default=str)
        with open(cfg.log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
