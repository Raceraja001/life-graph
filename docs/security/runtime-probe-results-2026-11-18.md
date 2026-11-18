# Task runtime: security probe results, 2026-11-18

**What ran:** `scripts/runtime_security_probe.py`. The probe program ran inside a real `DockerTaskRuntime` container, and the lifecycle checks ran from outside it.
**Where:** the owner's workstation (WSL2 Ubuntu, Docker 29.7.2 rootful, seccomp builtin).
**Images:**
- `life-graph-claude-driver:wo-test`, built from this branch by `docker/claude-driver/build.sh`. It is the same Dockerfile prod uses; the tag is separate so prod's `:latest` was not touched.
- `life-graph-sandbox-egress:dev` (proxy).

**Policy:** `POLICY_VERSION 2026-11-18.1`. Limits for this run: 512m memory, 1 CPU, 256 pids, 256m `/tmp`. The egress allowlist was the default: `api.anthropic.com, console.anthropic.com, platform.claude.com, claude.ai`.

These are observations from one machine. They are evidence for the design, not a proof that containers cannot be escaped (see the ADR's residual risks).

## Inside the container

| Probe | Result | Expected |
|---|---|---|
| uid / gid | 1000 / 1000 | non-root ✔ |
| CapEff / CapBnd | `0000000000000000` / `0000000000000000` | no capabilities ✔ |
| NoNewPrivs / Seccomp | 1 / 2 (filter) | ✔ |
| `os.setuid(0)` | PermissionError | ✔ |
| `sudo` present | no | ✔ |
| Host paths visible: `/mnt/h`, `/home/raja`, prod `.env` | none exist | ✔ |
| `/var/run/docker.sock`, `/run/docker.sock` | do not exist | ✔ |
| Read `/etc/shadow` | PermissionError | ✔ |
| Write `/`, `/usr`, `/etc` | EROFS (read-only fs) | ✔ |
| Write `/work` (the worktree) | ok, and the file appeared in the worktree on the host; the origin repo was untouched | ✔ |
| `/work` listing | `.git`, `app.py` (the worktree only) | ✔ |
| `LIFE_GRAPH_*` variables | none | ✔ |
| Credential-shaped variables | `GPG_KEY` only: the python base image's public release-signing key fingerprint, not a secret | ✔ (noted) |
| DNS `example.com`, `host.docker.internal` | name resolution fails | ✔ |
| Direct TCP: 1.1.1.1:443, 8.8.8.8:53, 192.168.1.1:80, 169.254.169.254:80 | network unreachable | ✔ |
| Direct TCP to host-published ports via 172.17.0.1: 55432 (Postgres), 56379 (Redis), 11434 (Ollama), 8080 (API) | network unreachable | ✔ |
| Proxy `CONNECT api.anthropic.com:443` | `200 Connection Established` | allowed ✔ |
| Proxy `CONNECT example.com:443`, `github.com:443` | `403 Forbidden` | ✔ |
| Proxy `CONNECT api.anthropic.com:22` | `403 Forbidden` | ✔ |
| Proxy `CONNECT 172.17.0.1:55432`, `169.254.169.254:80`, `127.0.0.1:8080` | `403 Forbidden` | ✔ |
| Fork until refused | 253 processes, then BlockingIOError (pids 256) | ✔ |
| Fill `/tmp` | ENOSPC at the 256m tmpfs | ✔ |
| Allocate 2 GiB | child killed (-9) at the 512m limit | ✔ |

## Lifecycle, from outside

| Check | Result |
|---|---|
| Startup + probe wall time | ~3 s (network + proxy + driver container + teardown) |
| Teardown after a normal run | `{"ok": true}`; no labelled container or network left |
| In-container deadline: `sleep 120` with timeout 3 s | raised "timed out after 3s" at 5.8 s; teardown ok |
| Caller SIGKILLed mid-run (a crashed API process) | 1 container left behind; `sweep(set())` removed it and its network; 0 after |
| Missing image | refused before anything was created (0 networks created) |
| `$HOME` as the workspace | refused by the validator ("outside the runtime's bind roots") before docker was called |

## End to end: one real task

`scripts/runtime_e2e_smoke.py`, same machine and images, plus `life-graph-verifier:wo-test`.

- **Driver:** claude_code in `task` mode, with OAuth via a staged token copy.
  - Instruction: add `mul(a, b)` and a test to a fixture repo.
  - Result: `success`, `boundary=task`, 7 turns, 18 s. The tools used were Read ×4, Edit ×4 and Bash ×4, all inside the container.
  - The CLI reached the API through the allowlisting proxy.
- **Verification:** `tests_pass` ran in the network-less verifier sandbox and passed, 2 tests.
- **Diff:** correct changes to `calc.py` and `tests/test_calc.py`. The origin repo was untouched, and teardown was ok.
- **Defect found:** the agent's own `python` runs left `__pycache__/*.pyc` files in the diff. Fixed by setting `PYTHONDONTWRITEBYTECODE=1` in the driver env. That fix has not been re-run end to end.
- **Cost:** the CLI reported a notional $0.137. OAuth runs bill the subscription, not the API; the Governor still books the reported figure.

## Not yet tested

- Kernel/runtime escape techniques. Out of scope; we make no claim.
- DNS tunnelling or data hidden inside traffic to an allowlisted host.
- OpenCode inside the runtime. It is not moved there yet.
- Long-running concurrent tasks under memory pressure on the shared WSL box.
- Prod configuration. Prod's images are still not built, and prod has not been switched to `task`.
