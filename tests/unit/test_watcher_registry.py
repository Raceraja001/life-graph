"""Every implemented watcher must be reachable from the hourly cron.

``run_watchers`` looks each enabled WatchConfig up in a ``watcher_map`` keyed
by ``watcher_name``. A name absent from that map hits ``.get() -> None`` and
is skipped with no log line, so a watcher can be implemented, configured and
enabled while never running. Two of the four were in exactly that state.

The two are not interchangeable, which is why they were never added:

    BaseWatcher subclasses  __init__(tenant_id, session_factory, settings)
                            execute() -> None, emits via self.emit_event()
                            run() owns config load, enabled/auto-disable
                            checks, the WatcherRun record and persistence
    ad-hoc watchers         __init__(config, session_factory)
                            execute() -> list[dict], no lifecycle at all

Registering a BaseWatcher subclass without handling that would call an
execute() returning None and then take len() of it.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import textwrap

import pytest

from life_graph.watchers.base import BaseWatcher
from life_graph.watchers.code_quality_watcher import CodeQualityWatcher
from life_graph.watchers.dependency_watcher import DependencyWatcher
from life_graph.watchers.server_health_watcher import ServerHealthWatcher
from life_graph.watchers.tech_radar_watcher import TechRadarWatcher
from life_graph.workers import tasks

ALL_WATCHERS = [
    ServerHealthWatcher,
    CodeQualityWatcher,
    DependencyWatcher,
    TechRadarWatcher,
]


def _registered_names() -> set[str]:
    """Names in run_watchers' watcher_map, read from source.

    The map is built inside the function body, so it is parsed rather than
    imported. Keys are ``<Class>.name`` references, which is what keeps the
    map and the classes from drifting apart.
    """
    src = textwrap.dedent(inspect.getsource(tasks.run_watchers))
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "watcher_map"
        ):
            continue

        names: set[str] = set()
        for key in node.value.keys:
            if isinstance(key, ast.Attribute) and key.attr == "name":
                cls = key.value.id
                names.add(next(c.name for c in ALL_WATCHERS if c.__name__ == cls))
            elif isinstance(key, ast.Constant):
                names.add(key.value)
        return names

    raise AssertionError("watcher_map not found in run_watchers")


def test_every_implemented_watcher_is_registered():
    registered = _registered_names()
    missing = sorted(w.name for w in ALL_WATCHERS if w.name not in registered)
    assert not missing, (
        f"implemented but unreachable from the hourly cron: {missing} — "
        "a WatchConfig naming one of these is skipped in silence"
    )


def test_registry_has_no_unknown_names():
    """A key with no class behind it is a config that can never match."""
    known = {w.name for w in ALL_WATCHERS}
    assert _registered_names() <= known


def test_watcher_names_are_unique():
    names = [w.name for w in ALL_WATCHERS]
    assert len(names) == len(set(names)), f"duplicate watcher names: {names}"


def test_no_watcher_module_is_unaccounted_for():
    """A new *_watcher.py must be added to ALL_WATCHERS and the map."""
    watcher_dir = pathlib.Path(BaseWatcher.__module__.replace(".", "/")).parent
    root = pathlib.Path(tasks.__file__).resolve().parents[2]
    modules = sorted((root / watcher_dir).glob("*_watcher.py"))

    assert len(modules) == len(ALL_WATCHERS), (
        f"{len(modules)} watcher modules on disk but {len(ALL_WATCHERS)} tracked: "
        f"{[m.name for m in modules]}"
    )


@pytest.mark.parametrize("cls", ALL_WATCHERS, ids=lambda c: c.__name__)
def test_each_watcher_declares_a_name(cls):
    assert isinstance(cls.name, str) and cls.name
    assert cls.name != BaseWatcher.name, f"{cls.__name__} never overrode the base name"


@pytest.mark.parametrize("cls", ALL_WATCHERS, ids=lambda c: c.__name__)
def test_calling_convention_is_one_of_the_two_supported(cls):
    """Guards against a third convention appearing that dispatch cannot handle."""
    params = set(inspect.signature(cls.__init__).parameters) - {"self"}

    if issubclass(cls, BaseWatcher):
        assert {"tenant_id", "session_factory"} <= params
        assert inspect.signature(cls.execute).return_annotation in (None, "None")
    else:
        assert {"config", "session_factory"} <= params
        ret = inspect.signature(cls.execute).return_annotation
        assert "list" in str(ret), f"{cls.__name__}.execute must return a list, got {ret}"


def test_dispatch_handles_both_conventions():
    """run_watchers must branch on BaseWatcher, not assume one shape."""
    src = textwrap.dedent(inspect.getsource(tasks.run_watchers))
    assert "issubclass(watcher_cls, BaseWatcher)" in src, (
        "run_watchers does not distinguish the two calling conventions; "
        "a BaseWatcher subclass would get execute() -> None and then len(None)"
    )


def test_lifecycle_helper_reads_events_back_for_notification_routing():
    """BaseWatcher.run() persists events and returns only counts."""
    src = textwrap.dedent(inspect.getsource(tasks._run_lifecycle_watcher))
    assert "run_id" in src
    assert "WatchEvent" in src, "events must be read back so they can be routed"
