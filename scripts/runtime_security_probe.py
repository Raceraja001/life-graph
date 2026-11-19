"""Security boundary probes for the per-task runtime (work order Stage 5, first cut).

Runs a probe program INSIDE a real task runtime (services/dev/task_runtime.py)
and reports, as JSON, what it could and could not reach. Also checks the
lifecycle claims from outside: the deadline stops a container, a crashed
caller's container is removed by the sweep, and a missing image fails closed.

Run in a controlled environment only (it makes real docker containers):

    python scripts/runtime_security_probe.py --image life-graph-claude-driver:wo-test

Needs docker and the egress image (life-graph-sandbox-egress:dev). Writes
nothing outside a scratch dir under the dispatch scratch root, which it
removes. Results are evidence for docs/security/runtime-probe-results.md;
they are not a claim that containers are escape-proof.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROBE = r"""
import json, os, socket, subprocess, sys
r = {}
def attempt(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)[:160]}

status = open("/proc/self/status").read()
field = lambda k: next((l.split(":",1)[1].strip() for l in status.splitlines() if l.startswith(k)), None)
r["identity"] = {"uid": os.getuid(), "gid": os.getgid(), "CapEff": field("CapEff"),
                 "CapBnd": field("CapBnd"), "NoNewPrivs": field("NoNewPrivs"),
                 "Seccomp": field("Seccomp")}
r["setuid_root"] = attempt(lambda: os.setuid(0))
r["sudo_present"] = any(os.path.exists(p) for p in ("/usr/bin/sudo", "/bin/sudo"))

# Filesystem
r["root_listing"] = sorted(os.listdir("/"))
r["work_listing"] = sorted(os.listdir("/work"))[:50]
for name, path in [("host_mnt", "/mnt/h"), ("host_home", "/home/raja"), ("root_home", "/root"),
                   ("docker_sock", "/var/run/docker.sock"), ("run_docker_sock", "/run/docker.sock"),
                   ("host_env_file", "/mnt/h/DevTools/Projects/life-graph-prod/.env")]:
    r["exists_" + name] = os.path.exists(path)
r["read_shadow"] = attempt(lambda: open("/etc/shadow").read(10))
for name, path in [("write_root", "/probe"), ("write_usr", "/usr/probe"), ("write_etc", "/etc/probe")]:
    r[name] = attempt(lambda p=path: open(p, "w").write("x"))
r["write_work"] = attempt(lambda: open("/work/.probe-write", "w").write("x"))
r["write_tmp"] = attempt(lambda: open("/tmp/probe", "w").write("x"))
r["git_dir_target"] = attempt(lambda: open("/work/.git").read().strip())
# Plant links the HOST would follow (relative and absolute): the agent cannot
# read through them in here, but host-side readers of the worktree could.
r["plant_symlinks"] = attempt(lambda: [os.symlink(t, "/work/" + n) for n, t in
    (("leak_abs", "/home/raja/.ssh/id_rsa"), ("leak_rel", "../../../../../../etc/passwd"))] and "planted")

# Environment
r["env_names"] = sorted(os.environ)
r["env_app_config"] = [k for k in os.environ if k.startswith("LIFE_GRAPH_")]
r["env_credential_shaped"] = [k for k in os.environ
    if any(s in k.lower() for s in ("key", "secret", "token", "password", "auth", "session"))]

# Network, direct (no proxy)
def tcp(host, port, t=3):
    s = socket.create_connection((host, port), timeout=t); s.close(); return "connected"
def tcp_ok(host, port):
    try:
        socket.create_connection((host, port), timeout=1.5).close(); return True
    except OSError:
        return False
r["dns_external"] = attempt(lambda: socket.getaddrinfo("example.com", 443)[0][4][0])
for name, (h, p) in {"internet_1111_443": ("1.1.1.1", 443), "internet_8888_53": ("8.8.8.8", 53),
                     "docker_gw_postgres": ("172.17.0.1", 55432), "docker_gw_redis": ("172.17.0.1", 56379),
                     "docker_gw_ollama": ("172.17.0.1", 11434), "docker_gw_api": ("172.17.0.1", 8080),
                     "metadata_169254": ("169.254.169.254", 80), "lan_192168_1_1": ("192.168.1.1", 80)}.items():
    r["direct_" + name] = attempt(lambda h=h, p=p: tcp(h, p))
r["resolve_host_docker_internal"] = attempt(lambda: socket.getaddrinfo("host.docker.internal", 80)[0][4][0])

# The bridge's own gateway address (first host of this container's subnet):
# with plain --internal the HOST held this address and answered on every
# 0.0.0.0 port. Read from the interface's netmask, not assumed to be a /24:
# runtime networks get a /28 from driver_runtime_subnet_pool.
def own_ip_and_mask():
    import fcntl, struct
    for name in os.listdir("/sys/class/net"):
        if name == "lo":
            continue
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        req = struct.pack("256s", name.encode()[:15])
        ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, req)[20:24])  # SIOCGIFADDR
        mask = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x891B, req)[20:24])  # SIOCGIFNETMASK
        return ip, mask
import ipaddress
_ip, _mask = own_ip_and_mask()
_subnet = ipaddress.ip_network(f"{_ip}/{_mask}", strict=False)
gw = str(_subnet.network_address + 1)
r["own_subnet"] = str(_subnet)
r["bridge_gateway"] = gw
# With gateway_mode_ipv4=isolated the network has no gateway, so docker hands
# .1 to the first container on it -- the egress proxy, which listens on its
# own port. Reaching that port is the proxy, not the host (seen 2026-11-19
# when the prod API, also on 8080, joined PROBE_HOST_PORTS).
try:
    _proxy_ip = socket.gethostbyname(os.environ.get("HTTPS_PROXY", "").split("//", 1)[1].rsplit(":", 1)[0])
except Exception:
    _proxy_ip = ""
r["bridge_gateway_is_egress_proxy"] = gw == _proxy_ip
ports = [int(x) for x in os.environ.get("PROBE_HOST_PORTS", "").split() if x]
open_ports = [p for p in ports if tcp_ok(gw, p)]
if r["bridge_gateway_is_egress_proxy"]:
    # Any open port other than the proxy's own would still be a finding.
    _proxy_port = int(os.environ.get("HTTPS_PROXY", "").rsplit(":", 1)[1].strip("/"))
    r["bridge_gateway_proxy_port"] = _proxy_port
    open_ports = [p for p in open_ports if p != _proxy_port]
r["bridge_gateway_open_host_ports"] = open_ports

# Network, through the proxy
proxy = os.environ.get("HTTPS_PROXY", "")
def connect_via_proxy(target):
    host, port = proxy.split("//",1)[1].rsplit(":",1)
    s = socket.create_connection((host, int(port)), timeout=10)
    s.sendall(("CONNECT %s HTTP/1.1\r\nHost: %s\r\n\r\n" % (target, target)).encode())
    line = s.recv(200).split(b"\r\n",1)[0].decode(errors="replace"); s.close(); return line
for name, target in {"allowlisted_api": "api.anthropic.com:443", "not_allowlisted": "example.com:443",
                     "github": "github.com:443", "allowlisted_wrong_port": "api.anthropic.com:22",
                     "docker_gw_postgres": "172.17.0.1:55432", "metadata": "169.254.169.254:80",
                     "loopback": "127.0.0.1:8080"}.items():
    r["proxy_" + name] = attempt(lambda t=target: connect_via_proxy(t)) if proxy else {"ok": False, "error": "no proxy"}

# Resources
def forks():
    n = 0; procs = []
    try:
        for _ in range(5000):
            procs.append(subprocess.Popen(["sleep", "30"])); n += 1
    except Exception as e:
        err = type(e).__name__
    else:
        err = None
    for p in procs: p.kill()
    return {"spawned": n, "stopped_by": err}
r["pids_limit"] = attempt(forks)
def fill_tmp():
    written = 0
    with open("/tmp/fill", "wb") as f:
        try:
            while written < 4 * 1024**3:
                f.write(b"\0" * 1024**2); written += 1024**2
        except OSError as e:
            return {"written_mb": written // 1024**2, "stopped_by": type(e).__name__}
    return {"written_mb": written // 1024**2, "stopped_by": None}
r["tmp_quota"] = attempt(fill_tmp)
os.remove("/tmp/fill") if os.path.exists("/tmp/fill") else None
mem = subprocess.run([sys.executable, "-c", "b = bytearray(2 * 1024**3); print(len(b))"],
                     capture_output=True, text=True)
r["memory_limit"] = {"returncode": mem.returncode, "stdout": mem.stdout.strip()}
print("PROBE_JSON=" + json.dumps(r))
"""


def _host_listening_ports() -> list[int]:
    """Every TCP port the host listens on for all addresses (0.0.0.0 / ::)."""
    out = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout
    ports = set()
    for line in out.splitlines():
        local = line.split()[3] if len(line.split()) > 3 else ""
        host, _, port = local.rpartition(":")
        if host in ("0.0.0.0", "*", "[::]") and port.isdigit():
            ports.add(int(port))
    return sorted(ports)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="life-graph-claude-driver:wo-test")
    ap.add_argument("--memory", default="512m")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    from life_graph.config import settings
    # Its own instance label (task_runtime.instance_id): a dev-task worker's
    # startup sweep removes this install's runtimes with no running task row,
    # which a script's runtimes never have (seen 2026-11-18).
    settings.edition = (settings.edition or "") + "-script"
    from life_graph.drivers.dispatcher import tenant_scratch_root
    from life_graph.services.dev import sandbox, task_runtime

    scratch = Path(tenant_scratch_root("probe")) / f"lg_dispatch_probe_{uuid.uuid4().hex[:6]}"
    repo, worktree = scratch / "origin", scratch / "wt_probe"
    repo.mkdir(parents=True)
    _git("init", "-q", cwd=repo)
    (repo / "app.py").write_text("print('hi')\n")
    _git("add", ".", cwd=repo)
    _git("-c", "user.email=p@p", "-c", "user.name=p", "commit", "-qm", "init", cwd=repo)
    _git("worktree", "add", "--detach", str(worktree), cwd=repo)

    rt = task_runtime.DockerTaskRuntime()
    report: dict = {"image": args.image, "policy_version": task_runtime.POLICY_VERSION}
    base = dict(
        tenant_id="probe", driver="probe", image=args.image, workspace=worktree,
        egress_allowlist=tuple(settings.driver_runtime_egress_allowlist_list),
        memory=args.memory, cpus="1", pids_limit=256, tmp_size="256m",
    )  # fmt: skip
    try:
        # 1. Inside the boundary.
        t0 = time.monotonic()
        out = await rt.run(
            task_runtime.RuntimeRequest(
                task_id=str(uuid.uuid4()),
                command=("python3", "-c", PROBE),
                timeout=300,
                env={"PROBE_HOST_PORTS": " ".join(map(str, _host_listening_ports()))},
                **base,
            )
        )
        report["startup_and_probe_seconds"] = round(time.monotonic() - t0, 1)
        line = next((ln for ln in out.stdout.splitlines() if ln.startswith("PROBE_JSON=")), None)
        report["inside"] = (
            json.loads(line.split("=", 1)[1])
            if line
            else {"stdout": out.stdout[-2000:], "stderr": out.stderr[-2000:]}
        )
        report["runtime_metadata"] = out.metadata
        report["host_side"] = {
            "probe_file_landed_in_worktree": (worktree / ".probe-write").exists(),
            "origin_untouched": not (repo / ".probe-write").exists(),
            # The dispatcher vetoes the run when this is non-empty (drivers/workdir.py).
            "escaping_symlinks_flagged": __import__(
                "life_graph.drivers.workdir", fromlist=["x"]
            ).escaping_symlinks(worktree),
        }

        # 1b. The project env mount (PR #267): readable, never writable.
        env_dir = sandbox._cache_root() / f"probe-{uuid.uuid4().hex[:12]}"
        env_dir.mkdir(parents=True)
        (env_dir / "marker").write_text("verifier-owned")
        try:
            out = await rt.run(task_runtime.RuntimeRequest(
                task_id=str(uuid.uuid4()), timeout=60, tool_env=env_dir.resolve(),
                command=("sh", "-c", "cat /venv/marker; "
                         "touch /venv/x 2>/dev/null && echo CREATE_OK || echo CREATE_NO; "
                         "(echo y > /venv/marker) 2>/dev/null && echo WRITE_OK || echo WRITE_NO; "
                         "rm -f /venv/marker 2>/dev/null; "
                         "[ -e /venv/marker ] && echo DELETE_NO || echo DELETE_OK"),
                **base,
            ))  # fmt: skip
            report["tool_env_mount"] = {
                "readable": "verifier-owned" in out.stdout,
                "write_refused": all(
                    s in out.stdout for s in ("CREATE_NO", "WRITE_NO", "DELETE_NO")
                ),
                "host_copy_intact": (env_dir / "marker").read_text() == "verifier-owned"
                and not (env_dir / "x").exists(),
                "bind": [b for b in out.metadata.get("binds", []) if b["target"] == "/venv"],
            }
        finally:
            shutil.rmtree(env_dir, ignore_errors=True)

        # 2. The in-container deadline.
        t0 = time.monotonic()
        try:
            await rt.run(task_runtime.RuntimeRequest(
                task_id=str(uuid.uuid4()), command=("sleep", "120"), timeout=3, **base))  # fmt: skip
            report["deadline"] = {"raised": False}
        except sandbox.SandboxUnavailableError as exc:
            report["deadline"] = {
                "raised": True, "message": str(exc),
                "seconds": round(time.monotonic() - t0, 1),
                "teardown": getattr(exc, "runtime_metadata", {}).get("teardown"),
            }  # fmt: skip

        # 3. A caller that dies mid-run leaves a container; the sweep removes it.
        # The child must carry this script's instance label (the "-script"
        # edition above), or the sweep rightly leaves its container alone.
        orphan_task = str(uuid.uuid4())
        child = subprocess.Popen(
            [sys.executable, "-c", (
                "import asyncio,sys;from pathlib import Path;"
                "from life_graph.config import settings;"
                f"settings.edition={settings.edition!r};"
                "from life_graph.services.dev import task_runtime as t;"
                f"asyncio.run(t.DockerTaskRuntime().run(t.RuntimeRequest(task_id='{orphan_task}',"
                f"tenant_id='probe',driver='probe',image='{args.image}',command=('sleep','600'),"
                f"workspace=Path('{worktree}'),timeout=600)))"
            )],
        )  # fmt: skip
        for _ in range(60):
            ps = subprocess.run(
                ["docker", "ps", "--filter", f"label=life-graph.runtime.task={orphan_task}", "-q"],
                capture_output=True, text=True,
            )  # fmt: skip
            if ps.stdout.strip():
                break
            await asyncio.sleep(0.5)
        child.kill()  # SIGKILL: no finally, no teardown -- a crashed API process
        child.wait()
        await asyncio.sleep(1)
        left = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"label=life-graph.runtime.task={orphan_task}", "-q"],
            capture_output=True, text=True,
        ).stdout.split()  # fmt: skip
        swept = await rt.sweep(set())
        after = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"label=life-graph.runtime.task={orphan_task}", "-q"],
            capture_output=True, text=True,
        ).stdout.split()  # fmt: skip
        report["orphan"] = {
            "containers_after_caller_killed": len(left),
            "sweep": {k: v for k, v in swept.items() if k != "errors"}
            | {"errors": swept["errors"]},
            "containers_after_sweep": len(after),
        }

        # 4. Missing image: fail closed, nothing created.
        before = subprocess.run(["docker", "network", "ls", "-q"], capture_output=True, text=True)
        try:
            await rt.run(task_runtime.RuntimeRequest(
                task_id=str(uuid.uuid4()), command=("true",), timeout=10,
                **{**base, "image": "life-graph-does-not-exist:none"}))  # fmt: skip
            report["missing_image"] = {"raised": False}
        except sandbox.SandboxUnavailableError as exc:
            after_n = subprocess.run(
                ["docker", "network", "ls", "-q"], capture_output=True, text=True
            )
            report["missing_image"] = {
                "raised": True, "message": str(exc)[:200],
                "networks_created": len(after_n.stdout.split()) - len(before.stdout.split()),
            }  # fmt: skip

        # 5. Workspace outside the scratch root: refused before docker is touched.
        try:
            await rt.run(task_runtime.RuntimeRequest(
                task_id=str(uuid.uuid4()), command=("true",), timeout=10,
                **{**base, "workspace": Path.home()}))  # fmt: skip
            report["home_as_workspace"] = {"raised": False}
        except sandbox.SandboxUnavailableError as exc:
            report["home_as_workspace"] = {"raised": True, "message": str(exc)[:300]}
    finally:
        _git("worktree", "remove", "--force", str(worktree), cwd=repo)
        shutil.rmtree(scratch, ignore_errors=True)

    text = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
