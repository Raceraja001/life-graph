"""Find where an edit applies when the model's ``old`` text is not exact.

Live trials (docs/specs/agent-condenser.md, 2026-10-15) showed the local
model's edits failing far more often than its reasoning: qwen3:14b reproduces
a file's text with small differences (indentation, trailing spaces, the
``12: `` prefixes ``code_read`` prints), and an exact-match edit refuses all
of them with "`old` not found". Matching is tried in tiers, strictest first,
and an edit is applied only where **exactly one** place matches at that tier:

1. ``exact``         the text as given;
2. ``prefixes``      with ``code_read``'s ``N: `` line prefixes removed;
3. ``trailing``      ignoring trailing whitespace on every line;
4. ``indentation``   ignoring leading whitespace; ``new`` is re-indented by
                     the difference so the edit lands at the file's
                     indentation.

When nothing matches, :func:`closest` names the most similar region with line
numbers, so the next attempt can copy the real text instead of guessing.
Pure: no I/O.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

_PREFIX = re.compile(r"^\s*\d+: ?", re.M)


@dataclass
class Match:
    start: int  # character offset in the file text
    end: int
    tier: str
    new: str  # the replacement, adjusted for the tier (re-indented)


@dataclass
class Miss:
    reason: str  # "not_found" | "ambiguous"
    tier: str | None = None
    count: int = 0


def _line_spans(text: str) -> list[tuple[int, int]]:
    """(start, end-without-newline) of every line."""
    spans, pos = [], 0
    for line in text.split("\n"):
        spans.append((pos, pos + len(line)))
        pos += len(line) + 1
    return spans


def _strip_blank_edges(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return lines


def _find_lines(text: str, old_lines: list[str], norm) -> list[tuple[int, int]]:
    """Every (first, last) file line index where ``old_lines`` match under ``norm``."""
    file_lines = text.split("\n")
    want = [norm(x) for x in old_lines]
    n = len(want)
    hits = []
    for i in range(len(file_lines) - n + 1):
        if all(norm(file_lines[i + k]) == want[k] for k in range(n)):
            hits.append((i, i + n - 1))
    return hits


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _reindent(new: str, old_first: str, file_first: str) -> str:
    """Shift every line of ``new`` by the indentation the file uses instead of ``old``'s."""
    have, want = _indent(old_first), _indent(file_first)
    if have == want:
        return new
    out = []
    for line in new.split("\n"):
        if not line.strip():
            out.append(line)
        elif line.startswith(have):
            out.append(want + line[len(have) :])
        else:
            out.append(want + line.lstrip())
    return "\n".join(out)


def locate(text: str, old: str, new: str) -> Match | Miss:
    """Where ``old`` applies in ``text``, at the strictest tier that finds one place."""
    count = text.count(old)
    if count == 1:
        start = text.index(old)
        return Match(start, start + len(old), "exact", new)
    if count > 1:
        return Miss("ambiguous", "exact", count)

    # The model copied code_read's "12: " prefixes: drop them from both sides
    # (only when `old` has them, so a file of "1: x" lines is left alone).
    if _PREFIX.search(old):
        old, new = _PREFIX.sub("", old), _PREFIX.sub("", new)
        count = text.count(old)
        if count == 1:
            start = text.index(old)
            return Match(start, start + len(old), "prefixes", new)
        if count > 1:
            return Miss("ambiguous", "prefixes", count)

    old_lines = _strip_blank_edges(old.split("\n"))
    if not old_lines:
        return Miss("not_found")
    spans = _line_spans(text)
    file_lines = text.split("\n")
    for tier, norm in (("trailing", str.rstrip), ("indentation", str.strip)):
        hits = _find_lines(text, old_lines, norm)
        if len(hits) > 1:
            return Miss("ambiguous", tier, len(hits))
        if len(hits) == 1:
            first, last = hits[0]
            adjusted = new.strip("\n")
            if tier == "indentation":
                adjusted = _reindent(adjusted, old_lines[0], file_lines[first])
            return Match(spans[first][0], spans[last][1], tier, adjusted)
    return Miss("not_found")


def closest(text: str, old: str, context: int = 2) -> str | None:
    """The file region most similar to ``old``, numbered like code_read, or None."""
    file_lines = text.split("\n")
    old_lines = _strip_blank_edges(_PREFIX.sub("", old).split("\n"))
    if not old_lines or not file_lines:
        return None
    n = len(old_lines)
    target = "\n".join(x.strip() for x in old_lines)
    best, best_i = 0.0, 0
    for i in range(max(1, len(file_lines) - n + 1)):
        window = "\n".join(x.strip() for x in file_lines[i : i + n])
        score = difflib.SequenceMatcher(None, target, window, autojunk=False).ratio()
        if score > best:
            best, best_i = score, i
    if best < 0.6:
        return None
    lo, hi = max(0, best_i - context), min(len(file_lines), best_i + n + context)
    return "\n".join(f"{k + 1}: {file_lines[k]}" for k in range(lo, hi))


def excerpt(text: str, start: int, length: int, context: int = 2) -> str:
    """Numbered lines around an edit, so the model sees what it wrote."""
    file_lines = text.split("\n")
    first = text[:start].count("\n")
    last = first + text[start : start + length].count("\n")
    lo, hi = max(0, first - context), min(len(file_lines), last + context + 1)
    return "\n".join(f"{k + 1}: {file_lines[k]}" for k in range(lo, hi))
