"""Tests for the read-only allowlisted system-inspection tool."""

from life_graph.tools import system_inspect as si


def test_rejects_unknown_check():
    # unknown check must not run anything
    import asyncio

    # asyncio.run() (not get_event_loop().run_until_complete()) — Python 3.14
    # no longer creates an implicit loop when none is running.
    out = asyncio.run(si.inspect_system(check="rm_root"))
    assert out["exit_code"] != 0
    assert "not an allowed" in out["output"].lower()


def test_allowlist_maps_to_readonly_commands():
    # the allowlist must contain only read-only inspection commands
    for cmd in si._ALLOWED.values():
        assert not any(w in cmd for w in ("rm ", "restart", "stop", "kill", "push", ">", "mkfs"))
    assert set(si._ALLOWED) >= {
        "disk",
        "memory",
        "uptime",
        "docker_ps",
        "docker_logs",
        "git_status",
    }
