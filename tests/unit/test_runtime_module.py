"""life_graph.runtime holds the shared service providers; the old name aliases it.

The providers lived in life_graph.api.dependencies, so code below the API
(services, workers, tools) imported the API package -- and with it the
FastAPI routers -- just to reach the store. They now live in
life_graph.runtime, and life_graph.api.dependencies IS that module.

It must stay the same module object, not a re-export: tests patch
``dependencies.get_store`` and friends, and with two module objects those
patches would miss every caller that imports life_graph.runtime.
"""

import subprocess
import sys


def test_the_old_name_is_the_same_module():
    import life_graph.api as api_pkg
    import life_graph.api.dependencies as old
    import life_graph.runtime as runtime

    assert old is runtime
    assert api_pkg.dependencies is runtime


def test_a_patch_through_the_old_name_reaches_runtime_callers(monkeypatch):
    import life_graph.api.dependencies as old
    import life_graph.runtime as runtime

    sentinel = object()
    monkeypatch.setattr(old, "get_store", lambda: sentinel)

    assert runtime.get_store() is sentinel


def test_importing_runtime_does_not_load_the_api_package():
    # A fresh interpreter: this test process has long since imported the API.
    code = (
        "import sys, life_graph.runtime; "
        "print(sorted(m for m in sys.modules if m.startswith('life_graph.api')))"
    )
    out = (
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        .stdout.strip()
        .splitlines()[-1]
    )
    assert out == "[]"


def _api_imports(rel: str, tree) -> list[str]:
    """Every import of ``life_graph.api`` in one module, at any depth (AST).

    Covers ``import life_graph.api.x``, ``from life_graph.api(.x) import ...``,
    ``from life_graph import api`` and relative imports that resolve into the
    API package -- function-local ones included, which a text grep for one
    module name (this guard's first version) missed: storage/postgres.py,
    services/claude_code_sessions.py and services/memory/page.py all reached
    into routers that way (audit M12).
    """
    import ast

    package = ["life_graph", *rel.split("/")[:-1]]
    found = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            names = [mod] + [f"{mod}.{a.name}" for a in node.names]
        for name in names:
            if name == "life_graph.api" or name.startswith("life_graph.api."):
                found.append((node.lineno, f"{rel}:{node.lineno} {name}"))
                break
    return [text for _, text in sorted(found)]


# What legitimately composes the HTTP app: the API package itself, main.py
# (mounts every router), and the feature routers that live beside their
# feature (autonomy/*/router.py, self_improving/router.py) -- they ARE the
# API layer and use its response envelope and auth helpers.
def _may_import_the_api(rel: str) -> bool:
    return rel.startswith("api/") or rel == "main.py" or rel.endswith("/router.py")


def test_no_code_below_the_api_imports_the_api():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "life_graph"
    offenders = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root).as_posix()
        if _may_import_the_api(rel):
            continue
        offenders += _api_imports(rel, ast.parse(p.read_text(encoding="utf-8")))
    assert offenders == [], (
        f"import life_graph.runtime, life_graph.core.pagination or a service instead: {offenders}"
    )


def test_the_guard_sees_function_local_and_relative_imports():
    import ast

    src = (
        "def f():\n"
        "    from life_graph.api.responses import decode_cursor\n"
        "def g():\n"
        "    from life_graph import api\n"
        "from ..api import sessions\n"
        "import life_graph.api.memories\n"
        "from life_graph.apiary import x\n"  # not the API package
    )
    got = _api_imports("services/x.py", ast.parse(src))
    assert [g.split(" ")[0] for g in got] == [
        "services/x.py:2",
        "services/x.py:4",
        "services/x.py:5",
        "services/x.py:6",
    ]


def test_importing_the_lower_layers_does_not_load_the_api_package():
    # Fresh interpreter, as above: the modules that used to reach into routers.
    code = (
        "import sys, life_graph.storage.postgres, life_graph.storage.hybrid, "
        "life_graph.services.claude_code_sessions, life_graph.services.memory.page, "
        "life_graph.services.session_lifecycle, life_graph.services.memory.transitions; "
        "print(sorted(m for m in sys.modules if m.startswith('life_graph.api')))"
    )
    out = (
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        .stdout.strip()
        .splitlines()[-1]
    )
    assert out == "[]"
