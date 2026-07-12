"""Client-side secret redaction — mirrors life_graph/core/redaction.py.

Kept in sync manually: the agent is a separate process and must not import
the backend package (it would drag in backend dependencies).
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

# key=value / key: value where the KEY looks sensitive. (No bare "auth" —
# it matched "author"/"Authorization"; auth headers handled separately below.)
_KV_SECRET = re.compile(
    r"(?i)([\w.-]*(?:api[_-]?key|secret|token|password|passwd|pwd|"
    r"access[_-]?key)[\w.-]*)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
# Authorization headers: redact the whole credential (scheme + token), not
# just the scheme word.
_AUTH_HEADER = re.compile(r"(?i)\b(authorization)\s*:\s*\S+(?:\s+\S+)?")
# Standalone bearer tokens.
_BEARER = re.compile(r"(?i)\b(bearer)\s+\S+")
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
    text = _AUTH_HEADER.sub(lambda m: f"{m.group(1)}: {REDACTED}", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = _KV_SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    for pat in _TOKEN_SHAPES:
        text = pat.sub(REDACTED, text)
    return text
