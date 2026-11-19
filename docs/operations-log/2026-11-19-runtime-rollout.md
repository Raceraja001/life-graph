# Secure runtime rollout: decision log, 2026-11-19

The owner delegated the remaining production-readiness calls on 2026-11-19: "no need to ask me … take better decisions and record them — later i will check them". This log records each decision, why it was made, how it was verified, and how to undo it. Times are UTC.

The limits did not change. The agent never prints secrets, never raises the $10 budget cap, never weakens approvals or merge safeguards, and never decides `driver_pr` / merge approvals, which stay with the owner.

## Already done before the delegation (owner-approved)

| When | What | Evidence |
|---|---|---|
| 04:17 | Prod switched to the task runtime (`prod-20261119-0417`). Migration 060. Images `821beec`. 1 task at once, API mode | Probe, reliability 8/8, pulse task 25c81200 |
| 05:26 | #263 released (`prod-20261119-0526`): sandboxed runs use the `claude setup-token` token, never a copy of `~/.claude` | Pulse task d4e76acb, `login=oauth_token`; the token appears in no event, log or record; cancel took 1.3 s |
| ~06:05 | Owner ran `claude setup-token` and put the token in prod `.env`, then logged in again on the host | Host `claude -p` works |

## Decisions under delegation

### D1. Switch prod to the images rebuilt from 6ce846a
- **What:** `life-graph-claude-driver:6ce846a-cli2.1.328`, `life-graph-sandbox-egress:6ce846a`. The verifier images stay `*-821beec`, because their inputs did not change.
- **Why:** no image inputs changed since 821beec. But the host CLI auto-updated 2.1.272 → 2.1.328, and the driver image carries the host CLI, so one CLI version should run everywhere.
- **Verified before the switch:**
  - The security probe on the exact tags: no caps, no socket, no host paths or `LIFE_GRAPH_*` variables, no direct network or DNS, 0 host ports, proxy 200 for the allowlist only.
  - A throwaway container logged in with the token and answered.
- **Rollback:** restore `.env` from `~/life-graph-backups/prod-runtime-switch-20261119/prod.env.before-6ce846a`, then `./dev.sh restart`.

### D2. API binds `127.0.0.1` again (`LIFE_GRAPH_BIND_HOST`)
- **What:** `0.0.0.0` → `127.0.0.1`.
- **Why:** `dev.sh up` honours the `.env` value. The old `restart-api.sh` ignored it, so the API had already run on `127.0.0.1` for about 22 h (11-18 05:59 → 11-19 04:17) with Windows and the phone working. Only loopback clients were seen on :8080. `0.0.0.0` also put the API on every docker bridge, which containers could reach.
- **Verify:** health from WSL and from Windows `localhost:8080`.
- **Rollback:** set it back to `0.0.0.0`, then `./dev.sh restart`.

### D3. `code-fixer` gets a shell, inside its container only
- **What:** `run_command` was added to the built-in persona (this PR). The startup reconcile updates existing tenants.
- **Why:**
  - In the first prod run the agent wrote tests it could not run ("no shell/Bash tool available").
  - Since the switch, `claude_code` runs in the per-task container: internal network, egress allowlist, no host paths.
  - On the host the driver still strips Bash unless `driver_allow_host_shell`. Tests now pin both halves for the real persona definition.
- **Not changed:** the verifiers, approvals and the merge path.
- **Rollback:** revert this PR, or set `DRIVER_CLAUDE_SANDBOX=none` (which strips the shell anyway).

### D4. Worker mode today, not tomorrow
- **What:** `LIFE_GRAPH_DEV_TASK_RUNNER_MODE=worker`, plus a systemd user unit `life-graph-dev-runner.service` with `Restart=always` and `TimeoutStopSec=1560`.
- **Why:**
  - The reliability suite already shows standby takeover, SIGTERM drain, SIGKILL recovery and no duplicate runs.
  - After D1–D3 prod is verified, and doing it while I can watch beats leaving it unattended.
  - The unit restarts a crashed or lock-lost worker (exit 3). The existing `life-graph.service` is oneshot and would not.
- **Verify:**
  - The worker log shows it holds the lock.
  - An API restart during a running task leaves the task running.
  - A SIGKILL of the worker → systemd restarts it → the task is recovered once.
- **Rollback:** `systemctl --user disable --now life-graph-dev-runner`, mode back to `api`, `./dev.sh restart`.

### D5. Keep the CLI's default model (`claude-sonnet-5` on the token)
- **Why:**
  - The tasks so far are small, and Sonnet passed every check.
  - Opus would use more of the subscription quota.
  - Adding a model setting is easy later if results drop. Measure first.

### D6. Leave the pulse `driver_pr` approvals to the owner
- **Why:** approving or merging belongs to the person, by design of the approval system (the MCP tools deliberately cannot approve).

### D7. Cleanup of my own artifacts only
- **Removed:**
  - the throwaway test DB and Redis (`lg_wo_testdb`, `lg_wo_testredis`);
  - the `:wo-test` images;
  - my merged scratch worktrees under `~/worktrees/life-graph/`.
- **Kept:**
  - the `821beec` images, as the rollback;
  - `life-graph-sandbox-egress:dev`, which is the code default and still used by the dev edition and the browser sandbox;
  - everything created by other agents.
- **Dashboard repo:**
  - Removed the stale 0-byte `.git/index.lock` (2026-11-02; no git process running).
  - Fast-forwarded `main` to `feat/live-task-session`. Prod's dashboard already runs those two commits.

## Results

(filled in as each step completes)
