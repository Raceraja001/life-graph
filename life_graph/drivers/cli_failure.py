"""Why a coding CLI run failed: rate-limited, signed out, or something else.

Shared by the subscription CLI drivers (codex, gemini). The text classified is
the CLI's own final error, the error events it streamed, and the plain-text
lines of its stderr. Rebuilt from race-app's ``agents/runtimes/failure-text.ts``
and ``codex-classify.ts`` (the owner's code).

Rule-based on purpose (CHARTER invariant 1): these are fixed strings a CLI
prints, so a regex is enough. Every message that leaves this module is
scrubbed of token-shaped strings and clipped, because it lands in task
metadata and on the dashboard.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

MAX_MESSAGE_CHARS = 200

RATE_LIMIT_PATTERN = re.compile(
    r"usage limit|rate[ _-]?limit|\b429\b|too many requests|overloaded|quota"
    r"|resource_exhausted|limit reached|resets? at",
    re.IGNORECASE,
)
AUTH_PATTERN = re.compile(
    r"not logged in|authentication|unauthori[sz]ed|\b401\b|invalid api key"
    r"|please run .*login|credentials|refresh token|sign in again|log ?in again"
    r"|token (?:could not be refreshed|has expired|is expired|was revoked)",
    re.IGNORECASE,
)

_ISO_IN_TEXT = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?"
)
# Codex: "try again in 2 hours 5 minutes"; Gemini (Google API): "Please retry in 23.5s".
_RELATIVE_RESET = re.compile(
    r"(?:try again|retry) in\s+((?:\d+(?:\.\d+)?\s*"
    r"(?:days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b[\s,]*(?:and\s+)?)+)",
    re.IGNORECASE,
)
_UNIT_SECONDS = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))

_TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),  # OpenAI / Anthropic keys
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),  # Google API keys
    re.compile(r"\bya29\.[0-9A-Za-z._-]{10,}"),  # Google OAuth access tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]+)?"),  # JWTs
    re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}"),  # long opaque blobs
)
_LABELLED_TOKEN = re.compile(
    r"\b(Bearer|token|api[_-]?key|x-api-key)([=:\s]+)[\"']?[A-Za-z0-9._~+/-]{8,}=*",
    re.IGNORECASE,
)

# Plausible reset times only: a stray number is not a date.
_MIN_RESET = datetime(2000, 1, 1, tzinfo=UTC)
_MAX_RESET = datetime(2200, 1, 1, tzinfo=UTC)


def scrub_secrets(text: str) -> str:
    """Replace token-shaped substrings with ``[redacted]``."""
    out = _LABELLED_TOKEN.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", text or "")
    for pattern in _TOKEN_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out


def failure_message(text: str) -> str | None:
    """Scrubbed, whitespace-collapsed, at most 200 characters; None when empty."""
    flat = " ".join(scrub_secrets(text).split())
    if not flat:
        return None
    return flat if len(flat) <= MAX_MESSAGE_CHARS else flat[: MAX_MESSAGE_CHARS - 1] + "…"


def normalize_reset(value: object) -> str | None:
    """A reset time (ISO string, epoch seconds or epoch ms) as ISO UTC, or None."""
    if isinstance(value, bool):
        return None
    when: datetime | None = None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value >= 1e12 else value
        try:
            when = datetime.fromtimestamp(seconds, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        if re.fullmatch(r"\d+(\.\d+)?", raw):
            return normalize_reset(float(raw))
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00").replace(" ", "T", 1))
        except ValueError:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
    if when is None or not (_MIN_RESET <= when <= _MAX_RESET):
        return None
    return when.astimezone(UTC).isoformat().replace("+00:00", "Z")


def reset_from_text(text: str, now: datetime | None = None) -> str | None:
    """An ISO time in *text*, else "try again in 2 hours 5 minutes" counted from *now*."""
    match = _ISO_IN_TEXT.search(text or "")
    if match:
        found = normalize_reset(match.group(0))
        if found:
            return found
    rel = _RELATIVE_RESET.search(text or "")
    if not rel:
        return None
    seconds = 0.0
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]+)", rel.group(1), re.IGNORECASE):
        for prefix, size in _UNIT_SECONDS:
            if unit.lower().startswith(prefix):
                seconds += float(amount) * size
                break
    if seconds <= 0:
        return None
    base = now or datetime.now(UTC)
    return (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def plain_text_lines(text: str) -> str:
    """The lines of *text* that are not JSON events (a CLI's own error prints)."""
    return "\n".join(
        line
        for line in (text or "").splitlines()
        if line.strip() and not line.lstrip().startswith("{")
    )


def _line_matching(text: str, pattern: re.Pattern) -> str:
    return next((line for line in text.splitlines() if pattern.search(line)), text)


def classify_failure(
    *,
    final_error: str = "",
    warnings: list[str] | None = None,
    stderr: str = "",
    exit_code: int | None = None,
    rate_limit_resets: list[str] | None = None,
    rejected: bool = False,
    login_hint: str = "",
    now: datetime | None = None,
) -> dict:
    """One failed run -> ``{"kind", "message"?, "resets_at"?, "hint"?}``.

    *rejected* and *rate_limit_resets* come from a structured rate-limit
    snapshot when the CLI streamed one (Codex does); they win over text.
    *login_hint* is the command that signs this CLI in, returned on ``auth``.
    """
    text = "\n".join(
        t for t in (final_error, *(warnings or []), plain_text_lines(stderr)) if t and t.strip()
    )
    if rejected or RATE_LIMIT_PATTERN.search(text):
        out: dict = {"kind": "rate_limited"}
        resets = sorted(r for r in (rate_limit_resets or []) if r)
        resets_at = (resets[0] if resets else None) or reset_from_text(text, now)
        if resets_at:
            out["resets_at"] = resets_at
        line = _line_matching(text, RATE_LIMIT_PATTERN) if text else ""
        out["message"] = failure_message(line) or "usage limit reached"
        return out
    if AUTH_PATTERN.search(text):
        out = {"kind": "auth"}
        message = failure_message(_line_matching(text, AUTH_PATTERN))
        if message:
            out["message"] = message
        if login_hint:
            out["hint"] = login_hint
        return out
    message = failure_message(final_error) or failure_message((text.splitlines() or [""])[-1])
    if not message and exit_code is not None:
        message = f"exited with code {exit_code}"
    return {"kind": "other", "message": message} if message else {"kind": "other"}
