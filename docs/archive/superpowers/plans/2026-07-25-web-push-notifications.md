# Web Push Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The daily brief (and a test push) reach the user's Android phone as real OS notifications via Web Push, even when the app is closed.

**Architecture:** VAPID Web Push. A `push_subscriptions` table stores each device; a `PushService` sends via `pywebpush`; a `PushDeliveryHandler` subscribed to `BRIEF_COMPOSED` fetches the brief Notification and pushes to the tenant's devices; the service worker shows the notification and opens the app on tap.

**Tech Stack:** FastAPI + SQLAlchemy async, Alembic, `pywebpush`, Next.js 16 dashboard, service worker.

## Global Constraints

- Python: async everywhere, type hints + docstrings on public APIs, double quotes, ruff line-length 100.
- Tenant only from the contextvar (`get_current_tenant_id()` / `Depends(get_current_tenant_id)`); `push_subscriptions` is tenant-scoped.
- Spec: docs/superpowers/specs/2026-07-25-web-push-notifications-design.md.
- VAPID keys: **private** key only in the VM `.env.production` (`LIFE_GRAPH_VAPID_PRIVATE_KEY`) — NEVER git. **Public** key in backend env + dashboard build env (`NEXT_PUBLIC_VAPID_PUBLIC_KEY`) — public by design. `.env.example` documents names only.
- Web Push payload ≤ ~4KB; body truncated to a push-safe length. Silence-by-design preserved (empty brief → no event → no push).
- `pywebpush` blocking calls run in `asyncio.to_thread` so they never block the event loop / brief cron.
- New Alembic revision `028`, `down_revision = "027"` (head is 027_conversations).
- Frontend: mobile inline styles + CSS vars (uzhavu); `NEXT_PUBLIC_*` read directly via `process.env`. No new npm deps (Web Push uses browser APIs).
- Commits end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Windows: ruff blocked — verify with `python -m py_compile` + pytest from the worktree ROOT (`python -m pytest tests/unit/ -v`; unit tests mock pywebpush + DB). `dashboard/`: `npm run build` passes, lint zero new.
- Worktree: `<scratchpad>/hotfix-wt`, branch `feat/notifications` (off master; spec committed).
- **Deploy is BATCHED** (user's workflow choice): Task 7 prepares deploy steps + PR, but the actual VM swap/live-E2E happens when the user calls a batch deploy — the plan documents the steps; do not deploy mid-build.

## Key facts (from investigation)

- `BRIEF_COMPOSED = "capture:brief:composed"` (core/events.py:109). Emit payload (brief.py:113-123): `{"notification_id", "tenant_id", "title", "questions", "held"}` — **no body**; fetch the `Notification` row by `notification_id` for the body. Kernel `Notification` model at `models/db.py:1196` (fields incl. `title`, `body`, `tenant_id`, `extra_metadata`).
- Lifespan subscription pattern (main.py:140-162): `service.subscribe()` calling `event_bus.subscribe(EventType.X, async_handler)`; handler is `async def(event: Event) -> None`. Wire a new handler after the judgment block (~line 162) in a try/except.
- Alembic head 027; mirror `026_approvals.py` for create_table + unique index (`postgresql_where` pattern).
- config.py `BaseSettings`, env prefix `LIFE_GRAPH_`; add VAPID settings near line 219.
- Routers registered in main.py:252-332 (`v1_router.include_router(...)`); no `api/push.py` — create it, mirror `api/approvals.py` (imports `get_session` from `storage.database`, `get_current_tenant_id` from `core.tenant`; `Depends(get_session)` per request).
- `sw.js` `CACHE_NAME='lifegraph-v2'` (line 7); install/activate/fetch listeners (lines 9-51) — add `push`+`notificationclick` additively, don't touch the three. SW registered in `dashboard/app/layout.tsx:60-70`.
- Mobile home `app/(mobile)/m/page.tsx` (`MobileHome`), approvals banner at lines 21-63 is the style to mirror for the enable-control. `api.ts` `api` object + `request` helper; `NEXT_PUBLIC_*` read via `process.env`. `dashboard/Dockerfile:11-16` build args; `dashboard/docker-compose.yml:5-9` args.
- `pyproject.toml` deps list (lines 9-51) — add `pywebpush`.

---

### Task 1: Config, dependency, table + migration

**Files:**
- Modify: `pyproject.toml` (add `pywebpush`), `life_graph/config.py` (VAPID settings), `.env.example`
- Modify: `life_graph/models/db.py` (PushSubscription model)
- Create: `alembic/versions/028_push_subscriptions.py`
- Create: `scripts/gen_vapid_keys.py` (one-off keygen helper)
- Test: `tests/unit/test_push_subscription_model.py`

**Interfaces:**
- Produces: `settings.vapid_public_key/vapid_private_key/vapid_subject`; `PushSubscription` model (id, tenant_id, endpoint, p256dh, auth, user_agent, created_at, last_used_at); migration 028. Tasks 2–6 use these.

- [ ] **Step 1: Failing test** `tests/unit/test_push_subscription_model.py`:

```python
"""Push subscription model + VAPID settings exist."""

from life_graph.config import settings
from life_graph.models.db import PushSubscription


def test_vapid_settings_exist():
    assert hasattr(settings, "vapid_public_key")
    assert hasattr(settings, "vapid_private_key")
    assert hasattr(settings, "vapid_subject")


def test_push_subscription_columns():
    cols = PushSubscription.__table__.columns.keys()
    assert {"id", "tenant_id", "endpoint", "p256dh", "auth", "user_agent", "created_at"} <= set(cols)
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/unit/test_push_subscription_model.py -v` → FAIL.

- [ ] **Step 3: Implement**

`config.py` (near line 219, after the Capture Spine block):

```python
    # ── Web Push Notifications ──────────────────────────
    vapid_public_key: str = ""  # Set LIFE_GRAPH_VAPID_PUBLIC_KEY
    vapid_private_key: str = ""  # Set LIFE_GRAPH_VAPID_PRIVATE_KEY (VM only, never git)
    vapid_subject: str = "mailto:tolokanathan@gmail.com"  # VAPID contact
```

`models/db.py` (near the other recent models, e.g. after `Conversation`):

```python
class PushSubscription(Base):
    """A browser/device Web Push subscription for a tenant."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_push_sub_endpoint", "endpoint", unique=True),
        Index("ix_push_sub_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<PushSubscription(id={self.id!s:.8}, tenant={self.tenant_id})>"
```

`alembic/versions/028_push_subscriptions.py`:

```python
"""028 — Web Push subscriptions.

Revision ID: 028
Revises: 027
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="legacy"),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_push_sub_endpoint", "push_subscriptions", ["endpoint"], unique=True)
    op.create_index("ix_push_sub_tenant", "push_subscriptions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_push_sub_tenant", table_name="push_subscriptions")
    op.drop_index("uq_push_sub_endpoint", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
```

`pyproject.toml` deps list: add `"pywebpush>=2.0",`.

`scripts/gen_vapid_keys.py` (one-off; prints keys, commits NOTHING):

```python
"""Generate a VAPID keypair for Web Push. Run once; store the private key in the
VM's .env.production (LIFE_GRAPH_VAPID_PRIVATE_KEY) and the public key in both the
backend env and the dashboard build env (NEXT_PUBLIC_VAPID_PUBLIC_KEY)."""

from py_vapid import Vapid02


def main() -> None:
    v = Vapid02()
    v.generate_keys()
    print("VAPID_PRIVATE_KEY:", v.private_key_to_base64url())  # exact method name may differ by py_vapid version — verify
    print("VAPID_PUBLIC_KEY:", v.public_key_to_base64url())


if __name__ == "__main__":
    main()
```

(The exact base64url export method varies by `py_vapid` version — the implementer verifies against the installed version; `pywebpush` bundles `py_vapid`.)

`.env.example`: add `LIFE_GRAPH_VAPID_PUBLIC_KEY=`, `LIFE_GRAPH_VAPID_PRIVATE_KEY=`, `LIFE_GRAPH_VAPID_SUBJECT=` (names only).

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_push_subscription_model.py tests/unit/ -v` → green. `python -m py_compile` changed Python files + the migration.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml life_graph/config.py life_graph/models/db.py alembic/versions/028_push_subscriptions.py scripts/gen_vapid_keys.py .env.example tests/unit/test_push_subscription_model.py
git commit -m "feat(push): VAPID config, push_subscriptions table + migration 028"
```

---

### Task 2: Push service

**Files:**
- Create: `life_graph/services/webpush.py`
- Test: `tests/unit/test_webpush_service.py`

**Interfaces:**
- Consumes: `PushSubscription`, `settings.vapid_*`, `async_session`, `get_current_tenant_id`, `pywebpush`.
- Produces: `PushService`:
  - `async def save_subscription(self, sub: dict, user_agent: str | None = None) -> None` (upsert by endpoint, tenant from contextvar)
  - `async def delete_subscription(self, endpoint: str) -> None`
  - `async def send_to_tenant(self, tenant_id: str, title: str, body: str, url: str = "/m") -> int` (webpush each; prune 404/410; return delivered count)
  Tasks 3–4 use these.

- [ ] **Step 1: Failing test** `tests/unit/test_webpush_service.py` — mock `pywebpush.webpush` and a fake session; assert: save upserts (no dup on same endpoint); `send_to_tenant` calls webpush per subscription with the VAPID private key + subject, returns the delivered count; a `WebPushException` with `response.status_code == 410` prunes that subscription. Full test skeleton (adapt session-fake to the repo's test style, e.g. test_conversation_service.py):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from life_graph.services.webpush import PushService


@pytest.mark.asyncio
async def test_send_prunes_dead_subscription(monkeypatch):
    # two subs; webpush raises 410 for the first → it gets deleted, second delivers
    ...
    with patch("life_graph.services.webpush.webpush") as mock_webpush:
        def side_effect(subscription_info, data, **kw):
            if "dead" in subscription_info["endpoint"]:
                from pywebpush import WebPushException
                resp = MagicMock(); resp.status_code = 410
                raise WebPushException("gone", response=resp)
        mock_webpush.side_effect = side_effect
        svc = PushService(session_factory)
        delivered = await svc.send_to_tenant("t1", "T", "B")
    assert delivered == 1  # only the live one
    # assert the dead endpoint was deleted from the session
```

- [ ] **Step 2: Run to verify failure** — FAIL (module absent).

- [ ] **Step 3: Implement** `life_graph/services/webpush.py`:

```python
"""Web Push delivery via VAPID (pywebpush)."""

from __future__ import annotations

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import PushSubscription

logger = logging.getLogger(__name__)

_MAX_BODY = 200


class PushService:
    """Persist push subscriptions and deliver Web Push notifications."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def save_subscription(self, sub: dict, user_agent: str | None = None) -> None:
        tenant_id = get_current_tenant_id()
        endpoint = sub["endpoint"]
        keys = sub.get("keys", sub)
        async with self._session_factory() as session:
            existing = await session.execute(
                select(PushSubscription).where(PushSubscription.endpoint == endpoint)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(PushSubscription(
                    tenant_id=tenant_id, endpoint=endpoint,
                    p256dh=keys["p256dh"], auth=keys["auth"], user_agent=user_agent,
                ))
            else:
                row.tenant_id = tenant_id
                row.p256dh = keys["p256dh"]
                row.auth = keys["auth"]
                row.user_agent = user_agent
            await session.commit()

    async def delete_subscription(self, endpoint: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.endpoint == endpoint)
            )
            await session.commit()

    async def send_to_tenant(self, tenant_id: str, title: str, body: str, url: str = "/m") -> int:
        if not settings.vapid_private_key:
            logger.warning("VAPID private key unset; skipping push")
            return 0
        payload = json.dumps({"title": title, "body": body[:_MAX_BODY], "url": url})
        async with self._session_factory() as session:
            rows = (await session.execute(
                select(PushSubscription).where(PushSubscription.tenant_id == tenant_id)
            )).scalars().all()
            delivered = 0
            dead: list[str] = []
            for row in rows:
                sub_info = {
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth},
                }
                try:
                    await asyncio.to_thread(
                        webpush, sub_info, payload,
                        vapid_private_key=settings.vapid_private_key,
                        vapid_claims={"sub": settings.vapid_subject},
                    )
                    delivered += 1
                except WebPushException as exc:
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status in (404, 410):
                        dead.append(row.endpoint)
                    else:
                        logger.warning("Web push failed for %s: %s", row.endpoint[:40], exc)
            if dead:
                await session.execute(
                    delete(PushSubscription).where(PushSubscription.endpoint.in_(dead))
                )
                await session.commit()
            return delivered
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_webpush_service.py tests/unit/ -v` → green. `python -m py_compile life_graph/services/webpush.py`.

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/webpush.py tests/unit/test_webpush_service.py
git commit -m "feat(push): PushService — save/delete subscriptions, deliver via pywebpush, prune dead"
```

---

### Task 3: Push API

**Files:**
- Create: `life_graph/api/push.py`
- Modify: `life_graph/main.py` (register router)
- Test: `tests/integration/test_push_api.py`

**Interfaces:**
- Consumes: `PushService`, `get_current_tenant_id`, `get_session`/`async_session`, `success_response`.
- Produces routes under `/push`:
  - `POST /api/v1/push/subscriptions` `{endpoint, keys:{p256dh, auth}}` → `{data:{ok:true}}`
  - `DELETE /api/v1/push/subscriptions` `{endpoint}` → `{data:{ok:true}}`
  - `GET /api/v1/push/vapid-key` → `{data:{key}}`
  - `POST /api/v1/push/test` → `{data:{delivered:n}}`
  Task 6 (frontend) calls these.

- [ ] **Step 1: Failing test** `tests/integration/test_push_api.py` (mirror `test_approvals.py`: ASGITransport, tenant headers, `@skip_on_db_error`): subscribe → 200; vapid-key → 200 with a `key` field; test → 200 (delivered may be 0 without a real sub). Tolerate 500 on DB-unavailable.

- [ ] **Step 2: Run to verify failure** — 404 (routes absent).

- [ ] **Step 3: Implement** `api/push.py` (mirror `api/approvals.py` structure; use module-level `async_session` for the service since it manages its own sessions):

```python
"""Web Push subscription + test API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.webpush import PushService
from life_graph.storage.database import async_session

router = APIRouter(prefix="/push", tags=["push"])


def _service() -> PushService:
    return PushService(async_session)


class SubscribeBody(BaseModel):
    endpoint: str
    keys: dict


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.post("/subscriptions")
async def subscribe(body: SubscribeBody, request: Request):
    await _service().save_subscription(body.model_dump(), user_agent=request.headers.get("user-agent"))
    return success_response(data={"ok": True})


@router.request("DELETE", "/subscriptions") if False else router.delete("/subscriptions")
async def unsubscribe(body: UnsubscribeBody):
    await _service().delete_subscription(body.endpoint)
    return success_response(data={"ok": True})


@router.get("/vapid-key")
async def vapid_key():
    return success_response(data={"key": settings.vapid_public_key})


@router.post("/test")
async def test_push(tenant_id: str = Depends(get_current_tenant_id)):
    delivered = await _service().send_to_tenant(
        tenant_id, "Life Graph", "Test notification 🎉", "/m"
    )
    return success_response(data={"delivered": delivered})
```

(Clean up the DELETE decorator to a plain `@router.delete("/subscriptions")` — the `if False` line above is illustrative; use the normal decorator. FastAPI `DELETE` with a body is allowed via a Pydantic model param.)

`main.py`: after `approvals_api` include:

```python
    from life_graph.api import push as push_api
    v1_router.include_router(push_api.router)
```

- [ ] **Step 4: Run tests** — integration tests SKIP locally; full unit suite green; verify routes: `python -c "from life_graph.main import app; print([r.path for r in app.routes if 'push' in r.path])"`. `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/api/push.py life_graph/main.py tests/integration/test_push_api.py
git commit -m "feat(push): subscription + test-push API"
```

---

### Task 4: Brief delivery handler

**Files:**
- Create: `life_graph/services/push_delivery.py`
- Modify: `life_graph/main.py` (wire in lifespan)
- Test: `tests/unit/test_push_delivery.py`

**Interfaces:**
- Consumes: `EventType.BRIEF_COMPOSED`, `PushService`, the kernel `Notification` model (fetch body by `notification_id`), `event_bus`.
- Produces: `PushDeliveryHandler` with `subscribe()` (idempotent) + `async def _on_brief(event) -> None` that fetches the Notification body and calls `send_to_tenant`.

- [ ] **Step 1: Failing test** `tests/unit/test_push_delivery.py` — construct a fake `Event` with `BRIEF_COMPOSED` payload `{notification_id, tenant_id, title}`, mock the Notification fetch (returns a body) and `PushService.send_to_tenant`; assert the handler calls `send_to_tenant(tenant_id, title, <body>, "/m")`. Also assert delivery failure is swallowed (no raise).

- [ ] **Step 2: Run to verify failure** — FAIL (module absent).

- [ ] **Step 3: Implement** `life_graph/services/push_delivery.py`:

```python
"""Deliver the daily brief to the phone via Web Push when BRIEF_COMPOSED fires."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from life_graph.core.events import Event, EventType, event_bus
from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Notification
from life_graph.services.webpush import PushService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


class PushDeliveryHandler:
    """Subscribes to BRIEF_COMPOSED and pushes the brief to the tenant's devices."""

    def __init__(self) -> None:
        self._subscribed = False
        self._push = PushService(async_session)

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.BRIEF_COMPOSED, self._on_brief)
        self._subscribed = True

    async def _on_brief(self, event: Event) -> None:
        try:
            data = event.data
            tenant_id = data.get("tenant_id")
            title = data.get("title") or "Daily brief"
            notif_id = data.get("notification_id")
            body = title
            if notif_id and tenant_id:
                set_tenant_context(tenant_id, "system")
                async with async_session() as session:
                    row = (await session.execute(
                        select(Notification).where(Notification.id == uuid.UUID(str(notif_id)))
                    )).scalar_one_or_none()
                    if row and row.body:
                        body = row.body
            if tenant_id:
                await self._push.send_to_tenant(tenant_id, title, body, "/m")
        except Exception:  # pragma: no cover - delivery must never break the brief flow
            logger.warning("Push delivery of brief failed", exc_info=True)


push_delivery_handler = PushDeliveryHandler()
```

(Verify `Event`'s attribute for the payload — the scout says handler gets a single `Event`; check whether it's `event.data` or `event.payload` and match.)

`main.py` lifespan (after the judgment block ~line 162):

```python
    try:
        from life_graph.services.push_delivery import push_delivery_handler
        push_delivery_handler.subscribe()
        logger.info("Web push brief delivery enabled")
    except Exception:
        logger.warning("Push delivery handler not available", exc_info=True)
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_push_delivery.py tests/unit/ -v` → green. `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/push_delivery.py life_graph/main.py tests/unit/test_push_delivery.py
git commit -m "feat(push): deliver the daily brief via Web Push on BRIEF_COMPOSED"
```

---

### Task 5: Service worker push listeners

**Files:**
- Modify: `dashboard/public/sw.js`
- Test: manual/inspection (no JS test harness in the repo) + `npm run build` (SW is static, build just copies it)

- [ ] **Step 1: Add listeners** — append to `sw.js` (do NOT touch install/activate/fetch):

```javascript
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  const title = data.title || "Life Graph";
  const body = data.body || "";
  const url = data.url || "/m";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/m";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w) { w.navigate(url); return w.focus(); }
      }
      return self.clients.openWindow(url);
    })
  );
});
```

(Verify the icon path against what exists in `dashboard/public/icons/` — use a real icon filename.)

- [ ] **Step 2: Bump CACHE_NAME** — `const CACHE_NAME = 'lifegraph-v3';` so the new SW activates and clients pick up the push listeners.

- [ ] **Step 3: Verify** — `cd dashboard && npm run build` passes (SW is copied as a static asset; ensure no syntax error via `node --check public/sw.js`).

- [ ] **Step 4: Commit**

```bash
git add dashboard/public/sw.js
git commit -m "feat(push): service worker push + notificationclick handlers"
```

---

### Task 6: Enable-notifications UI + build-arg plumbing

**Files:**
- Modify: `dashboard/lib/api.ts` (`api.push.*`), `dashboard/lib/mobile-api.ts` (helper if needed)
- Modify: `dashboard/app/(mobile)/m/page.tsx` (enable control)
- Modify: `dashboard/Dockerfile`, `dashboard/docker-compose.yml` (NEXT_PUBLIC_VAPID_PUBLIC_KEY build arg)
- Test: `npm run build` + lint

**Interfaces:**
- Consumes: Task 3 routes; `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.
- Produces: `api.push.{subscribe, unsubscribe, test, vapidKey}`; an "Enable notifications" control on mobile Home.

- [ ] **Step 1: API client** — add to `api.ts`:

```ts
  push: {
    subscribe: (sub: any) => POST<any>("/push/subscriptions", sub),
    unsubscribe: (endpoint: string) => request<any>("DELETE", "/push/subscriptions", { endpoint }),
    test: () => POST<any>("/push/test", {}),
    vapidKey: () => GET<any>("/push/vapid-key"),
  },
```

- [ ] **Step 2: Helper** — add a `urlBase64ToUint8Array(base64)` util (standard Web Push helper) in a small `dashboard/lib/push.ts`, plus an `enablePush()` async function: `Notification.requestPermission()` → if granted, `navigator.serviceWorker.ready` → `reg.pushManager.subscribe({userVisibleOnly:true, applicationServerKey: urlBase64ToUint8Array(process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || (await api.push.vapidKey()).data.key)})` → `api.push.subscribe(sub.toJSON())`. Return the resulting permission/subscription state. `disablePush()`: get existing subscription, `sub.unsubscribe()` + `api.push.unsubscribe(sub.endpoint)`.

- [ ] **Step 3: Mobile Home control** — in `app/(mobile)/m/page.tsx`, add a small "🔔 Enable notifications" button/banner (mirror the approvals-banner style, lines 21-63). States: default (not subscribed) → tap calls `enablePush()`; granted/subscribed → show "On" + a "Send test" button (`api.push.test()`) + "Turn off" (`disablePush()`); denied → "Blocked — enable in browser settings". Guard for SSR (`typeof window`, `"Notification" in window`, `"serviceWorker" in navigator`).

- [ ] **Step 4: Build-arg plumbing** — `dashboard/Dockerfile`: add `ARG NEXT_PUBLIC_VAPID_PUBLIC_KEY` + `ENV NEXT_PUBLIC_VAPID_PUBLIC_KEY=$NEXT_PUBLIC_VAPID_PUBLIC_KEY` before `RUN npm run build`. `dashboard/docker-compose.yml`: add it to the `build.args` block. (The actual key value is passed at deploy time — Task 7.)

- [ ] **Step 5: Verify** — `npm run build` passes; lint zero new. (Build works even with the key empty — the UI just no-ops/falls back to fetching the key from the API.)

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/api.ts dashboard/lib/push.ts dashboard/app/(mobile)/m/page.tsx dashboard/Dockerfile dashboard/docker-compose.yml
git commit -m "feat(push): enable-notifications UI + VAPID build arg"
```

---

### Task 7: Deploy (batched) + E2E + PR

**Files:** none (VM ops + PR). **NOTE: actual deploy is batched — run when the user calls a batch deploy.**

- [ ] **Step 1: Generate VAPID keys** — run `python scripts/gen_vapid_keys.py`; give the user the two values. Private → VM `.env.production` `LIFE_GRAPH_VAPID_PRIVATE_KEY=`, public → `.env.production` `LIFE_GRAPH_VAPID_PUBLIC_KEY=` AND the dashboard build (`--build-arg NEXT_PUBLIC_VAPID_PUBLIC_KEY=<public>`). (User step — never commit.)

- [ ] **Step 2: Deploy (batch)** — on the VM: fetch + checkout the merged master, `build app worker`, `alembic upgrade head` (creates `push_subscriptions`), `up -d --force-recreate --no-deps app worker`, `docker network connect web life_graph_app`; dashboard rebuild WITH `--build-arg NEXT_PUBLIC_VAPID_PUBLIC_KEY=<public>` + stop/rm/run swap; smoke 200s.

- [ ] **Step 3: Live E2E**:
  1. `GET /api/v1/push/vapid-key` → returns the public key.
  2. Phone: open the app → "🔔 Enable notifications" → grant → subscription saved (`push_subscriptions` has a row).
  3. `POST /api/v1/push/test` (or the "Send test" button) → **notification appears on the phone with the app closed** → tap → opens the app.
  4. Trigger the brief: enqueue `run_daily_brief` (or force `compose_daily` for the tenant) → the brief arrives as a push.
  5. Negative: deny permission → UI "blocked"; turn off → `push_subscriptions` row removed → no more pushes.

- [ ] **Step 4: PR**

```bash
gh pr create --repo Raceraja001/life-graph --base master --head feat/notifications \
  --title "feat: web push notifications — the daily brief reaches your phone" \
  --body "Implements docs/superpowers/specs/2026-07-25-web-push-notifications-design.md ..."
```

---

## Self-review notes

- Spec coverage: VAPID config + table (T1); push service w/ prune (T2); subscribe/test API (T3); BRIEF_COMPOSED delivery (T4); SW push listeners (T5); enable UI + build arg (T6); deploy+E2E+PR (T7). ✅
- Type consistency: `PushService.send_to_tenant(tenant_id, title, body, url)` signature identical across T2/T3/T4; `api.push.*` paths (T6) == routes (T3); migration down_revision 027. ✅
- Known judgment calls: brief body fetched from the Notification row (payload lacks body); pywebpush in `asyncio.to_thread`; deploy batched per the user's workflow; iOS untested (Android target). Verify `Event` payload attr (`event.data` vs `.payload`) and `py_vapid` key-export method names at implementation time.
