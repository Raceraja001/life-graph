"""Best-effort secret redaction for external transcript content.

Applied to every turn's text before fact extraction and to the raw thread
before archiving, so credentials never become memories or land in MinIO.
This is deliberately conservative-but-present: it removes the common
high-risk secret shapes, not every conceivable one.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "pem",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}")),
    ("openrouter_key", re.compile(r"sk-or-[A-Za-z0-9\-]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9\-]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    (
        "env_secret",
        re.compile(
            r"(?im)^(\s*[A-Z0-9_]*"
            r"(?:SECRET|TOKEN|PASSWORD|API[_-]?KEY|PRIVATE[_-]?KEY)[A-Z0-9_]*\s*[=:]\s*)\S+"
        ),
    ),
]


def redact(text: str) -> str:
    """Replace common secret shapes with ``«REDACTED:<kind>»``."""
    if not text:
        return text
    out = text
    for kind, pat in _PATTERNS:
        if kind == "env_secret":
            out = pat.sub(rf"\1«REDACTED:{kind}»", out)
        else:
            out = pat.sub(f"«REDACTED:{kind}»", out)
    return out
