"""Plan-limit windows per account: from runs, and from an opt-in Codex probe.

Sources (race-app AGENT_ACCOUNTS_USAGE.md §3, owner decision U4):

- **Codex runs.** ``codex exec --json`` streams ``rate_limits`` snapshots;
  ``drivers/codex.py`` already turns them into ``metadata.rate_limits``
  (``slot``, ``used_percent``, ``window_minutes``, ``resets_at``).
- **Claude runs.** ``rate_limit_event`` lines in ``stream-json`` carry
  ``rate_limit_info.unifiedWindows`` (``five_hour``, ``seven_day``...), read
  passively by :func:`claude_windows` from the run's own output. Claude's
  OAuth usage endpoint is **never** polled (U4).
- **Codex probe** (``driver_accounts_codex_probe_enabled``): ``codex
  app-server`` over JSON-RPC stdio, ``account/read`` then
  ``account/rateLimits/read``. No prompt is sent and nothing is spent.
- Gemini reports no plan windows; its accounts show runs only.

Every window is normalized to ``{window, used_percent, window_minutes,
resets_at, status}`` where ``window`` is ``five_hour`` / ``seven_day`` /
``seven_day_opus`` / ``monthly`` when known, else the CLI's slot name.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import tempfile
from datetime import UTC, datetime

from life_graph.drivers.cli_failure import normalize_reset
from life_graph.drivers.host_exec import kill_process_group

logger = logging.getLogger(__name__)

# ── Codex window classification ────────────────────────────
# Ported from stablyai/orca@a9d792a0c5b2 (MIT) — src/main/rate-limits/providers/codex/
# codex-rate-limit-window-classification.ts, codex-rate-limit-window-mapper.ts
# (via race-app services/gateway/src/agents/limits/codex-windows.ts). Adapted:
# Python, our normalized window shape (used_percent kept 0-100), no credits.

CODEX_SESSION_WINDOW_MINUTES = 300
CODEX_WEEKLY_WINDOW_MINUTES = 10_080
# Older Codex bucket lengths drift by one minute; tolerate that only.
_DURATION_TOLERANCE_MINUTES = 1


def _codex_kind(minutes: object) -> str | None:
    if not isinstance(minutes, (int, float)) or isinstance(minutes, bool):
        return None
    if abs(minutes - CODEX_SESSION_WINDOW_MINUTES) <= _DURATION_TOLERANCE_MINUTES:
        return "five_hour"
    if abs(minutes - CODEX_WEEKLY_WINDOW_MINUTES) <= _DURATION_TOLERANCE_MINUTES:
        return "seven_day"
    return None


def codex_windows(raw: list[dict] | None) -> list[dict]:
    """``metadata.rate_limits`` of a codex run -> normalized windows.

    The 5-hour and weekly windows are picked by duration; a window of unknown
    duration keeps the legacy mapping (primary = 5-hour, secondary = weekly).
    """
    by_slot = {w.get("slot"): w for w in raw or [] if isinstance(w, dict)}
    picked: dict[str, dict] = {}
    for slot in ("primary", "secondary"):
        w = by_slot.get(slot)
        if w is None:
            continue
        kind = _codex_kind(w.get("window_minutes"))
        if kind and kind not in picked:
            picked[kind] = w
    for slot, kind in (("primary", "five_hour"), ("secondary", "seven_day")):
        w = by_slot.get(slot)
        if w is not None and kind not in picked and _codex_kind(w.get("window_minutes")) is None:
            picked[kind] = w
    out = []
    for kind in ("five_hour", "seven_day"):
        w = picked.get(kind)
        if w is None or not _is_number(w.get("used_percent")):
            continue
        used = max(0.0, float(w["used_percent"]))
        out.append(
            {
                "window": kind,
                "used_percent": used,
                "window_minutes": w.get("window_minutes")
                if isinstance(w.get("window_minutes"), int)
                else None,
                "resets_at": normalize_reset(w.get("resets_at")),
                "status": "rejected" if used >= 100 else None,
            }
        )
    return out


# ── Claude passive windows ────────────────────────────────

_CLAUDE_ORDER = ("five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _claude_status(value: object) -> str | None:
    if value in ("allowed", None, ""):
        return "allowed" if value == "allowed" else None
    if value == "allowed_warning":
        return "warning"
    return "rejected"


def claude_rate_limit_info(info: dict) -> list[dict]:
    """One ``rate_limit_info`` -> normalized windows (utilization 0-1 -> percent).

    Rebuilt from race-app ``runtimes/claude-code-parser.ts`` ``limitWindows``.
    """
    top_type = info.get("rateLimitType") if isinstance(info.get("rateLimitType"), str) else ""
    top_status = _claude_status(info.get("status"))
    out: list[dict] = []
    unified = info.get("unifiedWindows")
    for window_id, rec in unified.items() if isinstance(unified, dict) else []:
        if not isinstance(rec, dict) or not _is_number(rec.get("utilization")):
            continue
        status = _claude_status(rec.get("status")) if rec.get("status") else None
        if status is None and window_id == top_type:
            status = top_status
        out.append(_claude_window(window_id, rec["utilization"], rec, status))
    if not out and top_type and _is_number(info.get("utilization")):
        out.append(_claude_window(top_type, info["utilization"], info, top_status))
    rank = {w: n for n, w in enumerate(_CLAUDE_ORDER)}
    return sorted(out, key=lambda w: (rank.get(w["window"], len(rank)), w["window"]))


def _claude_window(window_id: str, utilization: float, rec: dict, status: str | None) -> dict:
    used = max(0.0, float(utilization)) * 100
    if used >= 100 and status != "rejected":
        status = "rejected"
    return {
        "window": str(window_id)[:32],
        "used_percent": round(used, 2),
        "window_minutes": None,
        "resets_at": normalize_reset(rec.get("resetsAt", rec.get("resets_at"))),
        "status": status,
    }


def claude_windows(stream_text: str) -> tuple[list[dict], dict | None]:
    """The last ``rate_limit_event`` of a Claude stream -> (windows, info summary).

    The summary is ``{"status", "resets_at"}`` of that event (for failure
    classification), or None when the stream had none.
    """
    last: dict | None = None
    for line in (stream_text or "").splitlines():
        text = line.strip()
        if not text.startswith("{") or "rate_limit_event" not in text:
            continue
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "rate_limit_event":
            info = event.get("rate_limit_info")
            if isinstance(info, dict):
                last = info
    if last is None:
        return [], None
    reset = normalize_reset(last.get("resetsAt", last.get("resets_at", last.get("reset_at"))))
    return claude_rate_limit_info(last), {"status": last.get("status"), "resets_at": reset}


def windows_from_metadata(driver: str, metadata: dict | None) -> list[dict]:
    """The normalized windows a driver result carried, for any driver."""
    raw = (metadata or {}).get("rate_limits")
    if not raw:
        return []
    if driver == "codex":
        return codex_windows(raw)
    # claude_code stores already-normalized windows (drivers/claude_code.py).
    return [w for w in raw if isinstance(w, dict) and isinstance(w.get("window"), str)]


# ── Codex app-server probe ────────────────────────────────
# Ported from stablyai/orca@a9d792a0c5b2 (MIT) — src/main/rate-limits/providers/codex/
# codex-rpc-rate-limit-probe.ts (via race-app limits/codex-rpc-probe.ts and
# codex-app-server.ts). Adapted: asyncio subprocess, one deadline per phase,
# fixed messages (stderr is classified, never returned), our window shape.

API_KEY_REASON = "API-key accounts have no plan limits"
SIGNED_OUT_REASON = "Sign in to Codex to see plan limits"
INIT_TIMEOUT_SECONDS = 15.0
RPC_TIMEOUT_SECONDS = 20.0


def _rpc(msg_id: int, method: str, params: dict | None = None) -> bytes:
    return (
        json.dumps({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        + "\n"
    ).encode()


def probe_result_windows(result: object) -> list[dict]:
    """The ``account/rateLimits/read`` result -> normalized windows."""
    from life_graph.drivers.codex import rate_limit_snapshot

    snapshot = result.get("rateLimits") if isinstance(result, dict) else None
    parsed = rate_limit_snapshot(snapshot)
    windows = codex_windows(parsed[0]) if parsed else []
    cap = snapshot.get("individualLimit") if isinstance(snapshot, dict) else None
    if not windows and isinstance(cap, dict) and _is_number(cap.get("remainingPercent")):
        used = max(0.0, 100 - float(cap["remainingPercent"]))
        windows.append(
            {
                "window": "monthly",
                "used_percent": used,
                "window_minutes": None,
                "resets_at": normalize_reset(cap.get("resetsAt")),
                "status": "rejected" if used >= 100 else None,
            }
        )
    return windows


async def probe_codex(
    binary: str,
    env: dict[str, str],
    *,
    init_timeout: float = INIT_TIMEOUT_SECONDS,
    rpc_timeout: float = RPC_TIMEOUT_SECONDS,
) -> dict:
    """Ask ``codex app-server`` for this home's plan windows.

    Returns ``{"kind": "windows", "windows": [...], "observed_at": iso}``,
    ``{"kind": "unavailable", "reason": ...}`` (API-key or signed-out home),
    or ``{"kind": "error", "error": ...}``. Never raises; always kills the child.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "app-server",
            cwd=tempfile.gettempdir(),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return {"kind": "unavailable", "reason": "Codex CLI not installed"}
    assert proc.stdin is not None and proc.stdout is not None

    async def call(msg_id: int, method: str, params: dict | None, timeout: float) -> dict:
        proc.stdin.write(_rpc(msg_id, method, params))
        await proc.stdin.drain()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError
            line = await asyncio.wait_for(proc.stdout.readline(), remaining)
            if not line:
                raise EOFError
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == msg_id:
                return message

    try:
        init = await call(
            1, "initialize", {"clientInfo": {"name": "life-graph", "version": "1"}}, init_timeout
        )
        if init.get("error"):
            return {"kind": "error", "error": "Codex app-server refused to initialize"}
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"initialized","params":{}}\n')
        account = await call(2, "account/read", {"refreshToken": False}, rpc_timeout)
        if account.get("error"):
            return _rpc_error(account["error"])
        acct = (account.get("result") or {}).get("account")
        if not acct:
            return {"kind": "unavailable", "reason": SIGNED_OUT_REASON}
        if isinstance(acct, dict) and acct.get("type") == "apiKey":
            return {"kind": "unavailable", "reason": API_KEY_REASON}
        limits = await call(
            3, "account/rateLimits/read", {"excludeResetCreditDetails": True}, rpc_timeout
        )
        if limits.get("error"):
            return _rpc_error(limits["error"])
        return {
            "kind": "windows",
            "windows": probe_result_windows(limits.get("result")),
            "observed_at": datetime.now(UTC).isoformat(),
        }
    except TimeoutError:
        return {"kind": "error", "error": "Codex did not answer in time"}
    except (EOFError, BrokenPipeError, ConnectionResetError):
        return {"kind": "error", "error": "Codex app-server exited"}
    finally:
        await kill_process_group(proc)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), 5)


def _rpc_error(error: object) -> dict:
    message = str(error.get("message") or "") if isinstance(error, dict) else ""
    lowered = message.lower()
    if "api key" in lowered or "api-key" in lowered or "apikey" in lowered:
        return {"kind": "unavailable", "reason": API_KEY_REASON}
    if any(t in lowered for t in ("not logged in", "log in again", "sign in again", "401")):
        return {"kind": "unavailable", "reason": SIGNED_OUT_REASON}
    if "error sending request" in lowered:
        return {"kind": "error", "error": "Codex could not reach OpenAI"}
    return {"kind": "error", "error": "Codex app-server returned an error"}
