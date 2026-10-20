"""Verifiers that ask for proof, not plausibility (the owner's rule, 2026-10-20).

"Tests pass" says nothing about whether an agent understood the code it
changed, or whether the tests it wrote could ever fail. These checks make that
mechanical:

* ``diff_coverage`` — every changed line of production code must be run by
  a test (coverage.py in the sandbox, over the tests that import the changed
  modules). Untested lines are unproven lines.
* ``tests_catch_mutants`` — the functions a changed test file targets are
  mutated (``==`` to ``!=``, ``and`` to ``or``, returns to ``None``, ...)
  and the tests must fail for most mutants. A test that still passes when
  the code is wrong restates the code instead of checking it (#96, #99).
* ``change_explained`` — a change to production code must come with the
  agent's own account of it: what the code did, what changed and what could
  break, naming every function it touched.
* ``types_clean_diff`` — mypy, run on the changed files, may not report an
  error on a changed line (Tier 3; inconclusive where mypy is not installed).

Each passes at once when its subject is absent (no production change, no
changed test), and is inconclusive — never a pass — when it cannot measure.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from life_graph.services import sandbox
from life_graph.services.verifiers import (
    _HARDENED_GIT,
    _changed_files,
    _is_test_path,
    _local_modules,
)

DIFF_COVERAGE_MIN = 0.8
MUTATION_MIN_KILL = 0.6
MAX_MUTANTS = 10
MUTANT_TIMEOUT = 90
_MAX_RELATED_TESTS = 25
_DOC_SUFFIXES = (".md", ".rst", ".txt")


# ── What changed ─────────────────────────────────────────────


def _is_doc(rel: str) -> bool:
    p = PurePosixPath(rel)
    return (p.parts and p.parts[0] == "docs") or p.suffix.lower() in _DOC_SUFFIXES


def production_files(workdir: Path) -> list[str]:
    """Changed files that are neither tests nor documentation."""
    out = []
    for f in _changed_files(workdir):
        rel = str(f.relative_to(workdir))
        if not _is_test_path(rel) and not _is_doc(rel):
            out.append(rel)
    return sorted(out)


def _git_out(workdir: Path, *args: str) -> tuple[int, str]:
    try:
        res = subprocess.run(
            [*_HARDENED_GIT, *args], capture_output=True, text=True, timeout=30, cwd=str(workdir)
        )
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return res.returncode, res.stdout


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(workdir: Path, rel: str) -> set[int]:
    """Line numbers (in the new file) added or changed since HEAD; every line
    of a file git does not track yet."""
    code, _ = _git_out(workdir, "ls-files", "--error-unmatch", "--", rel)
    if code != 0:
        try:
            n = len((workdir / rel).read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            return set()
        return set(range(1, n + 1))
    _, diff = _git_out(workdir, "diff", "--no-color", "-U0", "HEAD", "--", rel)
    lines: set[int] = set()
    for row in diff.splitlines():
        m = _HUNK_RE.match(row)
        if m:
            start, count = int(m.group(1)), int(m.group(2) or 1)
            lines.update(range(start, start + count))
    return lines


def statement_lines(source: str, lines: set[int]) -> set[int]:
    """The changed *lines* as coverage counts them: the first line of the
    innermost statement holding each one. coverage.py records a multi-line
    statement under its first line, so line 351 of a comprehension that
    starts on 347 is "347" (found live, 2026-10-20). Blank and comment-only
    lines belong to no statement and drop out."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(lines)
    spans = sorted(
        (
            (node.lineno, node.end_lineno or node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.stmt)
        ),
        key=lambda s: s[1] - s[0],
    )
    text = source.splitlines()
    out = set()
    for line in lines:
        bare = text[line - 1].strip() if 0 < line <= len(text) else ""
        if not bare or bare.startswith("#"):
            continue
        for start, end in spans:  # narrowest first
            if start <= line <= end:
                out.add(start)
                break
    return out


def _defs_touching(source: str, lines: set[int]) -> list[str]:
    """Names of the functions/classes (and methods) whose body holds a changed line."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    defs = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def touches(node) -> bool:
        return bool(set(range(node.lineno, (node.end_lineno or node.lineno) + 1)) & lines)

    names = []
    for node in ast.walk(tree):
        if not isinstance(node, defs) or not touches(node):
            continue
        # A method's class also holds the line; the innermost name is enough.
        inner = any(isinstance(c, defs) and touches(c) for c in ast.walk(node) if c is not node)
        if not inner:
            names.append(node.name)
    return sorted(set(names))


# ── change_explained ─────────────────────────────────────────

_UNDERSTANDING_RE = re.compile(
    r"^#+\s*Understanding\b(.*)", re.IGNORECASE | re.DOTALL | re.MULTILINE
)
_PARTS = {
    "Current behaviour": re.compile(r"current behaviou?r\s*:", re.IGNORECASE),
    "Change": re.compile(r"\bchange\s*:", re.IGNORECASE),
    "Risk": re.compile(r"\brisks?\s*:", re.IGNORECASE),
}
UNDERSTANDING_HINT = (
    "You changed production code. End your reply with a section:\n"
    "## Understanding\n"
    "Current behaviour: what the code did before, in your words.\n"
    "Change: what you changed and why.\n"
    "Risk: what could break, and which test shows it does not.\n"
    "Name every function or class you changed."
)


async def change_explained(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """A production-code change must carry the agent's account of it."""
    prod = production_files(workdir)
    if not prod:
        return True, {"note": "no production code changed"}
    names: list[str] = []
    for rel in prod:
        if rel.endswith(".py"):
            try:
                text = (workdir / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            names += _defs_touching(text, changed_lines(workdir, rel))
    out = ctx.get("output") or ""
    m = _UNDERSTANDING_RE.search(out)
    problems = []
    if not m:
        problems.append("no '## Understanding' section in the reply")
        body = ""
    else:
        body = m.group(1)
        missing = [k for k, rx in _PARTS.items() if not rx.search(body)]
        if missing:
            problems.append(f"the Understanding section lacks: {', '.join(missing)}")
    unnamed = [n for n in dict.fromkeys(names) if body and n not in body]
    if body and unnamed:
        problems.append(f"it does not name: {', '.join(unnamed[:10])}")
    evidence: dict = {"production_files": prod, "changed_defs": names, "problems": problems}
    if problems:
        evidence["hint"] = UNDERSTANDING_HINT
    return not problems, evidence


# ── diff_coverage ────────────────────────────────────────────


def _module_name(rel: str) -> str:
    p = PurePosixPath(rel).with_suffix("")
    parts = list(p.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _test_root(ctx: dict) -> str:
    """The test directory the project's sandbox command runs (e.g. tests/unit):
    tests outside it may need services the network-less sandbox lacks."""
    try:
        argv = shlex.split(ctx.get("sandbox_test_command") or "")
    except ValueError:
        argv = []
    for arg in argv:
        is_path = "/" in arg or arg.startswith("test")
        if is_path and not arg.startswith("-") and "::" not in arg and not arg.endswith(".py"):
            return arg.rstrip("/")
    return "tests"


def related_tests(workdir: Path, prod: list[str], ctx: dict) -> list[str]:
    """Test files, under the project's test root, that import a changed module,
    plus the changed test files themselves."""
    root = _test_root(ctx)
    found: list[str] = []
    for f in _changed_files(workdir):
        rel = str(f.relative_to(workdir))
        if rel.endswith(".py") and _is_test_path(rel) and rel.startswith(root):
            found.append(rel)
    patterns = []
    for rel in prod:
        mod = _module_name(rel)
        if not mod:
            continue
        parent, _, leaf = mod.rpartition(".")
        patterns.append(re.compile(rf"\b(?:from|import)\s+{re.escape(mod)}\b"))
        if parent:
            patterns.append(
                re.compile(rf"\bfrom\s+{re.escape(parent)}\s+import\s+[^\n]*\b{re.escape(leaf)}\b")
            )
    base = workdir / root
    if base.is_dir() and patterns:
        for path in sorted(base.rglob("test_*.py")):
            rel = str(path.relative_to(workdir))
            if rel in found:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(p.search(text) for p in patterns):
                found.append(rel)
            if len(found) >= _MAX_RELATED_TESTS:
                break
    return found


_COVERAGE_SCRIPT = (
    'COVERAGE_FILE=/tmp/.coverage python -m pytest -q -p no:cacheprovider --tb=line -o addopts="" '
    '--cov=. --cov-report=json:/tmp/cov.json "$@" > /tmp/out.txt 2>&1; rc=$?; '
    'echo "@@RC $rc"; tail -c 3000 /tmp/out.txt; echo "@@COV"; cat /tmp/cov.json 2>/dev/null'
)


async def diff_coverage(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Every changed production line must be executed by a test."""
    prod = production_files(workdir)
    if not prod:
        return True, {"note": "no production code changed"}
    py = [f for f in prod if f.endswith(".py")]
    if not py:
        return None, {"note": f"coverage is measured for Python only: {', '.join(prod[:5])}"}
    tests = related_tests(workdir, py, ctx)
    hint = (
        "Add or extend unit tests that run the lines you changed, so the change is "
        "proven, not just plausible."
    )
    if not tests:
        return False, {
            "problems": ["no test imports the changed modules"],
            "changed": py,
            "hint": hint,
        }
    if not sandbox.enabled():
        return None, {"note": "diff coverage needs the docker sandbox"}
    try:
        venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
        res = await sandbox.run(
            ["sh", "-c", _COVERAGE_SCRIPT, "sh", *tests],
            workdir,
            venv=venv,
            timeout=int(ctx.get("sandbox_test_timeout") or 600),
        )
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc)}
    out = res.stdout
    rc_match = re.search(r"@@RC (\d+)", out)
    rc = int(rc_match.group(1)) if rc_match else -1
    log, _, cov_text = out.partition("@@COV")
    if "unrecognized arguments: --cov" in log or "no module named 'pytest_cov'" in log.lower():
        return None, {"note": "pytest-cov is not installed in the project environment"}
    if rc not in (0,):
        return False, {
            "problems": [f"the tests that cover this change fail (exit {rc})"],
            "tests": tests,
            "output": log[-1500:],
            "hint": "Make these tests pass first.",
        }
    try:
        files = json.loads(cov_text.strip() or "{}").get("files", {})
    except json.JSONDecodeError:
        return None, {"note": "coverage report could not be read", "output": log[-500:]}
    covered_total = executable_total = 0
    uncovered: dict[str, list[int]] = {}
    for rel in py:
        report = files.get(rel) or files.get(f"/work/{rel}") or {}
        executed = set(report.get("executed_lines") or [])
        missing = set(report.get("missing_lines") or [])
        try:
            source = (workdir / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            source = ""
        stmts = statement_lines(source, changed_lines(workdir, rel))
        lines = stmts & (executed | missing)
        if not report:
            lines = stmts  # never imported: none of it ran
        executable_total += len(lines)
        hit = lines & executed
        covered_total += len(hit)
        if lines - hit:
            uncovered[rel] = sorted(lines - hit)[:30]
    if executable_total == 0:
        return True, {"note": "no executable lines changed", "tests": tests}
    ratio = covered_total / executable_total
    floor = float(ctx.get("diff_coverage_min") or DIFF_COVERAGE_MIN)
    evidence: dict = {
        "covered": covered_total,
        "changed_lines": executable_total,
        "ratio": round(ratio, 3),
        "required": floor,
        "tests": tests,
    }
    if ratio < floor:
        evidence["uncovered"] = uncovered
        evidence["hint"] = hint
    return ratio >= floor, evidence


# ── tests_catch_mutants ──────────────────────────────────────

_SWAPS: dict[type, type] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.And: ast.Or,
    ast.Or: ast.And,
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv,
}


def _mutation_points(func: ast.AST) -> list[tuple[int, str]]:
    """(walk index, description) of every place in *func* that can be mutated,
    most telling kinds first."""
    points = []
    for i, node in enumerate(ast.walk(func)):
        if isinstance(node, ast.Compare) and type(node.ops[0]) in _SWAPS:
            points.append((0, i, f"line {node.lineno}: `{_op(node.ops[0])}` flipped"))
        elif isinstance(node, ast.BoolOp):
            points.append((0, i, f"line {node.lineno}: `{_op(node.op)}` flipped"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            points.append((1, i, f"line {node.lineno}: `not` removed"))
        elif isinstance(node, ast.Return) and node.value is not None:
            if not (isinstance(node.value, ast.Constant) and node.value.value is None):
                points.append((1, i, f"line {node.lineno}: returns None instead"))
        elif isinstance(node, ast.BinOp) and type(node.op) in _SWAPS:
            points.append((2, i, f"line {node.lineno}: `{_op(node.op)}` swapped"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            points.append((2, i, f"line {node.lineno}: {node.value} flipped"))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            points.append((3, i, f"line {node.lineno}: {node.value} → {node.value + 1}"))
    points.sort()
    return [(i, desc) for _rank, i, desc in points]


def _op(op: ast.AST) -> str:
    return {
        ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.GtE: ">=", ast.Gt: ">", ast.LtE: "<=",
        ast.In: "in", ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not", ast.And: "and",
        ast.Or: "or", ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
    }.get(type(op), type(op).__name__)  # fmt: skip


def _mutate(top: ast.AST, index: int) -> ast.AST | None:
    """A copy of *top* with the node at walk *index* mutated."""
    clone = copy.deepcopy(top)
    for i, node in enumerate(ast.walk(clone)):
        if i != index:
            continue
        if isinstance(node, ast.Compare):
            node.ops[0] = _SWAPS[type(node.ops[0])]()
        elif isinstance(node, ast.BoolOp | ast.BinOp):
            node.op = _SWAPS[type(node.op)]()
        elif isinstance(node, ast.Return):
            node.value = ast.Constant(value=None)
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            node.value = not node.value
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            node.value = node.value + 1
        elif isinstance(node, ast.UnaryOp):
            return _replace_not(clone, node)
        else:
            return None
        return clone
    return None


def _replace_not(clone: ast.AST, target: ast.UnaryOp) -> ast.AST:
    """Drop one ``not``: replace the UnaryOp with its operand in its parent."""
    for parent in ast.walk(clone):
        for field, value in ast.iter_fields(parent):
            if value is target:
                setattr(parent, field, target.operand)
                return clone
            if isinstance(value, list) and target in value:
                value[value.index(target)] = target.operand
                return clone
    return clone


def _test_targets(workdir: Path, tests: list[str]) -> list[tuple[str, str]]:
    """(source file, top-level name) the changed tests import from the project."""
    local = _local_modules(workdir)
    targets: list[tuple[str, str]] = []
    for rel in tests:
        try:
            tree = ast.parse((workdir / rel).read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
                continue
            if node.module.split(".")[0] not in local:
                continue
            base = Path(*node.module.split("."))
            for cand in (
                base.with_suffix(".py"),
                base / "__init__.py",
                Path("src") / base.with_suffix(".py"),
            ):
                if (workdir / cand).is_file():
                    for alias in node.names:
                        targets.append((str(cand), alias.name))
                    break
    return list(dict.fromkeys(targets))


def build_mutants(
    workdir: Path, targets: list[tuple[str, str]], limit: int = MAX_MUTANTS
) -> list[dict]:
    """Mutated copies of the target files, spread across the targets."""
    per_target: list[list[dict]] = []
    for rel, name in targets:
        try:
            text = (workdir / rel).read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        lines = text.splitlines(keepends=True)
        tops = [
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and n.name == name
        ]
        mutants = []
        for top in tops:
            start = min([top.lineno, *(d.lineno for d in top.decorator_list)]) - 1
            end = top.end_lineno or top.lineno
            for index, desc in _mutation_points(top):
                mutated = _mutate(top, index)
                if mutated is None:
                    continue
                try:
                    new = ast.unparse(mutated)
                except Exception:  # noqa: BLE001 - an unprintable mutant is skipped
                    continue
                source = "".join(lines[:start]) + new + "\n" + "".join(lines[end:])
                mutants.append({"file": rel, "source": source, "desc": f"{rel} {name}, {desc}"})
        if mutants:
            per_target.append(mutants)
    chosen: list[dict] = []
    while per_target and len(chosen) < limit:
        for bucket in list(per_target):
            if not bucket:
                per_target.remove(bucket)
                continue
            chosen.append(bucket.pop(0))
            if len(chosen) >= limit:
                break
    return chosen


_MUTANT_RUNNER = r"""
import json, os, shutil, subprocess, sys
src, dst = "/work", "/tmp/w"
shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "node_modules", ".venv", "__pycache__", "*.pyc"))
env = dict(os.environ, PYTHONPATH=f"{dst}:{dst}/src", COVERAGE_PROCESS_START="")
tests = json.load(open("/mutants/tests.json"))
mutants = json.load(open("/mutants/mutants.json"))
argv = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-o", "addopts=", *tests]
def run():
    try:
        return subprocess.run(argv, cwd=dst, env=env, capture_output=True, text=True, timeout=%(timeout)d).returncode
    except subprocess.TimeoutExpired:
        return 124
results = {"baseline": run(), "mutants": []}
if results["baseline"] == 0:
    for m in mutants:
        path = os.path.join(dst, m["file"])
        original = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(m["source"])
        results["mutants"].append({"desc": m["desc"], "rc": run()})
        open(path, "w", encoding="utf-8").write(original)
print("@@MUT " + json.dumps(results))
"""


async def tests_catch_mutants(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """The changed tests must fail when the code they test is made wrong."""
    tests = [
        str(f.relative_to(workdir))
        for f in _changed_files(workdir)
        if f.suffix == ".py" and _is_test_path(str(f.relative_to(workdir)))
    ]
    if not tests:
        return True, {"note": "no changed test files"}
    targets = _test_targets(workdir, tests)
    mutants = build_mutants(workdir, targets)
    if not mutants:
        return True, {"note": "nothing in the tested code to mutate", "targets": targets}
    if not sandbox.enabled():
        return None, {"note": "the mutation check needs the docker sandbox"}
    with tempfile.TemporaryDirectory(prefix="lg_mutants_") as tmp:
        Path(tmp, "tests.json").write_text(json.dumps(tests))
        Path(tmp, "mutants.json").write_text(json.dumps(mutants))
        Path(tmp, "run.py").write_text(_MUTANT_RUNNER % {"timeout": MUTANT_TIMEOUT})
        Path(tmp).chmod(0o755)
        for p in Path(tmp).iterdir():
            p.chmod(0o644)
        try:
            venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
            res = await sandbox.run(
                ["python", "/mutants/run.py"],
                workdir,
                venv=venv,
                timeout=120 + MUTANT_TIMEOUT * (len(mutants) + 1),
                extra_ro={Path(tmp): "/mutants"},
                tmp_size="2g",
            )
        except sandbox.SandboxUnavailableError as exc:
            return None, {"note": str(exc)}
    m = re.search(r"@@MUT (\{.*\})", res.stdout)
    if not m:
        return None, {"note": "the mutation run gave no result", "stderr": res.stderr[-800:]}
    results = json.loads(m.group(1))
    if results["baseline"] != 0:
        return False, {
            "problems": [
                f"the changed tests fail on the unmutated code (exit {results['baseline']})"
            ],
            "tests": tests,
        }
    runs = results["mutants"]
    survived = [r["desc"] for r in runs if r["rc"] == 0]
    killed = len(runs) - len(survived)
    ratio = killed / len(runs) if runs else 1.0
    floor = float(ctx.get("mutation_min_kill") or MUTATION_MIN_KILL)
    evidence: dict = {
        "mutants": len(runs),
        "killed": killed,
        "ratio": round(ratio, 3),
        "required": floor,
        "tests": tests,
    }
    if ratio < floor:
        evidence["survived"] = survived
        evidence["hint"] = (
            "These deliberate bugs in the code under test went unnoticed by your tests. "
            "Add assertions on the exact results of each branch so a wrong result fails."
        )
    return ratio >= floor, evidence


# ── types_clean_diff ─────────────────────────────────────────

_MYPY_LINE = re.compile(r"^(?P<file>[^:\n]+\.py):(?P<line>\d+):(?:\d+:)? error: (?P<msg>.*)$")


async def types_clean_diff(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """mypy may not report an error on a changed line of production code."""
    py = [f for f in production_files(workdir) if f.endswith(".py")]
    if not py:
        return True, {"note": "no Python production code changed"}
    if not sandbox.enabled():
        return None, {"note": "the type check needs the docker sandbox"}
    argv = [
        "sh",
        "-c",
        'command -v mypy >/dev/null || { echo "@@NOMYPY"; exit 0; }; '
        "mypy --python-executable /venv/bin/python --cache-dir /tmp/mypy "
        "--ignore-missing-imports --follow-imports=silent --no-error-summary "
        '--show-column-numbers --no-color-output --show-error-codes "$@"; echo "@@RC $?"',
        "sh",
        *py,
    ]
    try:
        venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
        res = await sandbox.run(argv, workdir, venv=venv, timeout=300)
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc)}
    if "@@NOMYPY" in res.stdout:
        return None, {"note": "mypy is not installed in the verifier image"}
    errors = []
    lines_by_file = {rel: changed_lines(workdir, rel) for rel in py}
    for row in res.stdout.splitlines():
        m = _MYPY_LINE.match(row.strip())
        if not m:
            continue
        rel = m.group("file").removeprefix("/work/")
        if int(m.group("line")) in lines_by_file.get(rel, set()):
            errors.append(f"{rel}:{m.group('line')}: {m.group('msg')}")
    evidence: dict = {"checked": py, "errors": errors[:30]}
    if errors:
        evidence["hint"] = "Fix these type errors on the lines you changed."
    return not errors, evidence
