"""HTTP API over the store (standard library only): what the e2e check drives."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.store import Store

store = Store()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if self.path == "/api/todos":
            return self._send(200, store.list())
        return self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/todos":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("content-length") or 0)
        try:
            title = json.loads(self.rfile.read(length) or b"{}").get("title")
            return self._send(201, store.add(title))
        except ValueError as exc:
            return self._send(400, {"error": str(exc)})

    def log_message(self, *args) -> None:  # quiet
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8000"))), Handler).serve_forever()
