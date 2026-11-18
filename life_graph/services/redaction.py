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
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openrouter_key", re.compile(r"sk-or-[A-Za-z0-9_\-]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}")),
    ("slack_token", re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}")),
    ("url_password", re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s@/]+(?=@)")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google_key", re.compile(r"AIza[0-9A-Za-z\-_]{35,}")),
    (
        "env_secret",
        # Anywhere, not only at a line start: inside a shell command
        # ("export TOKEN=..."), or a JSON-escaped file body ("\\nAPI_KEY=...").
        re.compile(
            r"(?:(?<=^)|(?<=[\s;&|'\"(])|(?<=\\n))((?:export\s+)?[A-Z0-9_]*"
            r"(?:SECRET|TOKEN|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY)[A-Z0-9_]*\s*[=:]\s*)"
            r"[^\s\"',;]+",
            re.M,
        ),
    ),
]


def redact(text: str) -> str:
    """Replace common secret shapes with ``«REDACTED:<kind>»``."""
    if not text:
        return text
    out = text
    for kind, pat in _PATTERNS:
        if kind in ("env_secret", "url_password"):
            out = pat.sub(rf"\1«REDACTED:{kind}»", out)
        else:
            out = pat.sub(f"«REDACTED:{kind}»", out)
    return out
