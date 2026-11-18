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
import logging
import os
import shutil
import time
import uuid
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
POLICY_VERSION = "2026-11-18.1"

OUTBOUND_NETWORK = "lg-rt-outbound"
EGRESS_PORT = 8080
DEADLINE_BIN = "/usr/bin/timeout"
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
) -> SandboxResult:
    # sandbox._exec keeps the parent env for the docker CLI itself (it needs
    # DOCKER_HOST etc.); nothing of it reaches the container unless named.
    return await sandbox._exec(argv, timeout, container=container, env=env)


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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _missing(res: SandboxResult) -> bool:
    text = (res.stderr or "").lower()
    return "no such" in text or "not found" in text


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
            await self._create_network(names["network"], labels)
            if req.egress_allowlist:
                meta["egress_image"] = settings.driver_runtime_egress_image
                meta["egress_image_id"] = await self._image_id(settings.driver_runtime_egress_image)
                await self._start_proxy(names["proxy"], names["network"], labels, req)
            argv = sandbox.docker_run_argv(spec, detach=False)
            grace = max(5, int(settings.driver_runtime_kill_grace_seconds))
            res = await self._docker(
                argv,
                timeout=req.timeout + grace,
                container=names["container"],
                env=dict(req.secret_env) or None,
            )
            # 124: coreutils timeout fired inside the container; 137 after -k.
            if res.returncode in (124, 137) and time.monotonic() - start >= req.timeout:
                meta["timed_out"] = True
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
            # The same dict: teardown below still lands in it.
            exc.runtime_metadata = meta  # type: ignore[attr-defined]
            raise
        finally:
            meta["finished_at"] = _now()
            meta["duration_ms"] = int((time.monotonic() - start) * 1000)
            meta["teardown"] = await self.teardown(names)

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
        self, active_task_ids: set[str], *, creds_max_age_seconds: int | None = None
    ) -> dict:
        """Remove runtime leftovers whose task is not running.

        Containers and networks are found by label, never by name pattern, so
        nothing this module did not create is touched. Staged credential
        copies older than the longest possible dispatch are deleted too: a
        crash between ``stage_credentials`` and its ``finally`` leaves a live
        token on disk otherwise.
        """
        report: dict = {"containers": [], "networks": [], "credentials": 0, "errors": []}
        fmt = f'{{{{.Names}}}}|{{{{.Label "{RUNTIME_LABEL}.task"}}}}'
        res = await self._docker(
            ["docker", "ps", "-a", "--filter", f"label={RUNTIME_LABEL}=1", "--format", fmt],
            timeout=30,
        )
        if res.returncode != 0:
            report["errors"].append(f"ps: {res.stderr.strip()[-200:]}")
        for line in (res.stdout or "").splitlines():
            name, _, task = line.partition("|")
            if name and task not in active_task_ids:
                rm = await self._docker(["docker", "rm", "-f", name], timeout=30)
                if rm.returncode == 0 or _missing(rm):
                    report["containers"].append(name)
                else:
                    report["errors"].append(f"rm {name}: {rm.stderr.strip()[-200:]}")
        nfmt = f'{{{{.Name}}}}|{{{{.Label "{RUNTIME_LABEL}.task"}}}}'
        res = await self._docker(
            ["docker", "network", "ls", "--filter", f"label={RUNTIME_LABEL}=1", "--format", nfmt],
            timeout=30,
        )
        if res.returncode != 0:
            report["errors"].append(f"network ls: {res.stderr.strip()[-200:]}")
        for line in (res.stdout or "").splitlines():
            name, _, task = line.partition("|")
            if name and task not in active_task_ids:
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

    async def _create_network(self, name: str, labels: dict[str, str]) -> None:
        argv = ["docker", "network", "create", "--internal"]
        for key in sorted(labels):
            argv += ["--label", f"{key}={labels[key]}"]
        res = await self._docker([*argv, name], timeout=30)
        if res.returncode != 0:
            raise SandboxUnavailableError(f"could not create runtime network: {res.stderr[-300:]}")
        # Internal is what makes the bridge gateway-less. Checked, not assumed.
        check = await self._docker(
            ["docker", "network", "inspect", "--format", "{{.Internal}}", name], timeout=30
        )
        if check.returncode != 0 or check.stdout.strip().lower() != "true":
            raise SandboxUnavailableError(f"runtime network {name} is not internal")

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


async def sweep_orphans(session_factory) -> dict | None:
    """Startup hook: remove runtime leftovers for tasks that are not running.

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
        report = await runtime.sweep(active)
    except Exception as exc:  # never block startup on cleanup
        logger.warning("task runtime sweep failed: %s", exc)
        return None
    if report["containers"] or report["networks"] or report["credentials"]:
        logger.warning("task runtime sweep removed leftovers: %s", report)
    return report
