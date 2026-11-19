"""Best-effort secret redaction for external transcript content.

Applied to every turn's text before fact extraction and to the raw thread
before archiving, so credentials never become memories or land in MinIO.
This is deliberately conservative-but-present: it removes the common
high-risk secret shapes, not every conceivable one.

The standalone token shapes are the canonical list in
:data:`life_graph.core.redaction.SECRET_SHAPES`; only the contextual patterns
(bearer, ``ENV_SECRET=``) are specific to this redactor.
"""

from __future__ import annotations

import re

from life_graph.core.redaction import SECRET_SHAPES, URL_PASSWORD

# Kinds whose replacement keeps the first group (the "KEY=" / "scheme://user:"
# prefix) and redacts only what follows it.
_KEEP_PREFIX = frozenset({"env_secret", "url_password"})

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    *[(s.kind, s.pattern) for s in SECRET_SHAPES if s.kind == "pem"],
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}")),
    *[(s.kind, s.pattern) for s in SECRET_SHAPES if s.kind != "pem"],
    ("url_password", URL_PASSWORD),
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
        if kind in _KEEP_PREFIX:
            out = pat.sub(rf"\1«REDACTED:{kind}»", out)
        else:
            out = pat.sub(f"«REDACTED:{kind}»", out)
    return out
