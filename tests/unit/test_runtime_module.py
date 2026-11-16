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


def test_no_code_outside_the_api_imports_it_through_the_api():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "life_graph"
    offenders = []
    for p in root.rglob("*.py"):
        rel = p.relative_to(root).as_posix()
        if rel.startswith("api/"):
            continue
        text = p.read_text(encoding="utf-8")
        if "from life_graph.api.dependencies import" in text or (
            "from life_graph.api.jarvis import" in text
        ):
            offenders.append(rel)
    assert offenders == [], f"import life_graph.runtime / a service instead: {offenders}"
