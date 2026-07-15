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
