"""Unit tests for `life-graph hooks install|uninstall|status`.

The real ``~/.claude/settings.json`` already holds the developer's own
PreCompact and PreToolUse hooks plus a statusLine. Every test here starts from
a faithful copy of that shape in a temp dir and asserts we merged into it
rather than over it. Nothing touches the real file.
"""

from __future__ import annotations

import json

import pytest

from life_graph.integrations.claude_code import installer

# A faithful stand-in for the developer's existing settings file.
EXISTING = {
    "theme": "dark",
    "agentPushNotifEnabled": True,
    "autoCompactEnabled": True,
    "autoCompactWindow": 200000,
    "statusLine": {
        "type": "command",
        "command": "node '/media/dev/DevTools/claude-usage/capture-statusline.cjs'",
    },
    "hooks": {
        "PreCompact": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/pre-compact.py",
                        "timeout": 10,
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Read",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/read-guard.py",
                        "timeout": 10,
                        "statusMessage": "Checking read size...",
                    }
                ],
            }
        ],
    },
}


@pytest.fixture
def settings_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(EXISTING, indent=2))
    return path


def _their_hooks(settings):
    return {
        event: [e for e in entries if not installer.is_ours(e)]
        for event, entries in settings.get("hooks", {}).items()
    }


# ── Merge preserves what is already there ────────────────────────────────


def test_install_preserves_existing_hooks_and_top_level_keys(settings_file):
    merged = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")

    assert merged["theme"] == "dark"
    assert merged["statusLine"] == EXISTING["statusLine"]
    assert merged["autoCompactWindow"] == 200000
    # Their two hooks survive verbatim.
    assert merged["hooks"]["PreCompact"] == EXISTING["hooks"]["PreCompact"]
    assert merged["hooks"]["PreToolUse"] == EXISTING["hooks"]["PreToolUse"]


def test_install_appends_into_an_event_array_that_already_has_entries(settings_file):
    """A pre-existing SessionStart hook of theirs must not be replaced."""
    settings = installer.load_settings(settings_file)
    theirs = {"hooks": [{"type": "command", "command": "echo hi", "timeout": 3}]}
    settings["hooks"]["SessionStart"] = [theirs]

    merged = installer.merge_install(settings, python_exe="/py")

    assert merged["hooks"]["SessionStart"][0] == theirs
    assert len(merged["hooks"]["SessionStart"]) == 2
    assert installer.is_ours(merged["hooks"]["SessionStart"][1])


def test_install_wires_every_expected_event(settings_file):
    merged = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")
    report = installer.status(merged)
    assert report["missing_events"] == []
    assert set(report["installed_events"]) == {e for e, _, _ in installer.HOOK_EVENTS}
    assert all(
        cmd == "/py -m life_graph.integrations.claude_code.hook"
        for cmd in report["installed_events"].values()
    )


def test_installed_entries_use_no_matcher(settings_file):
    """Absent matcher = all; UserPromptSubmit and Stop reject one outright."""
    merged = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")
    for event, _, _ in installer.HOOK_EVENTS:
        ours = [e for e in merged["hooks"][event] if installer.is_ours(e)]
        assert ours and "matcher" not in ours[0]


def test_session_start_entry_carries_a_status_message(settings_file):
    merged = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")
    entry = [e for e in merged["hooks"]["SessionStart"] if installer.is_ours(e)][0]
    assert entry["hooks"][0]["statusMessage"]
    assert entry["hooks"][0]["timeout"] == 10


# ── Idempotency ──────────────────────────────────────────────────────────


def test_install_twice_does_not_duplicate(settings_file):
    once = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")
    twice = installer.merge_install(once, python_exe="/py")
    assert once == twice
    for event, _, _ in installer.HOOK_EVENTS:
        assert sum(installer.is_ours(e) for e in twice["hooks"][event]) == 1


def test_reinstall_upgrades_a_stale_interpreter_path_in_place(settings_file):
    old = installer.merge_install(installer.load_settings(settings_file), python_exe="/old/py")
    new = installer.merge_install(old, python_exe="/new/py")
    commands = set(installer.status(new)["installed_events"].values())
    assert commands == {"/new/py -m life_graph.integrations.claude_code.hook"}
    assert len(new["hooks"]["Stop"]) == 1  # replaced, not appended


# ── Uninstall restores the original ──────────────────────────────────────


def test_uninstall_restores_the_original_settings(settings_file):
    original = installer.load_settings(settings_file)
    merged = installer.merge_install(original, python_exe="/py")
    restored = installer.merge_uninstall(merged)
    assert restored == original


def test_uninstall_leaves_their_entries_in_a_shared_event(settings_file):
    settings = installer.load_settings(settings_file)
    theirs = {"hooks": [{"type": "command", "command": "echo hi"}]}
    settings["hooks"]["Stop"] = [theirs]

    restored = installer.merge_uninstall(installer.merge_install(settings, python_exe="/py"))
    assert restored["hooks"]["Stop"] == [theirs]
    assert restored == settings


def test_uninstall_on_a_clean_file_is_a_noop(settings_file):
    original = installer.load_settings(settings_file)
    assert installer.merge_uninstall(original) == original


def test_uninstall_from_an_empty_settings_file():
    assert installer.merge_uninstall({}) == {}
    assert installer.merge_uninstall({"theme": "dark"}) == {"theme": "dark"}


# ── Backups and safety ───────────────────────────────────────────────────


def test_apply_writes_a_timestamped_backup(settings_file):
    original_text = settings_file.read_text()
    merged = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")
    backup_path = installer.apply(settings_file, merged)

    assert backup_path is not None
    # Matches the existing settings.json.bak.20260822135550 convention.
    assert backup_path.name.startswith("settings.json.bak.")
    stamp = backup_path.name.rsplit(".", 1)[-1]
    assert len(stamp) == 14 and stamp.isdigit()
    assert backup_path.read_text() == original_text
    assert installer.load_settings(settings_file) == merged


def test_dry_run_writes_nothing(settings_file):
    before = settings_file.read_text()
    merged = installer.merge_install(installer.load_settings(settings_file), python_exe="/py")
    assert installer.apply(settings_file, merged, dry_run=True) is None
    assert settings_file.read_text() == before
    assert not list(settings_file.parent.glob("*.bak.*"))


def test_malformed_settings_are_never_overwritten(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json")
    with pytest.raises(ValueError):
        installer.load_settings(path)
    assert path.read_text() == "{ this is not json"


def test_non_object_settings_are_rejected(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ValueError):
        installer.load_settings(path)


def test_missing_settings_file_starts_from_empty(tmp_path):
    assert installer.load_settings(tmp_path / "nope.json") == {}
    assert installer.backup(tmp_path / "nope.json") is None


def test_unexpected_hooks_shape_is_refused(settings_file):
    settings = installer.load_settings(settings_file)
    settings["hooks"]["Stop"] = "not an array"
    with pytest.raises(ValueError):
        installer.merge_install(settings, python_exe="/py")


# ── Status reporting ─────────────────────────────────────────────────────


def test_status_reports_not_installed_and_names_their_hooks(settings_file):
    report = installer.status(installer.load_settings(settings_file))
    assert report["installed_events"] == {}
    assert set(report["missing_events"]) == {e for e, _, _ in installer.HOOK_EVENTS}
    assert report["other_hook_events"] == ["PreCompact", "PreToolUse"]


def test_hook_command_defaults_to_the_current_interpreter():
    import sys

    assert installer.hook_command().startswith(sys.executable)
    assert installer.hook_command().endswith(installer.HOOK_MARKER)


# ── CLI wiring ───────────────────────────────────────────────────────────


def test_cli_install_and_uninstall_round_trip(settings_file, capsys):
    from life_graph import cli

    original = settings_file.read_text()

    cli.main_argv = None  # sanity: module imported
    args = _args(settings=str(settings_file), dry_run=False, python="/py")
    cli.cmd_hooks_install(args)
    assert installer.status(installer.load_settings(settings_file))["missing_events"] == []

    cli.cmd_hooks_uninstall(_args(settings=str(settings_file), dry_run=False))
    assert json.loads(settings_file.read_text()) == json.loads(original)


def test_cli_dry_run_prints_json_and_writes_nothing(settings_file, capsys):
    from life_graph import cli

    before = settings_file.read_text()
    cli.cmd_hooks_install(_args(settings=str(settings_file), dry_run=True, python="/py"))
    printed = json.loads(capsys.readouterr().out)
    assert installer.status(printed)["missing_events"] == []
    assert settings_file.read_text() == before


def test_cli_status_runs_without_a_backend(settings_file, capsys, monkeypatch, tmp_path):
    from life_graph import cli

    monkeypatch.setenv("LIFE_GRAPH_HOOK_STATE_DIR", str(tmp_path / "state"))
    cli.cmd_hooks_status(_args(settings=str(settings_file), dry_run=False))
    out = capsys.readouterr().out
    assert "not installed" in out
    assert "PreCompact" in out  # their hooks are surfaced, not clobbered


def test_cli_refuses_a_malformed_settings_file(tmp_path, capsys):
    from life_graph import cli

    path = tmp_path / "settings.json"
    path.write_text("{ nope")
    with pytest.raises(SystemExit) as exc:
        cli.cmd_hooks_install(_args(settings=str(path), dry_run=False, python="/py"))
    assert exc.value.code == 1
    assert path.read_text() == "{ nope"


class _args:  # noqa: N801 - a tiny argparse.Namespace stand-in
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return None
