#!/usr/bin/env python3
"""Count broad ``except`` handlers in life_graph/ by what they do (audit L7/F12).

A *broad* handler is a bare ``except:``, ``except Exception`` or
``except BaseException`` (alone or inside a tuple). Each one is put in exactly
one category, checked in this order:

* ``reraise``     -- the body contains a ``raise`` (bare, translated or chained).
* ``logged_tb``   -- it logs with a traceback: ``logger.exception(...)``, any
                     logging call with a truthy ``exc_info=``, or
                     ``traceback.print_exc()/format_exc()``.
* ``logged_no_tb``-- it logs (debug/info/warning/error/critical/log) but
                     without a traceback.
* ``silent``      -- no log and no raise, and the body only passes, continues,
                     breaks, returns or assigns a plain default.
* ``other``       -- everything else (records the error in a result, retries,
                     returns an error response, calls a handler ...).

``silent`` and ``logged_no_tb`` sites are additionally *documented* when the
handler carries a justification comment on the ``except`` line or inside
its body: ``# best-effort: <why>``, ``# fail-open: <why>``,
``# expected: <why>`` or ``# noqa: BLE001 - <why>`` (the form already used
across the code base). That is the convention for deliberate fail-open /
parse-fallback sites: say why swallowing the error is right.

The ratchet (tests/unit/test_exception_audit.py, baseline in
.github/exception-audit-baseline.json) checks that the number of
*undocumented* ``silent`` and ``logged_no_tb`` handlers per top-level package
does not go up.

Usage:
    python scripts/exception_audit.py              # table per package
    python scripts/exception_audit.py --sites silent   # list sites of a category
    python scripts/exception_audit.py --check      # compare with the baseline (exit 1 if worse)
    python scripts/exception_audit.py --update     # rewrite the baseline to the current counts
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "life_graph"
BASELINE = ROOT / ".github" / "exception-audit-baseline.json"

CATEGORIES = ("reraise", "logged_tb", "logged_no_tb", "silent", "other")
RATCHETED = ("silent", "logged_no_tb")

BROAD_NAMES = {"Exception", "BaseException"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "log", "exception"}
JUSTIFICATION = re.compile(
    r"#.*\b(?:best[- ]effort|fail[- ]open)\b"  # anywhere in a comment
    r"|#\s*expected:"  # "# expected: <why>"
    r"|noqa:\s*BLE001\s*[-:—–]+\s*\S",  # "# noqa: BLE001 - <why>"
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Site:
    path: str  # relative to the repo root
    line: int
    category: str
    documented: bool

    @property
    def package(self) -> str:
        parts = Path(self.path).parts  # life_graph/<pkg>/...
        return parts[1].removesuffix(".py")


def _is_broad(node: ast.expr | None) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in BROAD_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in BROAD_NAMES
    if isinstance(node, ast.Tuple):
        return any(_is_broad(elt) for elt in node.elts)
    return False


def _walk_body(stmts: list[ast.stmt]):
    """ast.walk over the handler body, not descending into nested scopes."""
    stack: list[ast.AST] = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            stack.append(child)


def _receiver_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):  # logging.getLogger(__name__).warning(...)
        return _receiver_name(node.func)
    return ""


def _is_log_call(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in LOG_METHODS:
        return False
    name = _receiver_name(func.value).lower()
    return "log" in name  # logger, log, _log, self._logger, logging, getLogger


def _has_traceback(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "exception" and _is_log_call(call):
        return True
    for kw in call.keywords:
        if kw.arg == "exc_info":
            return not (isinstance(kw.value, ast.Constant) and not kw.value.value)
    return False


def _is_traceback_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in {"print_exc", "format_exc", "print_exception", "format_exception"}
        and _receiver_name(func.value) == "traceback"
    )


def _is_plain_value(node: ast.expr | None) -> bool:
    if node is None or isinstance(node, (ast.Constant, ast.Name, ast.Attribute)):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    if isinstance(node, ast.UnaryOp):
        return _is_plain_value(node.operand)
    if isinstance(node, ast.Call):  # dict() / list() / set() / tuple()
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in {"dict", "list", "set", "tuple", "str"}
            and not node.args
            and not node.keywords
        )
    return False


def _is_silent_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
        return True
    if isinstance(stmt, ast.Return):
        return _is_plain_value(stmt.value)
    if isinstance(stmt, ast.Expr):
        return isinstance(stmt.value, ast.Constant)
    if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
        return _is_plain_value(stmt.value)
    return False


def classify(handler: ast.ExceptHandler) -> str:
    nodes = list(_walk_body(handler.body))
    if any(isinstance(n, ast.Raise) for n in nodes):
        return "reraise"
    calls = [n for n in nodes if isinstance(n, ast.Call)]
    if any((_is_log_call(c) and _has_traceback(c)) or _is_traceback_call(c) for c in calls):
        return "logged_tb"
    if any(_is_log_call(c) for c in calls):
        return "logged_no_tb"
    if all(_is_silent_stmt(s) for s in handler.body):
        return "silent"
    return "other"


def _comment_lines(source: str) -> dict[int, str]:
    comments: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comments[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError):
        pass  # best-effort: a file that fails to tokenize has no comments to read
    return comments


def scan_file(path: Path, root: Path = ROOT) -> list[Site]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    comments = _comment_lines(source)
    rel = path.relative_to(root).as_posix()
    sites: list[Site] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not _is_broad(node.type):
            continue
        category = classify(node)
        end = node.end_lineno or node.lineno
        documented = any(
            JUSTIFICATION.search(comments.get(line, "")) for line in range(node.lineno, end + 1)
        )
        sites.append(Site(rel, node.lineno, category, documented))
    return sites


def scan(package: Path = PACKAGE, root: Path = ROOT) -> list[Site]:
    sites: list[Site] = []
    for path in sorted(package.rglob("*.py")):
        sites.extend(scan_file(path, root))
    return sites


def table(sites: list[Site]) -> dict[str, Counter[str]]:
    """package -> Counter of categories (plus ``<cat>_documented``)."""
    out: dict[str, Counter[str]] = {}
    for site in sites:
        counter = out.setdefault(site.package, Counter())
        counter[site.category] += 1
        if site.category in RATCHETED and site.documented:
            counter[f"{site.category}_documented"] += 1
    return dict(sorted(out.items()))


def ratchet_counts(sites: list[Site]) -> dict[str, dict[str, int]]:
    """package -> {silent, logged_no_tb} counting only undocumented sites."""
    out: dict[str, dict[str, int]] = {}
    for site in sites:
        if site.category in RATCHETED and not site.documented:
            pkg = out.setdefault(site.package, dict.fromkeys(RATCHETED, 0))
            pkg[site.category] += 1
    return dict(sorted(out.items()))


def read_baseline() -> dict[str, dict[str, int]]:
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    return data["packages"]


def write_baseline(counts: dict[str, dict[str, int]]) -> None:
    data = {
        "_comment": (
            "Undocumented broad excepts per life_graph package that swallow the error "
            "silently or log it without a traceback. May go down, never up. "
            "Regenerate with: python scripts/exception_audit.py --update"
        ),
        "packages": counts,
    }
    BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare(
    current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]
) -> tuple[list[str], list[str]]:
    """(regressions, improvements) as human-readable lines."""
    worse: list[str] = []
    better: list[str] = []
    for pkg in sorted(set(current) | set(baseline)):
        for cat in RATCHETED:
            now = current.get(pkg, {}).get(cat, 0)
            was = baseline.get(pkg, {}).get(cat, 0)
            if now > was:
                worse.append(f"{pkg}: {cat} {was} -> {now}")
            elif now < was:
                better.append(f"{pkg}: {cat} {was} -> {now}")
    return worse, better


def _print_table(sites: list[Site]) -> None:
    rows = table(sites)
    cols = [*CATEGORIES, "total"]
    print(f"{'package':<16}" + "".join(f"{c:>14}" for c in cols))
    totals: Counter[str] = Counter()
    for pkg, counter in rows.items():
        cells = []
        for cat in CATEGORIES:
            cell = str(counter[cat])
            if cat in RATCHETED and counter[f"{cat}_documented"]:
                cell += f" ({counter[f'{cat}_documented']}d)"
            cells.append(cell)
        total = sum(counter[c] for c in CATEGORIES)
        cells.append(str(total))
        totals.update(counter)
        print(f"{pkg:<16}" + "".join(f"{c:>14}" for c in cells))
    grand = sum(totals[c] for c in CATEGORIES)
    cells = []
    for cat in CATEGORIES:
        cell = str(totals[cat])
        if cat in RATCHETED and totals[f"{cat}_documented"]:
            cell += f" ({totals[f'{cat}_documented']}d)"
        cells.append(cell)
    print(f"{'TOTAL':<16}" + "".join(f"{c:>14}" for c in [*cells, str(grand)]))
    if grand:
        print(
            "share: "
            + ", ".join(f"{c} {100 * totals[c] / grand:.1f}%" for c in CATEGORIES)
            + "   ((Nd) = N of them documented with a # best-effort/fail-open/expected comment)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if worse than the baseline")
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument("--json", action="store_true", help="print the per-package table as JSON")
    parser.add_argument("--sites", choices=CATEGORIES, help="list the sites of one category")
    parser.add_argument(
        "--undocumented", action="store_true", help="with --sites: only undocumented ones"
    )
    args = parser.parse_args(argv)

    sites = scan()
    if args.sites:
        for site in sites:
            if site.category == args.sites and not (args.undocumented and site.documented):
                mark = " [documented]" if site.documented else ""
                print(f"{site.path}:{site.line}{mark}")
        return 0
    if args.update:
        write_baseline(ratchet_counts(sites))
        print(f"wrote {BASELINE.relative_to(ROOT)}")
        return 0
    if args.check:
        worse, better = compare(ratchet_counts(sites), read_baseline())
        for line in better:
            print(f"improved (lower the baseline with --update): {line}")
        for line in worse:
            print(f"REGRESSION: {line}", file=sys.stderr)
        return 1 if worse else 0
    if args.json:
        print(json.dumps({k: dict(v) for k, v in table(sites).items()}, indent=2))
        return 0
    _print_table(sites)
    return 0


if __name__ == "__main__":
    sys.exit(main())
