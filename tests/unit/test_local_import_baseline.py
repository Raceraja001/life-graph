"""Function-local ``life_graph`` imports may not grow (audit M13 ratchet).

On 2026-11-19 the package held 1,505 imports inside functions. Some are
deliberate (heavy optional dependencies, startup steps that import what they
wire), but many exist only to dodge an import cycle, and every one hides an
edge of the dependency graph from a reader and from tooling. Rewriting them
all at once would be a large, risky diff, so this is a ratchet instead: the
count per top-level package may go down, never up.

When a change removes some, lower the number here in the same commit (the
test says which). When a change genuinely needs a new one, prefer a
module-level import; the layer contracts (``[tool.importlinter]`` in
pyproject.toml) say which directions are allowed.

Counted: ``import life_graph...`` / ``from life_graph... import`` / relative
``from . import`` statements nested in a ``def`` or ``async def`` body,
anywhere in ``life_graph/``.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "life_graph"

# Per top-level package (or module) under life_graph/, 2026-11-20 after the
# p2-boundaries batch removed the cycle-dodging imports it made unnecessary:
# storage 10 -> 7 (postgres.py reached into api.responses and
# services.embeddings), api 268 -> 261 (sessions/memories logic moved to
# services), services/claude_code_sessions.py and services/memory/page.py no
# longer import routers. services grew by the helpers moved into it verbatim
# (services/memory/transitions.py) -- net 1529 -> 1523 on 18b9e4e; 1532 after rebasing onto
# c626ddd, whose own commits added 9 (api 3, autonomy 2, kernel 4).
# autonomy 57 -> 53: PR #306 (p2appr) hoisted the autonomy-queue service's
# model imports to module level.
# p2db (shared arq pool): main 47 -> 46, workers 106 -> 104 (per-call
# create_pool sites removed); runtime 49 -> 50 for get_arq_pool's
# workers.settings import, which must stay local (test_runtime_module.py:
# importing runtime may not load the worker/API packages). Net -2.
BASELINE = {
    "agents": 4,
    "api": 263,
    "autonomy": 53,
    "cli": 23,
    "cold_start": 6,
    "connectors": 26,
    "core": 26,
    "drivers": 54,
    "extraction": 10,
    "integrations": 25,
    "jobs": 5,
    "kernel": 24,
    "main": 46,
    "mcp_server": 1,
    "runtime": 50,
    "self_improving": 59,
    "services": 610,
    "storage": 7,
    "tools": 101,
    "watchers": 28,
    "workers": 104,
}


def _is_life_graph_import(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(a.name == "life_graph" or a.name.startswith("life_graph.") for a in node.names)
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return True  # relative: inside the package by definition
        mod = node.module or ""
        return mod == "life_graph" or mod.startswith("life_graph.")
    return False


def _local_imports(tree: ast.AST) -> int:
    count = 0

    def visit(node: ast.AST, in_function: bool) -> None:
        nonlocal count
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, True)
            else:
                if in_function and _is_life_graph_import(child):
                    count += 1
                visit(child, in_function)

    visit(tree, False)
    return count


def count_local_imports(root: Path = ROOT) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).parts
        package = rel[0].removesuffix(".py")
        n = _local_imports(ast.parse(path.read_text(encoding="utf-8")))
        if n:
            counts[package] += n
    return counts


def test_function_local_imports_do_not_grow():
    counts = count_local_imports()
    grew = {
        pkg: (BASELINE.get(pkg, 0), n)
        for pkg, n in sorted(counts.items())
        if n > BASELINE.get(pkg, 0)
    }
    assert not grew, (
        "New function-local life_graph imports (package: (baseline, now)). Import at "
        f"module level instead, or justify and raise the baseline: {grew}"
    )


def test_the_baseline_is_lowered_when_imports_go():
    """Keeps the ratchet tight: a removal must also lower the number."""
    counts = count_local_imports()
    stale = {
        pkg: (n, counts.get(pkg, 0))
        for pkg, n in sorted(BASELINE.items())
        if counts.get(pkg, 0) < n
    }
    assert not stale, f"Lower BASELINE in this file (package: (baseline, now)): {stale}"


def test_the_counter_counts_only_function_local_package_imports():
    src = (
        "import life_graph.config\n"  # module level: not counted
        "from life_graph.core import tenant\n"
        "import json\n"
        "def f():\n"
        "    from life_graph.storage import database\n"  # 1
        "    import json\n"  # not life_graph
        "    if True:\n"
        "        import life_graph.runtime\n"  # 2
        "    def g():\n"
        "        from . import sibling\n"  # 3 (relative)
        "class C:\n"
        "    from life_graph import api\n"  # class body, not a function: not counted
        "    async def m(self):\n"
        "        from life_graph.services import lead\n"  # 4
    )
    assert _local_imports(ast.parse(src)) == 4
