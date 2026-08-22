"""Response schema annotations must agree with the column types they read.

Companion to test_response_schema_integrity.py, which checks that a field
*name* resolves. That is not enough: ``WatchEvent.details`` is JSONB and
resolves fine against a ``str | None`` field, and listing watch events 500'd
for every event whose details held a dict — which is what
``BaseWatcher.emit_event()`` produces, so every event from dependency_watcher
and tech_radar once both were registered.

That bug was found by calling the endpoint, not by scanning. This closes the
gap so the next one does not need a lucky manual probe.

Three mismatches are checked, all of which fail only at serialization time:

    JSONB/JSON column  -> scalar annotation   (dict reaches a str field)
    ARRAY column       -> non-list annotation
    nullable column    -> field that rejects None

Fields carrying a ``mode="before"`` validator are skipped: converting the
stored shape is exactly what such a validator is for, and WatchEventResponse
.details now has one.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import pathlib
import sys
import types
import typing
import warnings

import pytest
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import ARRAY, JSON
from sqlalchemy.dialects.postgresql import JSONB

import life_graph.models.db  # noqa: F401  - registers the core mappers
from life_graph.models.db import Base

_ROOT = pathlib.Path(life_graph.models.db.__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def classes() -> dict:
    warnings.filterwarnings("ignore")
    for path in sorted(_ROOT.rglob("*.py")):
        parts = path.relative_to(_ROOT.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        with contextlib.suppress(Exception):
            importlib.import_module(".".join(parts))

    registry = {m.class_.__name__: m.class_ for m in Base.registry.mappers}
    assert len(registry) >= 49, f"only {len(registry)} mappers registered"
    return registry


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


def _concrete_types(annotation) -> set:
    """Types named by an annotation, unwrapping unions and dropping None."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        found: set = set()
        for arg in typing.get_args(annotation):
            found |= _concrete_types(arg)
        return found
    if origin is not None:
        return {origin}
    return set() if annotation is type(None) else {annotation}


def _accepts_none(annotation) -> bool:
    """Ask Pydantic rather than guess.

    ``Any`` accepts None while naming neither NoneType nor a union, so
    inspecting the annotation by hand reports a false positive on it.
    """
    try:
        TypeAdapter(annotation).validate_python(None)
    except Exception:  # noqa: BLE001 - any validation failure means it rejects None
        return False
    return True


def _pre_validated_fields(schema) -> set[str]:
    """Fields with a mode="before" validator, which may legitimately convert."""
    fields: set[str] = set()
    decorators = getattr(schema, "__pydantic_decorators__", None)
    if decorators is None:
        return fields
    for validator in decorators.field_validators.values():
        if validator.info.mode == "before":
            fields |= set(validator.info.fields)
    return fields


def test_response_annotations_match_column_types(classes):
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

                converted = _pre_validated_fields(schema)
                rel = path.relative_to(_ROOT.parent)

                for model_name in sorted(selected):
                    columns = classes[model_name].__mapper__.columns

                    for field_name, info in schema.model_fields.items():
                        if field_name in converted:
                            continue
                        names = _accepted_names(field_name, info)
                        column = next((columns[n] for n in names if n in columns), None)
                        if column is None:
                            continue

                        annotated = _concrete_types(info.annotation)
                        col_type = column.type
                        where = f"{rel}:{lineno} {schema_name}.{field_name}"
                        target = f"{model_name}.{column.name}"

                        if (
                            isinstance(col_type, JSONB | JSON)
                            and annotated
                            and not (annotated & {dict, list, typing.Any})
                        ):
                            bad.append(
                                f"{where}: {target} is "
                                f"{type(col_type).__name__} but annotated {info.annotation}"
                            )
                        elif isinstance(col_type, ARRAY) and annotated and list not in annotated:
                            bad.append(
                                f"{where}: {target} is ARRAY but annotated {info.annotation}"
                            )
                        elif column.nullable and not _accepts_none(info.annotation):
                            bad.append(
                                f"{where}: {target} is nullable but {info.annotation} rejects None"
                            )

    assert not bad, "schema/column type mismatches:\n  " + "\n  ".join(sorted(set(bad)))
