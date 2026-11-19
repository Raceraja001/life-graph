"""Secret redaction for observation captures.

Tool-exhaust observations (capture spine) may contain secrets in command
arguments — API keys, tokens, passwords. Redact obvious secrets before any
storage. Best-effort: pattern-based, tuned to avoid storing credentials, not
a guarantee against every exfiltration shape.
"""

from __future__ import annotations

import json
import re
from typing import Any, NamedTuple

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


class SecretShape(NamedTuple):
    """One standalone credential format.

    ``high_confidence`` marks formats with a distinctive prefix that has no
    other legitimate reason to appear in text. The dev-agent's
    ``no_secrets_in_diff`` gate uses only those; the redactors use them all.
    """

    kind: str
    pattern: re.Pattern[str]
    high_confidence: bool


# The ONE canonical list of standalone secret shapes — the union of what
# core/redaction.py, services/redaction.py and services/dev/verifiers.py each
# used to keep on their own (audit H1, 2026-11-19: the old ``sk-`` pattern
# stopped at the first hyphen, so sk-ant-/sk-proj-/sk-or-v1- keys leaked).
# Order matters for the labelled redactor: specific shapes before generic
# ``sk-``. ``clients/desktop/redact.py`` mirrors these patterns by hand (it
# cannot import the backend); a unit test keeps the two identical.
SECRET_SHAPES: tuple[SecretShape, ...] = (
    SecretShape(
        "pem",
        # The END line is optional: a capture clipped mid-key still loses the
        # body (everything base64-looking after the BEGIN line).
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            r"(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|[A-Za-z0-9+/=\s\\]*)"
        ),
        True,
    ),
    SecretShape("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), True),
    SecretShape("openrouter_key", re.compile(r"\bsk-or-[A-Za-z0-9_\-]{20,}"), True),
    SecretShape("openai_project_key", re.compile(r"\bsk-proj-[A-Za-z0-9_\-]{20,}"), True),
    # Generic sk- keys. ``\b`` keeps "risk-assessment-…"/"task-…" out.
    SecretShape("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), False),
    SecretShape("stripe_live_key", re.compile(r"\bsk_live_[A-Za-z0-9]{24,}"), True),
    SecretShape(
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
        True,
    ),
    SecretShape("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}"), True),
    SecretShape("slack_token", re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"), True),
    SecretShape("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), True),
    SecretShape("google_key", re.compile(r"AIza[0-9A-Za-z\-_]{35,}"), True),
    SecretShape("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36}"), True),
    SecretShape("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]{8,}"), False),
)

# Standalone token shapes worth redacting wherever they appear.
_TOKEN_SHAPES: list[re.Pattern[str]] = [s.pattern for s in SECRET_SHAPES]

# Credentials inside a URL: scheme://user:PASSWORD@host.
URL_PASSWORD = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s@/]+(?=@)")


def redact_secrets(text: str) -> str:
    """Replace secret-looking substrings with ``[REDACTED]``.

    Handles ``key=value`` / ``key: value`` pairs with sensitive-looking
    keys, Bearer/Authorization headers, passwords in URLs, and every
    standalone token shape in :data:`SECRET_SHAPES`.
    """
    if not text:
        return text
    text = _AUTH_HEADER.sub(lambda m: f"{m.group(1)}: {REDACTED}", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = URL_PASSWORD.sub(lambda m: f"{m.group(1)}{REDACTED}", text)
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
