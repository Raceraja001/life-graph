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

The key, and what is yours to look after
----------------------------------------

**The cipher.** AES-256-GCM, a fresh 12-byte nonce per encryption, stored as
``nonce || ciphertext||tag`` in ``vault_secrets.encrypted_value``. The AAD is
``f"{tenant_id}:{handle}"``, so a row moved to another tenant or re-pointed at
another handle authenticates as the forgery it is and fails to decrypt — see
:func:`encrypt` and :func:`decrypt`.

**Provisioning.** ``LIFE_GRAPH_VAULT_KEY`` (or ``settings.vault_key``): 32
bytes as urlsafe base64 or hex. Generate one with::

    python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

With nothing configured, :func:`_key` reads ``settings.vault_key_file``
(``~/.config/life-graph/vault.key``) and, if that does not exist either,
*generates* a key there at mode 0600 and logs a warning. That is what makes a
self-host work without ceremony; it also means the key lives on one disk until
somebody backs it up.

**Rotation.** There is deliberately no bulk re-wrap function. A tool that
decrypted every row at once would be a second way back to plaintext, and
:func:`resolve_for_origin` being the only one is the property the rest of this
module is built on. Rotating therefore means re-entering secrets: set the new
key, then revoke and re-store each secret (the handles change, so anything
holding an old ``vault://`` handle is updated too — which is the honest
consequence of a rotation, not a bug). Changing the key without that leaves
old rows undecryptable; they refuse as "secret not found", which is the
correct answer but not an obvious one, so rotate deliberately.

**What is operational, not ours.** Backing up the key separately from the
database (a backup holding both is a backup holding the plaintext); keeping it
out of the repo, the image and the logs; restoring it before restoring a dump;
and accepting that losing it loses every secret, by design. ``docs/OPERATIONS.md``
has the runbook.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import logging
import os
import pathlib
import re
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.orm.attributes import set_committed_value

from life_graph.config import settings
from life_graph.core.tenant import get_scoped
from life_graph.models.vault import VaultSecret
from life_graph.services.destination_validator import parse_host_address

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


class MalformedOriginError(VaultError):
    """The origin given is not a usable ``scheme://host[:port]``.

    Distinct from :class:`OriginNotAllowedError`: that one is a well-formed
    origin the owner did not list, this one is an origin the vault refuses to
    guess at — userinfo, a non-web scheme, an impossible port. Guessing is how
    ``https://bank.com@evil.io`` becomes "the bank".
    """


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
    would otherwise read it — so a key changed underneath a running process
    does not take effect until a restart or :func:`reset_key_cache`.

    The precedence is deliberate: an operator who sets the env var gets it
    even if a key file is lying around from an earlier run. Provisioning,
    rotation and what remains an operational responsibility are in this
    module's docstring and in ``docs/OPERATIONS.md``.
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
    holding a handle is not entitled to learn why it failed. The message is
    the same fixed string in every case, and no branch puts plaintext — or a
    length, or a byte of it — into an exception a traceback would print.
    """
    if not blob or len(blob) <= _NONCE_BYTES:
        raise SecretNotFoundError("secret not found")
    try:
        raw = _cipher().decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], _aad(tenant_id, handle))
    except Exception as exc:  # InvalidTag: wrong key, wrong AAD, tampered blob
        raise SecretNotFoundError("secret not found") from exc
    try:
        return raw.decode()
    except UnicodeDecodeError:
        # Chained to nothing on purpose: a UnicodeDecodeError quotes the byte
        # it tripped on, and that byte is plaintext.
        raise SecretNotFoundError("secret not found") from None


# ── Origins ────────────────────────────────────────────
#
# An origin is the whole of the vault's authorisation model, so it is parsed
# rather than split on characters. The forms below all read as "the bank" to a
# person and resolve somewhere else, and a naive ``partition("://")`` lets
# every one of them through:
#
#   https://bank.com@evil.io     userinfo: the host is evil.io
#   https://bank.com\@evil.io    a browser reads ``\`` as ``/``; host is evil.io
#   file:///etc/passwd           not a web origin at all
#   javascript:alert(1)          a scheme that is code, not a place
#   https://bank.com:99999       not a port, so not an origin
#   https://bank.com.evil.io     a different site that ends in a familiar name
#
# Everything here is therefore decided from a real parse, and anything that
# does not come out as exactly ``scheme://host[:port]`` is a
# :class:`MalformedOriginError` rather than a best guess.


#: The only schemes a secret may travel to. ``file:``, ``data:``,
#: ``javascript:`` and friends are not places, and ``ftp:`` is not one a
#: password is typed into.
ORIGIN_SCHEMES = frozenset({"http", "https"})

#: Longer than any real origin (``last_used_origin`` is 255 too), and short
#: enough that a megabyte of "origin" is refused before it is parsed.
MAX_ORIGIN_CHARS = 255

#: Control characters, spaces and the Unicode blanks that get pasted in from a
#: browser bar. Any of them means the authority was never well-formed.
_BLANK_CHARS = re.compile(r"[\x00-\x20\x7f-\x9f   -‏ -  　﻿]")

#: ``scheme:rest`` — matched by hand because :func:`urlsplit` reads the host of
#: ``bank.com:8443`` as a *scheme*, which is how a port becomes a protocol.
_SCHEME_PREFIX = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*):(?P<rest>.*)$", re.DOTALL)

#: What a hostname may be made of, once lowercased and IDNA-encoded.
_HOSTNAME_CHARS = re.compile(r"^[a-z0-9._-]+$")

_DIGITS = re.compile(r"^\d+$")

#: The port a scheme does not need to name.
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _with_scheme(text: str) -> str:
    """*text* as something :func:`urlsplit` will read as an authority.

    A bare host ("bank.com", "localhost:3000") is assumed **https**: plaintext
    http is not a thing to guess into. A real scheme is kept as written so the
    check below can refuse it by name.
    """
    if text.startswith("//"):
        return "https:" + text  # protocol-relative
    match = _SCHEME_PREFIX.match(text)
    if match is None:
        return "https://" + text
    scheme, rest = match.group("scheme").lower(), match.group("rest")
    if rest.startswith("//"):
        return text  # http://…, file://…, ftp://… — judged by scheme below
    if _DIGITS.match(rest.split("/", 1)[0]):
        return "https://" + text  # "bank.com:8443", "localhost:3000"
    if scheme in ORIGIN_SCHEMES:
        raise MalformedOriginError("an origin is written scheme://host, with the slashes")
    # "javascript:alert(1)", "data:text/html,…", "mailto:a@b": a scheme whose
    # body is not an authority, so there is no origin here to authorise.
    raise MalformedOriginError(f"{scheme[:20]!r} is not a web scheme; use http or https")


def _canonical_host(hostname: str, *, bracketed: bool, allow_wildcard: bool) -> str:
    """A hostname as one spelling: lowercase, no trailing dot, IDNA, no tricks.

    Addresses are canonicalised through
    :func:`~life_graph.services.destination_validator.parse_host_address`, so
    ``0x7f.1`` and ``2130706433`` compare equal to ``127.0.0.1`` instead of
    looking like three different hosts.
    """
    host = hostname.strip().lower().rstrip(".")  # a trailing dot is the DNS root
    if not host:
        raise MalformedOriginError("an origin needs a host")
    if bracketed or ":" in host:
        try:
            return f"[{ipaddress.ip_address(host).compressed}]"
        except ValueError as exc:
            raise MalformedOriginError("that is not a usable IPv6 address") from exc
    prefix = ""
    if host.startswith("*."):
        if not allow_wildcard:
            raise MalformedOriginError("'*' belongs in an allowed origin, not in a page's origin")
        prefix, host = "*.", host[2:]
        if not host:
            raise MalformedOriginError("'*.' alone is every site — name the domain behind it")
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii").lower()
        except (UnicodeError, ValueError) as exc:
            raise MalformedOriginError("that hostname is not a usable name") from exc
    address = parse_host_address(host)
    if address is not None:
        if prefix:
            raise MalformedOriginError("an address has no subdomains to wildcard")
        return address.compressed
    if not _HOSTNAME_CHARS.match(host):
        raise MalformedOriginError("that hostname has characters a host may not have")
    if any(not label or len(label) > 63 for label in host.split(".")):
        raise MalformedOriginError("that hostname is malformed")
    return prefix + host


def _parse_origin(
    value: str, *, allow_wildcard: bool = False, origin_only: bool = False
) -> tuple[str, str, int | None] | None:
    """``(scheme, host, port)`` for *value*, or ``None`` if it is blank.

    *port* is ``None`` when the scheme's default was used, so one origin has
    one spelling: ``https://bank.com:443`` and ``https://bank.com`` are the
    same place and compare equal.

    Raises:
        MalformedOriginError: anything that is not exactly one web origin.
    """
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > MAX_ORIGIN_CHARS:
        raise MalformedOriginError(f"an origin is not longer than {MAX_ORIGIN_CHARS} characters")
    if _BLANK_CHARS.search(text):
        raise MalformedOriginError("an origin has no spaces or control characters in it")
    try:
        parts = urlsplit(_with_scheme(text))
    except ValueError as exc:
        raise MalformedOriginError("that is not a usable origin") from exc

    scheme = parts.scheme.lower()
    if scheme not in ORIGIN_SCHEMES:
        raise MalformedOriginError(
            f"{scheme[:20] or 'none'!r} is not a web scheme; use http or https"
        )
    if "@" in parts.netloc or parts.username or parts.password:
        # ``https://bank.com@evil.io`` reads as the bank and resolves evil.io.
        raise MalformedOriginError("an origin may not carry a user:password@ prefix")
    if "\\" in parts.netloc:
        # A browser treats ``\`` as ``/``, so the host ends earlier than it reads.
        raise MalformedOriginError("an origin may not contain a backslash")
    try:
        hostname, port = parts.hostname, parts.port
    except ValueError as exc:  # non-numeric or out of range
        raise MalformedOriginError("an origin's port is a number from 1 to 65535") from exc
    if port is not None and not 1 <= port <= 65535:
        raise MalformedOriginError("an origin's port is a number from 1 to 65535")
    if origin_only and (parts.path.strip("/") or parts.query or parts.fragment):
        # Where an origin is what is meant, a path is either a mistake or a
        # claim this secret is scoped to it — and the vault scopes by origin,
        # so the claim would be false. ``https://bank.com/#@evil.io`` is the
        # deceptive version of the same thing.
        raise MalformedOriginError(
            "an origin names a site, not a page — drop everything after the host"
        )
    host = _canonical_host(
        hostname or "", bracketed="[" in parts.netloc, allow_wildcard=allow_wildcard
    )
    return scheme, host, None if port == _DEFAULT_PORTS[scheme] else port


def _format_origin(scheme: str, host: str, port: int | None) -> str:
    """``scheme://host[:port]`` — the one spelling everything compares."""
    return f"{scheme}://{host}" if port is None else f"{scheme}://{host}:{port}"


def normalize_origin(value: str, *, origin_only: bool = False) -> str:
    """An origin as ``scheme://host[:port]``, canonical, or ``""`` if blank.

    The agent reports a page's origin in several shapes ("HDFC.com",
    "https://hdfc.com/", "https://hdfc.com/login?x=1"); the owner types a
    host. Both end up the same string so a match is a string comparison. A
    bare host is assumed https: plaintext http is not something to guess into.
    A default port is dropped (``https://bank.com:443`` → ``https://bank.com``)
    and a non-default one is kept, because it is part of the origin.

    A path, query or fragment is stripped for a page's origin — that is the
    shape a browser reports. Pass *origin_only* where an origin is the whole
    of the input (an owner's allow-list entry) and a path can only mislead;
    then it is refused instead.

    Raises:
        MalformedOriginError: userinfo, a non-web scheme, a bad port, a
            hostname that is not one, or anything else that is not an origin.
            Blank input is not an error — it is ``""``, which no allow-list
            matches.
    """
    parsed = _parse_origin(value, origin_only=origin_only)
    return "" if parsed is None else _format_origin(*parsed)


def origin_allowed(allowed: list[str] | None, target: str) -> bool:
    """Whether *target* is one of *allowed*.

    An entry is a host or a full origin, and its host may lead with ``*.`` to
    cover subdomains: ``*.bank.com`` matches ``login.bank.com``,
    ``a.b.bank.com`` and ``bank.com`` itself, and never ``notbank.com`` or
    ``bank.com.evil.io`` — the match is on whole labels, so the dot is a
    boundary and not a character that happens to be there.

    Scheme and port are part of the comparison, both canonical. An entry
    written without a scheme matches **https only** — a secret is not typed
    into a plaintext page on a guess; the owner who wants that writes
    ``http://…`` explicitly. An entry without a port matches only the
    scheme's default port, so ``https://bank.com`` does not cover
    ``https://bank.com:8443``, and ``https://*.bank.com:8443`` covers nothing
    else.

    Fails closed throughout: a target that does not parse, an empty list and
    an entry that does not parse all allow nothing. ``*`` alone is not a
    pattern — see :func:`store`.
    """
    try:
        parsed = _parse_origin(target)
    except MalformedOriginError:
        return False
    if parsed is None or not allowed:
        return False
    scheme, host, port = parsed
    for entry in allowed:
        try:
            pattern = _parse_origin(entry, allow_wildcard=True, origin_only=True)
        except MalformedOriginError:
            continue  # an entry that is not an origin names no site
        if pattern is None:
            continue
        entry_scheme, entry_host, entry_port = pattern
        if entry_scheme != scheme or entry_port != port:
            continue
        if entry_host.startswith("*."):
            suffix = entry_host[2:]
            if host == suffix or host.endswith(f".{suffix}"):
                return True
        elif entry_host == host:
            return True
    return False


def _clean_origins(origins: list[str] | None) -> list[str]:
    """Origins as stored: canonical, de-duplicated, order kept.

    ``*`` is refused. A vault secret names where it may go; "anywhere" is the
    one answer that makes the handle as dangerous as the secret. So is a path:
    the vault authorises an origin, and an entry that looked path-scoped would
    promise something it does not enforce.

    Raises:
        MalformedOriginError: an entry that is not a usable origin.
        VaultError: an entry that means "anywhere".
    """
    cleaned: list[str] = []
    for raw in origins or []:
        entry = (raw or "").strip()
        if not entry:
            continue
        if entry.lower() in {"*", "*.", "*://*", "https://*", "http://*", "*.*"}:
            raise VaultError("'*' is not an allowed origin — name the sites this secret may go to")
        parsed = _parse_origin(entry, allow_wildcard=True, origin_only=True)
        normalized = "" if parsed is None else _format_origin(*parsed)
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

    The order is the point, and it is: **exists → is ours → not revoked →
    origin allowed → claimed → decrypted.** A wrong origin therefore cannot
    burn a one-use secret, and nothing is decrypted until the row has been
    claimed, so a resolve that loses the claim never holds the plaintext at
    all.

    The claim is a single conditional ``UPDATE`` (``used_at IS NULL`` in the
    ``WHERE`` for a one-use secret) and the row is locked ``FOR UPDATE`` on
    the way in. Two of them is deliberate: the lock serialises the ordinary
    case, and the conditional update is what still holds if the lock does not
    — a different isolation level, a read replica, a session that was not in a
    transaction. ``rowcount != 1`` means somebody else got there first.

    Raises:
        SecretNotFoundError: unknown or revoked handle, or another tenant's.
        MalformedOriginError: *target_origin* is not a usable origin.
        OriginNotAllowedError: no origin given, or the owner did not list this
            one for this secret. Checked before the secret is spent.
        SecretSpentError: a one-use secret that has already been resolved —
            including by a request racing this one.
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

    # Origin first: before the claim, before the decrypt.
    if not origin_allowed(row.allowed_origins, origin):
        logger.warning(
            "Vault: refused %s (%s) for %s — %s is not an allowed origin",
            row.label,
            row.id,
            tenant_id,
            origin,
        )
        raise OriginNotAllowedError(f"{row.label} may not be used on {origin}")

    now = datetime.now(UTC)
    used_origin = origin[:255]
    claim = [
        VaultSecret.id == row.id,
        VaultSecret.tenant_id == tenant_id,
        VaultSecret.revoked_at.is_(None),
    ]
    if row.one_use:
        if row.used_at is not None:
            raise SecretSpentError(f"{row.label} was a one-use secret and has been used")
        claim.append(VaultSecret.used_at.is_(None))
    claimed = await session.execute(
        update(VaultSecret)
        .where(*claim)
        .values(
            used_at=now,
            # Computed in the database, so a concurrent resolve of a reusable
            # secret cannot overwrite the other one's count with its own.
            use_count=VaultSecret.use_count + 1,
            last_used_origin=used_origin,
        )
        .execution_options(synchronize_session=False)
    )
    if (claimed.rowcount or 0) != 1:
        if row.one_use:
            logger.warning(
                "Vault: %s (%s) for %s was claimed by another request on %s",
                row.label,
                row.id,
                tenant_id,
                origin,
            )
            raise SecretSpentError(f"{row.label} was a one-use secret and has been used")
        # Revoked between the select and the update.
        raise SecretNotFoundError("secret not found")
    # The loaded row now says what the database says. ``set_committed_value``
    # rather than assignment: the claim above *is* the write, and a dirty
    # attribute here would have the ORM flush a second, racier UPDATE.
    set_committed_value(row, "used_at", now)
    set_committed_value(row, "use_count", (row.use_count or 0) + 1)
    set_committed_value(row, "last_used_origin", used_origin)

    value = decrypt(tenant_id, row.handle, row.encrypted_value)
    # Label, id, tenant and origin — never the value, and never its length.
    logger.info("Vault: resolved %s (%s) for %s on %s", row.label, row.id, tenant_id, origin)
    return value
