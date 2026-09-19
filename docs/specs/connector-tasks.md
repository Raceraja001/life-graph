# Google Tasks Connector — Feature Spec

> **Status: Built (2026-09-19).** Plugin `plugins/tasks/`, migration 042, brief
> section **Tasks**, Overview → Today *Tasks* block, "in Tasks" on matching
> promises, tool `tasks_due`, task questions in jarvis's chat context. Verified
> end to end on a copy of the live DB against a fake Tasks API; unit tests in
> `tests/unit/test_connector_tasks.py`. Approved as proposed, read-only (no
> "Add to Tasks").
>
> **Where the build differs from the text below:**
> - The daily full listing does not use the API's `completedMin`, since it is
>   not certain that the filter keeps open tasks. Completed tasks older than a
>   week are dropped in code instead.
> - Task flags are replaced on each sync, like contacts and code items, so a
>   status or due date cleared in Google is cleared here.
> - A promise shows "in Tasks" off the machine even when the Tasks account is
>   local-only. That reveals that a match exists, never a task title.
> - The Google-client help text in Settings now names every API and says to set
>   the consent screen to *In production*.
>
> **Purpose**: Show the user's own to-do list next to the calendar, mail and
> bills:
> - overdue tasks, tasks due today and tasks due this week, in the brief and on
>   the Today card;
> - promises found in sent mail ("I'll send the deck by Friday") that already
>   have a matching task are marked, so the same thing isn't nagged about twice.
>
> **Shape**: a fifth connector plugin, `plugins/tasks/`, on the connector runtime
> ([connectors.md](connectors.md)). It reuses the Google OAuth client set up for
> Gmail, Calendar and Contacts.
>
> **Depends on**: PR #35 (runtime). Stacked after #38 so the branches stay
> linear. Migration 042.

---

## Decisions

| Question | Proposal | Why |
|---|---|---|
| Source | **Google Tasks API**, OAuth, scope `tasks.readonly` | Google Tasks has no app-password or CalDAV route, so sign-in is the only way in. |
| Read-only? | **Yes.** Creating a task from a promise is left for later. | Writing needs the full `tasks` scope, which gives up the read-only guarantee every connector has so far. Reminders from promises already exist (**Remind me**). |
| Which lists | All task lists; the list name is shown | Most people have one or two. |
| What is kept | Open tasks, plus tasks completed in the last 7 days (for "done this week") | Completed tasks disappear after a week. |
| Due dates | Google Tasks stores a date only (no time); taken as is | Nothing to parse: the API gives an ISO date. |
| Cloud visibility | **Title and due date** by default; notes **never**. The account can be local-only (counts). | Tasks are the user's own words, like calendar titles. Notes can hold anything. |
| Promise ↔ task | A promise whose words match an open task (shared distinctive words, as payees are matched for bills) shows "in Tasks" and no Remind me button | Avoids a duplicate reminder. |
| Sync | Every 15 min; incremental with `updatedMin` and `showDeleted`, a full listing once a day | Deleted and completed tasks are picked up quickly. |

---

## Requirements

### Story 1 — Sync

- **Account:** connector `tasks`, auth `oauth`, one per Google account. It is set up with the same Google client as the other connectors; the user enables the **Tasks API** in that Cloud project.
- **Calls:** `tasklists.list`, then `tasks.list` per list with `showCompleted`, `showHidden`, `showDeleted` and `updatedMin` (the last sync time minus a margin).
- **Item mapping:**

  | Item field | Holds |
  |---|---|
  | `external_id` | `list_id:task_id` |
  | `title` | The task title |
  | `starts_at` | The due date (midnight in the user's timezone), or empty |
  | `local_detail` | Notes. Never cloud-bound. |
  | `flags` | `list`, `status` (`needsAction` / `completed`), `completed_at`, `parent` (subtasks), `url` |

- **Retention:** completed more than 7 days ago, or deleted at the source → removed.
- **Errors:** a revoked grant → **Reconnect needed**. A Tasks API that isn't enabled gets a clear message, as for contacts.

### Story 2 — Use it

- **Brief section "Tasks"**, only when non-empty:
  ```
  ## Tasks
  - Overdue (2): Renew car insurance (Tue 15 Sep); Call plumber (Wed 16 Sep)
  - Today: Send invoice to Acme
  - This week (3): Book tickets (Fri); Pay school fee (Sat); +1 more
  - Done this week: 5
  ```
  - Subtasks are folded under their parent.
  - Tasks without a date appear only as a count ("+4 with no date").
- **Today card:** a *Tasks* block with the same groups, each row linking to Google Tasks.
- **You promised:** a promise whose words match an open task shows "in Tasks" instead of **Remind me**.
- **Tool `tasks_due`** for `admin` and `jarvis`, filtered by audience.
- **Chat context** for jarvis: task, to-do, todo, "my list".

### Story 3 — Exposure

| Field | LOCAL | CLOUD | `local_only` account, CLOUD |
|---|---|---|---|
| Title (redacted off the machine), due date, list, status | yes | yes | count only |
| Notes | yes | **never** | never |

---

## Design

- **`base.py`:** `KIND_TASK = "task"`.
- **Migration 042:** allows kind `task` in the kind check constraint.
- **`google_oauth.SCOPES["tasks"]`:** `tasks.readonly`.
- **Plugin `plugins/tasks/`:**
  - `connector.py`.
  - `google_source.py`: paging, incremental sync, mapping.
- **Core:**
  - `store.tasks_due(session, tenant, today)`.
  - `exposure._task_view`.
  - The brief section.
  - `tools.tasks_due`.
  - The chat intent.
  - The Today card block.
  - Promise matching in `open_promises` (flag `in_tasks`).
- **No new dependency.**

## Testing

- **Unit:**
  - Mapping: due dates in the user's timezone, completed, deleted, subtasks.
  - Incremental cursor.
  - Exposure (notes never to the cloud).
  - Brief grouping.
  - Promise matching.
  - 401 → reauth; API disabled → clear error.
- **End to end,** on a copy of the live DB with a fake Tasks API:
  - Full then incremental sync.
  - Complete and delete a task.
  - The brief for each audience.
  - A promise matched to a task.
  - Migration 042 down and up.
- **Real account:** checked after deploy, when the user signs in.

## What the user sets up (~2 minutes, after the Google client from #35)

- **Enable the Tasks API:** Google Cloud Console → APIs & Services → enable **Google Tasks API**.
- **Sign in:** Settings → Add account → *Google Tasks* → Continue to Google.
- **Keep the sign-in working:** the OAuth consent screen must be **In production**, not *Testing*. In Testing, Google expires the sign-in after 7 days. This applies to every Google sign-in, and is already noted in connectors.md.
