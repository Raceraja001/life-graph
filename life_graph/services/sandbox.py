"""Container sandbox for the verifier chain.

A verifier that runs a project's tests executes whatever code the agent just
wrote — ``conftest.py`` is arbitrary Python — and it used to do so on the
host, as the Life Graph user, with every credential that user can read. The
worktree isolation in :mod:`life_graph.drivers.workdir` separates the agent's
*files* from the live checkout; it does nothing about *execution*.

With ``LIFE_GRAPH_VERIFIER_SANDBOX=docker`` each check runs in a throwaway
container instead, in two phases:

1. **Setup** (network on). Installs the project's dependencies into a venv
   keyed by the image, the setup command and the dependency manifests. The
   worktree is mounted read-only and nothing from the host besides it is
   visible, so a malicious build backend reaches the network but no secrets.
   The venv is built under a temporary name and renamed into place only on
   success, so a half-built or concurrent setup is never reused.
2. **Check** (``--network none``). Worktree and venv both read-only, root
   filesystem read-only, all capabilities dropped, no privilege escalation,
   memory/CPU/PID limits, host uid. A read-only worktree also means test code
   cannot rewrite files after they were checked but before they are landed.

The setup command comes from the project registry
(``Project.scan_metadata["sandbox_setup"]``), never from the worktree — the
agent controls the worktree.

Anything that stops the sandbox from running is reported as
:class:`SandboxUnavailableError`, which verifiers turn into *inconclusive*: a
check that did not run is never a pass.

The second half of this module is the **errand sandbox chassis**: a
:class:`SandboxSpec` describing a container, a :func:`validate_spec` that
refuses any spec which would hand an errand a way out (a host mount, the
docker socket, privileged or host networking, anything credential-shaped in
the environment), and a :class:`SandboxManager` that starts, stops and
inspects those containers through an injectable runner. The two images it
describes live in ``Dockerfile.browser`` and ``Dockerfile.workspace``, and
``compose.sandbox.yaml`` declares the same two containers for a human to
bring up by hand; :func:`compose_violations` checks that file against the
very same policy, so the reviewed-by-hand path and the programmatic path
cannot drift apart.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from life_graph.config import settings

logger = logging.getLogger(__name__)

WORK = "/work"
VENV = "/venv"
# Where docker/claude-driver/Dockerfile installs the CLI.
DRIVER_CLI = "/usr/local/bin/claude"

# Files whose content decides what the setup phase installs.
_MANIFESTS: tuple[str, ...] = (
    "uv.lock",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
)

# Used when the project registry names no setup command. Installs
# dependencies only: the project itself is imported from /work via PYTHONPATH,
# which keeps the worktree read-only during setup.
DEFAULT_SETUP = (
    "if [ -f uv.lock ]; then uv sync --frozen --no-install-project; "
    f"elif [ -f requirements.txt ]; then uv pip install --python {VENV}/bin/python "
    "-r requirements.txt; "
    "fi"
)

# Always runs before the setup command. System site-packages keep the image's
# pytest/ruff visible as a fallback for projects that don't install their own.
_CREATE_VENV = (
    f"set -e; uv venv --quiet --allow-existing --system-site-packages "
    f"--python /usr/local/bin/python3 {VENV}; "
)

SETUP_TIMEOUT = 900

# ── Node toolchain ───────────────────────────────────────────
#
# A project whose registry sets ``sandbox_toolchain: node`` is checked in the
# Node image instead. Its dependencies cannot go in /work/node_modules (the
# worktree is mounted read-only, by design), so setup installs them into a
# cached directory, and checks mount that at /node_modules: Node's module
# resolution walks up from /work to /, so `import "vitest"` in /work/tests
# finds /node_modules/vitest with no config at all.
NODE_DEPS = "/node_modules"
_NODE_MANIFESTS: tuple[str, ...] = (
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
)
# Runs in the cache directory after the manifests are copied there. npm only:
# a pnpm/yarn lockfile falls back to `npm install` from package.json.
NODE_DEFAULT_SETUP = (
    "if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; "
    "then npm ci --no-audit --no-fund --loglevel=error; "
    "else npm install --no-audit --no-fund --loglevel=error; fi"
)


def node_toolchain(ctx: dict) -> bool:
    """Whether the project registry put this project on the Node toolchain."""
    return (ctx.get("sandbox_toolchain") or "").strip().lower() == "node"


# ── JVM toolchain (Gradle: Kotlin, Java, Android) ────────────
#
# A project whose registry sets ``sandbox_toolchain: jvm`` is checked in the
# JVM image. Setup (network on) runs the project's Gradle wrapper on a copy of
# the worktree with a cached Gradle home: the wrapper downloads Gradle, an init
# script of ours resolves every configuration, and the build files are
# compiled. It never runs the tests — test code never sees the network. Checks
# (network off) mount that home read-only, read dependencies through
# GRADLE_RO_DEP_CACHE, and run Gradle from the cached distribution, offline, on
# a copy of the worktree under /tmp (Gradle writes build/ next to the code).
GRADLE_RO = "/gradle-ro"
_GRADLE_MANIFESTS: tuple[str, ...] = (
    "settings.gradle.kts",
    "settings.gradle",
    "build.gradle.kts",
    "build.gradle",
    "app/build.gradle.kts",
    "app/build.gradle",
    "gradle.properties",
    "gradle/libs.versions.toml",
    "gradle/wrapper/gradle-wrapper.properties",
)
# Resolves every resolvable configuration of every project, so the offline
# check finds each dependency in the cache. Ours, not the worktree's.
_GRADLE_RESOLVE_ALL = """\
allprojects {
    tasks.register("lgResolveAll") {
        doLast {
            configurations.findAll { it.canBeResolved }.each { c ->
                try { c.resolve() } catch (Exception ignored) { }
            }
        }
    }
}
"""
# Bump when the setup recipe below changes (it is part of the cache key).
_GRADLE_SETUP_VERSION = "3"
# Kotlin's compiler daemon is a separate process the sandbox cannot keep.
_GRADLE_FLAGS = "--no-daemon --console=plain -Pkotlin.compiler.execution.strategy=in-process"
_GRADLE_JVMARGS = "-Dorg.gradle.jvmargs=-Xmx2g"
# The Android plugin writes ~/.android and Java reads user.home from the
# image's passwd (/home/ubuntu, read-only here): both go to the writable /tmp.
_JVM_HOME_ENV = (
    "-e",
    "ANDROID_USER_HOME=/tmp/.android",
    "-e",
    "JAVA_TOOL_OPTIONS=-Duser.home=/tmp",
)
# What runs `gradle` in a check: the distribution the setup downloaded.
_GRADLE_BIN = f"$(ls -d {GRADLE_RO}/wrapper/dists/*/*/gradle-*/bin/gradle | head -1)"


def jvm_toolchain(ctx: dict) -> bool:
    """Whether the project registry put this project on the JVM (Gradle) toolchain."""
    return (ctx.get("sandbox_toolchain") or "").strip().lower() == "jvm"


def _is_android(workdir: Path) -> bool:
    """An Android build: the plugin by id, or through the version catalogue
    (``alias(libs.plugins.android.application)``, which names no id)."""
    markers = ("com.android", "plugins.android.", "plugins.android.application")
    for name in ("app/build.gradle.kts", "app/build.gradle", "build.gradle.kts", "build.gradle"):
        f = workdir / name
        if f.is_file() and not f.is_symlink():
            text = f.read_text(errors="replace")
            if any(m in text for m in markers):
                return True
    return False


class SandboxUnavailableError(Exception):
    """The sandbox could not run the check. The message explains why."""


@dataclass
class SandboxResult:
    """Outcome of a command run inside the sandbox."""

    returncode: int
    stdout: str
    stderr: str


def enabled() -> bool:
    return settings.verifier_sandbox == "docker"


def driver_sandbox_enabled() -> bool:
    return settings.driver_claude_sandbox == "docker"


def _cache_root() -> Path:
    raw = settings.verifier_sandbox_cache_dir or "~/.cache/life-graph/verifier-envs"
    return Path(raw).expanduser()


def _limits(*, memory: str, cpus: str) -> list[str]:
    return [
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "512",
        "--memory",
        memory,
        "--cpus",
        cpus,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
    ]


async def _exec(
    argv: list[str], timeout: int, container: str | None = None, env: dict | None = None
) -> SandboxResult:
    """Run a docker CLI command, killing the container itself on timeout.

    Killing the ``docker run`` client does not stop the container it started,
    so a timed-out check would keep running unattended without the explicit
    ``docker kill``.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Extra variables for the docker CLI itself (e.g. a key passed to
            # the container by name); the parent environment is kept.
            env={**os.environ, **env} if env else None,
        )
    except FileNotFoundError as exc:
        raise SandboxUnavailableError("docker CLI not found") from exc
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        if container:
            killer = await asyncio.create_subprocess_exec(
                "docker",
                "kill",
                container,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        proc.kill()
        await proc.communicate()
        raise SandboxUnavailableError(f"sandboxed command timed out after {timeout}s") from None
    return SandboxResult(
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=out.decode("utf-8", errors="replace"),
        stderr=err.decode("utf-8", errors="replace"),
    )


async def _image_id() -> str:
    image = settings.verifier_sandbox_image
    res = await _exec(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
    if res.returncode != 0:
        raise SandboxUnavailableError(
            f"sandbox image {image!r} not available — build it with "
            f"`docker build -t {image} docker/verifier`"
        )
    return res.stdout.strip()


def _env_key(
    workdir: Path, image_id: str, setup: str, manifests: tuple[str, ...] = _MANIFESTS
) -> str:
    h = hashlib.sha256()
    h.update(image_id.encode())
    h.update(b"\0" + setup.encode())
    for name in manifests:
        f = workdir / name
        h.update(b"\0" + name.encode() + b"\0")
        if f.is_file() and not f.is_symlink():
            h.update(f.read_bytes())
    return h.hexdigest()[:24]


_setup_locks: dict[str, asyncio.Lock] = {}


async def prepare_env(workdir: Path, setup: str | None = None) -> Path:
    """Return a host directory holding the project's venv, building it if needed.

    Raises:
        SandboxUnavailableError: docker or the image is missing, or setup failed.
    """
    image_id = await _image_id()
    command = setup or DEFAULT_SETUP
    key = _env_key(workdir, image_id, command)
    root = _cache_root()
    ready = root / key

    lock = _setup_locks.setdefault(key, asyncio.Lock())
    async with lock:
        if ready.is_dir():
            return ready

        root.mkdir(parents=True, exist_ok=True)
        partial = root / f"{key}.partial-{uuid.uuid4().hex[:8]}"
        partial.mkdir()
        (partial / ".uv-cache").mkdir()
        container = f"lg-verify-setup-{uuid.uuid4().hex[:12]}"
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            container,
            *_limits(memory=settings.verifier_sandbox_memory, cpus=settings.verifier_sandbox_cpus),
            "-e",
            "HOME=/tmp",
            "-e",
            f"UV_CACHE_DIR={VENV}/.uv-cache",
            "-e",
            "UV_LINK_MODE=copy",
            "-e",
            f"UV_PROJECT_ENVIRONMENT={VENV}",
            "-e",
            "UV_PYTHON_DOWNLOADS=never",
            "-v",
            f"{workdir}:{WORK}:ro",
            "-v",
            f"{partial}:{VENV}",
            "-w",
            WORK,
            "--entrypoint",
            "sh",
            settings.verifier_sandbox_image,
            "-c",
            _CREATE_VENV + command,
        ]
        try:
            res = await _exec(argv, timeout=SETUP_TIMEOUT, container=container)
            if res.returncode != 0:
                raise SandboxUnavailableError(
                    f"sandbox setup failed (exit {res.returncode}): "
                    f"{(res.stderr or res.stdout)[-800:]}"
                )
            shutil.rmtree(partial / ".uv-cache", ignore_errors=True)
            try:
                partial.rename(ready)
            except OSError:
                # Another process finished the same env first; use theirs.
                shutil.rmtree(partial, ignore_errors=True)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
    return ready


async def _node_image_id() -> str:
    image = settings.verifier_sandbox_node_image
    res = await _exec(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
    if res.returncode != 0:
        raise SandboxUnavailableError(
            f"node sandbox image {image!r} not available — build it with "
            f"`docker build -t {image} docker/verifier-node`"
        )
    return res.stdout.strip()


async def prepare_node_env(workdir: Path, setup: str | None = None) -> Path:
    """Return a host directory holding the project's ``node_modules``, installing if needed.

    The manifests are copied out of the read-only worktree into the cache
    directory and installed there, with network (setup is the only phase that
    has it). Keyed by image, setup command and manifest contents, like the
    Python venv cache.

    Raises:
        SandboxUnavailableError: docker or the image is missing, no
            package.json, or the install failed.
    """
    if not (workdir / "package.json").is_file() or (workdir / "package.json").is_symlink():
        raise SandboxUnavailableError("node toolchain, but the project has no package.json")
    image_id = await _node_image_id()
    command = setup or NODE_DEFAULT_SETUP
    key = "node-" + _env_key(workdir, image_id, command, _NODE_MANIFESTS)
    root = _cache_root()
    ready = root / key

    lock = _setup_locks.setdefault(key, asyncio.Lock())
    async with lock:
        if (ready / "node_modules").is_dir():
            return ready
        root.mkdir(parents=True, exist_ok=True)
        partial = root / f"{key}.partial-{uuid.uuid4().hex[:8]}"
        partial.mkdir()
        container = f"lg-verify-node-setup-{uuid.uuid4().hex[:12]}"
        copy = " ".join(
            f"if [ -f {WORK}/{m} ] && [ ! -L {WORK}/{m} ]; then cp {WORK}/{m} /deps/; fi;"
            for m in _NODE_MANIFESTS
        )
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            container,
            *_limits(memory=settings.verifier_sandbox_memory, cpus=settings.verifier_sandbox_cpus),
            "-e",
            "HOME=/tmp",
            "-e",
            "npm_config_cache=/tmp/.npm",
            "-e",
            "npm_config_update_notifier=false",
            "-v",
            f"{workdir}:{WORK}:ro",
            "-v",
            f"{partial}:/deps",
            "-w",
            "/deps",
            "--entrypoint",
            "sh",
            settings.verifier_sandbox_node_image,
            "-c",
            f"set -e; {copy} {command}",
        ]
        try:
            res = await _exec(argv, timeout=SETUP_TIMEOUT, container=container)
            if res.returncode != 0 or not (partial / "node_modules").is_dir():
                raise SandboxUnavailableError(
                    f"node sandbox setup failed (exit {res.returncode}): "
                    f"{(res.stderr or res.stdout)[-800:]}"
                )
            try:
                partial.rename(ready)
            except OSError:
                shutil.rmtree(partial, ignore_errors=True)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
    return ready


async def _jvm_image_id() -> str:
    image = settings.verifier_sandbox_jvm_image
    res = await _exec(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
    if res.returncode != 0:
        raise SandboxUnavailableError(
            f"jvm sandbox image {image!r} not available — build it with "
            f"`docker build -t {image} docker/verifier-jvm`"
        )
    return res.stdout.strip()


async def prepare_gradle_env(workdir: Path, setup: str | None = None) -> Path:
    """Return a host directory holding a Gradle home with the project's
    distribution and dependencies, filling it if needed.

    Two Gradle runs: first our init script resolves every configuration (on
    its own, so nothing else can stop it: Gradle rejects a whole command line
    for one unknown task name); then *setup* — the registry's
    ``sandbox_setup``, by default the unit tests' compile
    (``compileDebugUnitTestKotlin`` for Android, ``testClasses`` otherwise) —
    which fetches what resolving alone does not (aapt2). A failing compile
    does not fail setup — the check reports it — but a wrapper that
    downloaded nothing does.

    Raises:
        SandboxUnavailableError: docker or the image is missing, no Gradle
            wrapper, or the wrapper could not fetch Gradle.
    """
    wrapper = workdir / "gradlew"
    if not wrapper.is_file() or wrapper.is_symlink():
        raise SandboxUnavailableError("jvm toolchain, but the project has no gradlew wrapper")
    image_id = await _jvm_image_id()
    tasks = setup or ("compileDebugUnitTestKotlin" if _is_android(workdir) else "testClasses")
    # The recipe version is in the key: a changed recipe never reuses a home
    # an older one filled (the first one reused an empty, failed setup).
    key = "jvm-" + _env_key(
        workdir, image_id, f"{_GRADLE_SETUP_VERSION}\0{tasks}", _GRADLE_MANIFESTS
    )
    root = _cache_root()
    ready = root / key

    lock = _setup_locks.setdefault(key, asyncio.Lock())
    async with lock:
        if (ready / "wrapper" / "dists").is_dir():
            return ready
        root.mkdir(parents=True, exist_ok=True)
        partial = root / f"{key}.partial-{uuid.uuid4().hex[:8]}"
        partial.mkdir()
        (partial / "lg-resolve.gradle").write_text(_GRADLE_RESOLVE_ALL)
        container = f"lg-verify-jvm-setup-{uuid.uuid4().hex[:12]}"
        gradle = f"./gradlew {_GRADLE_FLAGS} {_GRADLE_JVMARGS}"
        script = (
            f"cp -a {WORK}/. /tmp/work/ && cd /tmp/work && rm -f local.properties && chmod +x gradlew && "
            f"{gradle} -I /gradle/lg-resolve.gradle lgResolveAll; "
            f"{gradle} --continue {tasks}; "
            "ls -d /gradle/wrapper/dists/*/*/gradle-* >/dev/null"
        )
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            container,
            *_limits(
                memory=settings.verifier_sandbox_jvm_memory, cpus=settings.verifier_sandbox_cpus
            ),
            "--tmpfs",
            "/tmp:rw,exec,size=4g",
            "-e",
            "HOME=/tmp",
            "-e",
            "GRADLE_USER_HOME=/gradle",
            *_JVM_HOME_ENV,
            "-v",
            f"{workdir}:{WORK}:ro",
            "-v",
            f"{partial}:/gradle",
            "--entrypoint",
            "sh",
            settings.verifier_sandbox_jvm_image,
            "-c",
            script,
        ]
        try:
            res = await _exec(argv, timeout=SETUP_TIMEOUT, container=container)
            if res.returncode != 0 or not (partial / "wrapper" / "dists").is_dir():
                raise SandboxUnavailableError(
                    f"jvm sandbox setup failed (exit {res.returncode}): "
                    f"{(res.stderr or res.stdout)[-800:]}"
                )
            try:
                partial.rename(ready)
            except OSError:
                shutil.rmtree(partial, ignore_errors=True)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
    return ready


def gradle_tasks(command: str | None, default: str = "test") -> list[str]:
    """The Gradle arguments of a registry test command: "./gradlew test" and
    "gradle test" both mean ``["test"]`` (the check runs Gradle itself)."""
    import shlex

    argv = shlex.split(command) if command else []
    if argv and argv[0] in ("./gradlew", "gradlew", "gradle"):
        argv = argv[1:]
    return argv or [default]


async def _driver_image_id() -> str:
    image = settings.driver_claude_sandbox_image
    res = await _exec(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
    if res.returncode != 0:
        raise SandboxUnavailableError(
            f"claude_code sandbox image {image!r} not available — build it with "
            "docker/claude-driver/build.sh"
        )
    return res.stdout.strip()


async def run_driver(
    argv: list[str],
    workdir: Path,
    credentials_dir: Path | None,
    *,
    timeout: int = 300,
    api_key: str | None = None,
) -> SandboxResult:
    """Run the claude_code driver's CLI invocation inside a container.

    Unlike :func:`run` (the verifier's read-only, network-denied check
    phase) this is the OPPOSITE on both axes: *workdir* is mounted
    read-write — the driver's job is to edit it — and the network stays on,
    since the CLI is an API-backed tool. What's contained instead:

    - filesystem: only *workdir* and *credentials_dir* are visible from the
      host; root filesystem is read-only with a tmpfs /tmp scratch.
    - credentials: *credentials_dir* should hold a throwaway copy of just
      the OAuth token (see :func:`stage_credentials`), never the live
      ``~/.claude`` — that directory also carries session history and other
      projects' context that has no business inside this container.
      Mounted read-write (not ``:ro``): confirmed by hand that the CLI
      refreshes its own access token from the refresh token and writes the
      result back before using it — a read-only mount left it using a
      stale access token and failing every call with a 401. Since this is
      always the throwaway copy, not the live file, that write has nothing
      to corrupt.
    - capabilities/resources: same caps-dropped, no-new-privileges,
      pids/memory/cpu limits as the verifier sandbox, and the container
      runs as the host uid so files it writes land owned correctly for the
      host-side landing commit that follows.

    Raises:
        SandboxUnavailableError: docker, the image, or the container itself
            could not run, or the timeout was hit.
    """
    await _driver_image_id()
    container = f"lg-driver-{uuid.uuid4().hex[:12]}"
    if api_key:
        # Commercial mode: an API key, never the personal login. Passed by
        # NAME (-e VAR, value from the docker client's environment), so the
        # key never appears in a process listing the way -e VAR=value would.
        auth = ["-e", "ANTHROPIC_API_KEY", "-e", "CLAUDE_CONFIG_DIR=/tmp/.claude"]
        client_env = {"ANTHROPIC_API_KEY": api_key}
    else:
        if credentials_dir is None:
            raise SandboxUnavailableError("claude_code sandbox needs credentials or an API key")
        # rw, not :ro: the CLI refreshes its own access token in place from
        # the refresh token and needs to write the result back — this is
        # still only the throwaway copy from stage_credentials(), never the
        # live ~/.claude, so a write here has nothing to corrupt.
        auth = [
            "-e",
            "CLAUDE_CONFIG_DIR=/claude-config",
            "-v",
            f"{credentials_dir}:/claude-config",
        ]
        client_env = None
    docker_argv = [
        "docker",
        "run",
        "--rm",
        "--name",
        container,
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,size=512m",
        *_limits(
            memory=settings.driver_claude_sandbox_memory, cpus=settings.driver_claude_sandbox_cpus
        ),
        "-e",
        "HOME=/tmp",
        *auth,
        "-v",
        f"{workdir}:{WORK}",
        "-w",
        WORK,
        # The image's own binary, not argv[0]: argv[0] is the host's
        # configured path (driver_claude_code_bin, e.g. ~/.local/bin/claude),
        # which does not exist inside the container.
        "--entrypoint",
        DRIVER_CLI,
        settings.driver_claude_sandbox_image,
        *argv[1:],
    ]
    res = await _exec(docker_argv, timeout=timeout, container=container, env=client_env)
    if res.returncode in (125, 126, 127) and not res.stdout:
        raise SandboxUnavailableError(
            f"claude_code sandbox could not start: {res.stderr.strip()[-400:]}"
        )
    return res


async def stage_credentials(source: Path) -> Path:
    """Copy the CLI's OAuth token into a fresh throwaway directory.

    *source* is the real ``~/.claude/.credentials.json``. The container gets
    only this copy — never a mount of the live ``~/.claude`` — and the
    caller MUST remove the returned directory once the dispatch finishes
    (success or failure): it holds a live, usable credential.

    Raises:
        SandboxUnavailableError: no credentials file to stage — the driver
            would otherwise run unauthenticated, which is not a sandboxing
            concern to swallow silently.
    """
    if not source.is_file():
        raise SandboxUnavailableError(f"no claude CLI credentials at {source}")
    staged = _cache_root().parent / "driver-creds" / uuid.uuid4().hex
    staged.mkdir(parents=True)
    shutil.copy2(source, staged / ".credentials.json")
    os.chmod(staged / ".credentials.json", 0o600)
    return staged


async def run(
    argv: list[str],
    workdir: Path,
    *,
    venv: Path | None = None,
    node_deps: Path | None = None,
    gradle_home: Path | None = None,
    timeout: int = 120,
    extra_ro: dict[Path, str] | None = None,
    tmp_size: str | None = None,
) -> SandboxResult:
    """Run *argv* in the check-phase sandbox with *workdir* mounted at ``/work``.

    *extra_ro* mounts more host directories read-only (host path -> container
    path), e.g. the generated mutants of the mutation check; *tmp_size* raises
    the /tmp tmpfs for a check that copies the project there.

    Arguments that are paths must be relative to *workdir* (or under ``/work``):
    host paths do not exist inside the container. With *node_deps* (from
    :func:`prepare_node_env`) the Node image runs instead, with those
    dependencies at /node_modules and their binaries on PATH. With
    *gradle_home* (from :func:`prepare_gradle_env`) the JVM image runs and
    *argv* is Gradle's arguments (e.g. ``["test"]``): Gradle runs offline from
    the cached distribution, reading dependencies read-only.

    Raises:
        SandboxUnavailableError: the container could not run or timed out.
    """
    path = "/usr/local/bin:/usr/bin:/bin"
    image = settings.verifier_sandbox_image
    mounts = ["-v", f"{workdir}:{WORK}:ro"]
    if venv is not None:
        mounts += ["-v", f"{venv}:{VENV}:ro"]
        path = f"{VENV}/bin:{path}"
    for host, inside in (extra_ro or {}).items():
        mounts += ["-v", f"{host}:{inside}:ro"]
    entry, args = argv[0], argv[1:]
    tmp_size = tmp_size or "512m"
    if node_deps is not None:
        mounts += ["-v", f"{node_deps / 'node_modules'}:{NODE_DEPS}:ro"]
        path = f"{NODE_DEPS}/.bin:{path}"
        image = settings.verifier_sandbox_node_image
        # Node tooling writes next to the project: vitest's results cache and
        # Vite's cache under ./node_modules, jest's cache, Next's .next. The
        # worktree mount stays read-only, so the check runs in a throwaway
        # copy under /tmp instead. Resolution still walks up to /node_modules.
        entry, args, tmp_size = (
            "sh",
            ["-c", 'cp -a /work/. /tmp/work/ && cd /tmp/work && exec "$@"', "sh", *argv],
            "2g",
        )
    env: list[str] = []
    memory = settings.verifier_sandbox_memory
    if gradle_home is not None:
        mounts += ["-v", f"{gradle_home}:{GRADLE_RO}:ro"]
        image = settings.verifier_sandbox_jvm_image
        memory = settings.verifier_sandbox_jvm_memory
        # A writable Gradle home of its own; dependencies come read-only from
        # the setup's cache, so a test run cannot poison it for the next one.
        env = [
            "-e",
            "GRADLE_USER_HOME=/tmp/gradle",
            "-e",
            f"GRADLE_RO_DEP_CACHE={GRADLE_RO}/caches",
            *_JVM_HOME_ENV,
        ]
        entry, args, tmp_size = (
            "sh",
            [
                "-c",
                "cp -a /work/. /tmp/work/ && cd /tmp/work && rm -f local.properties && "
                f'exec {_GRADLE_BIN} --offline {_GRADLE_FLAGS} {_GRADLE_JVMARGS} "$@"',
                "sh",
                *argv,
            ],
            "3g",
        )
    container = f"lg-verify-{uuid.uuid4().hex[:12]}"
    docker_argv = [
        "docker",
        "run",
        "--rm",
        "--name",
        container,
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,exec,size={tmp_size}",
        *_limits(memory=memory, cpus=settings.verifier_sandbox_cpus),
        "-e",
        "HOME=/tmp",
        *env,
        "-e",
        f"PATH={path}",
        "-e",
        f"PYTHONPATH={WORK}:{WORK}/src",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        *mounts,
        "-w",
        WORK,
        "--entrypoint",
        entry,
        image,
        *args,
    ]
    res = await _exec(docker_argv, timeout=timeout, container=container)
    # 125: docker itself failed (bad flag, daemon down); 126/127: entrypoint
    # missing. None of these say anything about the agent's code.
    if res.returncode in (125, 126, 127) and not res.stdout:
        raise SandboxUnavailableError(f"sandbox could not start: {res.stderr.strip()[-400:]}")
    return res


# ── Errand sandbox chassis ───────────────────────────────────
# Everything below is about containers that run *errands* (a browser session,
# a scratch shell), not verifier checks. It is deliberately pure Python: a
# spec is built and validated without docker being installed, so the policy
# is testable and is checked before anything is started.

SANDBOX_COMPOSE_FILE = "compose.sandbox.yaml"
SANDBOX_NETWORK = "life_graph_sandbox_internal"
BROWSER_IMAGE = "life-graph-sandbox-browser:dev"
WORKSPACE_IMAGE = "life-graph-sandbox-workspace:dev"
BROWSER_WS_PORT = 9222
WORKSPACE_DIR = "/work"
SANDBOX_LABEL = "life-graph.sandbox"

# Variables prefixed this way are the application's own configuration. None
# of it belongs in a sandbox, secret or not: a sandbox that knows the
# database URL is a sandbox that can be asked to reach it.
APP_ENV_PREFIX = "LIFE_GRAPH_"

# Names that are credential-shaped. Matched as substrings, case-insensitively,
# so KEY/MY_KEY/api_key_2 all land. False positives (a legitimate variable
# with "key" in the name) are the intended bias: the fix is to rename it or
# not to pass it.
_SECRET_NAME = re.compile(
    r"key|secret|token|password|passwd|credential|cookie|private|auth|session",
    re.I,
)

# Values that look like a provider key even if the variable is named
# innocently. Prefix-anchored to the issuing provider's own format.
_KEY_SHAPED = re.compile(
    r"^(sk-|sk_live_|sk_test_|xox[bpas]-|ghp_|gho_|github_pat_|hf_|AIza|AKIA|glpat-|"
    r"nvapi-|gsk_|tvly-|or-v1-|Bearer\s)",
)

# A container runtime socket under any of its usual names. Handing this in is
# equivalent to handing over root on the host.
_RUNTIME_SOCKET = re.compile(
    r"(docker|podman|containerd|crio)[^\s:]*\.sock|/run/(docker|podman)", re.I
)

# Anything a container runtime would read as a path on the host, rather than
# as the name of a managed volume.
_HOST_PATH = re.compile(r"^\s*(/|~|\.{1,2}/|\$|[A-Za-z]:[\\/]|\\\\)")

_DOCKER_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")

# network_mode values that defeat the point: the host's own stack, or the
# default bridge, which has a route off the machine.
_HOST_NETWORK_MODES = ("host", "bridge", "default")

_MEMORY_LIMIT = re.compile(r"^\d+(\.\d+)?[bkmgKMG]?$")

# security_opt values that switch a protection off rather than on.
_UNCONFINED = re.compile(r"unconfined|:unconfined|=unconfined", re.I)

# A configured value shorter than this is ignored when matching the
# environment against settings: an empty or placeholder setting would
# otherwise make every spec invalid.
_MIN_SECRET_LEN = 8


class SandboxPolicyError(ValueError):
    """A sandbox spec (or ``compose.sandbox.yaml``) breaks an isolation rule.

    Carries every violation found, not just the first: a half-fixed spec that
    passes on the second attempt is worse than a spec that reports all of it
    at once.
    """

    def __init__(self, target: str, violations: list[str]) -> None:
        self.target = target
        self.violations = list(violations)
        super().__init__(f"{target}: " + "; ".join(self.violations))


@dataclass(frozen=True)
class SandboxSpec:
    """A container an errand may run in, plus every restriction it runs under.

    The defaults are the safe ones — a bare ``SandboxSpec(name=..., image=...)``
    already passes :func:`validate_spec`. Loosening a field is what takes a
    deliberate argument, which is the direction the asymmetry should run.

    ``mounts`` takes docker ``-v`` arguments for *named volumes only*
    (``cache:/cache:ro``); anything that reads as a host path is rejected.
    Writable space normally comes from ``tmpfs`` instead, so the sandbox
    leaves nothing behind.
    """

    name: str
    image: str
    role: str = "workspace"
    command: tuple[str, ...] = ()
    entrypoint: str | None = None
    # nobody:nogroup. Never 0; validated below.
    user: str = "65534:65534"
    network: str = SANDBOX_NETWORK
    network_mode: str | None = None
    privileged: bool = False
    read_only_root: bool = True
    cap_drop: tuple[str, ...] = ("ALL",)
    cap_add: tuple[str, ...] = ()
    security_opt: tuple[str, ...] = ("no-new-privileges:true",)
    pids_limit: int = 128
    memory: str = "512m"
    cpus: str = "0.5"
    tmpfs: tuple[str, ...] = ("/tmp:rw,nosuid,nodev,size=256m,mode=1777",)
    mounts: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    working_dir: str = WORKSPACE_DIR
    # Wall-clock ceiling for the docker CLI calls this spec produces.
    timeout: int = 120


def _settings_secret_values() -> set[str]:
    """Every credential-shaped value currently configured on the app.

    Read straight off :class:`~life_graph.config.Settings` by field name
    rather than from a hand-kept list, so a provider added to ``config.py``
    tomorrow is covered without anyone remembering to update this module.
    """
    found: set[str] = set()
    for name in type(settings).model_fields:
        if not _SECRET_NAME.search(name):
            continue
        value = getattr(settings, name, None)
        if not isinstance(value, str):
            continue
        # service_api_keys is a comma-separated list; each element counts.
        for part in value.split(","):
            part = part.strip()
            if len(part) >= _MIN_SECRET_LEN:
                found.add(part)
    return found


def _env_violations(env: dict[str, str]) -> list[str]:
    bad: list[str] = []
    secrets = _settings_secret_values()
    for raw_name, raw_value in env.items():
        name = str(raw_name)
        value = "" if raw_value is None else str(raw_value)
        if not name or "=" in name or name != name.strip():
            bad.append(f"env {name!r} is not a usable variable name")
        if name.upper().startswith(APP_ENV_PREFIX):
            bad.append(f"env {name} passes app configuration into the sandbox")
        if _SECRET_NAME.search(name):
            bad.append(f"env {name} is credential-shaped")
        if _KEY_SHAPED.search(value):
            bad.append(f"env {name} holds a value shaped like a provider key")
        if value.strip() and value.strip() in secrets:
            bad.append(f"env {name} holds a configured credential from settings")
        if _RUNTIME_SOCKET.search(value):
            bad.append(f"env {name} points at a container runtime socket")
        if "\n" in value or "\x00" in value:
            bad.append(f"env {name} holds a newline or NUL")
    return bad


def spec_violations(spec: SandboxSpec) -> list[str]:
    """Every isolation rule *spec* breaks, as readable sentences. Empty = clean."""
    bad: list[str] = []

    if not _DOCKER_NAME.match(spec.name or ""):
        bad.append(f"name {spec.name!r} is not a safe container name")
    if not spec.image or spec.image.startswith("-"):
        bad.append(f"image {spec.image!r} is empty or reads as a CLI flag")
    if _RUNTIME_SOCKET.search(spec.image):
        bad.append("image name mentions a container runtime socket")

    # ── The ways out ──
    if spec.privileged:
        bad.append("privileged mode is never allowed")
    # "none" is stricter than ours (no network at all) and allowed; every
    # other network_mode borrows a stack that is not the internal bridge.
    mode = (spec.network_mode or "").strip().lower()
    if mode in _HOST_NETWORK_MODES or mode.startswith(("container:", "service:")):
        bad.append(f"network_mode {spec.network_mode!r} leaves the internal sandbox network")
    elif mode and mode != "none":
        bad.append(f"network_mode {spec.network_mode!r} is not the internal sandbox network")
    if mode != "none" and spec.network != SANDBOX_NETWORK:
        bad.append(
            f"network {spec.network!r} is not the internal sandbox network {SANDBOX_NETWORK}"
        )

    for mount in spec.mounts:
        text = str(mount)
        if _RUNTIME_SOCKET.search(text):
            bad.append(f"mount {text!r} exposes a container runtime socket")
        elif _HOST_PATH.match(text):
            bad.append(f"mount {text!r} binds a host path into the sandbox")
        elif ":" not in text:
            bad.append(f"mount {text!r} is an anonymous volume, not a named one")

    for entry in spec.tmpfs:
        target = str(entry).split(":", 1)[0]
        if not target.startswith("/") or target == "/":
            bad.append(f"tmpfs {entry!r} must target an absolute path below /")
        if "suid" in str(entry) and "nosuid" not in str(entry):
            bad.append(f"tmpfs {entry!r} allows setuid binaries")

    # ── The restrictions that must stay on ──
    if not spec.read_only_root:
        bad.append("root filesystem must be read-only")
    if "ALL" not in {c.upper() for c in spec.cap_drop}:
        bad.append("capabilities must be dropped with cap_drop ALL")
    if spec.cap_add:
        bad.append(f"capabilities added back: {', '.join(spec.cap_add)}")
    if "no-new-privileges:true" not in {str(o).lower() for o in spec.security_opt}:
        bad.append("security_opt must include no-new-privileges:true")
    for opt in spec.security_opt:
        if _UNCONFINED.search(str(opt)):
            bad.append(f"security_opt {opt!r} switches a protection off")
    if spec.user.split(":")[0] in ("", "0", "root"):
        bad.append(f"user {spec.user!r} would run as root")

    # ── The ceilings ──
    if not isinstance(spec.pids_limit, int) or not 0 < spec.pids_limit <= 4096:
        bad.append(f"pids_limit {spec.pids_limit!r} must be between 1 and 4096")
    if not _MEMORY_LIMIT.match(str(spec.memory or "")):
        bad.append(f"memory {spec.memory!r} is not a docker memory limit")
    try:
        if not 0 < float(spec.cpus) <= 8:
            raise ValueError
    except (TypeError, ValueError):
        bad.append(f"cpus {spec.cpus!r} must be a share between 0 and 8")

    bad.extend(_env_violations(spec.env))
    return bad


def validate_spec(spec: SandboxSpec) -> SandboxSpec:
    """Return *spec* unchanged, or raise :class:`SandboxPolicyError`.

    Called by every builder below and again by :meth:`SandboxManager.start`,
    because a spec can be edited after it was built.
    """
    violations = spec_violations(spec)
    if violations:
        raise SandboxPolicyError(f"sandbox spec {spec.name!r}", violations)
    return spec


def browser_spec(
    name: str | None = None,
    *,
    port: int = BROWSER_WS_PORT,
    memory: str = "1g",
    cpus: str = "1.0",
    image: str = BROWSER_IMAGE,
) -> SandboxSpec:
    """A headless-Chromium sandbox, driven from outside over Playwright's
    browser-server protocol (``chromium.connect("ws://<name>:9222/")``).

    The port is only reachable on the internal network — nothing is published
    to the host, because a browser control endpoint is remote code execution
    on the browser.
    """
    return validate_spec(
        SandboxSpec(
            name=name or f"lg-sbx-browser-{uuid.uuid4().hex[:8]}",
            image=image,
            role="browser",
            user="1000:1000",  # pwuser, from the Playwright base image
            memory=memory,
            cpus=cpus,
            pids_limit=512,
            tmpfs=(
                "/tmp:rw,nosuid,nodev,size=512m,mode=1777",
                "/dev/shm:rw,nosuid,nodev,size=256m,mode=1777",
            ),
            env={
                "HOME": "/tmp",
                "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
                "SANDBOX_BROWSER_PORT": str(port),
                "SANDBOX_ROLE": "browser",
                "TZ": "UTC",
            },
            working_dir="/tmp",
        )
    )


def workspace_spec(
    name: str | None = None,
    *,
    command: tuple[str, ...] = ("sleep", "infinity"),
    memory: str = "512m",
    cpus: str = "0.5",
    image: str = WORKSPACE_IMAGE,
    browser: str | None = None,
) -> SandboxSpec:
    """A minimal scratch box. With *browser* (a container name), it is told
    where that browser's endpoint answers — a location, not a credential."""
    uid = 65534  # nobody; owns nothing in the image and nothing on the host
    env = {
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
        "SANDBOX_ROLE": "workspace",
        "TZ": "UTC",
    }
    if browser:
        env["SANDBOX_BROWSER_WS_URL"] = f"ws://{browser}:{BROWSER_WS_PORT}/"
    return validate_spec(
        SandboxSpec(
            name=name or f"lg-sbx-workspace-{uuid.uuid4().hex[:8]}",
            image=image,
            role="workspace",
            command=command,
            user=f"{uid}:{uid}",
            memory=memory,
            cpus=cpus,
            tmpfs=(
                # A tmpfs is root-owned 0755 unless told otherwise, which
                # would leave the non-root user unable to write to its own
                # work directory.
                f"/work:rw,nosuid,nodev,noexec,size=256m,uid={uid},gid={uid},mode=0700",
                "/tmp:rw,nosuid,nodev,size=256m,mode=1777",
            ),
            env=env,
        )
    )


def docker_run_argv(spec: SandboxSpec, *, detach: bool = True) -> list[str]:
    """The ``docker run`` argv for *spec*, validated first.

    With *detach* the container outlives the call and the manager removes it;
    otherwise ``--rm`` cleans up when the command exits. Detached containers
    are not auto-removed so that a crashed errand can still be inspected.
    """
    validate_spec(spec)
    argv = [
        "docker",
        "run",
        "--name",
        spec.name,
        "--init",
        "--label",
        f"{SANDBOX_LABEL}=1",
        "--label",
        f"{SANDBOX_LABEL}.role={spec.role}",
    ]
    argv.append("--detach" if detach else "--rm")
    argv += ["--network", "none" if spec.network_mode == "none" else spec.network]
    if spec.read_only_root:
        argv.append("--read-only")
    for cap in spec.cap_drop:
        argv += ["--cap-drop", cap]
    for opt in spec.security_opt:
        argv += ["--security-opt", opt]
    argv += [
        "--pids-limit",
        str(spec.pids_limit),
        "--memory",
        spec.memory,
        # Equal to --memory: no swap, so the ceiling is a real ceiling.
        "--memory-swap",
        spec.memory,
        "--cpus",
        spec.cpus,
        "--user",
        spec.user,
    ]
    for entry in spec.tmpfs:
        argv += ["--tmpfs", entry]
    for mount in spec.mounts:
        argv += ["-v", mount]
    for key in sorted(spec.env):
        argv += ["-e", f"{key}={spec.env[key]}"]
    argv += ["-w", spec.working_dir]
    if spec.entrypoint:
        argv += ["--entrypoint", spec.entrypoint]
    argv.append(spec.image)
    argv += list(spec.command)
    return argv


class SandboxRunner(Protocol):
    """How :class:`SandboxManager` reaches a container runtime.

    One async call, so a test injects a plain function and the suite never
    needs docker installed.
    """

    async def __call__(self, argv: list[str], *, timeout: int) -> SandboxResult: ...


async def docker_cli_runner(argv: list[str], *, timeout: int) -> SandboxResult:
    """The default runner: shells out to the docker CLI."""
    return await _exec(argv, timeout=timeout)


class SandboxManager:
    """Start, stop and inspect errand sandboxes.

    Every container it starts is validated first, so a caller cannot reach a
    running container through an unsafe spec even by building one by hand.
    """

    def __init__(self, runner: SandboxRunner | None = None) -> None:
        self._run: SandboxRunner = runner or docker_cli_runner

    async def start(self, spec: SandboxSpec) -> str:
        """Run *spec* detached and return the container id.

        Raises:
            SandboxPolicyError: the spec breaks an isolation rule.
            SandboxUnavailableError: the runtime refused or could not start it.
        """
        argv = docker_run_argv(spec, detach=True)
        res = await self._run(argv, timeout=spec.timeout)
        if res.returncode != 0:
            raise SandboxUnavailableError(
                f"sandbox {spec.name} did not start: {res.stderr.strip()[-400:]}"
            )
        container = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else spec.name
        logger.info("sandbox started role=%s name=%s id=%s", spec.role, spec.name, container[:12])
        return container

    async def stop(self, name: str, *, timeout: int = 10) -> bool:
        """Stop and remove the sandbox *name*. True if it is gone afterwards.

        Removal is forced and unconditional: a sandbox nobody is waiting on
        is a sandbox that should not still be running.
        """
        if not _DOCKER_NAME.match(name or ""):
            raise SandboxPolicyError(f"sandbox {name!r}", ["not a safe container name"])
        await self._run(["docker", "stop", "--time", str(timeout), name], timeout=timeout + 15)
        res = await self._run(["docker", "rm", "--force", "--volumes", name], timeout=30)
        gone = res.returncode == 0 or "no such container" in res.stderr.lower()
        if not gone:
            logger.warning("sandbox %s could not be removed: %s", name, res.stderr.strip()[-200:])
        return gone

    async def status(self, name: str) -> str:
        """Docker's state for *name* (``running``, ``exited``, ...), or ``absent``."""
        if not _DOCKER_NAME.match(name or ""):
            raise SandboxPolicyError(f"sandbox {name!r}", ["not a safe container name"])
        res = await self._run(
            ["docker", "inspect", "--format", "{{.State.Status}}", name], timeout=30
        )
        if res.returncode != 0:
            return "absent"
        return res.stdout.strip() or "absent"


# ── compose.sandbox.yaml, held to the same policy ────────────
# Compose keys that hand a container something this chassis refuses to hand
# it. Mapped to the sentence reported when they appear.
_FORBIDDEN_COMPOSE_KEYS = {
    "env_file": "reads an env file (the app's .env carries every provider key)",
    "ports": "publishes a port to the host",
    "devices": "maps a host device",
    "device_cgroup_rules": "widens device access",
    "cgroup_parent": "escapes its cgroup",
    "privileged": "runs privileged",
    "userns_mode": "overrides the user namespace",
    "sysctls": "sets kernel parameters",
    "cap_add": "adds capabilities back",
    "extra_hosts": "overrides name resolution",
    "secrets": "mounts a compose secret",
    "volumes_from": "inherits another container's mounts",
}
_FORBIDDEN_HOST_SHARING = {"pid": "host", "ipc": "host", "network_mode": "host", "uts": "host"}


def compose_path() -> Path:
    """Path to ``compose.sandbox.yaml`` at the repository root."""
    return Path(__file__).resolve().parents[2] / SANDBOX_COMPOSE_FILE


def _compose_env(raw: object) -> dict[str, str]:
    """Normalise compose's two environment forms into a dict."""
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}
    env: dict[str, str] = {}
    for item in raw or []:  # type: ignore[union-attr]
        name, _, value = str(item).partition("=")
        env[name] = value
    return env


def spec_from_compose(name: str, service: dict, networks: dict | None = None) -> SandboxSpec:
    """Build a :class:`SandboxSpec` out of one compose service definition.

    Only the fields the policy cares about are carried over; the point is to
    run :func:`spec_violations` against the file a human actually brings up,
    instead of trusting that it matches the Python defaults.
    """
    attached = list(service.get("networks") or [])
    # A compose network's real name comes from its `name:` key when it has
    # one, which is what the container is actually attached to.
    declared = (networks or {}).get(attached[0] if attached else "", {}) or {}
    network = str(declared.get("name") or (attached[0] if attached else ""))
    return SandboxSpec(
        name=f"compose-{name}",
        image=str(service.get("image") or ""),
        role=name,
        user=str(service.get("user") or ""),
        network=network,
        network_mode=service.get("network_mode"),
        privileged=bool(service.get("privileged", False)),
        read_only_root=bool(service.get("read_only", False)),
        cap_drop=tuple(str(c) for c in service.get("cap_drop") or ()),
        cap_add=tuple(str(c) for c in service.get("cap_add") or ()),
        security_opt=tuple(str(o) for o in service.get("security_opt") or ()),
        pids_limit=int(service.get("pids_limit") or 0),
        memory=str(service.get("mem_limit") or ""),
        cpus=str(service.get("cpus") or ""),
        tmpfs=tuple(str(t) for t in service.get("tmpfs") or ()),
        mounts=tuple(str(v) for v in service.get("volumes") or ()),
        env=_compose_env(service.get("environment")),
        working_dir=str(service.get("working_dir") or WORKSPACE_DIR),
    )


def compose_violations(path: Path | None = None) -> dict[str, list[str]]:
    """Check ``compose.sandbox.yaml`` against the sandbox policy.

    Returns service name -> violations (plus the pseudo-service ``"compose"``
    for file-level problems). An empty dict means the file is clean.
    """
    import yaml

    target = path or compose_path()
    document = yaml.safe_load(target.read_text()) or {}
    services = document.get("services") or {}
    networks = document.get("networks") or {}
    found: dict[str, list[str]] = {}

    file_level: list[str] = []
    if document.get("volumes"):
        file_level.append("declares named volumes at the top level")
    if not services:
        file_level.append("declares no services")
    for net_name, net in networks.items():
        if not (net or {}).get("internal"):
            file_level.append(f"network {net_name} is not internal-only")
    if file_level:
        found["compose"] = file_level

    for name, service in services.items():
        service = service or {}
        bad = [
            f"{name} {reason}"
            for key, reason in _FORBIDDEN_COMPOSE_KEYS.items()
            if service.get(key)
        ]
        bad += [
            f"{name} shares the host's {key} namespace"
            for key, value in _FORBIDDEN_HOST_SHARING.items()
            if str(service.get(key) or "").lower().startswith(value)
        ]
        if not service.get("networks"):
            bad.append(f"{name} is on the default network, not the internal sandbox network")
        bad += spec_violations(spec_from_compose(name, service, networks))
        if bad:
            found[name] = bad
    return found
