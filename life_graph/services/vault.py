"""The vault: store a secret once, hand around a ``vault://`` handle instead.

The agent that logs into a bank or fills a payment form needs real
credentials. Nothing else does — not the plan it follows, not the tool call it
makes, not its transcript, not a log line, not the dashboard. So the owner
puts the secret here once and everything downstream carries only
``vault://<handle>``, which is useless on its own:

* the value is stored encrypted (AES-256-GCM, key from
  ``LIFE_GRAPH_VAULT_KEY`` or ``settings.vault_key_file``), with
  ``tenant:handle`` as additional authenticated data — a row copied to
  another tenant, or a handle swapped between rows, no longer decrypts;
* :func:`resolve_for_origin` is the *only* way back to plaintext, and it
  refuses any origin the owner did not list for that secret, so a handle that
  leaks into the wrong page yields nothing;
* ``one_use`` secrets (an OTP, a one-off payment authorisation) are spent on
  first resolve and refused afterwards.

Everything else here is metadata-only on purpose: :func:`to_dict` is what the
API returns and it has no field that could carry a value. Resolution happens
in-process, in the filler, and is never an endpoint.

Tenant-scoped like the rest of the system: lookups filter by ``tenant_id``
(``get_scoped`` for id lookups), and :func:`resolve_for_origin` re-checks the
row's tenant before decrypting, so a handle alone never crosses tenants.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import pathlib
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.core.tenant import get_scoped
from life_graph.models.vault import VaultSecret

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: What a handle looks like outside the vault.
SCHEME = "vault://"

#: Hints for the filler. Not enforced — the core stays schema-less — but a
#: value outside this set is almost always a typo, so it is rejected.
SECRET_TYPES = frozenset({"generic", "password", "otp", "card", "token", "note"})

_KEY_BYTES = 32
_NONCE_BYTES = 12


# ── Errors ─────────────────────────────────────────────
# Separate types because the caller treats them differently: a mismatched
# origin is a bug or an attack worth surfacing, a spent one-use secret is
# ordinary (ask the owner for a new OTP).


class VaultError(Exception):
    """Base class for every vault refusal."""


class SecretNotFoundError(VaultError):
    """No such handle for this tenant (or it has been revoked)."""


class OriginNotAllowedError(VaultError):
    """This secret may not be sent to that origin."""


class SecretSpentError(VaultError):
    """A one-use secret that has already been resolved once."""


class VaultKeyMissingError(VaultError):
    """No encryption key is configured and none could be created."""


# ── Key handling ───────────────────────────────────────

_key_cache: bytes | None = None


def _decode_key(raw: str) -> bytes:
    """A configured key as 32 raw bytes, accepting base64 or hex."""
    raw = raw.strip()
    padded = raw + "=" * (-len(raw) % 4)  # a key pasted without padding still works
    candidates = (
        (base64.urlsafe_b64decode, padded),
        (base64.b64decode, padded),
        (bytes.fromhex, raw),
    )
    for decode, text in candidates:
        try:
            key = decode(text)
        except (binascii.Error, ValueError):
            continue
        if len(key) == _KEY_BYTES:
            return key
    raise VaultKeyMissingError(
        f"vault key must decode to {_KEY_BYTES} bytes (urlsafe base64 or hex); "
        'generate one with: python -c "import base64,os;'
        'print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
    )


def _key() -> bytes:
    """The vault key: the setting, else the key file, else a fresh key file.

    Generating on first use is what makes a self-host work without ceremony;
    the file is 0600 and outside the repo. It is cached because every resolve
    would otherwise read it.
    """
    global _key_cache
    if _key_cache is not None:
        return _key_cache
    configured = settings.vault_key or os.environ.get("LIFE_GRAPH_VAULT_KEY", "")
    if configured:
        _key_cache = _decode_key(configured)
        return _key_cache
    path = pathlib.Path(settings.vault_key_file).expanduser()
    if path.exists():
        _key_cache = _decode_key(path.read_text(encoding="utf-8"))
        return _key_cache
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(_KEY_BYTES)
        # Create 0600 first, then write: never readable by anyone else, not
        # even for the moment between write and chmod.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(base64.urlsafe_b64encode(key).decode())
    except OSError as exc:
        raise VaultKeyMissingError(
            f"no vault key: set LIFE_GRAPH_VAULT_KEY or make {path} writable ({exc})"
        ) from exc
    logger.warning(
        "Generated a new vault key at %s — back it up; losing it loses the secrets", path
    )
    _key_cache = key
    return key


def reset_key_cache() -> None:
    """Forget the cached key (tests, and after rotating the setting)."""
    global _key_cache
    _key_cache = None


def _aad(tenant_id: str, handle: str) -> bytes:
    """What the ciphertext is bound to: this tenant, this handle."""
    return f"{tenant_id}:{handle}".encode()


def _cipher():  # noqa: ANN202 - cryptography's AESGCM, imported lazily
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(_key())


def encrypt(tenant_id: str, handle: str, value: str) -> bytes:
    """``nonce || ciphertext`` for *value*, bound to *tenant_id* and *handle*."""
    nonce = secrets.token_bytes(_NONCE_BYTES)
    return nonce + _cipher().encrypt(nonce, value.encode(), _aad(tenant_id, handle))


def decrypt(tenant_id: str, handle: str, blob: bytes) -> str:
    """The plaintext of *blob*, or :class:`SecretNotFoundError` if it is not ours.

    A wrong tenant, a wrong handle, a blank value left by a revoke and a
    truncated blob all land here; none of them says which, because a caller
    holding a handle is not entitled to learn why it failed.
    """
    if not blob or len(blob) <= _NONCE_BYTES:
        raise SecretNotFoundError("secret not found")
    try:
        return (
            _cipher()
            .decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], _aad(tenant_id, handle))
            .decode()
        )
    except Exception as exc:  # InvalidTag, UnicodeDecodeError — same answer
        raise SecretNotFoundError("secret not found") from exc


# ── Origins ────────────────────────────────────────────


def normalize_origin(value: str) -> str:
    """An origin as ``scheme://host[:port]``, lowercased.

    The agent reports a page's origin in several shapes ("HDFC.com",
    "https://hdfc.com/", "https://hdfc.com/login?x=1"); the owner types a host.
    Both end up the same string so a match is a string comparison. A bare host
    is assumed https: plaintext http is not something to guess into.
    """
    text = (value or "").strip().lower()
    if not text:
        return ""
    scheme, _, rest = text.partition("://")
    if not rest:
        scheme, rest = "https", scheme
    host = rest.split("/", 1)[0].strip()
    return f"{scheme}://{host}" if host else ""


def origin_allowed(allowed: list[str] | None, target: str) -> bool:
    """Whether *target* is one of *allowed*.

    An entry is a host or a full origin, and its host may lead with ``*.`` to
    cover subdomains: ``*.bank.com`` matches ``login.bank.com`` and
    ``bank.com`` itself. An entry written without a scheme matches **https
    only** — a secret is not typed into a plaintext page on a guess; the owner
    who wants that writes ``http://…`` explicitly.

    An empty list allows nothing: a secret with no named site has no site it
    may go to. ``*`` alone is not a pattern — see :func:`store`.
    """
    target = normalize_origin(target)
    if not target or not allowed:
        return False
    target_scheme, _, target_host = target.partition("://")
    for entry in allowed:
        pattern = (entry or "").strip().lower()
        if not pattern:
            continue
        if "://" in pattern:
            scheme, _, host = pattern.partition("://")
        else:
            scheme, host = "https", pattern
        host = host.split("/", 1)[0]
        if scheme != target_scheme:
            continue
        if host.startswith("*."):
            suffix = host[2:]
            if suffix and (target_host == suffix or target_host.endswith("." + suffix)):
                return True
        elif host == target_host:
            return True
    return False


def _clean_origins(origins: list[str] | None) -> list[str]:
    """Origins as stored: trimmed, lowercased, de-duplicated, order kept.

    ``*`` is refused. A vault secret names where it may go; "anywhere" is the
    one answer that makes the handle as dangerous as the secret.
    """
    cleaned: list[str] = []
    for raw in origins or []:
        entry = (raw or "").strip().lower()
        if not entry:
            continue
        if entry in {"*", "*.", "*://*", "https://*"}:
            raise VaultError("'*' is not an allowed origin — name the sites this secret may go to")
        normalized = entry if entry.startswith("*.") else normalize_origin(entry)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


# ── Store, list, revoke ────────────────────────────────


def new_handle() -> str:
    """A fresh opaque handle. Random, so it says nothing about the secret."""
    return secrets.token_urlsafe(24)


def handle_uri(row: VaultSecret) -> str:
    """The ``vault://`` form of a row's handle — what callers pass around."""
    return f"{SCHEME}{row.handle}"


def parse_handle(handle: str) -> str:
    """The bare token from ``vault://token`` (or from a bare token).

    Raises:
        SecretNotFoundError: nothing usable was given.
    """
    token = (handle or "").strip()
    if token.startswith(SCHEME):
        token = token[len(SCHEME) :]
    token = token.strip().strip("/")
    if not token or len(token) > 64:
        raise SecretNotFoundError("secret not found")
    return token


async def store(
    session: AsyncSession,
    tenant_id: str,
    label: str,
    value: str,
    allowed_origins: list[str] | None = None,
    secret_type: str = "generic",
    one_use: bool = False,
) -> VaultSecret:
    """Encrypt *value* and return its row. The caller commits.

    Raises:
        VaultError: no value, no label, no allowed origin, or an unknown type.
    """
    label = (label or "").strip()[:120]
    if not label:
        raise VaultError("a secret needs a label")
    if not value:
        raise VaultError("a secret needs a value")
    if secret_type not in SECRET_TYPES:
        raise VaultError(f"unknown secret_type {secret_type!r}; one of {sorted(SECRET_TYPES)}")
    origins = _clean_origins(allowed_origins)
    if not origins:
        raise VaultError("name at least one origin this secret may be used on")
    handle = new_handle()
    row = VaultSecret(
        tenant_id=tenant_id,
        handle=handle,
        label=label,
        secret_type=secret_type,
        allowed_origins=origins,
        encrypted_value=encrypt(tenant_id, handle, value),
        one_use=one_use,
    )
    session.add(row)
    await session.flush()
    # Label and origins only: the point of the vault is that this line is safe.
    logger.info(
        "Vault: stored %s (%s, one_use=%s) for %s on %s",
        label,
        secret_type,
        one_use,
        tenant_id,
        ",".join(origins),
    )
    return row


def to_dict(row: VaultSecret) -> dict[str, Any]:
    """A secret as the API shows it: metadata, and no path to the value.

    There is deliberately no ``value``, no ``encrypted_value`` and no length —
    a length narrows a guess at a PIN. Everything here is safe to log.
    """
    return {
        "id": str(row.id),
        "handle": handle_uri(row),
        "label": row.label,
        "secret_type": row.secret_type,
        "allowed_origins": list(row.allowed_origins or []),
        "one_use": row.one_use,
        "used_at": row.used_at.isoformat() if row.used_at else None,
        "use_count": row.use_count,
        "last_used_origin": row.last_used_origin,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "spent": bool(row.one_use and row.used_at is not None),
    }


async def list_secrets(
    session: AsyncSession, tenant_id: str, include_revoked: bool = False
) -> list[VaultSecret]:
    """This tenant's secrets, newest first."""
    stmt = select(VaultSecret).where(VaultSecret.tenant_id == tenant_id)
    if not include_revoked:
        stmt = stmt.where(VaultSecret.revoked_at.is_(None))
    stmt = stmt.order_by(VaultSecret.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get(session: AsyncSession, tenant_id: str, secret_id: Any) -> VaultSecret:
    """One secret by id, refusing another tenant's row.

    Raises:
        SecretNotFoundError: no such row, or it belongs to someone else.
    """
    try:
        row = await get_scoped(session, VaultSecret, secret_id, tenant_id)
    except LookupError as exc:
        raise SecretNotFoundError("secret not found") from exc
    if row is None:
        raise SecretNotFoundError("secret not found")
    return row


async def revoke(session: AsyncSession, tenant_id: str, secret_id: Any) -> VaultSecret:
    """Revoke a secret and blank its ciphertext. The caller commits.

    The row stays (like ``devices.revoked_at``) so its history reads, but the
    value is destroyed rather than merely flagged: a revoked password should
    not be recoverable from tonight's backup.
    """
    row = await get(session, tenant_id, secret_id)
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        row.encrypted_value = b""
        await session.flush()
        logger.info("Vault: revoked %s (%s) for %s", row.label, row.id, tenant_id)
    return row


# ── The one way back to plaintext ──────────────────────


async def resolve_for_origin(
    session: AsyncSession, tenant_id: str, handle: str, target_origin: str
) -> str:
    """The plaintext behind *handle*, if it may be sent to *target_origin*.

    Every check is here rather than spread over the callers, because a filler
    that forgot one would type a bank password into whatever page it was on.
    The caller commits — a one-use secret is only spent if the transaction it
    was used in commits.

    Raises:
        SecretNotFoundError: unknown or revoked handle, or another tenant's.
        OriginNotAllowedError: the owner did not list this origin for this secret.
            Checked before the secret is spent, so a wrong origin cannot burn
            a one-use secret.
        SecretSpentError: a one-use secret that has already been resolved.
    """
    token = parse_handle(handle)
    origin = normalize_origin(target_origin)
    if not origin:
        raise OriginNotAllowedError("no target origin given")
    stmt = (
        select(VaultSecret)
        .where(VaultSecret.tenant_id == tenant_id, VaultSecret.handle == token)
        .with_for_update()  # one-use: two concurrent resolves must not both win
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    # The tenant is in the query; re-checked because this function is the last
    # gate before plaintext and the query may be built differently one day.
    if row is None or row.tenant_id != tenant_id or row.revoked_at is not None:
        raise SecretNotFoundError("secret not found")
    if not origin_allowed(row.allowed_origins, origin):
        logger.warning(
            "Vault: refused %s (%s) for %s — %s is not an allowed origin",
            row.label,
            row.id,
            tenant_id,
            origin,
        )
        raise OriginNotAllowedError(f"{row.label} may not be used on {origin}")
    if row.one_use and row.used_at is not None:
        raise SecretSpentError(f"{row.label} was a one-use secret and has been used")
    value = decrypt(tenant_id, row.handle, row.encrypted_value)
    now = datetime.now(UTC)
    row.used_at = now
    row.use_count = (row.use_count or 0) + 1
    row.last_used_origin = origin[:255]
    await session.flush()
    logger.info("Vault: resolved %s (%s) for %s on %s", row.label, row.id, tenant_id, origin)
    return value
