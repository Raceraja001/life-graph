# Jobs 5 and 7 — Money Check-in, App Health: Feature Spec

> **Status: Built** (2026-10-20), with stubs where the owner's data is not in yet. Jobs 5
> and 7 of [Jarvis and its workers](../design/11_persona_roster_plan.md). Both build on
> Phase C (money) and Phase E (uptime) of
> [assistant-capabilities.md](assistant-capabilities.md): the import, categories, budgets,
> health probes, certificates and backup checks were already there; these jobs make them
> reach the owner.

## Job 5 — money check-in

Where the money went this month, what changed against last month, and what is over budget:
weekly, and whenever the owner asks.

- **AC-5.1** The check-in compares the month so far (the 1st to today) with **the same days**
  of last month (the 31st against a 30-day month takes all of it). Spending is debits except
  transfers and investments; income is not spending. *(unit + integration)*
- **AC-5.2** Every figure is a sum of the imported rows: per category spent, last month,
  change and change %, % of budget; the month total; the top three merchants. *(integration)*
- **AC-5.3** Over budget (≥ 100%) and near budget (80–99%) are named, with the categories that
  moved most. *(unit)*
- **AC-5.4** Two renderings: with amounts and merchants for the dashboard, the API and the
  local model; categories and percentages only for the brief and any cloud model.
  *(unit + integration)*
- **AC-5.5** Monday's brief has a "Money this week" section (cloud rendering); nothing
  imported → no section. `GET /api/v1/money/checkin`; Jarvis tool `money_checkin` (personal:
  never offered to a cloud run, services/lead.py).

**Stub:** no statement has been imported for raja yet (0 transactions). The figures are
tested on fixture rows; real figures arrive with the first `POST /api/v1/money/import`
(statement CSV) or forwarded bank alerts (`POST /api/v1/money/alerts`).

## Job 7 — app health

An outage or a failing backup reaches the owner within the hour.

- **AC-7.1** The hourly `app_uptime` watcher confirms a failed check with a second one
  `RECHECK_SECONDS` (30) later **in the same run**, so an outage is declared within the hour
  rather than at the next run; one blip is still not an outage. *(integration)*
- **AC-7.2** IMPORTANT events from `app_uptime` and `server_health` (down, certificate ≤ 7
  days, backup failing) are sent at once by Web Push and Telegram, as approvals are; before,
  they were queued for a "terminal" channel nothing drained. Other watchers are unchanged.
  *(unit)*
- **AC-7.3** `GET /api/v1/apps/health` and the Jarvis tool `app_health` report each watched
  app: status (up / failing / down / not checked yet), HTTP status, latency, certificate days
  left, backup state, from the watcher's own state (no new probe). *(unit)*
- **AC-7.4** server_health findings are investigated by ops in propose mode (read-only tools;
  services `watchers/origination.py`, built with the Jarvis-lead step).

**Stub:** no project has a health URL yet. Set one per app with the project settings API
(`health_url`, and `backup_check_command` for a command that exits non-zero when the latest
backup is missing or stale); the watcher config is created on the first one.

## Not in this slice

- Error rates from an app's logs, and deploy checks (the dev-task pipeline's own smoke and
  rollback cover deploys it makes).
- A weekly money push of its own: the check-in rides on Monday's brief.
