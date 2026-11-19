"""Per-task execution runtime for coding drivers.

Work order: ``docs/work-orders/secure-execution-runtime.md``. ADR and threat
model: ``docs/design/adr-secure-task-runtime.md``.

A git worktree separates an agent's *files* from the live checkout; it does
nothing about what the agent's *process* can reach. This module gives one
dispatch one container that can reach almost nothing:

- **Filesystem.** The task's worktree is the only writable host path, plus
  (OAuth mode) a throwaway copy of the CLI token. Both are typed
  :class:`~life_graph.services.dev.sandbox.Bind` entries that
  :func:`~life_graph.services.dev.sandbox.validate_spec` refuses unless they
  sit under the dispatch scratch root or the staged-credentials root — never
  the live checkout, ``$HOME`` or ``/``. Root filesystem read-only, ``/tmp``
  a size-capped tmpfs.
- **Process.** Host uid (never root — the validator refuses uid 0), all
  capabilities dropped, ``no-new-privileges``, pids/memory/cpu ceilings with
  no swap, ``--init``, and an in-container deadline (coreutils ``timeout``)
  so a container whose API process died still stops on its own.
- **Network.** A fresh ``--internal`` bridge per task (no gateway — checked,
  not assumed). The only other member is a per-task egress proxy (the
  existing ``browser_egress_proxy``) that is also on an outbound bridge and
  relays only to the hostnames in ``driver_runtime_egress_allowlist``, only
  on 443, never to private/loopback/link-local addresses.
- **Secrets.** Nothing inherited from the API process. The environment is
  built here and checked by the same validator that refuses ``LIFE_GRAPH_*``
  names and credential-shaped values; an API key (commercial mode) is passed
  by name only, from the docker client's environment.
- **Audit and cleanup.** Every container and network carries
  ``life-graph.runtime.*`` labels (task, tenant, driver, policy version).
  Teardown is idempotent and always runs; :meth:`DockerTaskRuntime.sweep`
  removes what a crashed process left behind.

Anything that stops the runtime from starting raises
:class:`~life_graph.services.dev.sandbox.SandboxUnavailableError`. Callers
turn that into a failed dispatch. There is no host fallback anywhere here.

What this does NOT claim: containers share the host kernel and are not
escape-proof; the docker daemon is rootful and the API user can drive it;
the agent can read its own staged OAuth token and talk to the allowlisted
hosts with it. See the ADR's residual-risk section.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import os
import shutil
import time
import uuid
from collections.abc import Callable  # noqa: TC003
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from life_graph.config import settings
from life_graph.services.dev import sandbox
from life_graph.services.dev.sandbox import (
    RUNTIME_LABEL,
    RUNTIME_NETWORK_PREFIX,
    Bind,
    SandboxPolicyError,
    SandboxResult,
    SandboxSpec,
    SandboxUnavailableError,
)

logger = logging.getLogger(__name__)

# Bumped whenever what a runtime container is allowed changes, so a task's
# recorded metadata says which rules it ran under.
# 2026-11-19.1: the project's cached verifier env may be mounted read-only.
# 2026-11-19.2: the internal network gets an explicit subnet from
#   driver_runtime_subnet_pool (same internal + isolated-gateway network; only
#   where its addresses come from changed).
POLICY_VERSION = "2026-11-19.2"

OUTBOUND_NETWORK = "lg-rt-outbound"
EGRESS_PORT = 8080
DEADLINE_BIN = "/usr/bin/timeout"
# The runner's periodic sweep keeps runtimes younger than this: one may belong
# to a task claimed after the sweep read which tasks are running.
PERIODIC_MIN_AGE_SECONDS = 300
_SHARED_LABEL = f"{RUNTIME_LABEL}.shared"


class DockerRunner(Protocol):
    """How the runtime reaches docker. Tests inject a fake; nothing else differs."""

    async def __call__(
        self,
        argv: list[str],
        *,
        timeout: int,
        container: str | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxResult: ...


async def docker_runner(
    argv: list[str],
    *,
    timeout: int,
    container: str | None = None,
    env: dict[str, str] | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
) -> SandboxResult:
    # sandbox._exec keeps the parent env for the docker CLI itself (it needs
    # DOCKER_HOST etc.); nothing of it reaches the container unless named.
    return await sandbox._exec(
        argv, timeout, container=container, env=env, on_stdout_line=on_stdout_line
    )


@dataclass(frozen=True)
class RuntimeRequest:
    """One command to run for one task, and the policy it runs under."""

    task_id: str
    tenant_id: str
    driver: str
    image: str
    command: tuple[str, ...]
    workspace: Path
    credentials: Path | None = None
    credentials_target: str = "/claude-config"
    # The project's cached verifier environment (sandbox.prepare_env), mounted
    # read-only so the agent can run its tests offline.
    tool_env: Path | None = None
    tool_env_target: str = sandbox.VENV
    env: dict[str, str] = field(default_factory=dict)
    # NAME -> value, handed to the docker client only and passed into the
    # container by name (sandbox.PASSTHROUGH_ENV_ALLOWED limits the names).
    secret_env: dict[str, str] = field(default_factory=dict)
    egress_allowlist: tuple[str, ...] = ()
    memory: str = "4g"
    cpus: str = "4"
    pids_limit: int = 512
    timeout: int = 1200
    tmp_size: str = "512m"
    # Each stdout line as it arrives (the live session view); not policy.
    on_stdout_line: Callable[[str], None] | None = field(default=None, compare=False)


@dataclass
class RuntimeOutcome:
    returncode: int
    stdout: str
    stderr: str
    metadata: dict


def _origin(entry: str) -> str:
    """``api.example.com`` -> ``https://api.example.com``; explicit schemes kept."""
    entry = entry.strip()
    return entry if "://" in entry else f"https://{entry}"


_ISOLATED_GATEWAY_OPTS = (
    "com.docker.network.bridge.gateway_mode_ipv4",
    "com.docker.network.bridge.gateway_mode_ipv6",
)

# How many subnets one runtime tries before it fails closed.
SUBNET_ATTEMPTS = 8


def _subnet_candidates(rid: str, pool: str, prefix: int) -> list[str]:
    """Up to SUBNET_ATTEMPTS distinct /``prefix`` subnets of ``pool`` for ``rid``.

    Derived from the runtime id, so concurrent runtimes spread over the pool
    (a collision costs one retry) and a run is reproducible in tests.

    Raises:
        SandboxUnavailableError: the pool is not a private network, or the
            prefix does not fit inside it.
    """
    try:
        net = ipaddress.ip_network(pool.strip(), strict=True)
    except ValueError as exc:
        raise SandboxUnavailableError(
            f"driver_runtime_subnet_pool {pool!r} is not a network: {exc}"
        ) from exc
    if net.version != 4 or not net.is_private:
        raise SandboxUnavailableError(
            f"driver_runtime_subnet_pool {pool!r} must be a private IPv4 range"
        )
    # /29 is the smallest that holds the gateway reservation, proxy and driver.
    if not net.prefixlen <= prefix <= 29:
        raise SandboxUnavailableError(
            f"driver_runtime_subnet_prefix /{prefix} does not fit in {pool}"
            f" (allowed: /{net.prefixlen} to /29)"
        )
    slots = 2 ** (prefix - net.prefixlen)
    size = 2 ** (32 - prefix)
    picked: list[str] = []
    for i in range(SUBNET_ATTEMPTS * 4):
        if len(picked) >= min(SUBNET_ATTEMPTS, slots):
            break
        idx = int(hashlib.sha256(f"{rid}:{i}".encode()).hexdigest(), 16) % slots
        cand = str(ipaddress.ip_network((int(net.network_address) + idx * size, prefix)))
        if cand not in picked:
            picked.append(cand)
    return picked


def _overlaps(res: SandboxResult) -> bool:
    """Docker refused the subnet because another network already holds it."""
    return "overlap" in (res.stderr or "").lower()


def _event(req: RuntimeRequest, kind: str, content: str, data: dict | None = None) -> None:
    """A runtime lifecycle line in the task's live session (best-effort)."""
    from life_graph.services.dev import task_events

    task_events.emit(req.tenant_id, req.task_id, kind, content, data=data, source="runtime")


def instance_id() -> str:
    """A stable id for this Life Graph install: its edition and database.

    Prod and dev run on one docker daemon with different databases; labelling
    runtimes with this keeps each one's sweep to its own containers.
    """
    import hashlib
    from urllib.parse import urlsplit

    db = urlsplit(settings.database_url.replace("+asyncpg", "")).path.lstrip("/")
    edition = getattr(settings, "edition", "") or ""
    return hashlib.sha256(f"{edition}|{db}".encode()).hexdigest()[:12]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _missing(res: SandboxResult) -> bool:
    text = (res.stderr or "").lower()
    return "no such" in text or "not found" in text


def _age_seconds(created: str, now: datetime | None = None) -> float | None:
    """Age of a docker ``CreatedAt`` value, or None when it cannot be read.

    Containers print ``2026-11-19 06:41:26 +0000 UTC``; networks add
    nanoseconds (``06:41:26.380002525``). The zone name is dropped and the
    numeric offset kept.
    """
    parts = created.strip().split()
    if len(parts) < 3:
        return None
    clock = parts[1].split(".", 1)[0]
    try:
        stamp = datetime.strptime(f"{parts[0]} {clock} {parts[2]}", "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None
    return ((now or datetime.now(UTC)) - stamp).total_seconds()


class DockerTaskRuntime:
    """Start, run, and tear down one task's container (plus its network and proxy)."""

    def __init__(self, runner: DockerRunner | None = None) -> None:
        self._docker = runner or docker_runner

    # ── Lifecycle ─────────────────────────────────────────────

    async def run(self, req: RuntimeRequest) -> RuntimeOutcome:
        """Run ``req.command`` in a fresh runtime and always tear it down.

        Raises:
            SandboxUnavailableError: docker, an image, the network, the proxy
                or the policy check refused; or the deadline was hit (the
                message then contains "timed out", which the claude_code
                driver reports as a timeout).
        """
        rid = uuid.uuid4().hex[:16]
        names = {
            "container": f"lg-rt-{rid}",
            "proxy": f"lg-rt-egress-{rid}",
            "network": f"{RUNTIME_NETWORK_PREFIX}{rid}",
        }
        labels = {
            RUNTIME_LABEL: "1",
            # Which Life Graph install made it: prod and dev share one docker
            # daemon, and one's sweep must never remove the other's live task.
            f"{RUNTIME_LABEL}.instance": instance_id(),
            f"{RUNTIME_LABEL}.task": str(req.task_id),
            f"{RUNTIME_LABEL}.tenant": str(req.tenant_id),
            f"{RUNTIME_LABEL}.driver": req.driver,
            f"{RUNTIME_LABEL}.policy": POLICY_VERSION,
            f"{RUNTIME_LABEL}.rid": rid,
        }
        meta: dict = {
            "runtime": "task",
            "policy_version": POLICY_VERSION,
            "rid": rid,
            **names,
            "image": req.image,
            "limits": {
                "memory": req.memory,
                "cpus": req.cpus,
                "pids": req.pids_limit,
                "timeout_s": req.timeout,
                "tmp": req.tmp_size,
            },
            "egress_allowlist": list(req.egress_allowlist),
            "started_at": _now(),
        }
        start = time.monotonic()
        try:
            meta["image_id"] = await self._image_id(req.image)
            spec = self._driver_spec(req, names, labels)
            meta["user"] = spec.user
            meta["binds"] = [{"target": b.target, "read_only": b.read_only} for b in spec.binds]
            meta["subnet"] = await self._create_network(names["network"], labels, rid)
            _event(req, "runtime", "isolated network ready", {"network": names["network"]})
            if req.egress_allowlist:
                meta["egress_image"] = settings.driver_runtime_egress_image
                meta["egress_image_id"] = await self._image_id(settings.driver_runtime_egress_image)
                await self._start_proxy(names["proxy"], names["network"], labels, req)
            argv = sandbox.docker_run_argv(spec, detach=False)
            grace = max(5, int(settings.driver_runtime_kill_grace_seconds))
            _event(req, "runtime", "agent container starting", {"rid": rid})
            res = await self._docker(
                argv,
                timeout=req.timeout + grace,
                container=names["container"],
                env=dict(req.secret_env) or None,
                on_stdout_line=req.on_stdout_line,
            )
            # 124: coreutils timeout fired inside the container; 137 after -k.
            if res.returncode in (124, 137) and time.monotonic() - start >= req.timeout:
                raise SandboxUnavailableError(f"sandboxed command timed out after {req.timeout}s")
            if res.returncode in (125, 126, 127) and not res.stdout:
                raise SandboxUnavailableError(
                    f"task runtime could not start: {res.stderr.strip()[-400:]}"
                )
            meta["exit_code"] = res.returncode
            return RuntimeOutcome(res.returncode, res.stdout, res.stderr, meta)
        except SandboxPolicyError as exc:
            # A spec the validator refused is a runtime that must not start.
            err = SandboxUnavailableError(f"task runtime policy refused the spec: {exc}")
            err.runtime_metadata = meta  # type: ignore[attr-defined]
            raise err from exc
        except SandboxUnavailableError as exc:
            # Both the in-container deadline and the host-side kill say this.
            if "timed out" in str(exc):
                meta["timed_out"] = True
            # The same dict: teardown below still lands in it.
            exc.runtime_metadata = meta  # type: ignore[attr-defined]
            raise
        finally:
            meta["finished_at"] = _now()
            meta["duration_ms"] = int((time.monotonic() - start) * 1000)
            try:
                meta["teardown"] = await self.teardown(names)
            except Exception as exc:  # never mask the run's own outcome
                logger.error("task runtime teardown raised: %s", exc)
                meta["teardown"] = {"ok": False, "errors": [f"teardown raised: {exc}"]}
            _event(
                req,
                "runtime",
                "runtime removed" if meta["teardown"].get("ok") else "runtime teardown incomplete",
                {"teardown": meta["teardown"], "exit_code": meta.get("exit_code")},
            )

    async def teardown(self, names: dict[str, str]) -> dict:
        """Remove one runtime's container, proxy and network. Idempotent."""
        errors: list[str] = []
        for key in ("container", "proxy"):
            res = await self._docker(["docker", "rm", "-f", names[key]], timeout=30)
            if res.returncode != 0 and not _missing(res):
                errors.append(f"{key}: {res.stderr.strip()[-200:]}")
        res = await self._docker(["docker", "network", "rm", names["network"]], timeout=30)
        if res.returncode != 0 and not _missing(res):
            errors.append(f"network: {res.stderr.strip()[-200:]}")
        if errors:
            logger.warning("task runtime teardown incomplete: %s", "; ".join(errors))
        return {"ok": not errors, "errors": errors}

    async def sweep(
        self,
        active_task_ids: set[str],
        *,
        creds_max_age_seconds: int | None = None,
        min_age_seconds: int = 0,
    ) -> dict:
        """Remove runtime leftovers whose task is not running.

        Containers and networks are found by label, never by name pattern, so
        nothing this module did not create is touched. Staged credential
        copies older than the longest possible dispatch are deleted too: a
        crash between ``stage_credentials`` and its ``finally`` leaves a live
        token on disk otherwise. With ``min_age_seconds``, anything younger
        (or of unknown age) is kept.
        """
        report: dict = {"containers": [], "networks": [], "credentials": 0, "errors": []}

        def old_enough(created: str) -> bool:
            if not min_age_seconds:
                return True
            age = _age_seconds(created)
            return age is not None and age >= min_age_seconds

        # Only this install's: the other edition on the same daemon has its own
        # database, so its running tasks are not in active_task_ids.
        mine = ["--filter", f"label={RUNTIME_LABEL}=1"]
        mine += ["--filter", f"label={RUNTIME_LABEL}.instance={instance_id()}"]
        fmt = f'{{{{.Names}}}}|{{{{.Label "{RUNTIME_LABEL}.task"}}}}|{{{{.CreatedAt}}}}'
        res = await self._docker(["docker", "ps", "-a", *mine, "--format", fmt], timeout=30)
        if res.returncode != 0:
            report["errors"].append(f"ps: {res.stderr.strip()[-200:]}")
        for line in (res.stdout or "").splitlines():
            name, task, created = (line.split("|", 2) + ["", ""])[:3]
            if name and task not in active_task_ids and old_enough(created):
                rm = await self._docker(["docker", "rm", "-f", name], timeout=30)
                if rm.returncode == 0 or _missing(rm):
                    report["containers"].append(name)
                else:
                    report["errors"].append(f"rm {name}: {rm.stderr.strip()[-200:]}")
        nfmt = f'{{{{.Name}}}}|{{{{.Label "{RUNTIME_LABEL}.task"}}}}|{{{{.CreatedAt}}}}'
        res = await self._docker(["docker", "network", "ls", *mine, "--format", nfmt], timeout=30)
        if res.returncode != 0:
            report["errors"].append(f"network ls: {res.stderr.strip()[-200:]}")
        for line in (res.stdout or "").splitlines():
            name, task, created = (line.split("|", 2) + ["", ""])[:3]
            if name and task not in active_task_ids and old_enough(created):
                rm = await self._docker(["docker", "network", "rm", name], timeout=30)
                if rm.returncode == 0 or _missing(rm):
                    report["networks"].append(name)
                else:
                    report["errors"].append(f"network rm {name}: {rm.stderr.strip()[-200:]}")
        max_age = creds_max_age_seconds
        if max_age is None:
            max_age = max(settings.driver_claude_code_timeout_seconds, 1200) * 2 + 600
        root = sandbox.driver_creds_root()
        if root.is_dir():
            cutoff = time.time() - max_age
            for entry in root.iterdir():
                try:
                    if entry.is_dir() and not entry.is_symlink() and entry.stat().st_mtime < cutoff:
                        shutil.rmtree(entry, ignore_errors=True)
                        report["credentials"] += 1
                except OSError as exc:
                    report["errors"].append(f"creds {entry.name}: {exc}")
        return report

    # ── Pieces ────────────────────────────────────────────────

    async def _image_id(self, image: str) -> str:
        res = await self._docker(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30
        )
        if res.returncode != 0:
            raise SandboxUnavailableError(
                f"runtime image {image!r} not found — build it before enabling the task runtime"
                " (docs/OPERATIONS.md, 'Dev-agent execution runtime')"
            )
        return res.stdout.strip()

    async def _create_network(self, name: str, labels: dict[str, str], rid: str = "") -> str | None:
        """Create the runtime's internal network; return its explicit subnet, if any."""
        # --internal alone is not enough: it drops forwarded traffic, but the
        # host still holds an address on the bridge, and a container reached
        # host services bound to 0.0.0.0 through it (probe 2026-11-18: the prod
        # UI on :3006, ComfyUI, sshd on :2222). "isolated" gateway mode (docker
        # >= 28) gives the host no address on the bridge at all.
        argv = ["docker", "network", "create", "--internal"]
        for opt in _ISOLATED_GATEWAY_OPTS:
            argv += ["-o", f"{opt}=isolated"]
        for key in sorted(labels):
            argv += ["--label", f"{key}={labels[key]}"]
        pool = (settings.driver_runtime_subnet_pool or "").strip()
        # None: docker's default pools (the old behaviour). Otherwise only
        # subnets of the pool; never a fallback to the default pools.
        subnets: list[str | None] = (
            list(_subnet_candidates(rid or name, pool, int(settings.driver_runtime_subnet_prefix)))
            if pool
            else [None]
        )
        res: SandboxResult | None = None
        for subnet in subnets:
            extra = ["--subnet", subnet] if subnet else []
            res = await self._docker([*argv, *extra, name], timeout=30)
            if res.returncode == 0:
                break
            if not (subnet and _overlaps(res)):
                raise SandboxUnavailableError(
                    f"could not create an isolated runtime network (needs docker >= 28): "
                    f"{res.stderr[-300:]}"
                )
            logger.info("runtime subnet %s is taken; trying another", subnet)
        else:
            raise SandboxUnavailableError(
                f"could not create an isolated runtime network: {len(subnets)} subnets of"
                f" {pool} were all taken (driver_runtime_subnet_pool): "
                f"{(res.stderr if res else '')[-200:]}"
            )
        # Both properties checked, not assumed: an older daemon may accept and
        # ignore the option.
        check = await self._docker(
            [
                "docker", "network", "inspect", "--format",
                '{{.Internal}}|{{index .Options "' + _ISOLATED_GATEWAY_OPTS[0] + '"}}',
                name,
            ],
            timeout=30,
        )  # fmt: skip
        internal, _, mode = (check.stdout or "").strip().partition("|")
        if check.returncode != 0 or internal.lower() != "true" or mode != "isolated":
            raise SandboxUnavailableError(
                f"runtime network {name} is not internal with an isolated gateway"
            )
        return subnet

    async def _ensure_outbound(self) -> None:
        res = await self._docker(["docker", "network", "inspect", OUTBOUND_NETWORK], timeout=30)
        if res.returncode == 0:
            return
        res = await self._docker(
            ["docker", "network", "create", "--label", f"{_SHARED_LABEL}=1", OUTBOUND_NETWORK],
            timeout=30,
        )
        if res.returncode != 0 and "already exists" not in (res.stderr or ""):
            raise SandboxUnavailableError(f"could not create outbound network: {res.stderr[-300:]}")

    async def _start_proxy(
        self, name: str, network: str, labels: dict[str, str], req: RuntimeRequest
    ) -> None:
        """The per-task egress proxy: the internal network's only way out.

        Not built from a SandboxSpec on purpose — it is the one container that
        must sit on a network with a gateway, which a spec can never be. It
        gets the same hardening by hand and runs code the image was built
        from (no host path, no task data).
        """
        await self._ensure_outbound()
        argv = [
            "docker", "run", "--detach", "--init",
            "--name", name,
            *[x for k in sorted(labels) for x in ("--label", f"{k}={labels[k]}")],
            "--label", f"{RUNTIME_LABEL}.role=egress",
            "--network", network,
            "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--pids-limit", "64", "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.5",
            "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m",
            settings.driver_runtime_egress_image,
            "python3", "-m", "life_graph.services.browser_egress_proxy",
            "--host", "0.0.0.0", "--port", str(EGRESS_PORT),
            "--allowed-port", "443",
            "--idle-timeout", "600",
        ]  # fmt: skip
        for entry in req.egress_allowlist:
            argv += ["--allowed-origin", _origin(entry)]
        res = await self._docker(argv, timeout=60)
        if res.returncode != 0:
            raise SandboxUnavailableError(f"egress proxy did not start: {res.stderr[-300:]}")
        res = await self._docker(
            ["docker", "network", "connect", OUTBOUND_NETWORK, name], timeout=30
        )
        if res.returncode != 0:
            raise SandboxUnavailableError(f"egress proxy has no way out: {res.stderr[-300:]}")
        probe = (
            f"import socket;socket.create_connection(('127.0.0.1',{EGRESS_PORT}),timeout=1).close()"
        )
        for _ in range(20):
            res = await self._docker(["docker", "exec", name, "python3", "-c", probe], timeout=10)
            if res.returncode == 0:
                return
            await asyncio.sleep(0.25)
        raise SandboxUnavailableError("egress proxy never became ready")

    def _driver_spec(
        self, req: RuntimeRequest, names: dict[str, str], labels: dict[str, str]
    ) -> SandboxSpec:
        binds = [Bind(str(Path(req.workspace).resolve()), sandbox.WORK)]
        if req.credentials is not None:
            binds.append(Bind(str(Path(req.credentials).resolve()), req.credentials_target))
        if req.tool_env is not None:
            binds.append(
                Bind(str(Path(req.tool_env).resolve()), req.tool_env_target, read_only=True)
            )
        env = {"HOME": "/tmp", "LANG": "C.UTF-8", "TZ": "UTC", **req.env}
        if req.egress_allowlist:
            proxy = f"http://{names['proxy']}:{EGRESS_PORT}"
            env.update(
                {
                    "HTTPS_PROXY": proxy,
                    "HTTP_PROXY": proxy,
                    "https_proxy": proxy,
                    "http_proxy": proxy,
                }
            )
        kill_after = max(5, int(settings.driver_runtime_kill_grace_seconds) // 2)
        spec = SandboxSpec(
            name=names["container"],
            image=req.image,
            role="driver",
            entrypoint=DEADLINE_BIN,
            command=("-k", str(kill_after), str(req.timeout), *req.command),
            user=f"{os.getuid()}:{os.getgid()}",
            network=names["network"],
            memory=req.memory,
            cpus=req.cpus,
            pids_limit=req.pids_limit,
            tmpfs=(f"/tmp:rw,nosuid,nodev,exec,size={req.tmp_size},mode=1777",),
            env=env,
            working_dir=sandbox.WORK,
            binds=tuple(binds),
            passthrough_env=tuple(sorted(req.secret_env)),
            labels={**labels, f"{RUNTIME_LABEL}.role": "driver"},
            timeout=req.timeout,
        )
        return sandbox.validate_spec(spec)


# The process-wide runtime. Tests construct their own with a fake runner.
runtime = DockerTaskRuntime()


async def sweep_orphans(session_factory, *, expire_events: bool = True) -> dict | None:
    """Remove runtime leftovers for tasks that are not running.

    Runs at startup (with ``expire_events``) and from the runner's periodic
    recovery pass (without it). The periodic pass leaves anything younger
    than :data:`PERIODIC_MIN_AGE_SECONDS` alone: a task claimed between the
    "which tasks are running" query and the docker listing would otherwise
    look orphaned.

    Best-effort and silent when docker is absent (a host without the task
    runtime has nothing to sweep).
    """
    if shutil.which("docker") is None:
        return None
    from sqlalchemy import select

    from life_graph.models.db import AgentTask

    try:
        async with session_factory() as session:
            rows = await session.execute(select(AgentTask.id).where(AgentTask.status == "running"))
            active = {str(r) for r in rows.scalars().all()}
        if expire_events:
            report = await runtime.sweep(active)
            from life_graph.services.dev import task_events

            report["events_expired"] = await task_events.expire(
                session_factory, settings.dev_task_events_retention_days
            )
        else:
            report = await runtime.sweep(active, min_age_seconds=PERIODIC_MIN_AGE_SECONDS)
    except Exception as exc:  # never block startup on cleanup
        logger.warning("task runtime sweep failed: %s", exc)
        return None
    if report["containers"] or report["networks"] or report["credentials"]:
        logger.warning("task runtime sweep removed leftovers: %s", report)
    return report
