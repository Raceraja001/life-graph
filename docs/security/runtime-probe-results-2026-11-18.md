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
| Host services via the bridge's own gateway address (`.1` of the task subnet), all 26 host ports listening on `0.0.0.0` | **none reachable** (after the fix below) | ✔ |
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

## Finding fixed during review: the bridge gateway

The first version created a plain `docker network create --internal` network. An
independent review pointed out that such a network drops *forwarded* traffic, but the host
still holds the bridge's gateway address. The first probe set never tested that address.
Tested by hand, it was a real hole: from inside an internal network, the host's own
services bound to `0.0.0.0` answered on the gateway:

- 2222 (sshd)
- 3006 (the prod web UI)
- 3050
- 3390
- 8015, 8016
- 8085
- 8095
- 8188

Only docker-published ports were dropped.

Fix: the network is now created with
`com.docker.network.bridge.gateway_mode_ipv{4,6}=isolated` (docker ≥ 28), which gives the
host no address on the bridge at all. The runtime checks the option took effect and
refuses to run otherwise. Re-probed: 0 of 26 host ports reachable, while container-to-proxy
DNS and traffic still work. The probe script now always runs this check.

The same hole still applies to things this PR does not change:

- the legacy `driver_claude_sandbox=docker` mode (default bridge, which also has open egress);
- the verifier sandbox's dependency-setup phase (default bridge, network on).

The verifier's check phase uses `--network none` and is not affected.

## End to end: one real task

`scripts/runtime_e2e_smoke.py`, same machine and images, plus `life-graph-verifier:wo-test`.

- **Driver:** claude_code in `task` mode, with OAuth via a staged token copy.
  - Instruction: add `mul(a, b)` and a test to a fixture repo.
  - Result: `success`, `boundary=task`, 7 turns, 18 s. The tools used were Read ×4, Edit ×4 and Bash ×4, all inside the container.
  - The CLI reached the API through the allowlisting proxy.
- **Verification:** `tests_pass` ran in the network-less verifier sandbox and passed, 2 tests.
- **Diff:** correct changes to `calc.py` and `tests/test_calc.py`. The origin repo was untouched, and teardown was ok.
- **Defect found:** the agent's own `python` runs left `__pycache__/*.pyc` files in the diff. Fixed by setting `PYTHONDONTWRITEBYTECODE=1` in the driver env.
- **Re-run on the final code** (isolated network): success, 7 turns, 19 s. The diff has only `calc.py` and `tests/test_calc.py` (no `.pyc`); `tests_pass` passed; teardown ok.
- **Cost:** the CLI reported a notional $0.137. OAuth runs bill the subscription, not the API; the Governor still books the reported figure.

## Not yet tested

- Kernel/runtime escape techniques. Out of scope; we make no claim.
- DNS tunnelling or data hidden inside traffic to an allowlisted host.
- OpenCode inside the runtime. It is not moved there yet.
- Long-running concurrent tasks under memory pressure on the shared WSL box.
- Prod configuration. Prod's images are still not built, and prod has not been switched to `task`.

## Stage 5 re-probe (`runtime-probe-20261118.json`)

Same probe, on the code with all review fixes, plus a new attack:

| Check | Result |
|---|---|
| The agent plants `leak_abs -> /home/raja/.ssh/id_rsa` and `leak_rel -> ../../../../../../etc/passwd` in its worktree from inside the container | planting works, since a symlink is just a file. **`escaping_symlinks` flags both, so the dispatcher vetoes the run as tampering before any host-side reader (verifiers, PR description, review model, landing) touches the worktree.** |
| Host ports reachable through the bridge gateway | 0 |
| Proxy: api.anthropic.com / example.com | 200 / 403 |
| Deadline, orphan sweep, teardown | ok / 0 left / ok |

Why this matters: inside the container the agent cannot read a host file through such a link,
because the link resolves inside the container. But code on the host that trusts the worktree
would follow it. Before this fix, a planted link could have carried a host secret into a
verifier's evidence, a PR description, or a review-model prompt.

## Release-image probe, 2026-11-19 (`runtime-probe-20261119-821beec.json`)

Run against the images built for the production switch from master 821beec:
`life-graph-claude-driver:821beec-cli2.1.272` and `life-graph-sandbox-egress:821beec`.

| Check | Result |
|---|---|
| Capabilities, no-new-privileges, seccomp | none / 1 / filter |
| Host paths, docker socket, `LIFE_GRAPH_*` variables | none visible |
| Direct internet, LAN, metadata, docker gateway | unreachable (`Network is unreachable`) |
| External DNS from inside | fails (no resolver reachable) |
| Host ports reachable through the bridge gateway | 0 |
| Proxy: api.anthropic.com / not listed / github / wrong port / loopback / metadata | 200 / 403 / 403 / 403 / 403 / 403 |
| Planted escaping symlinks | both flagged |
| Deadline, orphan sweep, missing image, home as workspace | ok / 1 removed, 0 left / refused / refused |

The first run of this probe reported the orphan as not swept. That was a bug in the probe, not
the runtime: since the Stage 5 fix the probe labels its runtimes as a separate instance
(`-script`), but its crashed-caller child process did not, so the sweep correctly left the
child's container alone. The child now carries the same instance label.
