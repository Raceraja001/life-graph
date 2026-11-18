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
| Network | A fresh `docker network create --internal` per task, checked to be internal rather than trusted from its name. Its only other member is a per-task egress proxy: the existing `browser_egress_proxy`, which validates destinations, refuses private/loopback/link-local addresses, and connects to the address it resolved. The proxy relays only to `driver_runtime_egress_allowlist` hosts on 443. The driver has no DNS and no route anywhere else. |
| Secrets | Nothing is inherited. The env is built in code and checked by the same validator, which refuses `LIFE_GRAPH_*` and credential-shaped names and values. In API-key mode the key is passed by name only (`-e ANTHROPIC_API_KEY`, value in the docker client's environment); `PASSTHROUGH_ENV_ALLOWED` admits only that name. OAuth mode mounts a throwaway copy of the token. |
| Audit | Labels `life-graph.runtime.{task,tenant,driver,policy,rid,role}` go on every container and network. The run's metadata lands in `task.result.metadata.runtime`, with no migration: image id, egress image id, network, allowlist, limits, uid, binds, exit code, duration and the teardown result. |
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
| The OAuth token | Read and send out | Throwaway copy; egress limited to Anthropic hosts | **Partial.** The agent can read the token and use it against the allowlisted hosts |
| Host-side git (landing) | Agent rewrites `.git`, sets hooks or filters | Existing `_check_worktree_link`; hooks/config live in the origin's git dir, which is not mounted | Unchanged, existing tests |
| Availability | Fork bomb, disk fill, memory, run forever | pids, tmpfs size, memory=swap, in-container deadline + host kill | **Mitigated** (probe: 253 procs at 256, ENOSPC at 256m, OOM-kill at 512m, 3s deadline) |
| Approval integrity | Agent edits CI/tests/policy to get auto-merged | Protected paths, `no_test_weakening`, `auto_gate`, second opinion | **Unchanged** (permission is not verification; nothing loosened) |
| Memory as authority | A memory says "you may run X" | Runtime policy reads settings and code only, never packet content | **Mitigated** by construction |

### Residual risks: what this does NOT claim

- **Containers share the host kernel.** A kernel or runtime escape defeats this. Nothing here is escape-proof.
- **The API process's user is in the rootful `docker` group,** so it is effectively host root. A compromise of the *API process* (not the agent) is a host compromise. Rootless docker, or a narrow broker in front of the daemon, is the fix; it is out of scope here.
- **OAuth mode exposes the personal token to the agent,** limited to the allowlisted hosts. API-key mode is cleaner, but it is billed against the budget cap, so the owner kept OAuth (2026-11-18).
- **Anything reachable on an allowlisted host is reachable.** The proxy fences by hostname and does not terminate TLS.
- **The worktree's `.git` file reveals the origin path** inside the container. Git commands there fail, because the origin's git dir is not mounted; landing happens on the host.
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
3. OpenCode into the runtime, with an Ollama egress rule.
4. Pin image digests; record a `runtime_images.lock`.
5. Stage 4: a long-lived workspace container plus streamed events for reconnectable sessions.
