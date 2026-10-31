# Device access: what a paired phone's token opens

Status: built 2026-10-25 (life-graph-android docs/PLAN-v4.md, task S1.2).
Code: `life_graph/api/device_access.py` (the table), `life_graph/api/middleware.py`
(`_device_for`, `AuthMiddleware`, `TenantMiddleware`).

A phone pairs once (`POST /api/v1/devices/pair`, services/devices.py) and gets a
token of its own. That token is not a service key. It opens:

1. every Jarvis endpoint, `/api/v1/jarvis/*`, any method (api/jarvis.py), and
2. the routes in the table below, with exactly the method listed.

Everything else answers a device token with 401, as it always did. The
service key is unchanged.

## Rules

- **Tenant from the device.** `TenantMiddleware` sets the tenant to the one that
  paired the device and the user to `device:<id>`, whatever `X-Tenant-ID` or
  `X-User-ID` the phone sends.
- **Read-only first.** Beyond Jarvis, a phone may read what the dashboard
  screens show, and take four named actions. It cannot create, edit or delete
  anything else, start agent or dev work, change settings or connectors, pair
  or revoke devices, or reach `/admin`.
- **Exact match.** The path checked is the one Starlette routes on
  (`scope["path"]`, already percent-decoded) and it must equal
  `request.url.path`. It must be plain segments only: no `.` or `..` segment,
  no `//`, no `%` left after decoding, no `?`, `#`, `\` or spaces. Each entry
  is the route's own template, every `{param}` a UUID, matched against the
  whole path: no prefix matches, no trailing-slash or case variants, and an id
  can never be a literal route such as `tasks/stats`. A GET entry does not
  admit HEAD or OPTIONS.
- **Decisions from the phone are marked.** An approval approved or rejected
  with a device token is stored with `resolved_by = "phone:<device id>"`; the
  request body cannot name anyone else.
- **local_only accounts.** What the phone is sent leaves this machine (the
  tunnel, the handset). Connector items from a `local_only` account reach it
  as their due notifications do: when, and what kind, never the title,
  people, payee or amount (`connectors/exposure.phone_rows`). This applies to
  `GET /api/v1/connectors/today` called with a device token and to
  `GET /api/v1/jarvis/today`. The dashboard (service key) still gets the full
  local view.

## Read-only routes

| Method and route | Feature | Why the phone needs it |
|---|---|---|
| `GET /api/v1/money/summary` | Money | Month spent per category against budgets (Money screen, Today card). |
| `GET /api/v1/money/transactions` | Money | The month's transactions list. |
| `GET /api/v1/money/budgets` | Money | Budgets tab. |
| `GET /api/v1/money/categories` | Money | Category names for the lists. |
| `GET /api/v1/money/checkin` | Money | The weekly check-in card. |
| `GET /api/v1/documents` | Documents | Documents list. |
| `GET /api/v1/documents/expiring` | Documents | What expires soon. |
| `GET /api/v1/connectors/today` | Bills, calendar, mail waiting | Today's events, mail waiting on you, promises, tasks, bills and birthdays (local_only masked, see Rules). |
| `GET /api/v1/monitors` | Monitors | Page monitors and their last check. |
| `GET /api/v1/study/due` | Study | The cards due, to review on the phone. |
| `GET /api/v1/study/decks` | Study | Each deck's cards, due, reviewed and retention (counts and deck names only). |
| `GET /api/v1/study/progress` | Study | Streak, due/new/learning/mature counts, drafts waiting and accuracy per deck (counts and deck names only). |
| `GET /api/v1/study/drafts` | Study | Draft cards waiting for the owner to check, to read on the phone (accepting stays on Telegram and the dashboard). |
| `GET /api/v1/invoices` | Invoices | Invoices list. |
| `GET /api/v1/invoices/{invoice_id}` | Invoices | One invoice. |
| `GET /api/v1/memories/` | Memories | Search and browse memories (Memory tab). |
| `GET /api/v1/memories/pending/count` | Memories | The to-review badge. |
| `GET /api/v1/memories/{memory_id}` | Memories | One memory. |
| `GET /api/v1/judgment/decisions` | Decisions | Decisions list. |
| `GET /api/v1/judgment/decisions/{decision_id}` | Decisions | One decision with its predictions. |
| `GET /api/v1/judgment/calibration` | Calibration | Calibration score. |
| `GET /api/v1/judgment/calibration/curve` | Calibration | Calibration curve. |
| `GET /api/v1/judgment/stats` | Calibration | Judgment stats. |
| `GET /api/v1/research/runs` | Research | Research runs. |
| `GET /api/v1/research/runs/{run_id}` | Research | One research run. |
| `GET /api/v1/tech-watch` | Tech watch | What the tech watch found. |
| `GET /api/v1/kernel/tasks` | Tasks | Agent tasks (the dashboard's Tasks page). |
| `GET /api/v1/kernel/tasks/{task_id}` | Tasks | One task. |
| `GET /api/v1/kernel/drivers/tasks` | Dev tasks | Dev tasks list. |
| `GET /api/v1/kernel/drivers/tasks/stats` | Dev tasks | Dev task stats. |
| `GET /api/v1/kernel/drivers/tasks/{task_id}` | Dev tasks | One dev task and its stage. |
| `GET /api/v1/kernel/drivers/tasks/{task_id}/steps` | Dev tasks | A dev task's recorded steps. |
| `GET /api/v1/kernel/drivers/night-shift` | Dev tasks | The night run: merged, waiting, failed. |
| `GET /api/v1/approvals` | Approvals | What waits for a decision. |
| `GET /api/v1/kernel/observability/agents` | Agents | Agents console. |
| `GET /api/v1/kernel/drivers/scorecards` | Agents | Per driver: runs, success, bounces, merges, cost, top failure causes (owner OK 2026-10-25; numbers, model and persona names only). |
| `GET /api/v1/kernel/observability/budget` | Agents | Paid spend this month against the cap, projection, top tasks by cost (titles and cost; owner OK 2026-10-25). |
| `GET /api/v1/watchers/events` | Activity | Activity feed. |
| `GET /api/v1/watchers/events/summary` | Activity | Activity counts. |
| `GET /api/v1/kernel/schedules` | Schedules | Scheduled jobs. |
| `GET /api/v1/kernel/schedules/{schedule_id}` | Schedules | One schedule. |
| `GET /api/v1/kernel/personas` | Personas | The persona roster. |
| `GET /api/v1/kernel/personas/{persona_id}` | Personas | One persona. |
| `GET /api/v1/apps/health` | App health | Each watched app's last check. |
| `GET /api/v1/llm-offers` | LLM offers | Free model offers and their evaluations. |

`GET /api/v1/approvals` and `GET /api/v1/money/checkin` compute as they read
(the approvals feed reconciles its producers first), exactly as for the
dashboard; neither changes anything the owner sees as a decision.

## Actions

| Method and route | Feature | Why |
|---|---|---|
| `POST /api/v1/approvals/{approval_id}/approve` | Approve an approval | The owner decides on the phone; recorded as `phone:<device id>`. |
| `POST /api/v1/approvals/{approval_id}/reject` | Reject an approval | As above. |
| `POST /api/v1/study/cards/{card_id}/grade` | Answer a study card | Review cards on the phone (`{"grade": "again|hard|good|easy"}`). |

Two more actions the plan names are Jarvis endpoints, so they need no entry:

- **Mark a bill paid:** `POST /api/v1/jarvis/bills/{item_id}/paid`. Only "paid".
  The dashboard's `POST /api/v1/connectors/items/{item_id}/bill` also takes
  `dismiss` and `remind` in its body, which a path rule cannot tell apart, so
  it stays service-key only.
- **Approve or reject a memory:** `POST /api/v1/jarvis/memories/{memory_id}/approve`
  and `.../reject` (since v2).

## Deliberately not allowed

Examples: `POST /api/v1/memories/` and every memory edit or delete, the
dashboard's `/memories/{id}/approve` (the phone has its own), device pairing
codes and revocation (`/api/v1/devices*`), `/api/v1/kernel/tasks` writes and
`/kernel/tasks/{id}/cancel`, starting dev work (`POST /api/v1/kernel/drivers/tasks`,
`/dispatch`), dev task diffs, budgets, imports, connector accounts and
credentials, personas and schedules writes, watchers config, the autonomy
kill switch, `POST /api/v1/research` (spends model and fetch time), study card
generation, drafting, accepting, editing and deletion, invoice send/paid/void, LLM offer evaluation, and
everything under `/api/v1/admin`.

## Adding an entry

Add it to `DEVICE_ALLOWLIST` and to the table here with its reason.
`tests/unit/test_device_access.py` fails until both agree and the route really
exists with that method; `tests/integration/test_device_access.py` calls every
entry with a real device token.
