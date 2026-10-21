"""Phones paired with Jarvis: one-time codes, device tokens, revocation.

docs/design/12_android_app_plan.md (Phase 1). The owner asks for a code in the
dashboard (with the service key); the phone sends it once to
``POST /devices/pair`` and gets a token of its own. That token:

* is stored only as its SHA-256 (``devices.token_hash``) — the table cannot be
  used to sign in, and a token is shown exactly once;
* signs the phone in to the Jarvis endpoints and nothing else
  (api/middleware.py, ``DEVICE_PATH_PREFIX``), as the tenant that paired it;
* stops working the moment the device is revoked.

Pairing happens before the phone has any credential, so its endpoint is open;
:class:`PairingLimiter` caps failed attempts so six digits cannot be guessed.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
CODE_DIGITS = 6
_CACHE_SECONDS = 60.0
_SEEN_EVERY = timedelta(minutes=5)


class PairingError(Exception):
    """The code cannot pair a device. One message for every reason, so a
    caller learns nothing about which codes exist."""

    def __init__(self) -> None:
        super().__init__("That code is not valid. Ask for a new one on your PC.")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_code(session: AsyncSession, tenant_id: str) -> Any:
    """A fresh six-digit code for *tenant_id*; the caller commits."""
    from life_graph.models.assistant import DevicePairingCode

    now = datetime.now(UTC)
    for _ in range(10):
        code = "".join(secrets.choice("0123456789") for _ in range(CODE_DIGITS))
        existing = await session.get(DevicePairingCode, code)
        if existing is None or existing.expires_at < now or existing.used_at is not None:
            if existing is not None:
                await session.delete(existing)
                await session.flush()
            row = DevicePairingCode(code=code, tenant_id=tenant_id, expires_at=now + CODE_TTL)
            session.add(row)
            await session.flush()
            return row
    raise RuntimeError("could not find a free pairing code")


async def redeem(session: AsyncSession, code: str, name: str) -> tuple[Any, str]:
    """Spend *code* and pair a device called *name*: ``(device, token)``.

    The token is returned here and never again. The caller commits.

    Raises:
        PairingError: no such code, already used, or expired.
    """
    from life_graph.models.assistant import Device, DevicePairingCode

    code = (code or "").strip()
    if not code.isdigit() or len(code) != CODE_DIGITS:
        raise PairingError
    row = await session.get(DevicePairingCode, code, with_for_update=True)
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or row.expires_at < now:
        raise PairingError
    row.used_at = now
    token = secrets.token_urlsafe(32)
    device = Device(
        tenant_id=row.tenant_id,
        name=(name or "").strip()[:120] or "Phone",
        token_hash=hash_token(token),
        last_seen_at=now,
    )
    session.add(device)
    await session.flush()
    logger.info("Paired device %s (%s) for tenant %s", device.id, device.name, row.tenant_id)
    return device, token


# token hash -> (expires, tenant_id, device_id); a miss is not cached, so a
# fresh pairing works at once, and revoke() drops the entry.
_cache: dict[str, tuple[float, str, str]] = {}


async def authenticate(token: str) -> tuple[str, str] | None:
    """``(tenant_id, device_id)`` for a live device token, else None."""
    from life_graph.models.assistant import Device
    from life_graph.storage.database import async_session

    if not token or len(token) > 200:
        return None
    digest = hash_token(token)
    hit = _cache.get(digest)
    now = time.monotonic()
    if hit and hit[0] > now:
        return hit[1], hit[2]
    async with async_session() as session:
        device = (
            await session.execute(select(Device).where(Device.token_hash == digest))
        ).scalar_one_or_none()
        if device is None or device.revoked_at is not None:
            _cache.pop(digest, None)
            return None
        seen = datetime.now(UTC)
        if device.last_seen_at is None or seen - device.last_seen_at > _SEEN_EVERY:
            device.last_seen_at = seen
            await session.commit()
        _cache[digest] = (now + _CACHE_SECONDS, device.tenant_id, str(device.id))
        return device.tenant_id, str(device.id)


async def list_devices(session: AsyncSession, tenant_id: str) -> list[Any]:
    from life_graph.models.assistant import Device

    return list(
        (
            await session.execute(
                select(Device)
                .where(Device.tenant_id == tenant_id)
                .order_by(Device.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def revoke(session: AsyncSession, tenant_id: str, device_id: Any) -> bool:
    """Stop the device's token working, at once. False if not this tenant's."""
    from life_graph.models.assistant import Device

    device = await session.get(Device, device_id)
    if device is None or device.tenant_id != tenant_id:
        return False
    if device.revoked_at is None:
        device.revoked_at = datetime.now(UTC)
    for digest in [d for d, v in _cache.items() if v[2] == str(device.id)]:
        _cache.pop(digest, None)
    return True


def to_dict(device: Any) -> dict[str, Any]:
    return {
        "id": str(device.id),
        "name": device.name,
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
    }


class PairingLimiter:
    """Failed pairing attempts, per client and in total, over a sliding window.

    Six digits are a million codes. At most ``per_client`` failures per client
    and ``total`` overall in ``window`` seconds means a guesser gets a few dozen
    tries at a code that lives ten minutes. In memory, per process: the API
    runs as one.
    """

    def __init__(self, per_client: int = 5, total: int = 20, window: float = 600.0) -> None:
        self.per_client, self.total, self.window = per_client, total, window
        self._fails: dict[str, deque[float]] = {}
        self._all: deque[float] = deque()

    def _trim(self, q: deque[float], now: float) -> None:
        while q and q[0] <= now - self.window:
            q.popleft()

    def allowed(self, client: str) -> bool:
        now = time.monotonic()
        self._trim(self._all, now)
        q = self._fails.setdefault(client, deque())
        self._trim(q, now)
        return len(q) < self.per_client and len(self._all) < self.total

    def failed(self, client: str) -> None:
        now = time.monotonic()
        self._fails.setdefault(client, deque()).append(now)
        self._all.append(now)


pairing_limiter = PairingLimiter()
