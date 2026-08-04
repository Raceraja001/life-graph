"""Ship new Claude Code transcript bytes to Life Graph (thin, resumable).

Run periodically via Task Scheduler (see run_transcript_uploader.bat). Config
from %USERPROFILE%\\.life_graph_uploader.json; per-file byte offsets persisted
in %USERPROFILE%\\.life_graph_uploader_state.json. Stdlib only.
"""

from __future__ import annotations

import glob
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

CONFIG_PATH = Path(os.path.expanduser("~")) / ".life_graph_uploader.json"
STATE_PATH = Path(os.path.expanduser("~")) / ".life_graph_uploader_state.json"


def new_lines(data: bytes, offset: int) -> tuple[list[str], int]:
    """Return complete lines past ``offset`` and the byte offset after them."""
    if offset > len(data):  # truncation / rotation → re-read from the top
        offset = 0
    chunk = data[offset:]
    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:
        return [], offset  # no complete line yet
    complete = chunk[: last_nl + 1]
    text = complete.decode("utf-8", errors="replace")
    lines = [ln for ln in text.split("\n") if ln != ""]
    return lines, offset + len(complete)


def start_offset(size: int, stored: int) -> int | None:
    """Byte offset to read from, or None to skip (nothing new).

    Truncation/rotation (file shrank at/below the stored offset) => re-read from 0.
    """
    if size < stored:
        return 0  # truncated/rotated -> re-read whole file
    if size == stored:
        return None  # nothing new
    return stored  # file grew -> read from stored


def batched(seq: list, size: int) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def session_id_for(path: str) -> str:
    return Path(path).stem


def _load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _post(cfg: dict, tool: str, session_id: str, source_path: str, lines: list[str]) -> bool:
    body = json.dumps(
        {"tool": tool, "session_id": session_id, "source_path": source_path, "lines": lines}
    ).encode("utf-8")
    req = urllib.request.Request(
        cfg["backend_url"].rstrip("/") + "/api/v1/ingest/external-transcript",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
            "X-Tenant-ID": cfg.get("tenant_id", "personal"),
            "CF-Access-Client-Id": cfg.get("cf_access_client_id", ""),
            "CF-Access-Client-Secret": cfg.get("cf_access_client_secret", ""),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 - keep going with other files
        print(f"  ! POST failed for {session_id}: {exc}")
        return False


def main() -> None:
    cfg = _load_json(CONFIG_PATH, {})
    if not cfg.get("backend_url"):
        raise SystemExit(f"Missing config at {CONFIG_PATH}")
    state = _load_json(STATE_PATH, {})
    batch_lines = int(cfg.get("batch_lines", 500))

    for root in cfg.get("roots", []):
        tool = root["tool"]
        base = os.path.expanduser(root["dir"])
        pattern = os.path.join(base, root.get("glob", "**/*.jsonl"))
        for path in glob.glob(pattern, recursive=True):
            size = os.path.getsize(path)
            entry = state.get(path, {"offset": 0})
            start = start_offset(size, entry["offset"])
            if start is None:
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            lines, new_offset = new_lines(data, start)
            if not lines:
                continue
            sid = session_id_for(path)
            ok = True
            for batch in batched(lines, batch_lines):
                if not _post(cfg, tool, sid, path, batch):
                    ok = False
                    break
            if ok:
                # A mid-file batch failure leaves the offset unadvanced, so the next
                # run resends earlier successful batches too; safe because the
                # backend's SHA-256 dedup absorbs the resend.
                state[path] = {"offset": new_offset, "session_id": sid}
                STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
                print(f"  ✓ {sid}: shipped {len(lines)} lines")
            time.sleep(0.2)  # gentle during backfill


if __name__ == "__main__":
    main()
