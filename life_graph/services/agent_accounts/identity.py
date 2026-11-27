"""An account's identity, kept only masked and as a keyed hash.

The owner may say which login an account is (an email, an org name) so two
rows for the same login are refused and the dashboard can tell them apart.
The raw value is never stored, logged or returned: :func:`mask` keeps enough
to recognise it (``ra***@g***.com``), :func:`identity_hash` is an
HMAC-SHA256 under a key derived from the vault key, so the hash says nothing
to someone holding only the database. Rebuilt from race-app's
``connections/identity-key.ts`` (the owner's code).
"""

from __future__ import annotations

import hashlib
import hmac

from life_graph.services import vault

MAX_IDENTITY_CHARS = 254


def normalize(identity: str) -> str:
    """Trimmed and lower-cased: the same login always hashes the same."""
    return " ".join((identity or "").split()).lower()[:MAX_IDENTITY_CHARS]


def _mask_part(part: str, keep: int) -> str:
    if not part:
        return ""
    return part[:keep] + "***" if len(part) > keep else part[:1] + "***"


def mask(identity: str) -> str | None:
    """``rajasekar@gmail.com`` -> ``ra***@g***.com``; a non-email keeps 2 chars."""
    value = normalize(identity)
    if not value:
        return None
    if "@" in value:
        local, _, domain = value.partition("@")
        host, dot, tld = domain.rpartition(".")
        domain_masked = f"{_mask_part(host, 1)}{dot}{tld}" if dot else _mask_part(domain, 1)
        return f"{_mask_part(local, 2)}@{domain_masked}"
    return _mask_part(value, 2)


def identity_hash(tenant_id: str, driver: str, identity: str, key: bytes | None = None) -> str:
    """Keyed hash of the normalized identity, scoped to tenant and driver."""
    if key is None:
        key = vault.derived_key("agent-account-identity")
    message = f"{tenant_id}\0{driver}\0{normalize(identity)}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()
