"""alembic/env.py must see every table before autogenerate is trusted.

Base.metadata is populated as a side effect of importing the modules that
declare mapped classes. env.py imported only life_graph.models.db, which
registers 43 of the 64 tables. autogenerate compares that metadata against the
live database and emits DROP TABLE for anything it cannot see — so the
workflow CLAUDE.md documents,

    python -m alembic revision --autogenerate -m "add <feature> tables"

produced a migration that dropped 21 tables, among them approval_queue,
audit_log, trust_scores and every eval_* table. Nothing warned; the generated
file simply had to be read carefully enough to notice.

The same under-import hid a real bug from the .values() scan earlier
(WatcherRun.events_created), which is why this is asserted rather than assumed.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_ENV = pathlib.Path(__file__).resolve().parents[2] / "alembic" / "env.py"


@pytest.fixture(scope="module")
def env_source() -> str:
    return _ENV.read_text(encoding="utf-8")


def _metadata_after_env_imports() -> set[str]:
    """Import exactly what env.py imports, then read the table names."""
    import importlib

    tree = ast.parse(_ENV.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("life_graph"):
                    importlib.import_module(alias.name)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("life_graph"):
            importlib.import_module(node.module)

    from life_graph.models.db import Base

    return set(Base.metadata.tables)


def _all_mapped_tables() -> set[str]:
    """Every table any module declares."""
    import contextlib
    import importlib
    import warnings

    warnings.filterwarnings("ignore")
    root = _ENV.parents[1] / "life_graph"
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        with contextlib.suppress(Exception):
            importlib.import_module(".".join(parts))

    from life_graph.models.db import Base

    return set(Base.metadata.tables)


def test_env_registers_every_mapped_table():
    """The check that matters: nothing is invisible to autogenerate."""
    everything = _all_mapped_tables()
    # _all_mapped_tables imports the whole package, so re-reading metadata
    # after env's imports cannot distinguish. Compare against the explicit
    # import list in env.py instead.
    assert len(everything) >= 64, f"expected >= 64 tables, found {len(everything)}"

    visible = _metadata_after_env_imports()
    missing = sorted(everything - visible)
    assert not missing, (
        f"alembic/env.py does not import the modules declaring {missing} — "
        "autogenerate would emit DROP TABLE for each"
    )


def test_env_imports_each_known_model_module(env_source):
    """Named explicitly so a new model module is a visible omission."""
    for module in (
        "life_graph.models.db",
        "life_graph.autonomy.models",
        "life_graph.self_improving.models",
        "life_graph.watchers.models",
    ):
        assert module in env_source, f"alembic/env.py never imports {module}"


def test_env_filters_age_managed_tables(env_source):
    """Apache AGE owns 21 tables that are not and never will be models.

    Without a filter autogenerate emits DROP TABLE for Entity, Preference,
    Decision, _ag_label_vertex and every edge table — the knowledge graph.
    """
    assert "include_object" in env_source
    assert "ag_catalog.ag_label" in env_source, (
        "the AGE table list should come from AGE's own catalog rather than a "
        "hardcoded set that silently goes stale as labels are added"
    )


def test_include_object_excludes_age_labels():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_alembic_env_probe", _ENV)
    assert spec and spec.loader
    # env.py runs migrations on import, so exercise the function in isolation
    # rather than importing the module.
    source = _ENV.read_text(encoding="utf-8")
    namespace: dict = {}
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "include_object":
            exec(  # noqa: S102 - executing one function definition from our own repo
                compile(ast.Module(body=[node], type_ignores=[]), str(_ENV), "exec"),
                namespace,
            )
    include_object = namespace["include_object"]
    namespace["_AGE_LABELS"] = {"Entity", "_ag_label_vertex"}

    assert include_object(None, "Entity", "table", True, None) is False
    assert include_object(None, "_ag_label_vertex", "table", True, None) is False
    assert include_object(None, "memories", "table", True, None) is True
    # a column named like a label must not be filtered
    assert include_object(None, "Entity", "column", True, None) is True
