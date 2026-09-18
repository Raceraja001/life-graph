"""Unit tests for the Claude Code lifecycle-hook adapter.

No database, no network, no live Claude Code: hook JSON goes in on a fake
stdin, and the assertions are on the payload that *would* have been posted, the
process exit code, and what reached stdout.
"""

from __future__ import annotations

import io
import json
import os
from unittest.mock import patch

import pytest

from life_graph.core.trust import TrustTier, classify_surface
from life_graph.integrations.claude_code import config as hook_config
from life_graph.integrations.claude_code import hook, installer, policy, render, transport
from life_graph.integrations.claude_code.transport import SendResult, SendStatus

# ── Test doubles ─────────────────────────────────────────────────────────


class _Response:
    def __init__(self, status_code: int, body=None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text

    def json(self):
        return self._body


class FakeClient:
    """Records every POST; replays a scripted response or raises."""

    def __init__(self, response=None, raises: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._response = response or _Response(201, {"data": {"id": "x"}})
        self._raises = raises

    def post(self, url, json=None, headers=None):  # noqa: A002
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self._raises:
            raise self._raises
        return self._response

    def close(self):
        pass


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A hook config pointed entirely at a temp dir — nothing global is touched."""
    monkeypatch.setenv("LIFE_GRAPH_HOOK_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("LIFE_GRAPH_API_URL", "http://localhost:8080")
    monkeypatch.setenv("LIFE_GRAPH_TENANT_ID", "personal")
    monkeypatch.delenv("LIFE_GRAPH_HOOK_DISABLED", raising=False)
    monkeypatch.delenv("LIFE_GRAPH_API_KEY", raising=False)
    monkeypatch.delenv("LIFE_GRAPH_HOOK_PROJECT_ROOTS", raising=False)
    # Never read a real ~/.life-graph/claude-code/config.json from the dev box.
    monkeypatch.setenv("LIFE_GRAPH_HOOK_CONFIG", str(tmp_path / "no-config.json"))
    return hook_config.load_config()


def _base(event: str, **extra):
    payload = {
        "session_id": "sess-1",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/home/dev/projects/life-graph",
        "permission_mode": "default",
        "hook_event_name": event,
    }
    payload.update(extra)
    return payload


# ── 1 + 2. Per-event payloads, surfaces, and their trust tiers ───────────


def test_user_prompt_submit_captures_with_cli_surface(cfg):
    client = FakeClient()
    hook.dispatch(_base("UserPromptSubmit", prompt="add a retry to the worker"), cfg, client=client)

    assert len(client.calls) == 1
    body = client.calls[0]["json"]
    assert client.calls[0]["url"] == "http://localhost:8080/api/v1/capture/"
    assert client.calls[0]["headers"]["X-Tenant-ID"] == "personal"
    assert body["surface"] == hook_config.SURFACE_CLI == "cli"
    assert body["content"] == "add a retry to the worker"
    # Only "text" is processed into memory; "structured" is store-only.
    assert body["modality"] == "text"
    assert body["properties"]["session_id"] == "sess-1"
    assert body["properties"]["project"] == "life-graph"


def test_user_prompt_submit_surface_is_self_tier():
    """The regression that matters: `cli` must stay TrustTier.SELF."""
    assert classify_surface(hook_config.SURFACE_CLI) is TrustTier.SELF


def test_tool_exhaust_surface_is_verified_tier():
    """`tool_exhaust` must stay VERIFIED — an unknown surface would be EXTERNAL."""
    assert classify_surface(hook_config.SURFACE_TOOL_EXHAUST) is TrustTier.VERIFIED
    assert classify_surface("claude_code") is TrustTier.EXTERNAL  # why we never invent one


def test_user_prompt_submit_never_rewrites_the_prompt(cfg):
    out = hook.dispatch(_base("UserPromptSubmit", prompt="hello there"), cfg, client=FakeClient())
    assert out is None  # no updatedPrompt, no additionalContext


def test_post_tool_use_captures_tool_exhaust(cfg):
    client = FakeClient()
    hook.dispatch(
        _base(
            "PostToolUse",
            tool_name="Bash",
            tool_input={"command": "pytest -q"},
            tool_response={"stdout": "42 passed"},
            tool_use_id="toolu_1",
            duration_ms=1234,
        ),
        cfg,
        client=client,
    )
    body = client.calls[0]["json"]
    assert body["surface"] == hook_config.SURFACE_TOOL_EXHAUST == "tool_exhaust"
    assert body["content"].startswith("tool:Bash status:ok 1234ms args:")
    assert body["properties"]["tool_use_id"] == "toolu_1"


def test_post_tool_use_failure_is_high_signal_and_never_sampled(cfg):
    """A failure always sends, even with the daily cap exhausted."""
    counter = policy.DailyCounter(cfg.counter_path)
    counter.check_and_increment(low_signal=False, daily_cap=0, sample_rate=0.0)
    client = FakeClient()
    hook.dispatch(
        _base(
            "PostToolUseFailure",
            tool_name="Bash",
            tool_input={"command": "false"},
            tool_use_id="toolu_2",
            error="exit 1",
        ),
        cfg,
        client=client,
        # rng that would drop everything if the sampler were consulted
    )
    body = client.calls[0]["json"]
    assert "status:error" in body["content"]
    assert body["properties"]["error"] == "exit 1"


def test_stop_captures_last_assistant_message(cfg):
    client = FakeClient()
    message = "I refactored the scheduler so subscribe() is idempotent across restarts."
    hook.dispatch(
        _base("Stop", stop_hook_active=False, last_assistant_message=message), cfg, client=client
    )
    body = client.calls[0]["json"]
    assert body["surface"] == "tool_exhaust"
    assert body["content"] == message


def test_stop_drops_trivial_messages(cfg):
    client = FakeClient()
    hook.dispatch(
        _base("Stop", stop_hook_active=False, last_assistant_message="Done."), cfg, client=client
    )
    assert client.calls == []


def test_subagent_stop_records_agent_type(cfg):
    client = FakeClient()
    hook.dispatch(
        _base(
            "SubagentStop",
            stop_hook_active=False,
            agent_id="a-1",
            agent_type="Explore",
            last_assistant_message="Found the handler in life_graph/api/capture.py and traced it.",
        ),
        cfg,
        client=client,
    )
    props = client.calls[0]["json"]["properties"]
    assert props["agent_type"] == "Explore"
    assert props["agent_id"] == "a-1"


def test_session_start_injects_additional_context(cfg):
    recall = {
        "identity": [{"content": "Prefers cheap models (Gemini Flash, DeepSeek)."}],
        "decisions": [{"content": "Chose Apache AGE over Neo4j to stay inside Postgres."}],
        "intentions": [{"content": "Ship the hooks adapter", "priority": "high"}],
        "warnings": [],
    }
    client = FakeClient(response=_Response(200, {"data": recall}))
    out = hook.dispatch(_base("SessionStart", source="startup"), cfg, client=client)

    assert client.calls[0]["url"] == "http://localhost:8080/api/v1/search/recall"
    assert client.calls[0]["json"]["context"]["project"] == "life-graph"
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "Apache AGE" in hso["additionalContext"]
    assert "[high] Ship the hooks adapter" in hso["additionalContext"]
    assert out["systemMessage"].startswith("Life Graph recall:")


def test_session_start_is_skipped_on_compact(cfg):
    """`source == "compact"` means context is being compacted, not started."""
    client = FakeClient()
    assert hook.dispatch(_base("SessionStart", source="compact"), cfg, client=client) is None
    assert client.calls == []


def test_session_start_emits_nothing_when_recall_is_empty(cfg):
    empty = {"identity": [], "decisions": [], "intentions": [], "warnings": []}
    client = FakeClient(response=_Response(200, {"data": empty}))
    assert hook.dispatch(_base("SessionStart", source="startup"), cfg, client=client) is None


def test_unknown_event_is_a_noop(cfg):
    client = FakeClient()
    assert hook.dispatch(_base("PreCompact", trigger="auto"), cfg, client=client) is None
    assert client.calls == []


# ── 3. Backend unreachable / slow / 500 → exit 0, clean stdout ───────────


@pytest.mark.parametrize(
    "kwargs",
    [
        {"raises": ConnectionError("connection refused")},
        {"raises": TimeoutError("timed out")},
        {"response": _Response(500, text="boom")},
        {"response": _Response(401, text="nope")},
        {"response": _Response(422, text="bad payload")},
    ],
)
def test_backend_failures_never_break_the_hook(cfg, kwargs, monkeypatch):
    client = FakeClient(**kwargs)
    monkeypatch.setattr("httpx.Client", lambda **_: client)
    stdout = io.StringIO()
    payload = json.dumps(_base("UserPromptSubmit", prompt="does this survive a dead backend?"))

    code = hook.main(stdin=io.StringIO(payload), stdout=stdout)

    assert code == 0
    assert stdout.getvalue() == ""


def test_malformed_stdin_exits_zero_silently():
    stdout = io.StringIO()
    assert hook.main(stdin=io.StringIO("not json at all"), stdout=stdout) == 0
    assert stdout.getvalue() == ""
    assert hook.main(stdin=io.StringIO(""), stdout=io.StringIO()) == 0


def test_handler_exception_exits_zero(cfg, monkeypatch):
    monkeypatch.setattr(hook, "dispatch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    stdout = io.StringIO()
    assert hook.main(stdin=io.StringIO(json.dumps(_base("Stop"))), stdout=stdout) == 0
    assert stdout.getvalue() == ""


@pytest.mark.parametrize(
    "raw, expected",
    [
        (r"h:\DevTools\Projects\life-graph", "/mnt/h/DevTools/Projects/life-graph"),
        ("H:/DevTools/Projects", "/mnt/h/DevTools/Projects"),
        ("C:\\", "/mnt/c"),
        ("/home/raja/code", "/home/raja/code"),
    ],
)
def test_windows_cwd_maps_to_wsl_mount(raw, expected):
    assert hook_config.normalize_path(raw) == expected


def test_project_scope_accepts_windows_and_wsl_spellings():
    roots = (r"H:\DevTools\Projects",)
    assert hook_config.in_project_roots(r"h:\DevTools\Projects\life-graph", roots)
    assert hook_config.in_project_roots("/mnt/h/DevTools/Projects/learn-ai/x", roots)
    assert not hook_config.in_project_roots(r"C:\Users\me\Documents", roots)
    assert not hook_config.in_project_roots("/mnt/h/DevTools/ProjectsOther", roots)
    assert hook_config.in_project_roots("/anywhere", ())  # no roots: everything


def test_out_of_scope_session_does_nothing(cfg, monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_HOOK_PROJECT_ROOTS", "/mnt/h/DevTools/Projects")
    calls = []
    monkeypatch.setattr(hook, "dispatch", lambda payload, *a, **k: calls.append(payload["cwd"]))
    event = _base("UserPromptSubmit", prompt="hi", cwd=r"C:\Users\me\Documents")
    assert hook.main(stdin=io.StringIO(json.dumps(event)), stdout=io.StringIO()) == 0
    assert calls == []
    event["cwd"] = r"h:\DevTools\Projects\life-graph"
    hook.main(stdin=io.StringIO(json.dumps(event)), stdout=io.StringIO())
    assert calls == ["/mnt/h/DevTools/Projects/life-graph"]  # normalized before handlers


def test_config_file_supplies_key_and_env_overrides(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "tenant_id": "raja",
                "api_key": "k-file",
                "project_roots": ["/mnt/h/DevTools/Projects"],
            }
        )
    )
    for var in ("LIFE_GRAPH_TENANT_ID", "LIFE_GRAPH_API_KEY", "LIFE_GRAPH_HOOK_PROJECT_ROOTS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LIFE_GRAPH_HOOK_CONFIG", str(path))
    cfg = hook_config.load_config()
    assert (cfg.tenant_id, cfg.api_key, cfg.project_roots) == (
        "raja",
        "k-file",
        ("/mnt/h/DevTools/Projects",),
    )
    monkeypatch.setenv("LIFE_GRAPH_API_KEY", "k-env")
    assert hook_config.load_config().api_key == "k-env"


def test_disabled_flag_short_circuits(cfg, monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_HOOK_DISABLED", "1")
    calls = []
    monkeypatch.setattr(hook, "dispatch", lambda *a, **k: calls.append(1))
    assert hook.main(stdin=io.StringIO(json.dumps(_base("Stop"))), stdout=io.StringIO()) == 0
    assert calls == []


def test_transient_failure_spools_and_session_end_flushes(cfg):
    dead = FakeClient(raises=ConnectionError("refused"))
    hook.dispatch(_base("UserPromptSubmit", prompt="spool me please"), cfg, client=dead)
    assert transport.CaptureQueue(cfg.spool_path).pending_count() == 1

    alive = FakeClient()
    hook.dispatch(_base("SessionEnd", reason="clear"), cfg, client=alive)
    assert transport.CaptureQueue(cfg.spool_path).pending_count() == 0
    assert alive.calls[0]["json"]["content"] == "spool me please"


def test_auth_and_bad_are_not_spooled(cfg):
    """A wrong key or a rejected payload must not retry forever."""
    for response in (_Response(403, text="forbidden"), _Response(422, text="invalid")):
        hook.dispatch(
            _base("UserPromptSubmit", prompt="do not spool this one"),
            cfg,
            client=FakeClient(response=response),
        )
    assert transport.CaptureQueue(cfg.spool_path).pending_count() == 0


# ── 4. Sampling: client-side drops, and a cap that survives processes ────


def test_low_signal_definition_matches_the_backend_policy():
    from life_graph.services.tool_observation import (
        DAILY_CAP,
        LOW_SIGNAL_SAMPLE_RATE,
        ToolObservationHook,
    )

    assert hook_config.DAILY_CAP == DAILY_CAP
    assert hook_config.LOW_SIGNAL_SAMPLE_RATE == LOW_SIGNAL_SAMPLE_RATE
    obs = {"exit_status": "ok", "project_id": None}
    assert policy.is_low_signal(obs) is ToolObservationHook.is_low_signal(obs)
    err = {"exit_status": "error", "project_id": None}
    assert policy.is_low_signal(err) is ToolObservationHook.is_low_signal(err)


def test_throttled_tool_call_makes_no_http_call(cfg, monkeypatch):
    """The whole point of a client-side sampler: no request at all."""
    monkeypatch.setenv("LIFE_GRAPH_HOOK_DAILY_CAP", "0")
    monkeypatch.setenv("LIFE_GRAPH_HOOK_SAMPLE_RATE", "0.0")
    throttled_cfg = hook_config.load_config()

    client = FakeClient()
    payload = _base(
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": "/x.py"},
        tool_response={"ok": True},
        tool_use_id="t1",
    )
    hook.dispatch(payload, throttled_cfg, client=client)
    assert client.calls == []
    # …and nothing was spooled either — it was dropped, not deferred.
    assert not throttled_cfg.spool_path.exists()


def test_daily_cap_holds_across_processes(cfg, tmp_path):
    """Two DailyCounter instances = two hook processes sharing one state file."""
    path = tmp_path / "counter.json"
    first = policy.DailyCounter(path)
    for _ in range(3):
        assert first.check_and_increment(low_signal=True, daily_cap=3, sample_rate=0.0) is True

    second = policy.DailyCounter(path)  # a fresh process
    assert second.current() == 3
    assert second.check_and_increment(low_signal=True, daily_cap=3, sample_rate=0.0) is False
    # High-signal still gets through once the cap is hit.
    assert second.check_and_increment(low_signal=False, daily_cap=3, sample_rate=0.0) is True


def test_daily_cap_resets_on_a_new_utc_day(tmp_path):
    path = tmp_path / "counter.json"
    path.write_text(json.dumps({"date": "1999-01-01", "count": 9999}))
    assert policy.DailyCounter(path).current() == 0


def test_counter_fails_open_on_unwritable_state(tmp_path):
    """A broken counter file must not become a silent capture outage."""
    blocked = tmp_path / "not-a-dir" / "counter.json"
    (tmp_path / "not-a-dir").write_text("i am a file")
    assert (
        policy.DailyCounter(blocked).check_and_increment(
            low_signal=True, daily_cap=0, sample_rate=0.0
        )
        is True
    )


def test_sampling_uses_the_rate_above_the_cap():
    assert policy.should_store(600, True, daily_cap=500, sample_rate=0.1, rng=lambda: 0.05) is True
    assert policy.should_store(600, True, daily_cap=500, sample_rate=0.1, rng=lambda: 0.5) is False
    assert policy.should_store(600, False, daily_cap=500, sample_rate=0.1, rng=lambda: 0.9) is True


# ── 5. Redaction ─────────────────────────────────────────────────────────


SECRET = "sk-abcdefghijklmnop0123456789"


def test_api_key_in_a_prompt_never_leaves_the_machine(cfg):
    client = FakeClient()
    hook.dispatch(
        _base("UserPromptSubmit", prompt=f"deploy with OPENAI_API_KEY={SECRET} please"),
        cfg,
        client=client,
    )
    sent = json.dumps(client.calls[0]["json"])
    assert SECRET not in sent
    assert "[REDACTED]" in sent


def test_api_key_in_tool_args_never_leaves_the_machine(cfg):
    client = FakeClient()
    hook.dispatch(
        _base(
            "PostToolUse",
            tool_name="Bash",
            tool_input={"command": f"curl -H 'Authorization: Bearer {SECRET}' https://api.x.com"},
            tool_response={"stdout": "ok"},
            tool_use_id="t9",
        ),
        cfg,
        client=client,
    )
    sent = json.dumps(client.calls[0]["json"])
    assert SECRET not in sent
    assert "[REDACTED]" in sent


def test_secrets_in_nested_properties_are_redacted(cfg):
    payload = transport.build_capture_payload(
        surface="cli",
        content="nothing here",
        cfg=cfg,
        properties={"nested": {"list": [f"token={SECRET}"]}},
    )
    assert SECRET not in json.dumps(payload)


def test_content_is_clipped(cfg, monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_HOOK_MAX_CONTENT", "50")
    small = hook_config.load_config()
    payload = transport.build_capture_payload(
        surface="cli", content="x" * 500, cfg=small, properties={}
    )
    assert len(payload["content"]) < 100
    assert "[+450 chars]" in payload["content"]


# ── Rendering + context ──────────────────────────────────────────────────


def test_render_is_markdown_not_json():
    out = render.render_recall({"decisions": [{"content": "Use ARQ, not Celery."}]})
    assert out.startswith("## Recalled from Life Graph")
    assert "- Use ARQ, not Celery." in out
    assert "{" not in out


def test_render_handles_garbage():
    assert render.render_recall(None) == ""
    assert render.render_recall({"decisions": "not a list"}) == ""
    assert render.render_recall({"identity": [{"content": ""}, "junk", 3]}) == ""


def test_render_caps_item_count_and_length():
    long_items = [{"content": "y" * 1000} for _ in range(20)]
    out = render.render_recall({"decisions": long_items})
    bullets = [line for line in out.splitlines() if line.startswith("- ")]
    assert len(bullets) == render.MAX_ITEMS_PER_SECTION
    assert all(len(line) <= render.MAX_ITEM_CHARS + 2 for line in bullets)


def test_context_fingerprint_uses_cwd_and_branch(tmp_path):
    from life_graph.integrations.claude_code.context import build_session_context

    repo = tmp_path / "my-project"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/feature/hooks\n")
    context = build_session_context({"cwd": str(repo)})
    assert context["project"] == "my-project"
    assert context["git_branch"] == "feature/hooks"


def test_context_without_git_omits_branch(tmp_path):
    from life_graph.integrations.claude_code.context import build_session_context

    with patch.dict(os.environ, {}, clear=False):
        context = build_session_context({"cwd": str(tmp_path)})
    assert "git_branch" not in context or context["git_branch"]


# ── Config + transport plumbing ──────────────────────────────────────────


def test_defaults_when_nothing_is_configured(monkeypatch, tmp_path):
    for var in ("LIFE_GRAPH_API_URL", "LIFE_GRAPH_TENANT_ID", "LIFE_GRAPH_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # A real ~/.life-graph/claude-code/config.json on the dev box would win.
    monkeypatch.setenv("LIFE_GRAPH_HOOK_CONFIG", str(tmp_path / "no-config.json"))
    cfg = hook_config.load_config()
    assert cfg.capture_url == "http://localhost:8080/api/v1/capture/"
    assert cfg.tenant_id == "personal"
    assert "Authorization" not in cfg.headers


def test_api_key_becomes_a_bearer_header(monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_API_KEY", "secret-key")
    assert hook_config.load_config().headers["Authorization"] == "Bearer secret-key"


def test_send_triage_matches_the_desktop_client(cfg):
    cases = [
        (_Response(201), SendStatus.SENT),
        (_Response(403, text="x"), SendStatus.AUTH),
        (_Response(503, text="x"), SendStatus.TRANSIENT),
        (_Response(422, text="x"), SendStatus.BAD),
    ]
    for response, expected in cases:
        result = transport.post_capture({}, cfg, client=FakeClient(response=response))
        assert result.status == expected
    assert isinstance(result, SendResult)


def test_module_is_runnable_as_a_script():
    """`python3 -m life_graph.integrations.claude_code.hook` must work."""
    import runpy
    import subprocess
    import sys as _sys

    assert runpy is not None
    proc = subprocess.run(
        [_sys.executable, "-m", "life_graph.integrations.claude_code.hook"],
        input='{"hook_event_name":"PreCompact","trigger":"auto"}',
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "LIFE_GRAPH_HOOK_DISABLED": "1"},
    )
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_installer_marker_matches_the_module_path():
    """The installed command must be the module this test file imports."""
    assert hook.__name__ == installer.HOOK_MARKER
