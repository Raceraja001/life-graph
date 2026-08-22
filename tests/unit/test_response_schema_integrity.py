"""Response schemas must be able to read the models they serialize.

A ``model_config = ConfigDict(from_attributes=True)`` schema pulls each field
off an ORM row by name. When no such attribute exists Pydantic does not
complain — it falls back to the field default, so the endpoint returns 200
with a plausible-looking lie. Where the field is *required* there is no
default, and the endpoint 500s instead, but only once the table has a row.

Both outcomes shipped:

    NotificationResponse.channel_type/title   null for every row
    WatcherRunResponse.events_created         0 for every run
    WatchEventResponse.acknowledged           false for acknowledged events
    WatchEventResponse.retry_count            0, no such concept on the model
    TechRadarResponse.relevance_score         null for every article
    TechRadarResponse.published_at            null, never stored at all
    TechRadarResponse.created_at              REQUIRED -> 500 with any data
    NotificationChannelResponse.name          null; create silently dropped it

Pairing is per function, not per file: a schema is checked only against models
selected in the same function body. File-level pairing reported 61 hits, of
which 55 were schemas that merely shared a module with an unrelated model.

This checks that a *name* resolves. It cannot see type mismatches — the JSONB
``WatchEvent.details`` reaching a ``str | None`` field was a real 500 that
this scan passes clean. Integration tests that insert a row cover that.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import pathlib
import sys
import warnings

import pytest
from pydantic import BaseModel

import life_graph.models.db  # noqa: F401  - registers the core mappers
from life_graph.models.db import Base

_ROOT = pathlib.Path(life_graph.models.db.__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def loaded() -> tuple[dict, dict]:
    """Import everything, then map model name -> (class, attribute names)."""
    warnings.filterwarnings("ignore")
    for path in sorted(_ROOT.rglob("*.py")):
        parts = path.relative_to(_ROOT.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        with contextlib.suppress(Exception):
            importlib.import_module(".".join(parts))

    classes = {m.class_.__name__: m.class_ for m in Base.registry.mappers}
    attrs = {n: {a.key for a in c.__mapper__.attrs} for n, c in classes.items()}
    assert len(classes) >= 49, (
        f"only {len(classes)} mappers registered — an under-loaded registry "
        "makes this scan silently skip models"
    )
    return classes, attrs


def _find_schema(name: str):
    for module in list(sys.modules.values()):
        obj = getattr(module, name, None)
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__name__ == name:
            return obj
    return None


def _accepted_names(field_name: str, info) -> set[str]:
    names = {field_name}
    alias = info.validation_alias
    if alias is not None:
        names |= set(getattr(alias, "choices", []) or []) or {str(alias)}
    if info.alias:
        names.add(info.alias)
    return names


def test_every_response_field_resolves_on_its_model(loaded):
    classes, attrs = loaded
    bad: list[str] = []

    for path in sorted(_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue

        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue

            selected: set[str] = set()
            validated: set[tuple[str, int]] = set()
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "select"
                ):
                    selected |= {
                        a.id for a in node.args if isinstance(a, ast.Name) and a.id in classes
                    }
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "model_validate"
                    and isinstance(node.func.value, ast.Name)
                ):
                    validated.add((node.func.value.id, node.lineno))

            if not selected or not validated:
                continue

            for schema_name, lineno in validated:
                schema = _find_schema(schema_name)
                if schema is None or not schema.model_config.get("from_attributes"):
                    continue

                for field_name, info in schema.model_fields.items():
                    names = _accepted_names(field_name, info)
                    # A @property counts: Procedure.success_rate is computed,
                    # not a column, and is legitimately readable.
                    resolves = any(
                        (names & attrs[m]) or any(hasattr(classes[m], n) for n in names)
                        for m in selected
                    )
                    if not resolves:
                        kind = "REQUIRED -> 500" if info.is_required() else "silent default"
                        rel = path.relative_to(_ROOT.parent)
                        bad.append(
                            f"{rel}:{lineno} {schema_name}.{field_name} "
                            f"[{kind}] absent from {sorted(selected)}"
                        )

    assert not bad, "response fields no model can supply:\n  " + "\n  ".join(sorted(set(bad)))
