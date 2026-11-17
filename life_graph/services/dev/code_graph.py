"""A small Python code graph, so the dev-agent sees a change's reach first.

Before a dispatch, the symbols an instruction names (backticked, snake_case,
CamelCase, Class.method) are looked up in the task's own worktree: where each
is defined, who calls it, and what it calls. That goes into the instruction,
so an agent asked to change ``track_record`` knows the callers that depend
on its return shape before it edits it, instead of finding out from a
failing test (or not at all).

Idea from FORGE's tree-sitter knowledge graph, narrowed to what this
pipeline needs: stdlib ``ast`` only (no new dependency; life-graph's
projects are Python), built fresh from the worktree each dispatch rather
than persisted, so it can never be stale. Call resolution is by name, not
scope-aware -- the same documented limitation FORGE accepts. When a name is
ambiguous, every candidate is listed rather than guessing one.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from life_graph.cold_start.code_analyzer import VENDORED_DIRS

logger = logging.getLogger(__name__)

_MAX_FILES = 3000
_MAX_FILE_BYTES = 400_000
_MAX_SYMBOLS = 3
_MAX_DEFINITIONS_PER_SYMBOL = 3
_MAX_CALLERS = 6
_MAX_CALLEES = 8
_MAX_CONTEXT_CHARS = 3000

_BACKTICK_RE = re.compile(r"`([A-Za-z_][\w.]*)(?:\(\))?`")
_SNAKE_RE = re.compile(r"\b([a-z_][a-z0-9]*_[a-z0-9_]+)\b")
_CAMEL_RE = re.compile(r"\b([A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*)\b")
_DOTTED_RE = re.compile(r"\b([A-Z]\w*\.[a-z_]\w*)\b")
# Words that look like code but are path/extension noise in instructions.
_IGNORE = {"tests", "test", "py", "src"}


@dataclass
class Definition:
    qualname: str
    name: str
    file: str
    line: int
    calls: list[str] = field(default_factory=list)


@dataclass
class CallSite:
    callee: str
    caller: str
    file: str
    line: int


@dataclass
class CodeGraph:
    definitions: dict[str, list[Definition]] = field(default_factory=dict)
    calls: dict[str, list[CallSite]] = field(default_factory=dict)

    def find(self, symbol: str) -> list[Definition]:
        """Definitions matching a simple name or a ``Class.method`` qualname."""
        name = symbol.rsplit(".", 1)[-1]
        candidates = self.definitions.get(name, [])
        if "." in symbol:
            qualified = [d for d in candidates if d.qualname.endswith(symbol)]
            return qualified or candidates
        return candidates


def _callee_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, graph: CodeGraph, file: str, module: str) -> None:
        self.graph = graph
        self.file = file
        self.stack: list[str] = [module]
        self.current: list[Definition] = []

    def _define(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        qualname = ".".join([*self.stack, node.name])
        definition = Definition(qualname, node.name, self.file, node.lineno)
        self.graph.definitions.setdefault(node.name, []).append(definition)
        self.stack.append(node.name)
        self.current.append(definition)
        self.generic_visit(node)
        self.current.pop()
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._define(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._define(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._define(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _callee_name(node)
        if name:
            caller = self.current[-1].qualname if self.current else self.stack[0]
            self.graph.calls.setdefault(name, []).append(
                CallSite(name, caller, self.file, node.lineno)
            )
            if self.current and name not in self.current[-1].calls:
                self.current[-1].calls.append(name)
        self.generic_visit(node)


def _python_files(root: Path) -> list[Path]:
    """Python files under *root*, pruning vendored/dot dirs DURING the walk.

    Filtering after a full ``rglob`` still walks every file in
    ``node_modules`` and ``.venv`` first -- on a DrvFs-mounted checkout that
    alone took most of a minute for a repo with ~700 Python files.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in VENDORED_DIRS and not d.startswith(".") and not d.endswith(".egg-info")
        )
        out.extend(Path(dirpath) / f for f in sorted(filenames) if f.endswith(".py"))
        if len(out) >= _MAX_FILES:
            logger.info("code graph: stopped at %d files", _MAX_FILES)
            return out[:_MAX_FILES]
    return out


def build_graph(root: Path) -> CodeGraph:
    """Index every Python file under *root* (vendored dirs skipped)."""
    graph = CodeGraph()
    for path in _python_files(root):
        rel = path.relative_to(root)
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            continue
        module = ".".join(rel.with_suffix("").parts)
        _Visitor(graph, rel.as_posix(), module).visit(tree)
    return graph


def mentioned_symbols(instruction: str) -> list[str]:
    """Code-looking identifiers in an instruction, most explicit first."""
    found: list[str] = []
    for regex in (_BACKTICK_RE, _DOTTED_RE, _CAMEL_RE, _SNAKE_RE):
        for match in regex.finditer(instruction or ""):
            token = match.group(1).strip(".")
            if token and token.lower() not in _IGNORE and token not in found:
                found.append(token)
    return found


def _is_test_file(file: str) -> bool:
    parts = file.split("/")
    return parts[0] == "tests" or parts[-1].startswith("test_") or parts[-1] == "conftest.py"


def _defined_outside_tests(graph: CodeGraph, name: str) -> bool:
    return any(not _is_test_file(d.file) for d in graph.definitions.get(name, []))


def _callers(graph: CodeGraph, definitions: list[Definition]) -> list[CallSite]:
    """One row per calling function, real code before tests."""
    own = {d.qualname for d in definitions}
    seen: set[str] = set()
    rows: list[CallSite] = []
    for site in graph.calls.get(definitions[0].name, []):
        if site.caller in own or site.caller in seen:
            continue
        seen.add(site.caller)
        rows.append(site)
    return sorted(rows, key=lambda s: _is_test_file(s.file))


def context_for(graph: CodeGraph, instruction: str) -> str:
    """The definitions, callers and callees of symbols the instruction names."""
    blocks: list[str] = []
    for symbol in mentioned_symbols(instruction):
        definitions = graph.find(symbol)
        if not definitions:
            continue
        lines = [f"### `{symbol}`"]
        if len(definitions) > 1:
            lines.append(
                f"{len(definitions)} definitions share this name (calls resolved by name):"
            )
        for d in definitions[:_MAX_DEFINITIONS_PER_SYMBOL]:
            lines.append(f"- defined: `{d.qualname}` at {d.file}:{d.line}")
            # Only callees defined in real code: a method name that resolves
            # only to a test fake (execute, scalar_one_or_none) is noise.
            callees = [c for c in d.calls if c != d.name and _defined_outside_tests(graph, c)]
            if callees:
                lines.append(f"  - calls: {', '.join(f'`{c}`' for c in callees[:_MAX_CALLEES])}")
        callers = _callers(graph, definitions)
        if callers:
            lines.append(f"- called from ({len(callers)}):")
            lines.extend(f"  - `{c.caller}` at {c.file}:{c.line}" for c in callers[:_MAX_CALLERS])
            if len(callers) > _MAX_CALLERS:
                lines.append(f"  - ... and {len(callers) - _MAX_CALLERS} more")
        else:
            lines.append("- no callers found in this project")
        blocks.append("\n".join(lines))
        if len(blocks) >= _MAX_SYMBOLS:
            break
    text = "\n\n".join(blocks)
    return text[:_MAX_CONTEXT_CHARS]
