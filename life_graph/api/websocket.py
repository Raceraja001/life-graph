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
import json
import logging
from typing import Any

from fastapi import Query, WebSocket, WebSocketDisconnect

from life_graph.config import settings
from life_graph.core.events import Event
from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
from life_graph.storage.redis import get_redis

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

    async def broadcast_to_tenant(
        self, tenant_id: str, message: dict[str, Any]
    ) -> None:
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
            except Exception:
                logger.warning("Failed to send to WebSocket, marking dead")
                dead.append(ws)

        for ws in dead:
            connections.discard(ws)
        if not connections:
            self._connections.pop(tenant_id, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients.

        Failed sends are logged and the dead connection is removed,
        but never prevent delivery to other clients.
        """
        dead: list[tuple[str, WebSocket]] = []
        for tenant_id, connections in self._connections.items():
            for ws in connections:
                try:
                    await ws.send_json(message)
                except Exception:
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

    Falls back to local broadcast if Redis is unavailable.
    """
    r = get_redis()
    if r is not None:
        try:
            await r.publish(f"events:{tenant_id}", json.dumps(event, default=str))
            return
        except Exception:
            logger.warning("Redis publish failed, falling back to local broadcast")

    # Fallback: broadcast locally
    await ws_manager.broadcast_to_tenant(tenant_id, event)


async def start_subscriber() -> None:
    """Subscribe to ``events:*`` Redis pattern and relay to local connections.

    Runs as a long-lived background task. On each message received,
    extracts the tenant_id from the channel name and broadcasts to
    the matching local WebSocket connections.
    """
    r = get_redis()
    if r is None:
        logger.warning("Redis unavailable — WebSocket subscriber not started")
        return

    pubsub = r.pubsub()
    await pubsub.psubscribe("events:*")
    logger.info("Redis subscriber started on pattern events:*")

    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel: str = message["channel"]
            # Channel format: events:{tenant_id}
            tenant_id = channel.split(":", 1)[1] if ":" in channel else "unknown"
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid JSON on channel %s", channel)
                continue

            await ws_manager.broadcast_to_tenant(tenant_id, data)
    except asyncio.CancelledError:
        logger.info("Redis subscriber cancelled")
    except Exception:
        logger.exception("Redis subscriber error")
    finally:
        await pubsub.punsubscribe("events:*")
        await pubsub.close()


# ── Event handler ────────────────────────────────────────────


async def ws_event_handler(event: Event) -> None:
    """Convert an EventBus event to JSON and broadcast to all clients.

    Subscribed to the global event_bus via ``event_bus.subscribe_all()``.
    Silently skips if no clients are connected.
    """
    if ws_manager.active_count == 0:
        return

    message: dict[str, Any] = {
        "type": event.type.value,
        "payload": event.payload,
        "timestamp": event.timestamp.isoformat(),
        "source": event.source,
    }

    # Determine tenant_id from context or fall back to broadcast
    tenant_id: str | None = None
    if has_tenant_context():
        try:
            tenant_id = get_current_tenant_id()
        except RuntimeError:
            pass

    if tenant_id:
        await publish_event(tenant_id, message)
    else:
        await ws_manager.broadcast(message)


# ── WebSocket route ──────────────────────────────────────────


async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str | None = Query(None, alias="api_key"),
    tenant_id: str | None = Query(None, alias="tenant_id"),
) -> None:
    """WebSocket endpoint for real-time event streaming.

    Authenticates via an ``api_key`` query parameter (compared
    against ``settings.api_key``).  Once connected, the client
    receives JSON-encoded events from the EventBus broadcast.

    The connection stays alive listening for client messages
    (pings / keepalives) until the client disconnects.
    """
    # ── Auth check ────────────────────────────────────────
    if settings.api_key and api_key != settings.api_key:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    # ── Resolve tenant_id ─────────────────────────────────
    resolved_tenant_id = tenant_id or websocket.headers.get("x-tenant-id", "default")

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
