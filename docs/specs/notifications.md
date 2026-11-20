# Notifications — which module does what

> **Status: Built (description of existing code, no new design).** Last verified: 2026-11-20.
> Written for audit finding L16 (`docs/audits/2026-11-19-code-quality-audit.html`): three
> modules with similar names, two record tables. Nothing here was renamed; see
> "Naming" at the end for the recommendation.

## The three parts

| Module | What it owns | Table | Read by |
|---|---|---|---|
| `life_graph/kernel/notification_engine.py` (`NotificationEngine`, `runtime.get_notification_engine`) | **The owner's inbox records.** Creates, lists and marks read the rows the owner sees: task failures, schedule disables, threshold alerts, free-LLM offers (`services/llm/offers.py`), dev-task outcomes (`services/dev/outcomes.py`). It does **not** deliver anything. | `notifications` (`models/tenancy.py` `Notification`) | `GET /kernel/notifications`, `/kernel/notifications/{id}/read`, `/read-all`; the phone via `GET /jarvis/notifications` |
| `life_graph/watchers/notification_engine.py` (`NotificationEngine`, `runtime.get_watcher_notification_engine`) | **Watcher event delivery.** Routes a watcher's event by severity to channels (`watchers/channels/`: email, webhook, terminal, Telegram), queues the rest, re-sends stale criticals, and logs every attempt. Urgent watchers (`app_uptime`, `server_health`) also push to the phone at once. | `watcher_notifications` (delivery log: channel, status, retries, error) and `notification_channels` (per-tenant channel config), `watchers/models.py` | `GET /watchers/notifications`, the watcher digest (`watchers/digest.py`) |
| `life_graph/services/notifications/` (package) | **Reaching the phone and Telegram for owner-facing items.** `due` writes due bills, to-dos, documents and timed reminders as `notifications` rows; `actions` handles the buttons on those rows (bill paid, snooze, errand Approve/Reject); `approval` tells the owner a new approval needs them; `push_delivery`/`webpush` and `telegram_delivery`/`telegram_binding` deliver the daily brief over Web Push and Telegram. | writes `notifications` rows; push subscriptions and Telegram bindings in their own tables | `/jarvis/notifications` and `/jarvis/notifications/{id}/action` (`api/jarvis.py`) |

## Rules of thumb

- **Something the owner should see and act on later** → a `notifications` row, through the
  kernel engine (or `services/notifications/due.py` for due items). The phone polls these.
- **A watcher noticed something** → `watchers/notification_engine.route_event`; it picks the
  channels from the tenant's `notification_channels` and records each delivery in
  `watcher_notifications`.
- **Push it to a device now** → `services/notifications/` (Web Push, Telegram).
- The two `NotificationEngine` classes share a name only. Import them by module, and get
  the singletons from `runtime.get_notification_engine()` /
  `runtime.get_watcher_notification_engine()`.

## Naming (recommendation, not done)

The duplicate class name is the main source of confusion. Recommended, as its own PR once
the parallel refactors have landed: rename `watchers/notification_engine.py` to
`watchers/delivery.py` with class `WatcherDelivery`, keeping the old module as an alias
(the pattern used for the 2026-11-18 `services/` regrouping). Merging the two tables
(`notifications` and `watcher_notifications`) is a larger, later change: one is an inbox,
the other a delivery log, and the watcher digest reads the log.
