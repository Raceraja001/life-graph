"""Secret redaction for observation captures.

Tool-exhaust observations (capture spine) may contain secrets in command
arguments — API keys, tokens, passwords. Redact obvious secrets before any
storage. Best-effort: pattern-based, tuned to avoid storing credentials, not
a guarantee against every exfiltration shape.
"""

from __future__ import annotations

import json
import re
from typing import Any

REDACTED = "[REDACTED]"

# key=value / key: value where the KEY looks sensitive. (No bare "auth" — it
# matched "author"/"Authorization" and only redacted the scheme word, leaking
# the credential; Authorization is handled by _AUTH_HEADER below.)
_KV_SECRET = re.compile(
    r"(?i)([\w.-]*(?:api[_-]?key|secret|token|password|passwd|pwd|"
    r"access[_-]?key)[\w.-]*)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)

# Authorization headers: redact the whole credential (scheme + token), for
# both "Authorization: <cred>" and "AUTHORIZATION=<cred>" forms.
_AUTH_HEADER = re.compile(r"(?i)\b(authorization)\s*[:=]\s*\S+(?:\s+\S+)?")

# Standalone bearer tokens.
_BEARER = re.compile(r"(?i)\b(bearer)\s+\S+")

# Standalone token shapes worth redacting wherever they appear.
_TOKEN_SHAPES: list[re.Pattern[str]] = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),               # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),            # OpenAI-style keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),     # GitHub tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),   # Slack tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]{8,}\b"),  # JWT
]


def redact_secrets(text: str) -> str:
    """Replace secret-looking substrings with ``[REDACTED]``.

    Handles ``key=value`` / ``key: value`` pairs with sensitive-looking
    keys, Bearer/Authorization headers, and common standalone token shapes.
    """
    if not text:
        return text
    text = _AUTH_HEADER.sub(lambda m: f"{m.group(1)}: {REDACTED}", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = _KV_SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    for pat in _TOKEN_SHAPES:
        text = pat.sub(REDACTED, text)
    return text


def summarize_args(args: Any, *, max_len: int = 200) -> str:
    """Render tool args to a short, secret-redacted summary string.

    Full outputs/args are never stored — only a bounded, redacted summary
    (capture-spine storage discipline).
    """
    try:
        raw = json.dumps(args, default=str, ensure_ascii=False, sort_keys=True)
    except Exception:
        raw = str(args)
    raw = redact_secrets(raw)
    if len(raw) > max_len:
        raw = raw[:max_len] + "…"
    return raw
