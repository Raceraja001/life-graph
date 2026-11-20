# Quality phase 2: engineering progress log

This log tracks the remaining findings from the 2026-11-19 audit (`docs/audits/2026-11-19-code-quality-audit.html`). Each change carries three separate kinds of evidence: **local** (worktree test runs), **CI** (GitHub Actions on the PR, with Postgres) and **production** (a check on the live prod edition after a release).

## Batch 1: P0 trust boundaries (2026-11-20)

Three PRs went in, each reviewed and merged to master:
- #294 (`22d80d6`): host commands.
- #295 (`dde2958`): owner identity.
- #293 (`e0fbaa9`): at-most-once side effects.

**Not deployed to prod. Owner enforcement is not enabled.**

**Before starting, prod was checked read-only (counts only, no values):**
- 0 projects use deploy, smoke, rollback or backup_check commands or a `health_url`.
- 0 autonomy actions have a `rollback_command`.
- Prod has 2 owner keys, both also in the service-key list, and 1 non-owner service key.
- The key used by Claude Code and the MCP server (the agent path) is that **non-owner** key.

### Per-finding results

#### H3: owner-only approvals, both systems (#295)
- **Root cause:** `/autonomy/approvals/{id}/resolve` and `/batch` took `resolved_by` from the request body and ignored `approvals_require_owner`. Neither system recorded who asked for the work, so an agent could approve its own task.
- **Change:**
  - New shared `api/approval_identity.py` (`resolver`, `require_owner`, `refuse_self_approval`), used by both routers. The body's `resolved_by` survives only as a "client said" note.
  - `POST /drivers/tasks` now stamps `requested_by`, and a non-owner caller can't approve its own task. This holds whatever the setting.
  - Owner-enforcement readiness shows in `/kernel/observability/system` as counts only, and startup warns when enabling enforcement would lock everyone out.
- **Tests:**
  - 24 new tests: 15 failed and 6 errored on the old code (the other 3 cover the brand-new readiness module); all pass now.
  - Full unit suite: 6218 passed.
- **CI:** green.
- **Production:** not deployed.
- **Remaining risk:** only tasks started after deploy carry `requested_by`.

#### H2: host shell commands from project settings (#294)
- **Root cause:** any service key could set `deploy`, `smoke`, `rollback` or `backup_check` commands. The hourly watcher ran `backup_check` with no approval, and deploys ran whatever the payload held.
- **Change:**
  - Setting or changing a command needs an owner-verified caller. The owner's write is the approval, pinned by sha256 in `scan_metadata.command_approvals`.
  - A single gate, `approved_command()`, is used by the watcher, `app_health` and deploy filing. Deploy payloads carry the pins, which are re-checked right before deploy, smoke and rollback run.
  - Command text is hidden from non-owner keys.
- **Tests:**
  - 45 new tests: all 45 failed on the old code and pass now.
  - Full unit suite: 6246 passed.
- **CI:** green.
- **Production:** not deployed.
- **Remaining risk:** commands saved before this change stop running until the owner re-saves them. Prod has none.

#### NEW: autonomy `rollback_command` runs host shell (#294)
- **Root cause:** `POST /autonomy/auto-actions` stored a `rollback_command` from any caller. Both rollback routes ran it with `create_subprocess_shell`.
- **Change:** non-owner callers get 403. The command's sha256 is pinned in `before_state`, and rollback runs only while the pin matches.
- **Tests:** 7 new tests: 6 failed on the old code (the 7th is a positive control that passes on both); all pass now.
- **CI:** green.
- **Production:** not deployed.
- **Remaining risk:** low.

#### H4: at-most-once approved actions (#293)
- **Root cause:** side effects ran inside the request transaction. A crash or restart after the effect but before the commit rolled the row back to pending, and the next approve or the auto-merge sweep ran it again.
- **Change:**
  - A durable claim (`payload.execution`) is committed before the effect for `driver_pr`, `merge`, `deploy`, `plan` and `autonomous_action`.
  - A claim in progress gets 409. Once it is `failed` or `unknown`, an explicit owner-gated `retry` is needed, except where a re-run is harmless (PR and merge re-runs detect work already done).
  - A stale-claim sweep turns claims older than 1 h into `unknown` and notifies the owner. The auto-merge sweep uses the same claim.
  - Only the side effect's own transaction is exempt from the idle timeout.
- **Tests:**
  - 31 new unit tests: 15 failed on the old code.
  - 5 integration tests: a crash means no re-run; 3 concurrent approves give 200, 409, 409 with one deploy; manual approve vs the sweep; stale claim, then retry.
  - Full unit suite: 6300 passed.
- **CI:** green, including integration.
- **Production:** not deployed.
- **Remaining risk:**
  - The UI and Android app have no retry button yet.
  - `_auto_open_pr` opens PRs outside `resolve()`.

### Discovered during the batch (new, not yet fixed)
1. **Autonomy `command`:** `POST /autonomy/auto-actions` accepts the main `command` from any service key, and the classifier can run it as a host shell at L1–L3. The `agent_id` whose trust drives that decision comes from the request body. **This is P0 for batch 2.**
2. `PATCH /kernel/projects/{id}`: any service key can set `auto_approve_plans` or `auto_merge`.
3. `POST /autonomy/trust/override`: the `by` field comes from the request body.
4. `POST /autonomy/levels/{id}/set` is not owner-gated.
5. Errand approve and reject buttons in `/jarvis/notifications/{id}/action` are not owner-gated.
6. `/autonomy/approvals/batch` with no filters resolves every pending entry. It is owner-gated only when enforcement is on.
7. The autonomy queue has no `requested_by` (needs a migration), so self-approval is not detected there.

### Owner actions required (nothing has been changed in prod)
1. **Release batch 1 to prod.** On approval:
   1. Merge master into `prod`.
   2. Tag a rollback point.
   3. `./dev.sh restart`.
   4. Restart `life-graph-dev-runner`.
   5. Run the live checks.

   No migrations are involved.
2. **Enable owner enforcement:**
   1. Confirm the key you sign in to the dashboards with is one of the 2 owner keys. It lives in the browser as `localStorage lg_api_key` and is sent as `Authorization: Bearer`.
   2. Keep the Claude Code and MCP key out of `LIFE_GRAPH_OWNER_API_KEYS`. It is a non-owner key today.
   3. After the release, check that `/kernel/observability/system` shows `approvals.lockout_risk=false`.
   4. Set `LIFE_GRAPH_APPROVALS_REQUIRE_OWNER=true` in prod `.env` and restart.
   5. Test one approve from the dashboard and one from the phone.

   If the dashboard uses the non-owner key, approving its own MCP-started tasks returns 403 *even before enforcement*, because the self-approval guard is always on. Signing in with an owner key fixes that.
3. **Add a retry button** in the UI and Android app for failed or unknown approvals (`POST /approvals/{id}/approve` with body `{"retry": true}`).

## Batches 2 to 6, merged 2026-11-20

Every PR in this section was reviewed, passed CI (including integration tests against Postgres) and merged. In each one the regression tests failed on the pre-change code. The per-finding tables are in each PR body.

| PR | Batch | What it fixed |
|---|---|---|
| #300 | P0 autonomy trust | (1) A non-owner `auto-actions` caller acts under its own server-derived identity, is always queued and never auto-executes. (2) Every autonomy command is pinned by sha256. (3) Owner-only: trust override, level set, safety rules, kill-switch resume, shadow grading, rollback. (4) Batch resolve needs an explicit filter. (5) `approval_queue.requested_by` (migration **061**) plus a self-approval guard |
| #301 | P0 settings gates | (1) Loosening a project's safety settings needs the owner; tightening does not. (2) Errand approvals are gated like approvals. (3) `/admin` cross-tenant reads need the owner; `admin_require_owner` defaults to off. (4) Pairing codes for phones and Telegram are owner-only. (5) Skill approval records its approver. (6) Admin ingest is trust-classified |
| #297, #299 | P1 tests | All **266** integration asserts that accepted HTTP 500 were removed, and a hard CI guard now rejects new ones. Real bug fixed: delegation returned 500 instead of 404/400. 3 approval-gate search tests that had always been skipped now run |
| #298 | P1 builds | (1) CI and Docker install from `uv.lock` with `uv sync --locked`, which fails on drift. (2) The Docker image moved to Python 3.12 and CPU torch is in the lock. (3) An extras smoke job. (4) Major-version caps on fast-moving libraries. (5) pip-audit is **blocking**, with a dated ignore list for 14 advisories blocked upstream (review by 2026-12-18). (6) npm audit is report-only |
| #303 | P2 typing | mypy: `core` is clean under strict, `api` passes a baseline config, and a strict-mode ratchet (now 269) runs in CI. Found and fixed 2 bugs: workflow run detail always returned 500, and transcript ingest could call `upload(key=None)` |
| #304 | P2 boundaries | (1) Removed imports from storage and services into api. (2) import-linter contracts in CI. (3) Ratchet on function-local imports. (4) A single `resolve_run_tools`; **this fixed a leak where the local driver gave cloud models personal tools**. (5) C901/PLR0915 ratchet. (6) Startup split into steps |
| #307 | P2 API contracts | (1) One error envelope `{error:{code,message,request_id}}` that keeps `detail`. (2) Domain exceptions. (3) `Envelope[T]` response models on memories, search and graph. (4) Typed analytics sync; analytics items now arrive as **pending**. (5) Typed agent tasks. (6) A `degraded` flag instead of silent empty results. Fixed `/search/ask` early exits that returned unwrapped bodies |
| #308 | P2 database | (1) Migrations run up, down, up in CI, plus a schema-drift ratchet; `env.py` was missing models, so autogenerate would have dropped 17 tables. (2) Session close and both distillers no longer hold a transaction across the LLM call. (3) Telegram replay idempotency (migration **062**). (4) Async MinIO calls and a lock on transcript ingest. (5) Lighter decay query, AGE pool setup once, one shared arq pool, `hnsw.iterative_scan` |
| #305 | P2 small items | (1) Startup guard module; **not wired, see the owner decisions below**. (2) `metrics_require_key` setting. (3) MCP-over-HTTP forwards the caller's credential. (4) `/drivers/dispatch` is off by default. (5) Webhook delivery id. (6) Errand requester stamp. (7) Approve/reject of memories records who decided. (8) Repo hygiene and the memory benchmark moved to `life_graph/evals`. (9) Docs refreshed. (10) Notifications spec. (11) `core/utils` |
| #306 | P2 approval stores (H9) | (1) The autonomy queue and the feed copy resolve together, and a disagreeing decision returns 409. (2) Approving in the autonomy queue now actually runs the action, with claim and pin. (3) The notify-before timer no longer approves without running; it notifies. (4) `also_trust` is deprecated. (5) The kill-switch pause and dev-task cancel revoke live capabilities, and return 503 if the store is down |
| #310 | Discovered defects | (1) Workflow engine column names fixed. (2) Memory deny-with-replacement no longer returns 500. (3) Cancel cascades to all unfinished descendants and revokes their capabilities; default priority is now `normal`. (4) `kernel_cloud_strip_personal_tools` setting, **off**. (5) The dispatcher and chat, study, money and connector paths no longer hold a transaction across slow calls |
| #311 | Silent exceptions | Undocumented silent and no-traceback broad excepts went from 109 to 4. Audit script plus ratchet. **Diff verifiers now fail closed when git fails**; before, they passed with nothing checked |

### Production release, 2026-11-20 10:50 UTC
- **Tag:** `prod-20261120-1050`. **Rollback:** `prod-20261119-1345`.
- **Backups:** `~/life-graph-backups/phase2-release-20261120/` holds a 206 MB `pg_dump` from before 061, `prod.env`, the venv freeze and the dry-run output.
- **Venv** synced from the lock with `--no-install-project`:
  - fastapi 0.141 → 0.165, sqlalchemy 2.0 → 2.1, litellm 1.103 → 1.105, pr-agent 0.47 → 0.50.
  - The editable install still points at the dev checkout. Prod runs its own code through `PYTHONPATH`.
- **Rollback for the venv:** `uv pip install -r venv-freeze-before.txt`. For the DB, restore the dump (061 and 062 also have working downgrades).

**Live checks (production evidence):**
- alembic is at 062; `uq_ce_telegram_message` and `approval_queue.requested_by` are present.
- health 200, all checks healthy; UI 200; dev runner active.
- `/brainX` returns 401. An unknown route returns the new envelope with `detail` kept.
- `/api/v1/memories/` returns 200 with `{data, meta}`.
- Approvals readiness: `lockout_risk=false`, 2 owner keys, 0 owner keys not accepted, 3 paired phones.
- All new safety settings are at their defaults (off).
- 0 ERROR lines in the API and worker logs since the restart.
- The dev edition is on the same master, health 200, alembic 062.

### Open owner decisions
1. **Startup guard.** Wire `check_auth_exposure()` into `lifespan` in `main.py`. The batch agent's edit to `main.py` was refused by a permission check, so it waits for the owner.
2. **Owner enforcement.** Confirm the dashboard key is one of the 2 owner keys (the readiness panel shows no lockout risk). Then set `LIFE_GRAPH_APPROVALS_REQUIRE_OWNER=true` and `LIFE_GRAPH_ADMIN_REQUIRE_OWNER=true`.
3. **Aliases and schemas.** Delete the 57 alias modules. Keep the 21 unused schemas and wire them into response models.
4. **Cloud personal tools.** Move admin, scout, tutor, rex, scribe and swe-lead to local models or a local fallback chain, then enable `kernel_cloud_strip_personal_tools`.
5. **Micro-consolidation dedup.** Off because of the negation risk; enable it or not.
6. **L2 autonomy.** Should notify-before ever execute after the window? Today it only notifies.
7. **UI and Android.** Add a retry button for failed or unknown approvals (`{"retry": true}`).
8. **pip-audit ignore list.** It expires on 2026-12-18. Decide how to handle the pins in pr-agent and litellm.

### Deferred, with reasons
- **Orchestrator `run()` split.** Highest-risk refactor; a plan is in `docs/design/orchestrator-run-split-plan.md`.
- **The idle-in-transaction timeout stays at 600 s.** The dispatcher approval path `_create_pr_approval` / `_auto_open_pr` still holds a transaction across the PR-description LLM call and `gh pr create`.
- **API keys are not bound to tenants.** `X-Tenant-ID` chooses the tenant. This is a design decision for multi-tenant use.
- **The api strict-mypy backlog** (269 errors, mostly missing return annotations) is under a ratchet.
- **Real model/DB schema drift** (191 entries in the baseline) needs data-checked migrations.
