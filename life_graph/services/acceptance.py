"""Acceptance criteria bound to tests, for plan-stage specs.

A plan's spec lists acceptance criteria as ``AC-1: <criterion> — test:
tests/unit/test_x.py::test_y`` and each task cites the criteria it
satisfies, e.g. ``1. Add the parser (AC-1, AC-2)``. That lets each fanned-out
task be checked against the specific tests that prove its criteria
(verifier ``acceptance_tests_pass``), instead of the human approving a spec
that nothing ever checks the code against.

Pure parsing, no I/O. Idea adapted from FORGE's spec-driven development
(AC-n ids bound to tests), kept to what this pipeline can actually check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CRITERION_RE = re.compile(
    r"^[\s>*-]*\**(AC-\d+)\**\s*[:.)\-–—]\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE
)
_TEST_SPLIT_RE = re.compile(r"\s*[-–—(,;]?\s*\btest\s*:\s*", re.IGNORECASE)
_CITE_RE = re.compile(r"\bAC-(\d+)\b", re.IGNORECASE)

# A test reference ends up as a pytest argument, and it is agent-authored
# (it comes from the model's spec). Only a plain relative path to a .py file,
# optionally followed by ::node parts, is accepted -- nothing that could read
# as an option (-p plugin, --rootdir, ...), no absolute paths, no "..".
_SAFE_TEST_REF_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.py(::[A-Za-z0-9_\[\]\-.]+)*$")
# The same for a JS/TS test (vitest/jest): a *.test.* or *.spec.* file, then
# optionally one ::test name. JS test names are sentences ("adds a todo"), so
# spaces and light punctuation are allowed in the name; it is only ever passed
# as one argv element (never through a shell) and regex-escaped for -t.
_SAFE_JS_TEST_REF_RE = re.compile(
    r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.(test|spec)\.[cm]?[jt]sx?(::[A-Za-z0-9 _\-.,'()]+)?$"
)


@dataclass(frozen=True)
class AcceptanceCriterion:
    """One acceptance criterion from a spec's Requirements section."""

    id: str
    text: str
    test: str | None


def is_safe_test_ref(ref: str | None) -> bool:
    """Whether *ref* is a plain relative test path/node id, safe as an argument.

    A pytest path (``tests/x.py::test_y``) or a JS/TS test file with an
    optional test name (``tests/x.test.ts::adds a todo``).
    """
    if not ref or ".." in ref.split("::", 1)[0].split("/"):
        return False
    return bool(_SAFE_TEST_REF_RE.match(ref) or _SAFE_JS_TEST_REF_RE.match(ref))


def is_js_test_ref(ref: str) -> bool:
    """Whether a (safe) test reference names a JS/TS test rather than a pytest one."""
    return bool(_SAFE_JS_TEST_REF_RE.match(ref))


def parse_criteria(spec_text: str | None) -> list[AcceptanceCriterion]:
    """Every ``AC-n: ...`` line in the spec, in order, first definition wins."""
    if not spec_text:
        return []
    seen: dict[str, AcceptanceCriterion] = {}
    for match in _CRITERION_RE.finditer(spec_text):
        ac_id = match.group(1).upper()
        if ac_id in seen:
            continue
        parts = _TEST_SPLIT_RE.split(match.group(2), maxsplit=1)
        text = parts[0].strip().rstrip("—–-").strip()
        test = parts[1].strip().strip("`").strip().rstrip(").,;") if len(parts) > 1 else None
        seen[ac_id] = AcceptanceCriterion(id=ac_id, text=text, test=test or None)
    return list(seen.values())


def cited_criteria(task_text: str) -> list[str]:
    """The AC ids a task cites, in order, de-duplicated."""
    out: list[str] = []
    for match in _CITE_RE.finditer(task_text or ""):
        ac_id = f"AC-{match.group(1)}"
        if ac_id not in out:
            out.append(ac_id)
    return out


def spec_gaps(criteria: list[AcceptanceCriterion], tasks: list[str]) -> list[str]:
    """Human-readable problems a reviewer should see before approving a plan.

    Advisory, not blocking: the person approving decides whether a gap
    matters. Surfaced in the approval rather than silently ignored.
    """
    if not criteria:
        return ["No acceptance criteria (AC-n lines) — tasks will not be checked against the spec."]
    gaps: list[str] = []
    defined = {c.id for c in criteria}
    for c in criteria:
        if not c.test:
            gaps.append(f"{c.id} has no bound test.")
        elif not is_safe_test_ref(c.test):
            gaps.append(f"{c.id} test reference {c.test!r} is not a plain pytest path — ignored.")
    covered: set[str] = set()
    for i, task in enumerate(tasks, start=1):
        cites = cited_criteria(task)
        if not cites:
            gaps.append(f"Task {i} cites no acceptance criterion.")
        for ac_id in cites:
            if ac_id in defined:
                covered.add(ac_id)
            else:
                gaps.append(f"Task {i} cites {ac_id}, which the spec doesn't define.")
    gaps.extend(f"{c.id} is not covered by any task." for c in criteria if c.id not in covered)
    return gaps


def bound_tests(criteria: list[AcceptanceCriterion], ac_ids: list[str]) -> list[str]:
    """The safe bound tests for the given AC ids, de-duplicated, in order."""
    by_id = {c.id: c for c in criteria}
    out: list[str] = []
    for ac_id in ac_ids:
        c = by_id.get(ac_id)
        if c and is_safe_test_ref(c.test) and c.test not in out:
            out.append(c.test)
    return out


def describe(criteria: list[AcceptanceCriterion], ac_ids: list[str]) -> str:
    """Instruction text naming the criteria (and tests) a task must satisfy."""
    by_id = {c.id: c for c in criteria}
    lines = []
    for ac_id in ac_ids:
        c = by_id.get(ac_id)
        if not c:
            continue
        if is_safe_test_ref(c.test):
            lines.append(f"- {c.id}: {c.text} (proved by test: {c.test})")
        else:
            lines.append(f"- {c.id}: {c.text}")
    return "\n".join(lines)
