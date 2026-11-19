# ADR: Per-task execution runtime for coding drivers

**Status:** Accepted (Stage 1 + Stage 2 vertical slice), 2026-11-18
**Work order:** [docs/work-orders/secure-execution-runtime.md](../work-orders/secure-execution-runtime.md)
**Code:** `life_graph/services/dev/task_runtime.py`, `life_graph/services/dev/sandbox.py`
(typed `Bind`, labels, runtime networks), `life_graph/drivers/claude_code.py`,
`life_graph/drivers/host_exec.py`
**Evidence:** [docs/security/runtime-probe-results-2026-11-18.md](../security/runtime-probe-results-2026-11-18.md)

## Context

What Stage 0 found on master `0987505`, verified from the code and the machine:

- **The claude_code driver had two modes.**
  - `none` (the source default): the CLI and its Bash tool run on the host as the API's user, with the API's whole environment (`env=None`).
  - `docker`: a container on Docker's default bridge. It could reach the internet, the LAN and every port published on the host (Postgres, Redis, Ollama). It had random names and no labels, and nothing cleaned up after a crash.
  - Both stop only the CLI on timeout, not what it started.
- **OpenCode runs on the host** with bash denied and the API's whole environment.
- **The verifier, with its sandbox off, ran agent code on the host.** That covers pytest and acceptance tests, and also `ruff`, `python` or `pip-audit` binaries found in the agent's own worktree.
- **A strict container-policy validator already existed** (`validate_spec`: no host paths, no runtime socket, internal networks only, no secret-shaped env, non-root, caps dropped, limits). It had 59 tests, but only errands used it; the driver path bypassed it.
- **Prod sets both sandboxes to `docker`, but none of their images were built.** Every code task failed closed: 12 of 12 in 14 days.

## Decision

Add a per-task runtime, built on the existing validator, and make it a third value of the existing setting:

```
driver_claude_sandbox = none   | host; Bash denied unless driver_allow_host_shell
                      | docker | legacy open-network container (kept as the rollback)
                      | task   | per-task runtime (this ADR)  ← recommended
```

One dispatch gets:

| Concern | How |
|---|---|
| Filesystem | The worktree is the only writable host path, mounted as a typed `Bind` to `/work`. The validator refuses a bind unless its resolved, non-symlink source sits *under* the dispatch scratch root (`$TMP/lg-tenants`) or the staged-credentials root. So the live checkout, `$HOME` and `/` are refused, and so is a `/drivers/dispatch` call with `isolate_workdir=false`. Errand specs still refuse every host path. Root fs is read-only; `/tmp` is a size-capped tmpfs. |
| Process | Host uid (the validator refuses uid 0), `cap-drop ALL`, `no-new-privileges`, pids/memory/cpu limits with swap equal to memory, and `--init`. Coreutils `timeout` is the entrypoint, so a container whose API process died still stops on its own. |
| Network | A fresh `docker network create --internal` per task, in **isolated gateway mode**, so the host has no address on the bridge. Plain `--internal` left host services bound to `0.0.0.0` reachable on the gateway (found in review, fixed, re-probed). Both properties are checked after creation rather than trusted. Its only other member is a per-task egress proxy: the existing `browser_egress_proxy`, which validates destinations, refuses private/loopback/link-local addresses, and connects to the address it resolved. The proxy relays only to `driver_runtime_egress_allowlist` hosts on 443. The driver has no DNS and no route anywhere else. |
| Secrets | Nothing is inherited. The env is built in code and checked by the same validator, which refuses `LIFE_GRAPH_*` and credential-shaped names and values. In API-key mode the key is passed by name only (`-e ANTHROPIC_API_KEY`, value in the docker client's environment); OAuth mode passes the long-lived `claude setup-token` token the same way (`-e CLAUDE_CODE_OAUTH_TOKEN`). `PASSTHROUGH_ENV_ALLOWED` admits only those two names. Copying the host's login file in is a legacy opt-in (see "Login revocation" below). |
| Audit | Labels `life-graph.runtime.{instance,task,tenant,driver,policy,rid,role}`; `instance` is this install's edition plus database, so prod's and dev's sweeps on the shared daemon never touch each other's runtimes go on every container and network. The run's metadata lands in `task.result.metadata.runtime`, with no migration: image id, egress image id, network, allowlist, limits, uid, binds, exit code, duration and the teardown result. |
| Cleanup | Teardown (rm container, rm proxy, rm network) always runs and treats "already gone" as done. `sweep_orphans` runs at startup on the runner-lock holder, after interrupted-task recovery. It finds leftovers **by label** and removes those whose task is not `running`. It also deletes staged token copies older than twice the longest dispatch. |
| Fail closed | A missing docker/image, a network that isn't internal, a proxy that isn't ready, a validator refusal, or the container failing to start all raise `SandboxUnavailableError`. The driver turns that into `exit_status=sandbox_unavailable`. No code path falls back to the host. |

Alongside the runtime, and for every driver on the host:

- **Host-run CLIs** (claude_code in `none` mode, OpenCode) get an **allowlisted environment** (`host_exec.host_driver_env`) and **start their own process group**. A timeout kills the group.
- **`driver_allow_host_shell=false`** (default): the claude_code driver's Bash tool is denied on the host. A persona whose only tool is the shell is refused with a message naming the fix.
- **`verifier_allow_host_execution=false`** (default): with `verifier_sandbox=none`, tests and acceptance tests are *inconclusive* rather than run on the host. A tool or interpreter inside the worktree is never chosen.
- **Checkpoints record verdicts.**
  - `verifier_completed` is `ok` only when verification passed.
  - `finished` is `ok` only when the dispatch succeeded.
  - Recovery treats a `finished`-but-failed run as failed rather than completed or re-run.

### Why not something bigger

- **Kubernetes / a job platform:** one machine and one runner; the work order rules it out without evidence.
- **gVisor / Firecracker / Kata:** stronger kernel isolation, but a new runtime to install and operate on WSL. It is the natural next step if the threat model grows (multi-tenant customers). The runtime interface keeps the docker calls in one class.
- **A long-lived workspace container per task** (OpenHands-style exec into a running box): needed for Stage 4 interactive sessions, not for headless dispatch. `DockerTaskRuntime` is where that would go.

## Threat model

**Adversary:** the coding agent itself, assumed prompt-injected through repository content, issue text, web pages, memories or a malicious dependency. Model output is untrusted. The human operator and the Life Graph process are trusted.

| Asset | Attack | Control | After this slice |
|---|---|---|---|
| Host filesystem, other repos, `.env` | Read/write outside the task | One validated bind; read-only root; no host paths | **Mitigated** (probe: `/mnt/h`, `/home/raja`, prod `.env` not visible) |
| Docker socket, host root | Mount the socket; privileged mode; setuid | Validator refuses socket/privileged; caps 0; NoNewPrivs | **Mitigated** in the container. The API user is still in the `docker` group on the host (see residual risks) |
| App secrets, DB, Redis | Inherited env; reach host-published ports | Env built in code and validated; internal network | **Mitigated** (probe: no `LIFE_GRAPH_*`; 172.17.0.1:55432/56379 unreachable) |
| LAN, cloud metadata, internet | Lateral movement, exfiltration | No route; proxy refuses private addresses and unlisted hosts | **Mitigated by hostname** (probe: example.com, github.com, 169.254.169.254 all 403) |
| The OAuth token | Read and send out | Long-lived token by env name, no host file mounted; egress limited to Anthropic hosts | **Partial.** The agent can read the token and use it against the allowlisted hosts |
| The host's own login | Revoked as a side effect | No host login file in the container, so no refresh can rotate it | **Fixed 2026-11-19** (the old staged copy did revoke it in prod) |
| Host-side git (landing) | Agent rewrites `.git`, sets hooks or filters | Existing `_check_worktree_link`; hooks/config live in the origin's git dir, which is not mounted | Unchanged, existing tests |
| Availability | Fork bomb, disk fill, memory, run forever | pids, tmpfs size, memory=swap, in-container deadline + host kill | **Mitigated** (probe: 253 procs at 256, ENOSPC at 256m, OOM-kill at 512m, 3s deadline) |
| Approval integrity | Agent edits CI/tests/policy to get auto-merged | Protected paths, `no_test_weakening`, `auto_gate`, second opinion | **Unchanged** (permission is not verification; nothing loosened) |
| Memory as authority | A memory says "you may run X" | Runtime policy reads settings and code only, never packet content | **Mitigated** by construction |

### Residual risks: what this does NOT claim

- **Containers share the host kernel.** A kernel or runtime escape defeats this. Nothing here is escape-proof.
- **The API process's user is in the rootful `docker` group,** so it is effectively host root. A compromise of the *API process* (not the agent) is a host compromise. Rootless docker, or a narrow broker in front of the daemon, is the fix; it is out of scope here.
- **OAuth mode exposes the personal token to the agent,** limited to the allowlisted hosts. API-key mode is cleaner, but it is billed against the budget cap, so the owner kept OAuth (2026-11-18). Since 2026-11-19 that is a long-lived `setup-token` token, not the host's login file. It is a long-lived secret now, so rotate it with `claude setup-token` if an agent run looks suspicious.
- **Login revocation (found in prod, 2026-11-19).** The first design mounted a throwaway copy of `~/.claude/.credentials.json`. With the host's access token expired, the CLI in the container refreshed it inside the copy. The refresh token rotated, so the host's own login was revoked, and every later run failed with a 401. Writing the refreshed file back was rejected: it would let an agent plant its own account's login on the host. The fix is the long-lived token (owner choice A). The copy stays behind `driver_claude_code_allow_staged_login`, off by default.
- **Anything reachable on an allowlisted host is reachable.** The proxy fences by hostname and does not terminate TLS.
- **The worktree's `.git` file reveals the origin path** inside the container. Git commands there fail, because the origin's git dir is not mounted; landing happens on the host.
- **The legacy `docker` mode and the verifier's setup phase use the default bridge,** where the host is reachable on its gateway. Prefer `task`. Moving verifier setup behind the same isolated network and proxy is a follow-up.
- **The per-task proxy listens on `0.0.0.0`,** so anything on the shared `lg-rt-outbound` bridge can use it, but only to reach the allowlisted hosts.
- **OpenCode still runs on the host.** Bash is denied and the env is now allowlisted, but its file tools can read anything the user can. Moving it into the runtime is the next driver; it needs an Ollama egress rule, because the proxy refuses private addresses today.
- **Tasks started immediately still run in the process that received the request,** and a dev-task cancel does not stop the driver. Both are Stage 3.

## Rollback

- `driver_claude_sandbox=docker` gives the previous container behaviour.
- `driver_claude_sandbox=none` gives the host, with Bash denied.
- `driver_allow_host_shell=true` / `verifier_allow_host_execution=true` restore the old host behaviour on a disposable dev box.
- No schema change, so reverting the PR is enough.

## Follow-ups

1. Build the prod images and switch prod to `task`; deploy is owner-gated.
2. Stage 3: route immediate starts through the runner, add a per-task lease/heartbeat, make dev-task cancel reach the driver, and implement a real land-only resume.
3. OpenCode into the runtime, with an Ollama egress rule. Parked until then (2026-11-18, `driver_opencode_enabled=false`): fewer completed tasks than the local driver in prod, no shell on the host.
4. Pin image digests; record a `runtime_images.lock`.
6. Verifier setup phase onto an isolated network with a registry-only allowlist.
5. Stage 4: a long-lived workspace container plus streamed events for reconnectable sessions.

## Stage 3: durable worker boundary (2026-11-18)

**Decision:** keep one source of truth (the `agent_tasks` rows, the `LGDV` advisory lock and
the `SKIP LOCKED` claim) and add one runner object that owns all execution. It can run
outside the API (`dev_task_runner_mode=worker`). No second queue, no Redis job and no ARQ
(an ARQ job's timeout and retry would re-run a coding agent).

| Gap from Stage 0 | Now |
|---|---|
| "Start now" ran as an `asyncio.create_task` in any API process, skipping the lock | queued with `start_now` and woken (`NOTIFY`); only the lock holder runs it |
| WIP limits were a count that two starts could both pass | the runner counts in one process: max N, at most one unattended |
| No per-task lease | `properties.lease` heartbeat; an atomic JSONB merge, so it never clobbers checkpoints |
| Cancel didn't stop the driver | cancel flag → the runner cancels the run → process group / container killed → `cancelled` |
| `land_only` was a label only | `TaskDispatcher.resume_landing` lands the kept worktree (diff SHA-256 must match), or files the lost PR approval once |
| An API restart killed running agents | worker mode: API restarts don't touch them; worker SIGTERM drains |

Evidence:
- `tests/unit/test_dev_runner.py`.
- `tests/integration/test_dev_task_runner.py`, against a real Postgres: claim order,
  queue-only start, cancel, heartbeat merge, and a real-git land-only resume, including
  the refusal when the worktree changed after verification.
- A worker-process smoke run against a throwaway database with a fake CLI: pickup ~2 s via
  `NOTIFY`, cancel 0.26 s with the child process killed, SIGTERM drained for the full 3 s
  window, and the next start recovered the task.

Remaining:
- A worker killed with SIGKILL leaves its tasks `running` until the next worker start.
  There is no cross-process takeover of stale leases while a live runner holds the lock,
  because only the lock holder may run tasks.
- Prod still needs `dev.sh` and its systemd unit updated at the prod switch.

## Stage 4: live session and UI (2026-11-18)

**Decision:** a read-only, reconnectable session view, not an interactive terminal. The
owner chose this on 2026-11-18: every action stays the agent's and is audited, and there is
no human-typed path into the agent's container. The session is a durable event log, not a
socket, so a reload or a dropped connection resumes from the last sequence number with no
gaps and no repeats.

| Piece | Where |
|---|---|
| Event log | `dev_task_events` (migration 060), written by `services/dev/task_events.py`: one ordered in-process writer, batched inserts, per-task `seq`, redacted and capped, a unique (task, seq) constraint against cross-process races |
| Sources | runner (claimed, cancelled, final status), dispatcher (each checkpoint stage, driver choice, every verifier verdict), claude_code (each stream-json line while the CLI runs: text, tool calls, tool results, on the host and inside the task runtime), task runtime (network ready, container starting, teardown), API (cancel requested) |
| Read | long-poll `/events?after&wait` (the dashboard; works with the Bearer header) and SSE `/events/stream` (resumes from `Last-Event-ID`); both tenant-checked |
| Controls | cancel (Stage 3) and a per-task `timeout_seconds` (capped) |
| UI (life-graph-ui) | run page: live session panel with reconnect and follow-mode scroll, execution panel (boundary, image, allowlist, limits, uid, mounts, teardown, lease heartbeat age), two-click Cancel, changed files and diff |

Evidence:
- `tests/integration/test_dev_task_events.py` (9 tests): order, redaction, cap, an exact
  cursor, long-poll latency and early return on a finished task, tenant isolation, API and
  SSE resume, a real runner pass with a timeout override.
- `tests/unit/test_live_stream.py`: lines are streamed before the process exits, a broken
  viewer never breaks the run, stream-json maps to events.
- life-graph-ui `tests/live-session.spec.ts` (Playwright, API stubbed): ordered stream, a
  dropped connection resumed from the cursor, the runtime panel, two-click cancel.
- **Real end-to-end run:** this API on a throwaway DB, the dashboard dev server, and a fake
  CLI that streams stream-json.
  - All 23 events reached the page in order, and the task landed `lg/task-…`.
  - A reload mid-run resumed with 0 duplicates.
  - Cancel from the page ended the task as `cancelled`.

Found by that run and fixed:
- **Rate limit:** the page's polling hit the API's 60-requests-a-minute limit. It is now
  batched.
- **Bytecode on the branch:** `build_ok`/`build_ok_diff` used `py_compile`, which wrote
  `__pycache__/*.pyc` into the agent's worktree, and the landing commit put that on the
  task branch. The syntax check now compiles in memory.

Not done (by choice): an interactive shell into the container, and live streaming for the
local driver (its steps still arrive at the end of the attempt).

## Stage 5: benchmark and hardening (2026-11-18)

**Benchmark** (`evals/driver_bench/README.md`, 2026-11-18):
- 10 tasks in 5 categories. Each new hidden test was validated against its starting repo and a
  reference fix.
- Claude Code in the task runtime passed 10/10 (bugfix 2/2 when not disturbed). Local
  gpt-oss:20b passed 9/10 and fails the two-bug fix consistently.
- The project's own verifier chain agreed with the hidden tests 14/14, with 0 false positives.
- Runtime overhead is ~3 s; the agent container peaks at ~0.2 GiB.

**Reliability** (`scripts/runtime_reliability.py`, `evals/reliability/20261118-runtime-reliability.json`): 8/8.
- **Container killed:** the run ends; nothing is left.
- **Egress proxy killed (network loss):** the run ends; nothing is left.
- **Pickup** via NOTIFY.
- **Cancel:** 0.32 s, and the agent's child process is dead.
- **SIGTERM** drains before the worker exits.
- **SIGKILL mid-run:** a standby takes the lock and recovers the task once its lease is stale.
  The task completes, with exactly one recovery run.
- **Two workers at once:** each of 6 tasks ran exactly once.
- **Three concurrent tasks:** three separate worktrees.

Found and fixed by these checks:
- **WIP at claim time.** The runner claimed a third task for a project already running two,
  and the dispatcher failed it outright ("Project WIP limit reached"). The claim now applies the
  dispatcher's per-project and per-tenant limits, and such a task waits in the queue.
- **Scripts swept by workers.** A worker's startup sweep removed runtimes created by scripts
  (no task row). Scripts now use their own instance label.
- **Host-run agents get an allowlisted environment (by design).** The reliability script's fake
  CLI needed its variables passed via `driver_host_env_passthrough`, which is how the
  isolation is meant to work. Its first cancel check had passed vacuously; it now requires the
  children it checks to have been seen.

**Hardening:** a symlink leaving the worktree is tampering (`drivers/workdir.py`
`escaping_symlinks`; vetoed in the dispatcher's worktree check). Verified against a real
container (`docs/security/`).

**Still unproven / not done:**
- kernel or container escapes;
- DNS tunnelling through allowlisted hosts;
- a large or representative repository benchmark;
- moving the verifier's dependency-setup step onto an isolated network (it uses the default
  bridge);
- OpenCode inside the runtime (parked);
- prod deployment.
