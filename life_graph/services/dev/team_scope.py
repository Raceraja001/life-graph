"""File scopes of a parallel plan's tasks, and which of them may run at once.

docs/specs/agent-drivers.md, "Phase 4b". A plan task may declare the files it
will change (``Files: a.py, src/**``, parsed by
:func:`life_graph.drivers.plan_spec.parse_task_files`). Two scopes *overlap*
when any pair of their entries can name the same file: the same path, one path
inside the other's directory, or a path a simple glob matches (``*`` = part of
one segment, ``**`` = any depth, ``?`` = one character). Two globs are compared
by their literal directory prefixes -- conservative: writers that might collide
run one after the other. A task that declares **no** scope overlaps everything
(fail closed: an unknown footprint is not assumed to be disjoint).

Pure functions. Rebuilt from race-app's ``automation/team/scope.ts`` (the
owner's code), with the one deliberate difference above: race-app let an empty
scope overlap nothing.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_GLOB_CHARS = re.compile(r"[*?]")


def normalize_scope_path(raw: str) -> str:
    """``"./src//a/"`` -> ``"src/a"``; backslashes become slashes; ``"."`` -> ``""``."""
    path = raw.strip().replace("\\", "/")
    path = re.sub(r"/{2,}", "/", path)
    path = re.sub(r"^(\./)+", "", path)
    path = path.strip("/")
    return "" if path == "." else path


def _has_glob(path: str) -> bool:
    return bool(_GLOB_CHARS.search(path))


def static_prefix(glob: str) -> str:
    """The literal directory segments before the first segment holding a glob character."""
    parts = glob.split("/")
    for i, part in enumerate(parts):
        if _has_glob(part):
            return "/".join(parts[:i])
    return "/".join(parts)


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """An anchored pattern for a simple glob (``*``, ``**``, ``?``)."""
    out: list[str] = []
    i = 0
    while i < len(glob):
        ch = glob[i]
        if ch == "*":
            if i + 1 < len(glob) and glob[i + 1] == "*":
                slash = i + 2 < len(glob) and glob[i + 2] == "/"
                out.append("(?:.*/)?" if slash else ".*")
                i += 3 if slash else 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _same_or_nested(a: str, b: str) -> bool:
    if a == "" or b == "":
        return True
    return a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/")


def paths_overlap(raw_a: str, raw_b: str) -> bool:
    """Whether two scope entries can name the same file."""
    a, b = normalize_scope_path(raw_a), normalize_scope_path(raw_b)
    glob_a, glob_b = _has_glob(a), _has_glob(b)
    if not glob_a and not glob_b:
        return _same_or_nested(a, b)
    if glob_a and glob_b:
        return _same_or_nested(static_prefix(a), static_prefix(b))
    glob, path = (a, b) if glob_a else (b, a)
    if glob_to_regex(glob).match(path):
        return True
    # A plain directory that holds the glob's base ("src" vs "src/ui/**") overlaps it.
    prefix = static_prefix(glob)
    return path == "" or prefix == path or prefix.startswith(f"{path}/")


def scopes_overlap(a: Sequence[str], b: Sequence[str]) -> bool:
    """Whether two task scopes overlap; an empty scope overlaps everything."""
    if not a or not b:
        return True
    return any(paths_overlap(x, y) for x in a for y in b)


def overlap_dependencies(scopes: Sequence[Sequence[str]]) -> list[list[int]]:
    """For each scope (plan order), the indexes of EARLIER scopes it overlaps.

    Those run first: the later task gets ``depends_on`` on each of them and
    starts from their changes. Indexes are 0-based.
    """
    return [
        [i for i in range(j) if scopes_overlap(scopes[i], scope)] for j, scope in enumerate(scopes)
    ]


def parallel_waves(scopes: Sequence[Sequence[str]]) -> list[list[int]]:
    """The tasks grouped by the earliest wave they can run in (for the team view)."""
    deps = overlap_dependencies(scopes)
    wave: list[int] = []
    for ds in deps:
        wave.append(1 + max((wave[i] for i in ds), default=-1))
    out: list[list[int]] = [[] for _ in range(max(wave, default=-1) + 1)]
    for j, w in enumerate(wave):
        out[w].append(j)
    return out
