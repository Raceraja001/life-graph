"""Built-in personas must converge on their definition, pins included.

``seed_builtins`` reconciles already-seeded rows, but only ``allowed_tools``
and ``system_prompt``. The three columns migration 021 added to make personas
drive the agent loop — ``driver``, ``verifier_chain``, ``task_types`` — were
never reconciled and were not in the seeder's SELECT at all.

The effect on any tenant seeded before 021: ``driver`` stays NULL forever.
uzhavu-ops and dependency-updater exist specifically to pin claude_code, and
their pin never arrived — no restart, redeploy, or reseed fixed it, because
the only code path that writes those columns is the INSERT for a persona that
does not exist yet.

Safe to overwrite because ``PersonaService.update`` does not list them as
updatable, so unlike allowed_tools there is no hand-granted value to clobber.
"""

import ast
import pathlib

from life_graph.kernel.personas import _BUILTIN_PERSONAS

PERSONAS_PY = pathlib.Path(__file__).resolve().parents[2] / "life_graph" / "kernel" / "personas.py"

_PIN_COLUMNS = ("driver", "verifier_chain", "task_types")


class _Row:
    """Row shape the seeder's SELECT produces."""

    def __init__(self, **kw):
        self.is_builtin = kw.get("is_builtin", True)
        self.allowed_tools = kw.get("allowed_tools")
        self.system_prompt = kw.get("system_prompt", "")
        self.driver = kw.get("driver")
        self.verifier_chain = kw.get("verifier_chain")
        self.task_types = kw.get("task_types")


def _seeder_selected_columns() -> set[str]:
    """Columns seed_builtins fetches for the reconcile comparison."""
    tree = ast.parse(PERSONAS_PY.read_text())
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and node.targets
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "existing_stmt"
        ):
            continue
        return {
            sub.attr
            for sub in ast.walk(node.value)
            if isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "AgentPersona"
        }
    raise AssertionError("seed_builtins has no existing_stmt")


def test_seeder_selects_the_pin_columns():
    """A column absent from the SELECT raises AttributeError on the Row."""
    selected = _seeder_selected_columns()
    missing = [c for c in _PIN_COLUMNS if c not in selected]
    assert not missing, (
        f"seed_builtins does not SELECT {missing}, so _reconcile_builtin "
        "cannot compare them — the rows it gets are SQLAlchemy Rows, not ORM "
        "objects, and reading an unselected attribute raises"
    )


def _defn(name: str) -> dict:
    return next(d for d in _BUILTIN_PERSONAS if d["name"] == name)


def _reconcile(defn, row):
    """Compute the UPDATE values _reconcile_builtin would issue."""
    from life_graph.kernel.personas import PersonaService

    captured = {}

    class _Session:
        async def execute(self, stmt):
            captured.update(stmt.compile().params)
            return None

    import asyncio

    asyncio.run(PersonaService._reconcile_builtin(_Session(), "t", defn, row))
    return captured


def test_a_pre_021_tenant_gets_its_driver_pin_back():
    defn = _defn("dependency-updater")
    row = _Row(system_prompt=defn["system_prompt"], allowed_tools=defn["allowed_tools"])
    values = _reconcile(defn, row)
    assert values.get("driver") == "claude_code"


def test_a_pre_021_tenant_gets_its_verifier_chain_back():
    defn = _defn("dependency-updater")
    row = _Row(system_prompt=defn["system_prompt"], allowed_tools=defn["allowed_tools"])
    values = _reconcile(defn, row)
    assert values.get("verifier_chain") == defn["verifier_chain"]


def test_an_already_correct_row_issues_no_update():
    """Reconciliation must be a no-op when nothing drifted."""
    defn = _defn("dependency-updater")
    row = _Row(
        system_prompt=defn["system_prompt"],
        allowed_tools=defn["allowed_tools"],
        driver=defn["driver"],
        verifier_chain=list(defn["verifier_chain"]),
        task_types=list(defn["task_types"]),
    )
    assert _reconcile(defn, row) == {}


def test_user_owned_personas_are_left_alone():
    defn = _defn("dependency-updater")
    row = _Row(is_builtin=False)
    assert _reconcile(defn, row) == {}


def test_pin_columns_are_not_user_editable():
    """Reconciling them is only safe while update() refuses to set them."""
    src = PERSONAS_PY.read_text()
    start = src.index("allowed_fields = {")
    whitelist = src[start : src.index("}", start)]
    for col in _PIN_COLUMNS:
        assert f'"{col}"' not in whitelist, (
            f"{col} became user-editable; reconciliation would now silently "
            "overwrite a hand-set value on every startup"
        )


def test_no_builtin_pins_a_whole_repo_verifier():
    """Whole-repo verifiers fail on pre-existing debt the agent never touched."""
    for defn in _BUILTIN_PERSONAS:
        for name in defn.get("verifier_chain") or []:
            assert name != "build_ok", (
                f"persona {defn['name']!r} pins build_ok, which compiles every "
                "file in the project — one unparseable legacy file fails the "
                "gate on work that never touched it. Use build_ok_diff."
            )
            assert name != "lint_clean", (
                f"persona {defn['name']!r} pins lint_clean; use lint_clean_diff"
            )
