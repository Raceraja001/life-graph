"""Queries on tenant-scoped models must filter by tenant.

There is no automatic scoping in this codebase — no ``with_loader_criteria``,
no ``do_orm_execute`` listener. Every query filters by hand, so a forgotten
filter is a silent cross-tenant read, and the endpoint returns 200.

Four such leaks were found in the nightly consolidation pipeline. A scan then
found thirty more across services, the API and the kernel, including:

    IdentityService.get_current_identity()   every tenant's identity memories
    IdentityService.get_timeline()           every tenant's belief history
    IntentionService.list_pending()          every tenant's pending intentions
    IntentionService.expire_overdue()        UPDATE across every tenant
    list_sessions()                          every tenant's sessions
    match_procedures()                       every tenant's procedures

Demonstrated before fixing: tenant A calling get_current_identity() received
tenant B's memories.

The check is deliberately coarse — it asks whether a function that queries a
tenant-scoped model mentions tenancy anywhere at all, which a real filter
always does (directly or via get_current_tenant_id()). It cannot verify the
filter is correct, only that tenancy was considered. Genuinely cross-tenant
code is allowlisted by name below, with a reason, rather than being tolerated
by a check loose enough to miss real leaks.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import pathlib
import warnings

import pytest

import life_graph.models.db
from life_graph.models.db import Base

_ROOT = pathlib.Path(life_graph.models.db.__file__).resolve().parents[1]

# (module suffix, function name) -> why it is legitimately cross-tenant
_INTENTIONAL_GLOBAL: dict[tuple[str, str], str] = {
    ("workers/tasks.py", "run_all_consolidations"): "tenant discovery — selects distinct tenant_id",
    ("workers/tasks.py", "run_all_merge_suggestions"): "tenant discovery",
    ("workers/tasks.py", "run_all_research"): "tenant discovery",
    ("workers/tasks.py", "run_nightly_self_heal"): "tenant discovery",
    ("workers/tasks.py", "run_watchers"): "tenant discovery, then scopes per tenant",
    ("workers/tasks.py", "run_daily_digest"): "tenant discovery",
    ("workers/tasks.py", "run_daily_brief"): "tenant discovery",
    ("workers/tasks.py", "decay_trust_scores"): "tenant discovery",
    ("workers/tasks.py", "failure_pattern_mining"): "tenant discovery",
    ("workers/decay.py", "run_all_decay_sweeps"): "tenant discovery",
    ("workers/cleanup.py", "cleanup_memories_all"): "tenant discovery",
    ("autonomy/approvals/service.py", "check_expirations"): (
        "system cron with no tenant context; sweeps every tenant in one pass"
    ),
    ("autonomy/approvals/service.py", "send_escalations"): (
        "system cron with no tenant context; sweeps every tenant in one pass"
    ),
}


@pytest.fixture(scope="module")
def tenanted_models() -> set[str]:
    warnings.filterwarnings("ignore")
    for path in sorted(_ROOT.rglob("*.py")):
        parts = path.relative_to(_ROOT.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        with contextlib.suppress(Exception):
            importlib.import_module(".".join(parts))

    models = {
        mapper.class_.__name__
        for mapper in Base.registry.mappers
        if "tenant_id" in {attr.key for attr in mapper.attrs}
    }
    assert len(models) >= 58, f"only {len(models)} tenant-scoped models seen"
    return models


def _queried_models(fn: ast.AST, tenanted: set[str]) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(fn):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("select", "update", "delete")
        ):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in tenanted:
                found.add(arg.id)
            elif (
                isinstance(arg, ast.Attribute)
                and isinstance(arg.value, ast.Name)
                and arg.value.id in tenanted
            ):
                found.add(arg.value.id)
    return found


def test_tenant_scoped_queries_consider_tenancy(tenanted_models):
    unscoped: list[str] = []

    for path in sorted(_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue

        rel = str(path.relative_to(_ROOT))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if "tenant" in ast.dump(fn).lower():
                continue

            key = next(
                (k for k in _INTENTIONAL_GLOBAL if rel.endswith(k[0]) and fn.name == k[1]),
                None,
            )
            if key is not None:
                continue

            models = _queried_models(fn, tenanted_models)
            if models:
                unscoped.append(f"{rel}::{fn.name}() queries {sorted(models)}")

    assert not unscoped, (
        "queries on tenant-scoped models with no mention of tenancy:\n  "
        + "\n  ".join(sorted(unscoped))
        + "\n\nAdd the filter, or allowlist it in _INTENTIONAL_GLOBAL with a reason."
    )


def test_allowlist_entries_still_exist(tenanted_models):
    """A stale allowlist silently re-permits an unscoped query."""
    missing: list[str] = []
    for (module_suffix, fn_name), _reason in _INTENTIONAL_GLOBAL.items():
        path = _ROOT / module_suffix
        if not path.exists():
            missing.append(f"{module_suffix} (file gone)")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        if fn_name not in names:
            missing.append(f"{module_suffix}::{fn_name} (function gone)")

    assert not missing, "allowlist entries that no longer exist:\n  " + "\n  ".join(missing)


def test_no_automatic_tenant_scoping_exists(tenanted_models):
    """Pins the premise: if global scoping is ever added, this check is redundant.

    Manual filtering is only necessary because nothing applies tenancy
    automatically. Someone adding a with_loader_criteria hook should see this
    fail and reconsider the whole approach rather than leaving it in place.
    """
    hooks = []
    for path in sorted(_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in ("with_loader_criteria", "do_orm_execute"):
            if marker in text:
                hooks.append(f"{path.relative_to(_ROOT)}: {marker}")

    assert not hooks, (
        "automatic tenant scoping may now exist:\n  "
        + "\n  ".join(hooks)
        + "\nIf so, the manual filters and this test should be revisited."
    )
