"""Install / uninstall the Life Graph hooks in a Claude Code settings file.

``~/.claude/settings.json`` is the developer's file, not ours — it already
holds their own ``PreCompact`` and ``PreToolUse`` hooks and a ``statusLine``.
Every operation here is therefore a deep merge, never a rewrite:

* Existing keys and existing entries in each event array are preserved.
* Our entries are identified by :data:`HOOK_MARKER` appearing in the entry's
  ``command`` string — no extra keys are added to the entry, so nothing depends
  on Claude Code preserving fields its schema does not know about.
* Re-running install replaces our entry in place (idempotent, and it upgrades
  a stale interpreter path) instead of appending a duplicate.
* Any write is preceded by a timestamped ``.bak`` beside the original, matching
  the ``settings.json.bak.20260822135550`` convention already in use.
* A settings file that does not parse is never overwritten.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

#: Substring that marks an entry as ours. Stable across versions.
HOOK_MARKER = "life_graph.integrations.claude_code.hook"

#: (event, timeout seconds, status message). ``matcher`` is deliberately
#: omitted everywhere: absent means "all", and several of these events
#: (UserPromptSubmit, Stop) do not support a matcher at all.
HOOK_EVENTS: list[tuple[str, int, str | None]] = [
    ("SessionStart", 10, "Recalling from Life Graph…"),
    ("UserPromptSubmit", 5, None),
    ("PostToolUse", 5, None),
    ("PostToolUseFailure", 5, None),
    ("Stop", 5, None),
    ("SubagentStop", 5, None),
    ("SessionEnd", 5, None),
]


def default_settings_path() -> Path:
    """The user-level Claude Code settings file."""
    return Path.home() / ".claude" / "settings.json"


def hook_command(python_exe: str | None = None) -> str:
    """The shell command Claude Code will run for every wired event.

    Defaults to the *current* interpreter so the hook inherits the virtualenv
    that ``life-graph`` itself was invoked from — a bare ``python3`` would not
    have ``life_graph`` importable.
    """
    exe = python_exe or sys.executable or "python3"
    return f"{exe} -m {HOOK_MARKER}"


def _entry(command: str, timeout: int, status_message: str | None) -> dict[str, Any]:
    hook: dict[str, Any] = {"type": "command", "command": command, "timeout": timeout}
    if status_message:
        hook["statusMessage"] = status_message
    return {"hooks": [hook]}


def is_ours(entry: Any) -> bool:
    """True when a settings hook entry was installed by this integration."""
    if not isinstance(entry, dict):
        return False
    for hook in entry.get("hooks") or []:
        if isinstance(hook, dict) and HOOK_MARKER in str(hook.get("command", "")):
            return True
    return False


def load_settings(path: Path) -> dict[str, Any]:
    """Read a settings file. Missing file → empty settings.

    Raises ``ValueError`` on malformed JSON so callers refuse to overwrite a
    file they cannot faithfully reproduce.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def backup(path: Path) -> Path | None:
    """Copy ``path`` to ``path.bak.<YYYYMMDDHHMMSS>``. None if nothing to back up."""
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    dest = path.with_name(f"{path.name}.bak.{stamp}")
    shutil.copy2(path, dest)
    return dest


def merge_install(settings: dict[str, Any], *, python_exe: str | None = None) -> dict[str, Any]:
    """Return a copy of ``settings`` with our hook entries merged in.

    Pure function — no I/O — so tests can assert the merge directly.
    """
    result = json.loads(json.dumps(settings))  # deep copy, JSON-safe by construction
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("settings['hooks'] is not an object")

    command = hook_command(python_exe)
    for event, timeout, status_message in HOOK_EVENTS:
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise ValueError(f"settings['hooks']['{event}'] is not an array")
        new_entry = _entry(command, timeout, status_message)
        for index, existing in enumerate(entries):
            if is_ours(existing):
                entries[index] = new_entry  # in place: idempotent + upgrades the path
                break
        else:
            entries.append(new_entry)
    return result


def merge_uninstall(settings: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``settings`` with only our entries removed.

    Event arrays we emptied are dropped, and an emptied ``hooks`` object is
    dropped too, so uninstalling restores the original file byte-for-byte in
    the common case.
    """
    result = json.loads(json.dumps(settings))
    hooks = result.get("hooks")
    if not isinstance(hooks, dict):
        return result

    for event in list(hooks):
        entries = hooks[event]
        if not isinstance(entries, list):
            continue
        kept = [e for e in entries if not is_ours(e)]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        del result["hooks"]
    return result


def _write(path: Path, settings: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def apply(
    path: Path,
    settings: dict[str, Any],
    *,
    dry_run: bool = False,
) -> Path | None:
    """Back up then write ``settings`` to ``path``. Returns the backup path."""
    if dry_run:
        return None
    backup_path = backup(path)
    _write(path, settings)
    return backup_path


def status(settings: dict[str, Any]) -> dict[str, Any]:
    """Describe which events currently carry our hook, and with what command."""
    hooks = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    installed: dict[str, str] = {}
    for event, entries in (hooks or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if is_ours(entry):
                for hook in entry.get("hooks") or []:
                    if HOOK_MARKER in str(hook.get("command", "")):
                        installed[event] = hook["command"]
    expected = [event for event, _, _ in HOOK_EVENTS]
    return {
        "installed_events": installed,
        "expected_events": expected,
        "missing_events": [e for e in expected if e not in installed],
        "other_hook_events": sorted(
            event
            for event, entries in (hooks or {}).items()
            if isinstance(entries, list) and any(not is_ours(e) for e in entries)
        ),
    }
