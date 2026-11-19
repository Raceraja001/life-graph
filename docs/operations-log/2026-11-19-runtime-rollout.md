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

### D8. The container shell has no test tools; do not open PyPI egress
- **Found:** in the D4 test run, `code-fixer` used Bash inside the container (it read files and wrote the test file), but it could not run the tests. The driver image has no `pytest`/`ruff`/`uv`, and `pip install` is blocked because the egress allowlist only admits Anthropic hosts. It said so in its summary. The verifiers ran the tests in their own sandbox and they passed.
- **Decision:** keep the allowlist as it is. Adding pypi.org would give a prompt-injected agent a package-install and data-exit channel.
- **Follow-up (not done):** mount the project's cached verifier venv (`verifier_sandbox_cache_dir`) read-only into the driver container and put it on `PATH`. That gives offline test tools with no new egress. It needs a new read-only bind root in `sandbox.validate_spec`, so it gets its own PR and review.

### D9. Periodic runtime sweep (PR #265)
- **Found:** in the D4 SIGKILL test, the killed run left its egress proxy and network. The restarted worker's startup sweep kept them, because the task still read as `running`.
- **Fix:** the runner's recovery pass (every 4 heartbeats) also sweeps runtimes whose task is not running and that are at least 5 minutes old. The age floor avoids racing a task that is being claimed.

### D10. The dev edition matches prod (main checkout, :8180)
- **Found:**
  - The main checkout was 38 commits behind master (still at 92f42b4) and its dev edition was down.
  - Its `.env` still had `DRIVER_CLAUDE_SANDBOX=docker` and no token, so a sandboxed dev task would refuse.
  - The dev API was bound to `0.0.0.0`.
- **Done (owner: "fix that too"):**
  - Fast-forwarded the clean checkout to master and started dev (dev DB → 060).
  - Set the same runtime keys as prod: `task` mode, the same image tags, 1 task at once, `127.0.0.1`.
  - Copied prod's `setup-token` token into dev's `.env` without printing it.
- **Verified:**
  - Dev health returns 200 from WSL and from Windows `localhost:8180`, and the dev API listens on `127.0.0.1` only.
  - A throwaway container logged in with the dev token and answered.
  - The dev runner stays off (`DEV_TASK_RUNNER_ENABLED=false`).
- **Note:** one token now lives in two `.env` files. A rotation (`claude setup-token`) must update both, or dev can get its own token.
- **Rollback:** `~/life-graph-backups/dev-runtime-20261119/dev.env.before`, then `./dev.sh restart`.

## Results

| Step | Time | Result |
|---|---|---|
| D1 images | 06:2x | `.env` backup `prod.env.before-6ce846a`. Restart OK. Smoke task 514a2883 completed on `6ce846a-cli2.1.328`: 6/6 checks, `login=oauth_token`, no token in events/record/logs, host login file untouched, test-only diff, no `.pyc`. Cancel test 00094efb: cancelled in 1.3 s, 0 leftovers |
| D2 bind | 06:2x | Listening on `127.0.0.1:8080`. Health 200 from WSL and from Windows `localhost:8080` |
| D3 shell | 06:38 | #264 released (`prod-20261119-0638`). Task a87b48e6 used Bash inside the container (see D8 for the missing test tools) |
| D4 worker | 06:38 | `life-graph-dev-runner.service` is active and holds the runner lock. The API logs "Dev tasks run in the dedicated worker". **API restart during a running task:** the task kept running and completed (1 agent run, same runner). **SIGKILL of the worker mid-task:** systemd restarted it in 10 s; the task was re-claimed once the 180 s lease went stale and completed with 1 agent run. It left one proxy and network behind → D9 |
| D5–D6 | – | No change. The two pulse `driver_pr` approvals are waiting for the owner, plus those from the smoke/D4 tasks |
| D7 cleanup | 06:5x | Test DB/Redis containers and `:wo-test` images removed. 5 merged worktrees and their branches removed. Dashboard lock removed, `main` fast-forwarded to 07dd39d, the Windows-created dashboard worktree removed |

## Rollback, all in one place
- **Worker:** `systemctl --user disable --now life-graph-dev-runner`, set `LIFE_GRAPH_DEV_TASK_RUNNER_MODE=api`, then `./dev.sh restart`.
- **Images:** restore `prod.env.before-6ce846a`.
- **Bind:** set `LIFE_GRAPH_BIND_HOST=0.0.0.0`.
- **Code:** move `prod` back to an earlier tag. Never go further back than `22021b1` (the #263 release): older code copies the host login into containers and revokes it.
- **Backups:** `~/life-graph-backups/prod-runtime-switch-20261119/`.
