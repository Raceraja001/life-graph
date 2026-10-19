"""Allowlisted shell for ``run_command`` (``tool_shell_mode=allowlist``).

``run_command`` used to offer two choices: off, or an arbitrary shell string
behind a denylist that its own module calls "a mistake-catcher, NOT a security
boundary". The ops personas therefore stayed off, since a model holding a
full shell is a model holding the machine.

This mode is a boundary of its own:

- **No shell.** The command is split with ``shlex`` and run with exec, so
  ``;``, ``|``, ``&&``, redirection, ``$()`` and globbing do not exist. A
  command containing any shell metacharacter is refused outright, rather than
  silently run without it.
- **Allowlisted programs only**, by bare name (no paths, so ``./evil`` or
  ``/tmp/ls`` cannot stand in for one), each with the subcommands or flags that
  keep it read-only: ``docker ps`` but not ``docker rm``, ``git log`` but not
  ``git push``, and ``find`` without ``-exec`` or ``-delete``.
- **File arguments stay in the roots.** For programs that read files, every
  argument that names a path must resolve inside ``tool_fs_roots`` and must not
  be credential material (the same check the file tools use).
- **No secrets in the child.** The child gets PATH, HOME and the locale only,
  never the API's environment, which holds its keys.

The result is enough to answer "is the disk full, is the container up, what
did the last deploy log say" and nothing that changes the machine.
"""

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

from life_graph.tools._guards import ToolDeniedError, resolve_in_roots

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_METACHARS = set(";&|<>`$\n\r")

# Programs that read files: path-like arguments are confined.
_READERS = {"ls", "cat", "head", "tail", "wc", "grep", "stat", "file", "tree", "find", "du"}
# Programs that only report state; arguments are flags.
_REPORTERS = {
    "df",
    "free",
    "uptime",
    "uname",
    "whoami",
    "hostname",
    "date",
    "nproc",
    "lscpu",
    "lsblk",
}

_FIND_DENY = {
    "-exec",
    "-execdir",
    "-ok",
    "-okdir",
    "-delete",
    "-fprint",
    "-fprint0",
    "-fprintf",
    "-fls",
}
_DOCKER_SUB = {"ps", "images", "logs", "stats", "info", "version", "top", "df"}
_DOCKER_COMPOSE_SUB = {"ps", "logs", "ls", "top", "images"}
_GIT_SUB = {
    "status",
    "log",
    "diff",
    "show",
    "rev-parse",
    "describe",
    "ls-files",
    "shortlog",
    "blame",
}
_SYSTEMCTL_SUB = {"status", "is-active", "is-enabled", "is-failed", "list-units", "list-timers"}
_JOURNAL_DENY_PREFIX = ("--vacuum", "--rotate", "--flush", "--relinquish", "--sync", "--setup-keys")
_PS_ARGS = {"aux", "-ef", "-e", "-A", "-o", "-eo", "--forest", "-u", "-p"}


def _deny(why: str) -> ToolDeniedError:
    return ToolDeniedError(f"Command not allowed in allowlist mode: {why}.")


def _check_paths(args: list[str], cwd: Path) -> None:
    for arg in args:
        value = arg.split("=", 1)[1] if arg.startswith("-") and "=" in arg else arg
        if arg.startswith("-") and value is arg:
            continue  # a plain flag
        looks_like_path = "/" in value or value.startswith("~") or (cwd / value).exists()
        if looks_like_path:
            target = value if value.startswith(("/", "~")) else str(cwd / value)
            resolve_in_roots(target, tool_name="run_command")


def _docker(args: list[str]) -> None:
    if not args:
        raise _deny("docker needs a subcommand")
    if args[0] == "compose":
        if len(args) < 2 or args[1] not in _DOCKER_COMPOSE_SUB:
            raise _deny(f"docker compose allows only {', '.join(sorted(_DOCKER_COMPOSE_SUB))}")
        if args[1] == "logs" and not any(
            a in ("--tail", "-n") or a.startswith("--tail=") for a in args
        ):
            raise _deny("docker compose logs needs --tail N")
        return
    if args[0] not in _DOCKER_SUB:
        raise _deny(f"docker allows only {', '.join(sorted(_DOCKER_SUB))}")
    if args[0] == "stats" and "--no-stream" not in args:
        raise _deny("docker stats needs --no-stream")
    if args[0] == "logs" and ("-f" in args or "--follow" in args):
        raise _deny("docker logs cannot follow")


def _git(args: list[str]) -> None:
    # The subcommand comes first: global options (-c, -C, --exec-path) can
    # run programs or point git elsewhere.
    if not args or args[0] not in _GIT_SUB:
        raise _deny(f"git allows only {', '.join(sorted(_GIT_SUB))}, with no options before it")
    if any(a.startswith("--output") or a.startswith("--ext-diff") for a in args):
        raise _deny("git output redirection is not allowed")


def _systemctl(args: list[str]) -> None:
    sub = next((a for a in args if not a.startswith("-")), "list-units")
    if sub not in _SYSTEMCTL_SUB:
        raise _deny(f"systemctl allows only {', '.join(sorted(_SYSTEMCTL_SUB))}")


def _journalctl(args: list[str]) -> None:
    if any(a.startswith(_JOURNAL_DENY_PREFIX) for a in args):
        raise _deny("journalctl maintenance flags are not allowed")
    if "-f" in args or "--follow" in args:
        raise _deny("journalctl cannot follow")


def _ps(args: list[str]) -> None:
    # BSD-style options ("e", "eww") print every process's environment, which
    # holds secrets, so the only BSD form accepted is "aux".
    takes_value = {"-o", "-eo", "-p", "-u"}
    i = 0
    while i < len(args):
        a = args[i]
        if a in takes_value:
            if i + 1 < len(args) and "environ" in args[i + 1]:
                raise _deny("ps cannot show process environments")
            i += 2
            continue
        if a.startswith("--sort=") or a in _PS_ARGS:
            i += 1
            continue
        raise _deny(f"ps argument {a!r} (use aux, -ef, -eo FORMAT, -p PID, --sort=KEY)")


def _ss(args: list[str]) -> None:
    if any(
        a in ("-K", "--kill") or (a.startswith("-") and not a.startswith("--") and "K" in a)
        for a in args
    ):
        raise _deny("ss cannot kill sockets")


_SPECIAL: dict[str, Callable[[list[str]], None]] = {
    "docker": _docker,
    "git": _git,
    "systemctl": _systemctl,
    "journalctl": _journalctl,
    "ps": _ps,
    "ss": _ss,
}

ALLOWED_PROGRAMS = frozenset(_READERS | _REPORTERS | set(_SPECIAL))


def parse(command: str, cwd: Path) -> list[str]:
    """argv for ``command`` if it is allowed, else :class:`ToolDeniedError`."""
    if any(c in _METACHARS for c in command):
        raise _deny("shell operators (; | & < > $ `) are not available; run one program")
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise _deny(f"could not parse ({exc})") from exc
    if not argv:
        raise _deny("empty command")
    program, args = argv[0], argv[1:]
    if "/" in program or program not in ALLOWED_PROGRAMS:
        raise _deny(f"{program!r} is not on the allowlist ({', '.join(sorted(ALLOWED_PROGRAMS))})")
    if program in _SPECIAL:
        _SPECIAL[program](args)
    if program == "find" and _FIND_DENY & set(args):
        raise _deny("find cannot run or delete")
    if program in _READERS or program == "git":
        _check_paths(args if program != "grep" else _grep_paths(args), cwd)
    return argv


def _grep_paths(args: list[str]) -> list[str]:
    """grep's first operand is the pattern unless -e/-f supplied one."""
    operands = [a for a in args if not a.startswith("-")]
    has_pattern_flag = any(a in ("-e", "-f") or a.startswith(("--regexp", "--file")) for a in args)
    flags = [a for a in args if a.startswith("-")]
    files = operands if has_pattern_flag else operands[1:]
    # -f FILE reads patterns from a file: that file is confined too.
    if "-f" in args:
        i = args.index("-f")
        if i + 1 < len(args):
            files.append(args[i + 1])
    return flags + files


def child_env() -> dict[str, str]:
    """The child's whole environment: no API keys, no tokens."""
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TZ")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    return env
