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
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

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
