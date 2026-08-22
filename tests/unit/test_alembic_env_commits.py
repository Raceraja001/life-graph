"""`alembic upgrade head` must not be able to succeed without committing.

env.py once loaded the Apache AGE label list on the same connection it then
handed to ``context.configure``. That query opened an implicit transaction, so
alembic's ``context.begin_transaction()`` found one already in progress and
became a no-op -- the connection closed without a commit and every migration
rolled back. The command still logged "Running upgrade 034 -> 035" and exited
0, so it read as applied.

The rule this asserts: the connection given to ``context.configure`` is used
for nothing before configure sees it.
"""

import ast
import pathlib

ENV_PY = pathlib.Path(__file__).resolve().parents[2] / "alembic" / "env.py"


def _online_migrations_fn() -> ast.FunctionDef:
    tree = ast.parse(ENV_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_migrations_online":
            return node
    raise AssertionError("alembic/env.py has no run_migrations_online()")


def _migration_connection_name(fn: ast.FunctionDef) -> str:
    """The variable bound to the connection passed to context.configure."""
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "configure"
        ):
            for kw in node.keywords:
                if kw.arg == "connection":
                    assert isinstance(kw.value, ast.Name), (
                        "context.configure(connection=...) must take a plain name "
                        "so this guard can follow it"
                    )
                    return kw.value.id
    raise AssertionError("run_migrations_online() never calls context.configure()")


def test_configure_connection_is_untouched_before_configure():
    fn = _online_migrations_fn()
    conn = _migration_connection_name(fn)

    # Statement index of the context.configure call, in the flattened body of
    # whichever `with` block introduces the migration connection.
    for node in ast.walk(fn):
        if not isinstance(node, ast.With):
            continue
        binds = {
            item.optional_vars.id for item in node.items if isinstance(item.optional_vars, ast.Name)
        }
        if conn not in binds:
            continue
        # Inside the block that opens the migration connection, the first
        # thing done with it must be context.configure.
        uses: list[str] = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                if (
                    isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id == conn
                ):
                    uses.append(f"{conn}.{sub.func.attr}()")
                elif any(isinstance(a, ast.Name) and a.id == conn for a in sub.args):
                    name = getattr(sub.func, "id", getattr(sub.func, "attr", "?"))
                    if name != "configure":
                        uses.append(f"{name}({conn})")
        assert not uses, (
            f"{', '.join(uses)} runs on the migration connection before "
            "context.configure. An implicit transaction there makes "
            "begin_transaction() a no-op and every migration silently roll back. "
            "Use a separate connection."
        )
        return
    raise AssertionError(f"no `with ... as {conn}:` block in run_migrations_online()")


def test_age_labels_are_loaded_on_their_own_connection():
    fn = _online_migrations_fn()
    conn = _migration_connection_name(fn)
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_load_age_labels"
        ):
            arg = node.args[0]
            assert isinstance(arg, ast.Name) and arg.id != conn, (
                "_load_age_labels must not run on the migration connection"
            )
            return
    raise AssertionError("run_migrations_online() never loads the AGE labels")
