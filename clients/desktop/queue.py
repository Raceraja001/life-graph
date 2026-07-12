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
