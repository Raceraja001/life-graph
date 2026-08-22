"""Static checks that ORM usage names real columns.

Three production bugs were found by scans of this shape, all in modules with
no coverage, all of which would only fail at the moment the code path ran:

  Preference.reinforced_count      constructor kwarg that is a Memory column
  SharedContext.context_type       column is content_type
  WatcherRun.events_created        column is events_generated

These run without a database and therefore cover the parts of the package
that tests never execute — which is precisely where such bugs survive.

Note the model registry is built after importing **every** module. An earlier
version of this scan imported only ``life_graph.models.db``, which registers
43 of the 49 mapped classes; the 6 declared in ``watchers/models.py`` were
silently skipped as "unknown model", and that is how the WatcherRun bug
survived a scan that reported clean.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import pathlib
import warnings

import pytest

import life_graph.models.db  # noqa: F401  - registers the core mappers
from life_graph.models.db import Base

_ROOT = pathlib.Path(life_graph.models.db.__file__).resolve().parents[1]


def _import_everything() -> None:
    """Import every module so all Base subclasses register their mappers."""
    warnings.filterwarnings("ignore")
    for path in sorted(_ROOT.rglob("*.py")):
        rel = path.relative_to(_ROOT.parent)
        parts = rel.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        # Optional deps (dspy, gitpython, ...) may be absent; a module that
        # cannot import simply contributes no mappers.
        with contextlib.suppress(Exception):
            importlib.import_module(".".join(parts))


@pytest.fixture(scope="module")
def models() -> dict[str, set[str]]:
    _import_everything()
    registry = {
        mapper.class_.__name__: {attr.key for attr in mapper.attrs}
        for mapper in Base.registry.mappers
    }
    assert len(registry) >= 49, (
        f"only {len(registry)} mappers registered — the scan would silently "
        "skip models it cannot resolve, which is how a real bug was missed"
    )
    return registry


@pytest.fixture(scope="module")
def sources() -> list[tuple[pathlib.Path, ast.Module]]:
    out = []
    for path in sorted(_ROOT.rglob("*.py")):
        try:
            out.append((path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))
        except SyntaxError:
            continue
    return out


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(_ROOT.parent))


def test_update_values_keys_are_real_columns(models, sources):
    """`update(Model).where(...).values(bogus=...)` raises only when executed."""
    bad: list[str] = []

    for path, tree in sources:
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "values"
            ):
                continue

            # Walk back down the chained call to find update(Model)/insert(Model)
            cur = node.func.value
            model = None
            while isinstance(cur, ast.Call):
                fn = cur.func
                if isinstance(fn, ast.Name) and fn.id in ("update", "insert") and cur.args:
                    arg = cur.args[0]
                    if isinstance(arg, ast.Name):
                        model = arg.id
                    break
                if isinstance(fn, ast.Attribute):
                    cur = fn.value
                else:
                    break

            if model is None or model not in models:
                continue

            for kw in node.keywords:
                if kw.arg and kw.arg not in models[model]:
                    bad.append(f"{_rel(path)}:{node.lineno} {model}.values({kw.arg}=...)")

    assert not bad, "values() keys that are not columns:\n  " + "\n  ".join(bad)


def test_constructor_kwargs_are_real_columns(models, sources):
    """`Model(bogus=...)` raises TypeError only when constructed."""
    bad: list[str] = []

    for path, tree in sources:
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in models
            ):
                continue
            attrs = models[node.func.id]
            for kw in node.keywords:
                if kw.arg and kw.arg not in attrs:
                    bad.append(f"{_rel(path)}:{node.lineno} {node.func.id}({kw.arg}=...)")

    assert not bad, "constructor kwargs that are not columns:\n  " + "\n  ".join(bad)
