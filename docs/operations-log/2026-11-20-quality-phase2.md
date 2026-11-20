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
