"""WebSocket endpoint for real-time Life Graph events (Phase B).

Provides a ConnectionManager for tracking active clients, a
broadcast-capable event handler that subscribes to the global
EventBus, and a WebSocket route with API-key authentication.

Usage — add to the FastAPI app directly (not via a router)::

    from life_graph.api.websocket import websocket_endpoint, ws_event_handler
    from life_graph.core.events import event_bus

    app.add_api_websocket_route("/ws", websocket_endpoint)
    event_bus.subscribe_all(ws_event_handler)
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import Query, WebSocket, WebSocketDisconnect

from life_graph.api.auth import extract_api_key, key_may_use_tenant
from life_graph.config import settings
from life_graph.core.events import EventType
from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
from life_graph.storage.redis import get_redis

if TYPE_CHECKING:
    from life_graph.core.events import Event

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage active WebSocket connections.

    Tracks connected clients and provides a broadcast helper
    that sends JSON messages to all of them concurrently.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        if tenant_id not in self._connections:
            self._connections[tenant_id] = set()
        self._connections[tenant_id].add(websocket)
        logger.info(
            "WebSocket connected (tenant=%s, total=%d)",
            tenant_id,
            self.active_count,
        )

    def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Remove a WebSocket connection from the active set."""
        if tenant_id in self._connections:
            self._connections[tenant_id].discard(websocket)
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        logger.info(
            "WebSocket disconnected (tenant=%s, total=%d)",
            tenant_id,
            self.active_count,
        )

    async def broadcast_to_tenant(self, tenant_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients for a specific tenant.

        Failed sends are logged and the dead connection is removed,
        but never prevent delivery to other clients.
        """
        connections = self._connections.get(tenant_id, set())
        if not connections:
            return

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:  # expected: a closed socket raises; it is pruned
                logger.warning("Failed to send to WebSocket, marking dead")
                dead.append(ws)

        for ws in dead:
            connections.discard(ws)
        if not connections:
            self._connections.pop(tenant_id, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients, of every tenant.

        Only for what belongs to no tenant (``GLOBAL_EVENT_TYPES``). Failed sends are logged and the dead connection is removed,
        but never prevent delivery to other clients.
        """
        dead: list[tuple[str, WebSocket]] = []
        for tenant_id, connections in self._connections.items():
            for ws in connections:
                try:
                    await ws.send_json(message)
                except Exception:  # expected: a closed socket raises; it is pruned
                    logger.warning("Failed to send to WebSocket, marking dead")
                    dead.append((tenant_id, ws))

        for tenant_id, ws in dead:
            if tenant_id in self._connections:
                self._connections[tenant_id].discard(ws)
                if not self._connections[tenant_id]:
                    del self._connections[tenant_id]

    @property
    def active_count(self) -> int:
        """Number of currently connected clients."""
        return sum(len(conns) for conns in self._connections.values())


# ── Global singleton ─────────────────────────────────────────

ws_manager = ConnectionManager()


# ── Redis Pub/Sub helpers ────────────────────────────────────


async def publish_event(tenant_id: str, event: dict) -> None:
    """Publish an event to Redis channel ``events:{tenant_id}``.

    Every API process's relay (:func:`start_subscriber`) hears it and sends
    it to its own sockets for that tenant, so a client gets it once, whichever
    process holds its socket. Falls back to local broadcast if Redis is
    unavailable.
    """
    r = get_redis()
    if r is not None:
        try:
            await r.publish(f"events:{tenant_id}", json.dumps(event, default=str))
            return
        except Exception:  # fail-open: Redis down, broadcast locally
            logger.warning("Redis publish failed, falling back to local broadcast")

    # Fallback: broadcast locally
    await ws_manager.broadcast_to_tenant(tenant_id, event)


#: Channel prefix shared by the WebSocket relay and the EventBus Redis bridge.
_CHANNEL_PREFIX = "events:"

#: Seconds between reconnect attempts after the subscription drops (doubles, capped).
_RECONNECT_FIRST_SECONDS = 1.0
_RECONNECT_MAX_SECONDS = 60.0


def _channel_tenant(channel: str) -> tuple[str | None, bool]:
    """``(tenant, is_relay_channel)`` for a channel heard on ``events:*``.

    Two publishers share the prefix:

    - :func:`publish_event` (this module): ``events:{tenant}``, one message
      per event, ready for the sockets;
    - ``RedisBridge`` (core/events.py): ``events:{tenant}:{event_type}``.

    The tenant used to be read as everything after the first colon, so a
    bridge channel gave ``"{tenant}:{event_type}"``, a tenant no socket has.
    Event type values have colons of their own (``memory:created``,
    ``kernel:task:completed``), so the channel is a bridge one only when it
    ends in ``:`` plus a real ``EventType`` value; a tenant id with a colon
    in it still parses.
    """
    if not channel.startswith(_CHANNEL_PREFIX):
        return None, False
    rest = channel[len(_CHANNEL_PREFIX) :]
    # Longest first, so a type that ends another type's name cannot cut it short.
    for value in sorted((t.value for t in EventType), key=len, reverse=True):
        suffix = f":{value}"
        if rest.endswith(suffix) and len(rest) > len(suffix):
            return rest[: -len(suffix)], False
    return (rest or None), True


async def _relay(message: dict[str, Any]) -> None:
    """Send one pub/sub message to its tenant's local sockets.

    Only the relay's own ``events:{tenant}`` channel is sent on. The bridge's
    ``events:{tenant}:{type}`` copy of the same event is skipped: both are
    published, in the same API process, for every event (ws_event_handler and
    the bridge are both subscribed to the event bus, main.py), so relaying
    both would give each socket every event twice. The relay copy is the one
    kept because ws_event_handler tells the tenant safely (payload and
    context must agree) while the bridge uses the context alone and falls
    back to "system".
    """
    if message.get("type") != "pmessage":
        return
    channel = str(message.get("channel", ""))
    tenant_id, is_relay = _channel_tenant(channel)
    if not is_relay or tenant_id is None:
        return
    try:
        data = json.loads(message["data"])
    except (json.JSONDecodeError, TypeError, KeyError):
        logger.warning("Invalid JSON on channel %s", channel)
        return
    await ws_manager.broadcast_to_tenant(tenant_id, data)


async def start_subscriber() -> None:
    """Subscribe to ``events:*`` on Redis and relay to local connections.

    Runs as a long-lived background task, started by :func:`start_relay` at
    API startup. Without it, :func:`publish_event` published every event to
    Redis and nothing ever sent it on, so with Redis up no socket got any
    event. When the subscription drops it reconnects, waiting longer each time
    (up to a minute), until cancelled.
    """
    delay = _RECONNECT_FIRST_SECONDS
    while True:
        r = get_redis()
        if r is None:
            logger.warning("Redis unavailable — WebSocket subscriber not started")
            return
        pubsub = r.pubsub()
        try:
            await pubsub.psubscribe(f"{_CHANNEL_PREFIX}*")
            logger.info("Redis subscriber started on pattern events:*")
            delay = _RECONNECT_FIRST_SECONDS
            async for message in pubsub.listen():
                await _relay(message)
        except asyncio.CancelledError:
            logger.info("Redis subscriber cancelled")
            raise
        except Exception:  # fail-open: reconnect after a pause; local publish still falls back
            logger.warning("Redis subscriber dropped; retrying in %.0fs", delay, exc_info=True)
        finally:
            with contextlib.suppress(Exception):
                await pubsub.punsubscribe(f"{_CHANNEL_PREFIX}*")
            with contextlib.suppress(Exception):
                await pubsub.aclose()  # type: ignore[no-untyped-call, unused-ignore]  # strict only
        await asyncio.sleep(delay)
        delay = min(delay * 2, _RECONNECT_MAX_SECONDS)


def start_relay() -> asyncio.Task[None]:
    """Start :func:`start_subscriber` as a background task (API startup)."""
    return asyncio.create_task(start_subscriber(), name="ws-redis-relay")


async def stop_relay(task: asyncio.Task[None] | None) -> None:
    """Cancel the relay task and wait for it to finish (API shutdown)."""
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


# ── Event handler ────────────────────────────────────────────


#: Event types that carry nothing of any tenant's and may go to every socket.
#: Empty: every EventType today is about one tenant's memories, tasks,
#: projects, approvals or runs. Add one here only if it is truly global.
GLOBAL_EVENT_TYPES: frozenset[str] = frozenset()


def _event_tenant(event: Event) -> str | None:
    """The tenant an event belongs to, or None when that cannot be told.

    The payload's ``tenant_id`` (most emitters put one there) or the tenant
    context the event was emitted in. Should the two disagree, it is neither's.
    """
    payload = event.payload if isinstance(event.payload, dict) else {}
    named = payload.get("tenant_id")
    named = str(named) if named else None
    context: str | None = None
    if has_tenant_context():
        with contextlib.suppress(RuntimeError):
            context = get_current_tenant_id() or None
    if named and context and named != context:
        return None
    return named or context


async def ws_event_handler(event: Event) -> None:
    """Convert an EventBus event to JSON and send it to its tenant's clients.

    Subscribed to the global event_bus via ``event_bus.subscribe_all()``.
    Silently skips if no clients are connected. An event whose tenant cannot
    be told is dropped: it used to be broadcast to every socket, so one
    tenant saw another's events from background jobs, which run with no
    tenant context.
    """
    if ws_manager.active_count == 0:
        return

    message: dict[str, Any] = {
        "type": event.type.value,
        "payload": event.payload,
        "timestamp": event.timestamp.isoformat(),
        "source": event.source,
    }

    tenant_id = _event_tenant(event)
    if tenant_id:
        await publish_event(tenant_id, message)
    elif event.type.value in GLOBAL_EVENT_TYPES:
        await ws_manager.broadcast(message)
    else:
        logger.debug("WebSocket: %s has no tenant; not sent", event.type.value)


# ── WebSocket route ──────────────────────────────────────────


async def _authenticate(
    websocket: WebSocket, key: str | None, tenant_param: str | None
) -> str | None:
    """The tenant this handshake may listen to, or None to refuse it."""
    named = tenant_param or websocket.headers.get("x-tenant-id") or "default"
    valid = settings.service_api_keys_list + ([settings.api_key] if settings.api_key else [])
    if not valid:
        # verify_service_key's rule: no keys at all is open in development only.
        return named if settings.is_development else None
    if not key:
        return None
    if any(hmac.compare_digest(key.encode(), k.encode()) for k in valid):
        # The same key -> tenant binding as HTTP (settings.service_key_tenants).
        return named if key_may_use_tenant(key, named) else None
    from life_graph.services.devices import authenticate

    try:
        device = await authenticate(key)
    except Exception:  # noqa: BLE001 - a lookup failure is a refusal, never a pass
        logger.warning("WebSocket device token lookup failed", exc_info=True)
        return None
    return device[0] if device is not None else None


async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str | None = Query(None, alias="api_key"),
    tenant_id: str | None = Query(None, alias="tenant_id"),
) -> None:
    """WebSocket endpoint for real-time event streaming.

    Authenticates via, in order: an ``Authorization: Bearer`` header, an
    ``X-API-Key`` header, or an ``api_key`` query parameter — the same precedence as the HTTP auth
    path (``api/auth.py``'s ``verify_service_key``). The header sources
    matter here specifically: a browser's native WebSocket API can't set
    custom headers on its own outgoing handshake, but Caddy injects
    ``X-API-Key`` on proxied ``/ws`` requests once Cloudflare Access has
    already gated them, the same way it does for ``/api``/``/docs``. A
    check that only looked at the query parameter never saw that header,
    so every browser connection sent a placeholder key and failed auth —
    once connected, receives JSON-encoded events from the EventBus
    broadcast.

    The key is checked against ``service_api_keys`` plus the legacy
    ``api_key``, as ``verify_service_key`` does; a paired phone's device token
    is accepted too. Only a service key may name its tenant (``tenant_id``
    query parameter or ``X-Tenant-ID``); a device is the tenant that paired
    it. Anything else is closed with 4401. It used to compare against
    ``settings.api_key`` alone, which this deployment leaves unset, so the
    socket was open to anyone, for any tenant named in the query string
    (security review 2026-10-24, H1).

    The connection stays alive listening for client messages
    (pings / keepalives) until the client disconnects.
    """
    # ── Auth check + tenant ───────────────────────────────
    resolved_tenant_id = await _authenticate(
        websocket, extract_api_key(websocket.headers, websocket.query_params) or api_key, tenant_id
    )
    if resolved_tenant_id is None:
        await websocket.close(code=4401, reason="Invalid API key")
        return

    await ws_manager.connect(websocket, resolved_tenant_id)

    try:
        while True:
            # Keep alive — listen for pings or client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, resolved_tenant_id)
    except Exception:
        logger.exception("WebSocket error")
        ws_manager.disconnect(websocket, resolved_tenant_id)
