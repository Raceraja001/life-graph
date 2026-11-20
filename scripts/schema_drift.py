#!/usr/bin/env python3
"""Model/schema drift check: the ORM metadata against a database migrated to head.

``alembic.autogenerate.compare_metadata`` lists every difference between what
the SQLAlchemy models declare and what the migrations actually built. Until
2026-11-20 nothing ran it (audit M18), and on the first run it found 245
differences. Most are harmless spelling (an index declared ascending in the
model and ``DESC`` in the migration, ``TEXT`` vs ``String(64)``), some are not
(17 tables invisible to autogenerate, foreign keys whose ``ON DELETE`` the
model and the database disagree on).

Fixing all of them at once means touching most model files, so this is a
ratchet: the differences known on 2026-11-20 are listed in
``alembic/schema_drift_baseline.txt`` and

* any difference NOT in the baseline fails (new drift: fix the model or add a
  migration), and
* any baseline entry that no longer occurs fails too (it was fixed: delete the
  line), so the list only ever shrinks.

Usage::

    python scripts/schema_drift.py --check            # exit 1 on any change
    python scripts/schema_drift.py --list             # print current drift keys
    python scripts/schema_drift.py --write-baseline   # rewrite the baseline

Reads ``LIFE_GRAPH_DATABASE_URL_SYNC`` like alembic does. Point it at a
throwaway database migrated to head, never at a live one (it only reads, but
there is no reason to aim it at production).
"""

from __future__ import annotations

import argparse
import ast
import importlib
import pathlib
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV = ROOT / "alembic" / "env.py"
BASELINE = ROOT / "alembic" / "schema_drift_baseline.txt"


def _import_env_models() -> None:
    """Import exactly the model modules alembic/env.py imports."""
    tree = ast.parse(ENV.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("life_graph"):
                    importlib.import_module(alias.name)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("life_graph"):
            importlib.import_module(node.module)


def _key(op: tuple) -> str:
    """A stable one-line description of one autogenerate difference."""
    kind = op[0]
    if kind.startswith("modify_"):
        # (kind, schema, table, column, existing, old, new)
        return f"{kind} | {op[2]}.{op[3]} | {op[5]!r} -> {op[6]!r}"
    obj = op[1]
    if kind in ("add_index", "remove_index"):
        exprs = ",".join(str(e) for e in obj.expressions)
        return f"{kind} | {obj.table.name}.{obj.name} | {exprs}{' UNIQUE' if obj.unique else ''}"
    if kind in ("add_table", "remove_table"):
        return f"{kind} | {obj.name}"
    if kind in ("add_column", "remove_column"):
        return f"{kind} | {op[2]}.{op[3].name} | {op[3].type}"
    if kind in ("add_fk", "remove_fk"):
        cols = [c.name for c in obj.columns]
        ref = obj.referred_table.fullname if obj.referred_table is not None else "?"
        return f"{kind} | {obj.parent.name} | {cols} -> {ref} ondelete={obj.ondelete}"
    if kind in ("add_constraint", "remove_constraint"):
        cols = [c.name for c in obj.columns]
        return f"{kind} | {obj.table.name}.{obj.name} | {type(obj).__name__}{cols}"
    return f"{kind} | {obj}"


def current_drift(url: str | None = None) -> list[str]:
    """Sorted drift keys between the models and the database at *url*."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    _import_env_models()
    from life_graph.config import settings, sqlalchemy_sync_url
    from life_graph.models.db import Base

    engine = create_engine(sqlalchemy_sync_url(url or settings.database_url_sync))
    try:
        # Same AGE filter as env.py: the graph's tables are not models.
        with engine.connect() as conn:
            try:
                labels = {
                    r[0] for r in conn.exec_driver_sql("SELECT name FROM ag_catalog.ag_label")
                }
            except Exception:  # noqa: BLE001 - no AGE
                labels = set()

        def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ARG001
            return not (type_ == "table" and name in labels)

        with engine.connect() as conn, warnings.catch_warnings():
            warnings.simplefilter("ignore")  # "Did not recognize type ag_catalog.graphid"
            ctx = MigrationContext.configure(
                conn, opts={"include_object": include_object, "compare_type": True}
            )
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()

    keys: list[str] = []
    for entry in diff:
        # Column changes come grouped as a list of tuples, one per attribute.
        for op in entry if isinstance(entry, list) else [entry]:
            keys.append(_key(op))
    return sorted(set(keys))


def read_baseline() -> list[str]:
    lines = BASELINE.read_text(encoding="utf-8").splitlines()
    return sorted({ln for ln in lines if ln.strip() and not ln.startswith("#")})


def compare_to_baseline(current: list[str], baseline: list[str]) -> tuple[list[str], list[str]]:
    """(new drift, baseline entries that no longer occur)."""
    cur, base = set(current), set(baseline)
    return sorted(cur - base), sorted(base - cur)


_HEADER = """\
# Known model/schema drift, accepted 2026-11-20 (audit M18). One line per
# alembic autogenerate difference; see scripts/schema_drift.py.
#
# Do NOT add lines to make a check pass: new drift means a model and its
# migration disagree, so fix one of them. When a fix makes a line disappear,
# delete the line (the check fails until you do, so this list only shrinks).
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--list", action="store_true")
    g.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args(argv)

    current = current_drift()
    if args.list:
        print("\n".join(current))
        return 0
    if args.write_baseline:
        BASELINE.write_text(_HEADER + "\n".join(current) + "\n", encoding="utf-8")
        print(f"wrote {len(current)} entries to {BASELINE.relative_to(ROOT)}")
        return 0

    new, gone = compare_to_baseline(current, read_baseline())
    for k in new:
        print(f"NEW DRIFT: {k}")
    for k in gone:
        print(f"FIXED (delete from baseline): {k}")
    if new or gone:
        print(
            f"schema drift check failed: {len(new)} new, {len(gone)} stale baseline entries",
            file=sys.stderr,
        )
        return 1
    print(f"schema drift: {len(current)} known differences, none new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
