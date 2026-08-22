"""EventBus payload contracts: what subscribers read vs what producers emit.

``Event.payload`` is ``dict[str, Any]`` — an untyped contract between 58 emit
sites and their subscribers. ``EventBus._safe_invoke`` catches and logs handler
exceptions, and handlers read payloads with ``.get(key, default)``, so a key no
producer emits does not raise. The handler silently uses the default and the
event is processed with wrong data.

Three real gaps were found this way, all in the preference -> knowledge graph
sync, all of which corrupted the graph rather than failing:

    PREFERENCE_CREATED   choice, confidence never emitted -> every Preference
                         node written with choice="" and confidence=0.5
    PREFERENCE_UPDATED   topic, choice, confidence never emitted. sync_preference
                         upserts with `topic or "unknown"`, so any update
                         overwrote the node with topic="unknown", choice="",
                         confidence=0.5 — losing the topic that had been
                         correct at creation
    EVIDENCE_ADDED       weight, credibility never emitted -> every evidence
                         edge written with strength 1.0

The scan is deliberately conservative: an event with any non-literal payload
at some emit site is skipped entirely, since its keys cannot be read
statically. It reports only what it can prove.
"""

from __future__ import annotations

import ast
import collections
import pathlib

import pytest

import life_graph.core.events as events_mod

_ROOT = pathlib.Path(events_mod.__file__).resolve().parents[2] / "life_graph"


@pytest.fixture(scope="module")
def trees() -> dict[pathlib.Path, ast.Module]:
    out = {}
    for path in sorted(_ROOT.rglob("*.py")):
        try:
            out[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
    return out


def _event_type(node) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "EventType"
    ):
        return node.attr
    return None


def _dict_keys(node: ast.Dict) -> set[str]:
    return {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def _collect_producers(trees) -> tuple[dict[str, set[str]], set[str]]:
    """Returns (event -> emitted keys, events with an opaque payload)."""
    emitted: dict[str, set[str]] = collections.defaultdict(set)
    opaque: set[str] = set()

    for tree in trees.values():
        functions = [
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        for fn in functions:
            local: dict[str, set[str]] = {}
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Dict)
                ):
                    local[node.targets[0].id] = _dict_keys(node.value)

            for node in ast.walk(fn):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "emit"
                    and node.args
                ):
                    continue
                event = _event_type(node.args[0])
                if event is None:
                    continue

                payload = (
                    node.args[1]
                    if len(node.args) > 1
                    else next((kw.value for kw in node.keywords if kw.arg == "payload"), None)
                )
                if isinstance(payload, ast.Dict):
                    emitted[event] |= _dict_keys(payload)
                elif isinstance(payload, ast.Name) and payload.id in local:
                    emitted[event] |= local[payload.id]
                else:
                    opaque.add(event)

    return emitted, opaque


def _collect_subscriptions(trees) -> list[tuple[str, str, pathlib.Path]]:
    subs: list[tuple[str, str, pathlib.Path]] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "subscribe"
                and len(node.args) == 2
            ):
                continue
            event = _event_type(node.args[0])
            handler = node.args[1]
            name = (
                handler.attr
                if isinstance(handler, ast.Attribute)
                else handler.id
                if isinstance(handler, ast.Name)
                else None
            )
            if event and name:
                subs.append((event, name, path))
    return subs


def _payload_reads(fn) -> set[str]:
    """Keys read off event.payload, directly or through a local alias."""
    aliases = {"payload"}
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "payload"
        ):
            aliases.add(node.targets[0].id)

    keys: set[str] = set()
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            base, key = node.func.value, node.args[0].value
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            base, key = node.value, node.slice.value
        else:
            continue

        reads_payload = (isinstance(base, ast.Attribute) and base.attr == "payload") or (
            isinstance(base, ast.Name) and base.id in aliases
        )
        if reads_payload and isinstance(key, str):
            keys.add(key)
    return keys


def test_subscribers_only_read_keys_producers_emit(trees):
    emitted, opaque = _collect_producers(trees)
    subs = _collect_subscriptions(trees)
    assert subs, "no EventBus subscriptions found — the scan is not looking anywhere"
    assert emitted, "no emit() calls with literal payloads found"

    by_name: dict[str, list] = collections.defaultdict(list)
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                by_name[node.name].append((path, node))

    gaps: list[str] = []
    for event, handler_name, sub_path in sorted(subs):
        if event in opaque:
            continue  # a payload built somewhere we cannot read statically
        for handler_path, fn in by_name.get(handler_name, []):
            if handler_path != sub_path:
                continue
            missing = _payload_reads(fn) - emitted.get(event, set())
            if missing:
                rel = handler_path.relative_to(_ROOT.parent)
                gaps.append(
                    f"{event}: {rel}::{handler_name} reads {sorted(missing)}, "
                    f"but producers emit only {sorted(emitted.get(event, set()))}"
                )

    assert not gaps, "EventBus payload contract gaps:\n  " + "\n  ".join(sorted(set(gaps)))
