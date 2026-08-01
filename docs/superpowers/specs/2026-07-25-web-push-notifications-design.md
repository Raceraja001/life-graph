# Proactive Notifications (Web Push) — the daily brief reaches your phone

> **Date:** 2026-07-25
> **Status:** Approved design — ready for implementation planning
> **Scope:** new `push_subscriptions` table + migration, `services/webpush.py`, push API routes,
> a `BRIEF_COMPOSED` delivery handler, `dashboard/public/sw.js` (push listeners),
> mobile "enable notifications" UI. Deployed at `brain.raceraja001.in`.
> **Roadmap:** memory-quality → **notifications** → reliability debt → reactive UI → distillation.
> **Target device:** Android (Web Push works in-browser; no install requirement, none of the iOS caveats).

## Problem

The daily brief is fully generated (needs-attention, big decisions, yesterday's capture count,
pending-approval count) by `BriefComposer.compose_daily`, stored as a `Notification` row, and it
fires a `BRIEF_COMPOSED` event. **But delivery only reaches an open dashboard tab** — via the
WebSocket/Redis relay. When the phone is asleep or the app is closed, the brief is generated and
effectively dropped. There is **no push-to-phone capability at all** today (`sw.js` has no `push`
listener; no VAPID; no subscription storage). The user wants the brief to actually arrive on their
phone each morning.

## Decisions (locked with user)

- **Web Push (VAPID)** — real OS notifications from the PWA, delivered even when the app is closed.
  (User is on Android, so the browser path works without PWA-install.)
- **Daily brief first** — deliver the already-generated brief; time-based reminders (which need a
  new date-extraction step) are a later phase, explicitly out of scope here.
- **Test-push button** — a `POST /notifications/push/test` + a UI button so the user can verify
  delivery immediately instead of waiting for the 07:30 IST cron.
- **Global on/off** — a single subscribe/unsubscribe toggle per device; no per-type prefs, no quiet
  hours in v1.

## Non-goals (v1)

- No time/date-based reminders ("insurance due in 3 days") — needs date extraction; separate feature.
- No per-notification-type preferences, no quiet hours, no snooze.
- No delivery of other events (pending-approval pings, etc.) — brief only. (The delivery service is
  generic, so adding events later is a one-line subscription.)
- No iOS-specific handling (Android target); the code stays standards-compliant so iOS-installed-PWA
  works too, but it isn't tested/guided here.
- No in-app notification-center rewrite — the existing `/notifications` API + activity feed stay.

## Architecture

```
Phone PWA  ── tap "🔔 Enable" ──▶ Notification.requestPermission()
                                  └▶ registration.pushManager.subscribe({
                                        userVisibleOnly: true,
                                        applicationServerKey: <VAPID public> })
                                     │
              POST /api/v1/notifications/push/subscribe { endpoint, keys{p256dh, auth} }
                                     │
                       push_subscriptions table (tenant-scoped, endpoint unique)

Daily brief cron (run_daily_brief, 02:00 UTC ≈ 07:30 IST)
        └▶ compose_daily → Notification row + emit BRIEF_COMPOSED {id,title,body,tenant_id}
                                     │
                    PushDeliveryHandler.subscribe() (registered in main.py lifespan)
                                     │  webpush(sub, payload={title, body, url:"/m"}, VAPID private)
                                     │  ├─ 201/2xx → delivered
                                     │  └─ 404/410 → prune dead subscription
                                     ▼
              Phone service worker  self.addEventListener('push') → showNotification(title, body)
                                    self.addEventListener('notificationclick') → focus/open "/m"
```

## Components

### 1. VAPID keys (config)

- Generate a VAPID keypair once (via `pywebpush`/`py-vapid` CLI or a one-off script). **Private key**
  → VM `.env.production` `LIFE_GRAPH_VAPID_PRIVATE_KEY` (never git). **Public key** → both
  `LIFE_GRAPH_VAPID_PUBLIC_KEY` (backend, to serve) and the dashboard build env
  `NEXT_PUBLIC_VAPID_PUBLIC_KEY` (the browser needs it to subscribe — it is public by design).
- New settings in `config.py`: `vapid_public_key: str = ""`, `vapid_private_key: str = ""`,
  `vapid_subject: str = "mailto:tolokanathan@gmail.com"` (VAPID requires a contact).

### 2. `push_subscriptions` table (+ migration)

- Columns: `id` (UUID pk), `tenant_id` (String, indexed, NOT NULL), `endpoint` (Text, unique),
  `p256dh` (Text), `auth` (Text), `user_agent` (Text, nullable), `created_at`, `last_used_at`
  (nullable). Unique index on `endpoint` (a device re-subscribing upserts). Index `(tenant_id)`.
- Alembic migration next revision after current head. Tenant-scoped like every table.

### 3. Push service (`services/webpush.py`)

- `pywebpush` dependency (add to `pyproject.toml`).
- `async def save_subscription(sub: dict) -> None` — upsert by endpoint (tenant from contextvar).
- `async def delete_subscription(endpoint: str) -> None`.
- `async def send_to_tenant(tenant_id: str, title: str, body: str, url: str = "/m") -> int` —
  load the tenant's subscriptions, `webpush(...)` each with the VAPID private key + subject; on
  `WebPushException` with 404/410, delete that dead subscription; return delivered count. Runs the
  blocking `pywebpush` call in a thread (`asyncio.to_thread`) so it doesn't block the loop.
- Payload JSON: `{"title", "body", "url"}` (small — Web Push has a ~4KB limit; the brief body is
  truncated to a sensible push length, full brief remains in the app).

### 4. Push API (`api/notifications.py` additions or a new `api/push.py`)

- `POST /api/v1/notifications/push/subscribe` `{endpoint, keys:{p256dh, auth}}` → save → `{ok:true}`.
- `DELETE /api/v1/notifications/push/subscribe` `{endpoint}` → delete.
- `GET /api/v1/notifications/push/vapid-key` → `{key: <public>}` (so the client can fetch it if not
  baked into the build env — belt-and-suspenders).
- `POST /api/v1/notifications/push/test` → `send_to_tenant(title="Life Graph", body="Test
  notification 🎉", url="/m")` → `{delivered: n}`.
- All tenant-scoped via the contextvar.

### 5. Delivery handler (event-driven)

- `PushDeliveryHandler` subscribes to `EventType.BRIEF_COMPOSED` in `main.py` lifespan (mirroring
  how `preference_graph_service.subscribe()` and the webhook handler are wired). On the event:
  `send_to_tenant(payload.tenant_id, title=payload.title, body=<first ~200 chars of body>, url="/m")`.
- Delivery failures never raise into the brief flow (the handler swallows/logs), matching the
  event-bus isolation pattern.

### 6. Service worker (`dashboard/public/sw.js`)

- Add `self.addEventListener("push", e => { const d = e.data.json(); e.waitUntil(
  self.registration.showNotification(d.title, { body: d.body, data: { url: d.url }, icon,
  badge })) })`.
- Add `self.addEventListener("notificationclick", e => { e.notification.close(); e.waitUntil(
  clients.matchAll({type:"window"}).then(wins => a focused/existing window → navigate, else
  clients.openWindow(d.url)) )})`.
- Bump `CACHE_NAME` (existing convention) so the new SW activates; the existing install/activate/
  fetch caching logic is preserved.

### 7. Mobile UI ("enable notifications")

- On the mobile Home (`app/(mobile)/m/page.tsx`) or a small settings row: a **"🔔 Enable
  notifications"** control. On tap: `Notification.requestPermission()`; if granted,
  `navigator.serviceWorker.ready` → `pushManager.subscribe({userVisibleOnly:true,
  applicationServerKey: urlBase64ToUint8Array(NEXT_PUBLIC_VAPID_PUBLIC_KEY)})` →
  `api.push.subscribe(sub.toJSON())`. Reflect state: enabled (subscribed) / blocked (permission
  denied → hint to unblock in browser settings) / off. A small "Send test" affordance calls
  `POST /push/test`. Unsubscribe removes the subscription + calls DELETE.
- `lib/api.ts`: `api.push.{subscribe, unsubscribe, test, vapidKey}` helpers.

## Failure handling

| Case | Behaviour |
|---|---|
| Permission denied | UI shows "blocked" state + how to re-enable in browser settings; no crash |
| Subscription endpoint dead (410/404) | Pruned from `push_subscriptions` on next send; delivered count reflects reality |
| VAPID keys unset | Push service no-ops with a logged warning; subscribe endpoint returns a clear 503 |
| Brief is empty (compose_daily → None) | No event, no push (silence-by-design preserved) |
| pywebpush blocking call | Run in `asyncio.to_thread`; a slow/failed send never blocks the brief cron |
| Push payload too large | Body truncated to a push-safe length; full brief stays in-app |

## Verification

1. Unit: `save_subscription` upserts by endpoint (tenant-scoped); `send_to_tenant` calls webpush per
   sub and prunes on a simulated 410; the `BRIEF_COMPOSED` handler calls `send_to_tenant` with the
   brief's title/body; test endpoint sends. (Mock `pywebpush`.)
2. Migration up on a copy of live data: `push_subscriptions` created, existing data untouched.
3. Live E2E: subscribe from the phone → `POST /push/test` → **notification appears on the phone**
   (app closed) → tap → opens the app. Then trigger `run_daily_brief` (or wait/force) → the brief
   arrives as a push.
4. Negative: deny permission → UI blocked state; unsubscribe → no more pushes; dead endpoint pruned.
