"""A change's risk report: block/warn findings with file and line, from the diff.

docs/specs/agent-drivers.md, "Autonomy policy" (2026-11-27). Deterministic,
no I/O, never raises on odd input, and never stores a matched value: a
finding names the file, the line, the rule and a shape ("28-char string,
4.3 bits/char"), so the report is not a second place a secret lives.

Rules, on **added** lines only (what the change brings in, not what was there):

* ``secret_pattern`` (block): a known credential shape, the same
  high-confidence list ``no_secrets_in_diff`` uses (core/redaction.py).
* ``high_entropy_string`` (block; warn in tests/fixtures): a long token that
  looks random -- digits and letters mixed, at least three character classes,
  Shannon entropy at or above :data:`ENTROPY_MIN_BITS`. Catches keys no
  pattern knows. Pure hex is reported separately as ``hex_string`` (warn):
  commit SHAs and checksums are hex and common in code.
* ``secret_assignment`` (warn): a literal assigned to a name like
  ``password``/``api_key``/``token``.

And on the change as a whole (warn): ``protected_path`` (the gate's protected
globs), ``out_of_scope`` (a non-test file the instruction does not name, when
it names any) and ``large_deletion`` (a deleted file, or more than
:data:`LARGE_DELETION_LINES` lines removed from one).

Who acts on it: nothing by default. The owner's autonomy policy
(``conditions.risk_tolerance``, services/dev/autonomy_policy.py) can refuse
auto-approval on blocks or on any finding. The report is stored on the task
(``properties.risk_report``) and returned with it.
"""

from __future__ import annotations

import fnmatch
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from life_graph.core.redaction import SECRET_SHAPES

# As a module: verifiers imports this one at its top (no_high_entropy_in_diff),
# so its names are read at call time, once both are loaded.
from life_graph.services.dev import verifiers as _verifiers
from life_graph.services.dev.change_policy import DEFAULT_PROTECTED

ENTROPY_MIN_BITS = 3.5
MIN_TOKEN_CHARS = 20
HEX_MIN_CHARS = 32
LARGE_DELETION_LINES = 200
MAX_FINDINGS = 100
MAX_LINE_CHARS = 2000
REPORT_VERSION = 1

_TOKEN = re.compile(rf"[A-Za-z0-9+/=_\-]{{{MIN_TOKEN_CHARS},}}")
_HEX = re.compile(r"^[0-9a-fA-F]+$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_ASSIGNMENT = re.compile(
    r"(?i)\b[\w.-]*(password|passwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|"
    r"private[_-]?key|client[_-]?secret)\b[\w.-]*\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
)
# Placeholders a real config never holds; a literal like these is not a secret.
_PLACEHOLDER = re.compile(r"(?i)^(x+|\*+|<.*>|\$\{.*\}|changeme|example|dummy|test|fake|redacted)")
# Hash/checksum context on the same line: a random-looking value there is a digest.
_DIGEST_CONTEXT = re.compile(r"(?i)sha\d*|integrity|checksum|digest|\bhash\b|\betag\b")
# Generated or vendored files: random-looking strings are normal there.
_SKIP_SUFFIXES = (".lock", ".min.js", ".min.css", ".map", ".svg", ".snap", ".ipynb")
_SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock"}
_FIXTURE_PARTS = {"tests", "test", "__tests__", "fixtures", "testdata", "__fixtures__"}
# AWS's own documented placeholder (see verifiers._AWS_EXAMPLE_KEY).
_AWS_EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"


def shannon_entropy(value: str) -> float:
    """Bits per character of *value* (0.0 for an empty string)."""
    if not value:
        return 0.0
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in Counter(value).values())


def _classes(value: str) -> int:
    return sum(bool(re.search(p, value)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))


def classify_token(token: str) -> tuple[str, float] | None:
    """``("random", bits)`` / ``("hex", bits)`` for a token that looks like key
    material, else None. Pure; the thresholds are this module's constants."""
    value = token.strip("=-_/+")
    if len(value) < MIN_TOKEN_CHARS or _UUID.match(value):
        return None
    bits = shannon_entropy(value)
    if _HEX.match(value):
        if len(value) >= HEX_MIN_CHARS and bits >= 3.0:
            return "hex", bits
        return None
    # Paths and dotted/underscored identifiers: low digit count, readable.
    if value.count("/") >= 2 and bits < 4.5:
        return None
    digits = sum(ch.isdigit() for ch in value)
    letters = sum(ch.isalpha() for ch in value)
    if digits >= 2 and letters >= 1 and _classes(value) >= 3 and bits >= ENTROPY_MIN_BITS:
        return "random", bits
    return None


def skipped_path(path: str) -> bool:
    """Generated or vendored files the entropy rules do not read."""
    p = PurePosixPath(path)
    return p.name in _SKIP_NAMES or p.name.endswith(_SKIP_SUFFIXES)


def _fixture(path: str) -> bool:
    return _verifiers._is_test_path(path) or bool(_FIXTURE_PARTS & set(PurePosixPath(path).parts))


def parse_unified_diff(diff_text: str) -> dict[str, dict[str, Any]]:
    """Per post-image path: ``added`` [(new line number, text)], ``removed``
    count and ``deleted`` (the file is gone). Tolerates any junk input."""
    files: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    new_line = 0
    old_path: str | None = None
    for raw in (diff_text or "").splitlines():
        if raw.startswith("diff --git "):
            current, old_path = None, None
            continue
        if raw.startswith("--- "):
            old_path = raw[4:].strip()
            old_path = old_path[2:] if old_path.startswith("a/") else old_path
            continue
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                path = old_path or "?"
                current = files.setdefault(path, {"added": [], "removed": 0, "deleted": True})
                current["deleted"] = True
            else:
                path = target[2:] if target.startswith("b/") else target
                current = files.setdefault(path, {"added": [], "removed": 0, "deleted": False})
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line = int(m.group(1)) if m else 0
            continue
        if current is None:
            continue
        if raw.startswith("+"):
            current["added"].append((new_line, raw[1:][:MAX_LINE_CHARS]))
            new_line += 1
        elif raw.startswith("-"):
            current["removed"] += 1
        elif raw.startswith(" "):
            new_line += 1
    return files


def _finding(severity: str, rule: str, file: str, line: int | None, detail: str) -> dict:
    return {"severity": severity, "rule": rule, "file": file, "line": line, "detail": detail}


def scan_line(path: str, lineno: int, text: str) -> list[dict]:
    """The findings one added line produces (pure)."""
    if _AWS_EXAMPLE_KEY in text:
        return []
    out: list[dict] = []
    for shape in SECRET_SHAPES:
        if shape.high_confidence and shape.pattern.search(text):
            out.append(_finding("block", "secret_pattern", path, lineno, f"{shape.kind} shape"))
    if out:
        return out  # the line already blocks; no second finding for the same value
    fixture = _fixture(path)
    digest = bool(_DIGEST_CONTEXT.search(text))
    for match in _TOKEN.finditer(text):
        kind = classify_token(match.group(0))
        if kind is None:
            continue
        what, bits = kind
        shape = f"{len(match.group(0))}-char string, {bits:.1f} bits/char"
        if what == "hex":
            out.append(_finding("warn", "hex_string", path, lineno, f"{shape} (hash or hex key)"))
        elif fixture or digest:
            why = "test/fixture file" if fixture else "digest context"
            out.append(_finding("warn", "high_entropy_string", path, lineno, f"{shape} ({why})"))
        else:
            out.append(_finding("block", "high_entropy_string", path, lineno, shape))
    m = _ASSIGNMENT.search(text)
    if m and not _PLACEHOLDER.match(m.group(2)) and not out:
        out.append(
            _finding("warn", "secret_assignment", path, lineno, f"literal assigned to {m.group(1)}")
        )
    return out


def build_report(
    diff_text: str,
    *,
    instruction: str = "",
    protected_globs: list[str] | None = None,
    complete: bool = True,
) -> dict[str, Any]:
    """The risk report for one unified diff.

    ``complete`` is False when the diff could not be read in full (the caller
    knows: e.g. files changed but the diff came back empty); a policy that
    looks at risk treats an incomplete report as a refusal, never as clean.
    """
    files = parse_unified_diff(diff_text)
    findings: list[dict] = []
    for path, info in files.items():
        if not skipped_path(path):
            for lineno, text in info["added"]:
                findings.extend(scan_line(path, lineno, text))
        if info["deleted"]:
            findings.append(_finding("warn", "large_deletion", path, None, "file deleted"))
        elif info["removed"] > LARGE_DELETION_LINES:
            findings.append(
                _finding("warn", "large_deletion", path, None, f"{info['removed']} lines removed")
            )
    patterns = [*DEFAULT_PROTECTED, *(protected_globs or [])]
    for path in files:
        if any(fnmatch.fnmatch(path, p) for p in patterns):
            findings.append(_finding("warn", "protected_path", path, None, "protected path"))
    named = _verifiers.named_paths(instruction)
    if named:
        bare = {a for a in named if "/" not in a}
        for path in files:
            named_here = path in named or PurePosixPath(path).name in bare
            if not named_here and not _verifiers._is_test_path(path):
                findings.append(
                    _finding("warn", "out_of_scope", path, None, "not named by the task")
                )
    findings.sort(key=lambda f: (f["severity"] != "block", f["file"], f["line"] or 0))
    return {
        "version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "complete": bool(complete),
        "files": len(files),
        "block": sum(f["severity"] == "block" for f in findings),
        "warn": sum(f["severity"] == "warn" for f in findings),
        "findings": findings[:MAX_FINDINGS],
        "truncated": len(findings) > MAX_FINDINGS,
    }


def summary(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """The counts an approval payload carries (None when there is no report)."""
    if not report:
        return None
    return {
        "block": int(report.get("block") or 0),
        "warn": int(report.get("warn") or 0),
        "complete": bool(report.get("complete")),
    }
