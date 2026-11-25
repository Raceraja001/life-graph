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

## Hardening round (later on 2026-11-19)

### D11. #265 was already deployed
- The periodic sweep code is in prod's files, and the dev-runner unit restarted at 07:00:48, after the `prod-20261119-0700` release.

### D12. Test tools inside the container: the read-only project env (PR #267, released as `prod-20261119-1005`)
- **What:** the project's cached verifier venv is mounted read-only at `/venv`, and the driver image carries the verifier's pinned `pytest`/`ruff`/`mypy`/`uv`. Image: `life-graph-claude-driver:a3aa3f4-cli2.1.328`; policy version `2026-11-19.1`.
- **Egress unchanged.** That was the constraint. `pip install` still fails.
- **Review:** an independent review found no way to poison the env. Follow-ups applied before merge:
  - the bind rule allows only a direct, finished cache entry, read-only even if the cache sits inside a writable root;
  - any env build error lets the agent run on without tools;
  - the doc claim about bounces was corrected;
  - the probe gained a real-container check of the read-only mount.
- **Verified in prod:** task d4bb67c6 completed. The agent itself ran `ruff format --check`, `ruff check` and `pytest` (37 passed) inside the container. The run recorded `tool_env: mounted read-only`, policy `2026-11-19.1` and `login=oauth_token`, with a 13-line test-only diff, no cache files, and 0 leftovers.
- **Rollback:** `LIFE_GRAPH_DRIVER_RUNTIME_PROJECT_TOOLS=false`, or `.env` from `prod.env.before-a3aa3f4`.

### D13. Monitoring (PR #268, released as `prod-20261119-1005`)
- **What:** `runtime_health` reports the runner lock, stale leases, queue wait, 24 h failures, orphans past the 5-minute floor, and agent container CPU/memory, as counts and codes only. It appears as the `runtime` section of `GET /api/v1/kernel/observability/system`.
- **Alerts:** an arq cron every 10 minutes writes one owner notification per issue per 6 hours. It runs in the arq worker, a different process from the dev-task worker.
- **Fixed after release:** the docs and the alert text named the wrong path (`/observe/system`). This PR fixes it.

### D14. Concurrency under pressure (local evidence, on the prod docker daemon)
- `scripts/runtime_pressure.py`, with its own instance label.
- **Light run (6 jobs):** all checks pass.
- **Heavy run (13 jobs, 2 GB limits):**
  - 11 ran together, and the host kept at least 18 GB free;
  - the memory hog was OOM-killed alone (exit 137) and the fork bomb was capped at 124 pids;
  - all teardowns succeeded and nothing was left behind.
- **The 12th runtime could not start:** "all predefined address pools have been fully subnetted". Each runtime has its own network, and 18 of the daemon's ~32 default pools are held by other stacks. It failed closed, with a clear error and no host fallback.
- **Decision:** prod stays at concurrency 1 (max 3).
- **Recommended fix (not done):** allocate runtime networks from a dedicated private range (e.g. `/28`s from `10.213.0.0/16`) with `--subnet`, so the daemon config, and with it every container's restart, is not touched.

### D15. Backup and restore (verified by a read-only check)
- **Mechanism:** `life_graph_backup` runs `pg_dump -Fc` daily at 14:00 UTC and at each start, keeps 30 days, and stores to `/mnt/h/DevTools/Backups/life-graph` (7 GB, 165 dumps). A drill runs on Sundays.
- **The newest dump (03:46 UTC) restores:** 11–13 s into a throwaway container, and the relational rows match prod exactly as of the dump time.
- **Problems found, not fixed:**
  - **The AGE graph does not restore.** The `ag_label` COPY fails on `fk_graph_oid`, the label catalog comes back empty, and a cypher query crashed the copy (signal 11). The weekly drill only counts rows and tolerates restore errors, so it doesn't catch this.
  - **The off-site restic copy has failed since 2026-11-12:** 183 "repository unreachable" attempts, all recorded as `status=success`.
  - Local dumps sit on the same SSD as prod, unencrypted and world-readable.

### D16. Repeated-failure drills against prod (harmless pulse tasks, 10:09–10:22 UTC)

| Drill | What happened | Result |
|---|---|---|
| A: SIGKILL the worker twice (mid-run, then mid-recovery) | systemd restarted it both times. History: `queued > running > running > queued > running > running > completed` | Completed with **1 agent run**. The killed run's proxy and network were swept at 10:15:40 |
| B: API restart mid-task, then cancel | The task stayed `running` through the API restart. It was cancelled by 10:15:30, 35 s after its container started, with the API restart in between | `cancelled`, 0 leftovers afterwards |
| C: 3 worker restarts back to back, with a task queued in between | – | Completed with **1 agent run**, 0 leftovers |
| D: a stand-in orphan (prod instance label, a finished task's id), with the worker left running | The health panel flagged `orphan_containers=1` at 10:21:22, once past the 5-minute floor. **The periodic sweep removed it at 10:21:41, with the same worker pid**, so #265 works in prod | 0 leftovers |
| Alerts | At 10:13 the arq job wrote `stale_leases` (important; real, from drill A's kill) and `failures` (info) to `raja`, with dedup keys for the 6-hour window | – |

### D17. The four follow-ups, done in parallel (PRs #270–#272, released as `prod-20261119-1114`)
- **#270, subnet pool.** Runtime networks get a `/28` from `10.213.0.0/16`. That range was checked against WSL, docker, Tailscale and the Windows LAN, and it doesn't touch the daemon config. Retries on overlap; fails closed after 8.
  - Local proof: 23 runtimes started, 20 at once; the old ceiling was 11.
  - Probe: isolation is unchanged. The probe also stopped assuming `/24` networks when computing the gateway.
  - Policy is now `2026-11-19.2`.
- **#271, setup egress.** Verifier setup runs on an internal network whose only exit is the egress proxy, allowing only that toolchain's registries plus a per-project `sandbox_setup_allow`. Before that, a manifest scanner refuses URL, VCS, index-override and path sources, so the check is inconclusive, never passed.
  - The scanner finds no problem in any real project: pulse, life-graph, life-graph-android, uzhavu.
  - Prod proof with prod code: pulse built through the proxy, and a `https://example.com/...?t=SECRET` requirement was refused.
  - **Still open:** the allowed registries accept uploads (`npm publish`), so code running during setup could still publish data.
- **#272, backups.**
  - Root cause: `ag_label` restored before `ag_graph` under a parallel `pg_restore`. Also, `restore.sh --clean` doubled the vertices.
  - Fix: restore into an empty database in a fixed order and stop on the first error. `restore.sh` restores into a staging database and swaps it in. Each dump gets a `.graph` inventory taken from the same snapshot.
  - The drill now fails on restore errors, inventory or cypher mismatches, and sequence drift.
  - A failed off-site upload is recorded as `partial` or `failed` and notifies the owner after 24 h.
  - **Live in prod, 11:15:** backup ok, 203 MB with 18 graph labels and a `.graph` file, recorded as `partial` (off-site unreachable). The old code logged `success`.
- **Smoke after release:** task 7b74c57d completed on policy `.2`, `tool_env` mounted read-only, the agent ran pytest (37) and ruff itself, 6/6 checks, 0 leftovers.
- **Nightly batch run early (10:48):** queued 5 life-graph tasks.
  - In daytime they go to the free cloud models, which are rate-limited (429), so the runner put them back on the queue, as designed ("wait for night").
  - **Decision:** I did not force the local model onto the GPU in daytime (owner's compute routing). They run in tonight's local window, and the 21:00 job adds none, because 5 are already open.
- **Owner actions:**
  - restart the restic rest-server on the laptop (`raja-lap` answers Tailscale ping, but the port refuses connections);
  - optionally tighten the Windows ACL on `H:\DevTools\Backups` (Authenticated Users can modify) — the `icacls` command is in PR #272;
  - decide on encrypting local dumps.

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

### D18. Code quality audit quick wins (#274–#278), released 13:45 UTC

The read-only audit (`docs/audits/2026-11-19-code-quality-audit.html`) found 0 critical, 9 high, 22 medium and 20 low findings. The quick wins were fixed in five parallel PRs, one batch each. Every regression test was shown to fail on the old code. Each PR was reviewed and green in CI before merge. Release tag `prod-20261119-1345`, rollback `90cc730`.

| PR | Findings | Decision taken in review |
|---|---|---|
| #276 | H1 single secret-pattern list (sk-ant, sk-proj, sk-or, AIza, PEM, github_pat, …) and server-side redaction at capture ingest. M9: dedup no longer overwrites the original capture's status; Telegram captures use the message's own date. M22: the Telegram token is masked in logs, and the arq worker now configures logging | Redact **before** hashing, so the hash matches what is stored. The worker log now carries INFO lines |
| #275 | H6 `uv.lock` regenerated, `uv lock --check`, pip-audit job, dependabot. M21 optional deps declared (watchers extra, python-docx); orjson and testcontainers dropped. H5 ratchet on integration asserts that accept 500 (266 → 197). M17 coverage in CI (unit 68%, integration 52%); Postgres capability tests now run in CI | **pip-audit is report-only.** filelock (13 CVEs) and opentelemetry-api are pinned by litellm and pr-agent upstream. CI and Docker still install with pip, not from the lock |
| #274 | H8: the micro-consolidation job no longer closes the shared graph pool; its search call is fixed; edges use the vertices' real labels and match-or-create. H7: capture commits before the language-model extraction; idle-in-transaction timeout added; embeddings are batched. L6: background-task references are kept | **Dedup is behind `micro_consolidation_dedup`, default off.** It supersedes the newer memory, and a negated update ("I no longer use X") can be ≥0.95 cosine to the old one. **Idle timeout is 600 s**, because the session-end summary and the transcript distiller still hold a transaction across a language-model call |
| #278 | H4: approval rows are claimed with `FOR UPDATE NOWAIT`, so a second approve gets 409; the auto-merge sweep uses `SKIP LOCKED`; timed-out commands have their whole process group killed. M1: revoke raises when the store is unavailable. H3: `resolved_by` comes from the caller's identity; owner-only approvals are behind a setting | The approval transaction runs `SET LOCAL idle_in_transaction_session_timeout = 0`, because a deploy plus its smoke check can exceed the 600 s idle timeout from #274. **`approvals_require_owner` stays off:** the dashboard key is not known to be in `LIFE_GRAPH_OWNER_API_KEYS` |
| #277 | M3: fixed error messages (`/health`, graph routes). M4: Cypher column validation. M7: exempt paths match whole segments only; metrics are labelled by route template. M8: the watcher tenant lookup fails closed. M6: SSRF guard on webhooks (create and every delivery), no redirects, `/test` returns only delivered or failed. L10: constant-time key check; admin job limit ≤200 | `health_url` was left alone (often a LAN app). Prod and dev both have **0** tenant webhooks and notification channels, so nothing existing is blocked |

**Live checks after release:**
- health 200, no error text in the body;
- `/brainX` returns 401 and `/docs` returns 200;
- 0 raw-path metric labels;
- an Anthropic-style key is redacted;
- Postgres reports `idle_in_transaction_session_timeout` as 10min;
- dedup and owner-only approvals are off;
- dev runner active; approvals list OK;
- the worker logs at INFO.

The runtime panel shows `failures` (info), from earlier failed tasks.

**Waiting for the owner:**
- Put the dashboard key in `LIFE_GRAPH_OWNER_API_KEYS`, then turn on `LIFE_GRAPH_APPROVALS_REQUIRE_OWNER` (release it on its own).
- Decide whether to enable micro-consolidation dedup.
- A one-off scan of past captures for leaked keys.
- Whether `/metrics` should stay public (it still has `tenant_id` labels).
- Owner-only `/admin`.
- Default environment = production (M5).
- One approval store (H9).
- Deleting the 57 alias modules and 18 dead schemas.

**Follow-ups, no owner decision needed:**
- Lower the idle timeout once the session-end summary and the distiller are split.
- Install from the lock in CI and Docker, and cap major versions.
- Make pip-audit blocking once upstream allows the fixed versions.
- Set a coverage floor.
- Wire `revoke_all` into the kill switch.
- `/autonomy/approvals/{id}/resolve` still trusts the body's `resolved_by`.
- Unique index on the Telegram message id.
- Convert the remaining 197 asserts that accept 500.

**Rollback:** move `prod` back to `90cc730` (or an earlier tag no older than `22021b1`) and run `./dev.sh restart`. No migrations were added in this release.

### D19. The dev-task runner did not come back after a reboot (2026-11-21)

**What happened:** WSL rebooted at 2026-11-20 18:00. `life-graph.service` brought the API back, but `life-graph-dev-runner.service` was never started. Its state was `inactive (dead)`, with no activation time and 0 restarts. The 4 nightly tasks queued at 21:03 waited until 08:55 the next morning.

**Monitoring:** it worked. `runner_down` (important) fired at 18:03, 00:03 and 06:03.

**Root cause:** an ordering loop in the unit file created in D4:
- The runner was `WantedBy=default.target` and `After=life-graph.service`.
- `life-graph.service` is `After=default.target`.
- A target waits for the units it wants, so `default.target` waited on the runner, the runner waited on `life-graph.service`, and that waited on `default.target`.
- systemd breaks such a loop by dropping a job, and it dropped the runner. The boot journal had rotated, so the loop message itself was not seen.
- This was the first reboot since the unit was created.

**Fix:**
- `[Install] WantedBy=life-graph.service` (still `After=life-graph.service`).
- Re-enabled: the link moved from `default.target.wants/` to `life-graph.service.wants/`.
- The old file is in `~/life-graph-backups/life-graph-dev-runner.service.before-20261121`.

**Verified:**
- `default.target` no longer wants the runner, and `life-graph.service` does.
- Runner active since 08:55:19 UTC; it claimed the first queued task straight away.
- The real proof is the next reboot: check `systemctl --user is-active life-graph-dev-runner` afterwards.

**Rollback:** restore the backup file, then run `systemctl --user daemon-reload` and `systemctl --user reenable life-graph-dev-runner`.

### D20. Dev tasks could not be verified: a blocked download host and deleted sandbox images (2026-11-24)

**What happened:** every life-graph dev task from 2026-11-20 to 11-24 ended "could not verify". There were two separate causes, one behind the other.

**Cause 1, the setup guard refused the manifests:**
- #298 added `[[tool.uv.index]] pytorch-cpu` to `pyproject.toml`, and `uv.lock` now names `download.pytorch.org` and `download-r2.pytorch.org`.
- The verifier setup guard refuses hosts outside the toolchain registries unless the project lists them in `sandbox_setup_allow`.
- The life-graph `sandbox_setup` already skips torch/nvidia/triton, so nothing is actually fetched from those hosts.

**Fix 1:** the owner added both hosts to the life-graph project's `sandbox_setup_allow`, at 03:56 UTC with the owner key. Adding allowed hosts is an owner-only loosening, because auto_merge is on. The call is `PATCH /api/v1/kernel/projects/{id}` with `X-Tenant-ID: raja`; the dashboard has no form for project settings. The guard scan on master went from 31 violations to 0.

**Cause 2, the sandbox images were gone:**
- `/etc/cron.weekly/gh-runner-prune` (added 2026-10-13 for the self-hosted CI runners) runs `docker system prune -af --filter until=168h`.
- The sandbox images are used for only minutes per task, so 7 days after they were built (11-18) the 11-22 run deleted all four:
  - `life-graph-verifier:py3.12-821beec`
  - `life-graph-verifier:node22-821beec`
  - `life-graph-sandbox-egress:6ce846a`
  - `life-graph-claude-driver:a3aa3f4-cli2.1.328`

**Fix 2:** all four were rebuilt at the same tags, from the commits the tags name (`git archive`). The claude-driver image was built with the installed CLI, which is 2.1.328. Each image carries the label `life-graph.keep=true`.

**Still open:** the prune job must skip that label (`--filter 'label!=life-graph.keep'`). Editing the root-owned cron file was refused by the agent's permission check, so it needs the owner. Until that is done, the images will be deleted again at the next weekly run after 2026-11-30.

**Verified:** test task 1e2261c4 (a new unit test file) passed every check, including `tests_pass` on the full unit suite in the no-network sandbox (6727 passed). This also confirms the #313 network-test fix end to end.

**Rollback:** remove the two hosts from `sandbox_setup_allow`. The images are additive.

### D21. Startup auth guard released; owner locks on for approvals and admin (2026-11-24)

**Owner decision (2026-11-24):**
- Wire the startup guard in.
- Check, then turn on `approvals_require_owner` and `admin_require_owner`.

**Released:** tag `prod-20261124-0508` (rollback `0abb7f0`), containing:
- #317: `main.lifespan` calls `check_auth_exposure()` first, and the call is fatal.
- #313: the network-test fix, with `tests/no_network.py`.
- Docs #314–#316.

There was no `uv.lock` change and no new migration (alembic stays at 062). The `.env` backup is in `~/life-graph-backups/release-20261124/`.

**Checks before turning the locks on:**
- The prod dashboard (`life-graph-ui-prod`, `VITE_API_KEY`) uses an owner key, compared by fingerprint without printing the key.
- 2 owner keys and 3 paired phones; `lockout_risk=false`; Telegram approvals are off.
- Nothing in the last 7 days of API logs, scripts or cron calls the approve or admin-write routes.
- Both editions have `SERVICE_API_KEYS` set, so the startup guard returns at once for both.

**Verified live:**
- Health 200, UI 200, dev runner active.
- Approving a non-existent approval: the non-owner key gets **403**, and the owner key gets **404** (it passed the lock).
- The readiness panel shows `approvals_require_owner: true`.
- 0 errors in the API and worker logs after the restart.
- Dev edition restarted, health 200.

**Effect:** only your owner keys (the dashboard) or a paired phone can approve, reject, or use the admin routes that change the deployment or export data. The Claude Code/MCP key is the non-owner key and is refused.

**Rollback:** set `LIFE_GRAPH_APPROVALS_REQUIRE_OWNER` and `LIFE_GRAPH_ADMIN_REQUIRE_OWNER` to false in prod `.env` (or restore the backup), then run `./dev.sh restart`. For the code, check out `0abb7f0` on the `prod` branch and restart.


### D22. Kill switch verified live; `/metrics` locked; dependency pass (2026-11-24)

**Kill switch, live on prod (tenant `raja`), 09:06 UTC:**
- **Pause with the Claude Code/MCP key (non-owner): 200.** `autonomy_paused` was true and `capabilities_revoked` was 0, because no live capabilities existed. That count was checked before pausing.
- **Resume with the same key: 403**, "needs the owner". Autonomy stayed paused.
- **Owner resumed with an owner key: 200**, and `autonomy_paused` was false.
- This confirms the runbook in `OPERATIONS.md` (#320): any key can stop autonomy, and only the owner can restart it.

**`/metrics` locked (audit M7). Owner OK, 2026-11-24:**
- Prod `.env` now has `LIFE_GRAPH_METRICS_REQUIRE_KEY=true`, then `./dev.sh restart`. The backup is in `~/life-graph-backups/metrics-lock-20261124/`.
- Checked before the change: no Prometheus is running. Uptime Kuma only checks `/alive`. There were no `/metrics` requests in the last 2 days of logs.
- **Verified:**
  - No key: **401**. With a key: **200**.
  - Health 200, UI 200, API, UI and dev runner all active, and 0 errors in the log.
- **Rollback:** remove the line, or restore the backup, then run `./dev.sh restart`.

**Dependency pass, merged on master and not yet released:**
- #321 fixed two tests that blocked the updates: a `/proc` race in the kill-group test, and the typing of the dashboard fetch spy.
- Merged updates:
  - Dependabot: #279–#283 (Actions), #285 (tsup 9), #287 (happy-dom 21), #286 (dashboard minor), #322 (playwright 1.65, ruff 0.17, grimp 3.20, google-auth, icalendar).
  - #323: Vitest 5, which moves the dashboard CI and its Dockerfile to Node 22.
- Left open until the upstream tools support them: TypeScript 7 (#284, #289) and ESLint 10 (#288).
- **The next release must sync the shared venv and run `playwright install chromium`.**


### D23. Release with the dependency pass and the H7 fix (2026-11-24)

**Owner said "release".** Tag `prod-20261124-1144`, rollback `541bad2`. It contains:
- The dependency pass from D22, and #321.
- The H7 fix (#324).
- Docs.

There were no new migrations; alembic stays at 062. CI was green at `b0a4c5e`, and only the bot's `[skip ci]` docs commit came after it.

**Shared venv** (`~/.venvs/life-graph`, editable on the main checkout):
- Synced to `uv.lock` with `uv sync --locked --inexact --no-install-project` and the extras dev, multimodal, cold-start, watchers and browser-sandbox.
- Exactly 5 upgrades:
  - playwright 1.52.0 → 1.65.2
  - ruff 0.16.1 → 0.17.6
  - grimp 3.17 → 3.20
  - google-auth 2.62.2 → 2.63.0
  - icalendar 7.3.0 → 7.3.2
- The spaCy model was kept.
- Ran `playwright install chromium`, which downloaded headless shell v1255.
- Backups in `~/life-graph-backups/release-20261124-2/`: `.env`, `pip freeze` and the uv plans.

**Verified:**
- Health 200, UI 200, and `/metrics` without a key 401.
- API, UI and dev runner all active. Kill switch not paused.
- Approving a fake approval id with the owner key gets 404.
- Playwright Chromium launches.
- 0 errors in the API and worker logs. Dev edition health 200.

**Rollback:**
1. Check out `541bad2` on `prod`.
2. Restore the venv with `uv pip install -r ~/life-graph-backups/release-20261124-2/venv-freeze.before.txt`. Or sync from that commit's `uv.lock`.
3. Run `./dev.sh restart`.

### D24. Release of the remaining audit fixes and the alias deletion (2026-11-25)

**Decision:** the owner said yes. Released tag `prod-20261125-0126`. Rollback is `5f99eded`.

**Included:**
- #326: L8 (dev task and its link saved in one commit) and M3 (a fixed "Dispatch failed." message instead of raw error text).
- #327: L12 (advisory lock so the same dev task cannot be created twice).
- #328: L15 (one shared Redis job pool) and L14 (numpy memory grouping, 1000 memories 13.6 s → 0.43 s).
- #329: task briefs point at the moved files.
- #330: the 57 old-name alias modules are deleted.

There were no new migrations; alembic stays at 062. There were also no changes to `uv.lock`, `pyproject.toml` or the dashboard lock file, so the shared venv was not synced. CI was green at `58adf9d`, and only the bot's `[skip ci]` docs commit came after it.

**Verified:**
- Health 200, UI 200, and `/metrics` without a key 401.
- API, UI and dev runner all active. Kill switch not paused.
- Approving a fake approval id with the owner key gets 404.
- Playwright Chromium launches.
- 0 errors in the API and worker logs. Dev edition health 200.
- `life_graph/services/money.py` is gone on prod.

**Backups:** `.env` and `pip freeze` in `~/life-graph-backups/release-20261125/`.

**Rollback:** check out `5f99eded` on `prod`, then run `./dev.sh restart`.
