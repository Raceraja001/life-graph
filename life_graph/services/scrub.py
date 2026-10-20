"""Hide personal details in text that is about to leave the machine.

The owner's rule (2026-10-20): personal data is handled by the local model;
other work may go to free cloud models, and personal details are hidden
before anything leaves. The first defence is to never put them in a brief —
a worker's brief is written from only what it needs (services/workers.py).
This is the second: a deterministic pass over every outgoing brief.

Secrets go through :func:`life_graph.services.redaction.redact`; this adds the
personal shapes that matter in India and in general: phone numbers, email
addresses, PAN, Aadhaar, card numbers, bank account numbers and IFSC codes.
Each becomes ``«HIDDEN:<kind>»``. It is a net, not a guarantee: names and
context in free text are not caught here.
"""

from __future__ import annotations

import re

from life_graph.services.redaction import redact

# Order matters: longer, more specific shapes first, so a card number is not
# half-eaten by the account-number rule.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # 13-19 digits, in groups of 4 or straight: payment cards.
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
    # Aadhaar: 12 digits, usually 4-4-4.
    ("aadhaar", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    # PAN: AAAAA9999A.
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    # IFSC: 4 letters, 0, 6 alphanumerics.
    ("ifsc", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    # Indian mobiles (+91 / 0 prefixes) and international numbers.
    ("phone", re.compile(r"(?<![\w+])(?:\+?91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}\b")),
    ("phone", re.compile(r"(?<![\w])\+\d{1,3}[ -]?\(?\d{1,4}\)?(?:[ -]?\d{2,4}){2,4}\b")),
    # Bank account numbers: 9-18 digits standing alone.
    ("account", re.compile(r"(?<![\w.])\d{9,18}(?![\w.])")),
]


def scrub(text: str) -> str:
    """Secrets and personal details replaced with placeholders."""
    if not text:
        return text
    out = redact(text)
    for kind, pattern in _PATTERNS:
        out = pattern.sub(f"«HIDDEN:{kind}»", out)
    return out
