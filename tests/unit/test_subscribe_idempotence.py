"""Every service ``subscribe()`` must be safe to call twice.

The DI providers are ``@lru_cache``d, so a second lifespan in the same
process — which the test suite does routinely — hands back the *same*
service instance and calls ``subscribe()`` on it again. Without a guard the
handler is appended to the bus a second time and runs twice per event.

Seven services already guard this with a ``_subscribed`` flag and say so in
their docstring. SchedulerService did not, and its handler duplicated on
every restart:

    after startup #1: TASK_FAILED handlers=1
    after startup #2: TASK_FAILED handlers=2

The convention is fine; forgetting it is silent. This checks it instead.
"""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "life_graph"


def _subscribe_methods() -> list[tuple[pathlib.Path, ast.FunctionDef]]:
    """Public subscribe() methods that register EventBus handlers."""
    found = []
    for path in ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == "subscribe"
            ):
                continue
            # Match on the call SHAPE, not the receiver name: the bus reaches
            # these services three ways — the module-level `event_bus`, an
            # injected `self._bus`, and a local alias. What identifies a
            # registration is that the first argument is an EventType.
            registers = any(
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "subscribe"
                and sub.args
                and isinstance(sub.args[0], ast.Attribute)
                and isinstance(sub.args[0].value, ast.Name)
                and sub.args[0].value.id == "EventType"
                for sub in ast.walk(node)
            )
            if registers:
                found.append((path, node))
    return found


def _has_early_return_guard(fn) -> bool:
    """A leading `if self._<flag>: return` before any registration."""
    for stmt in fn.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring
        if (
            isinstance(stmt, ast.If)
            and isinstance(stmt.test, ast.Attribute)
            and isinstance(stmt.test.value, ast.Name)
            and stmt.test.value.id == "self"
            and any(isinstance(b, ast.Return) for b in stmt.body)
        ):
            return True
        return False
    return False


def test_scan_finds_the_subscribe_methods():
    """Guard the guard — finding none would pass vacuously."""
    methods = _subscribe_methods()
    assert len(methods) >= 7, f"only found {len(methods)} subscribe() methods"


def test_every_subscribe_is_idempotent():
    offenders = [
        f"{path.relative_to(ROOT.parent)}::{fn.name}"
        for path, fn in _subscribe_methods()
        if not _has_early_return_guard(fn)
    ]
    assert not offenders, (
        f"{offenders} register EventBus handlers without an early-return "
        "guard. The DI providers are @lru_cache'd, so a second startup in "
        "the same process re-subscribes the same instance and the handler "
        "runs twice per event. Follow the `if self._subscribed: return` "
        "convention the other services use."
    )


def test_every_subscribe_sets_its_flag():
    """A guard that never latches is worse than none — it reads as safe."""
    missing = []
    for path, fn in _subscribe_methods():
        assigns_flag = any(
            isinstance(sub, ast.Assign)
            and any(
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id == "self"
                for t in sub.targets
            )
            and isinstance(sub.value, ast.Constant)
            and sub.value.value is True
            for sub in ast.walk(fn)
        )
        if not assigns_flag:
            missing.append(f"{path.relative_to(ROOT.parent)}::{fn.name}")
    assert not missing, f"{missing} guard on a flag they never set to True"
