# Job 2 — Night Shift Report: Feature Spec

> **Status: Built** (2026-10-20). Job 2 of [Jarvis and its workers](../design/11_persona_roster_plan.md).

## Goal

Every morning, one message that says what the coding engines did since the last one: what
merged, what is waiting for the owner **and why**, what failed **and why**, and what is still
queued. Plain code over dev tasks and approvals; no model call.

## Acceptance criteria

- **AC-1** GIVEN dev tasks that settled in the last 24 h WHEN the daily brief is composed THEN
  it has a "Night shift" section with counts (merged / waiting for you / failed / queued) and one
  line per task. *(test: `test_night_shift_lines`)*
- **AC-2** A merged task's line has its PR link. *(test)*
- **AC-3** A task waiting for the owner says why: the reasons the quality gate gave
  (`change_policy.auto_gate`: protected path, size, no proof checks, trust not yet earned) or
  that the change is unverified. *(test)*
- **AC-4** A failed task names its cause (`failure_causes.classify`), and says when the failure
  was handed on (escalated to OpenCode, or re-queued after a rate limit). *(test)*
- **AC-5** Nothing settled and nothing queued → no section (the brief stays silent about it).
  *(test)*
- **AC-6** `GET /api/v1/kernel/drivers/night-shift?hours=24` returns the same report as data.
  *(integration test)*
- **AC-7** *(2026-11-28)* A task that settled as "no changes needed" (status `completed`, stage
  `no_changes`: it finished normally and said nothing needed changing) is listed under
  `no_changes` with the agent's message (one line, ≤ 160 chars) as its `reason` — never under
  `failed`. `lines` adds `no changes needed: <title> — <reason>` and, when there are any,
  `, N checked with no changes needed` on the head line. *(test:
  `tests/unit/test_no_changes_outcome.py`)*

## Design

`services/night_shift.py`:

- `report(session, tenant_id, since)` → `{since, merged: [...], waiting: [...], failed: [...],
  no_changes: [...], queued: n}`, each item `{id, title, stage, pr_url, reason}`. Built from
  `dev_tasks.list_dev_tasks` (the same stages the dashboard shows); for a waiting task the reason
  comes from the pending approval's payload through `change_policy.auto_gate`; for a failed task
  from `failure_causes.classify`.
- `lines(report)` → the brief section's lines. Task titles are code work, not personal data, so
  the section may go to Telegram like the rest of the brief.

Brief: `BriefComposer` adds `## Night shift` after "Coming up" when `lines` is not empty.
