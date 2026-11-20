"""H2 (audit 2026-11-19): a service key could make the host run shell commands.

A project's ``deploy_command``, ``smoke_command``, ``rollback_command`` and
``backup_check_command`` run as a shell on the host, as the worker user, and
any service key could set them (``POST /projects``, ``PATCH /projects/{id}``);
the hourly uptime watcher then ran the backup check with no approval at all.
(An autonomy action's ``rollback_command``: test_autonomy_rollback_approval.py.)

Now:

* setting or changing one needs an owner-verified caller (owner key or paired
  device, api/auth.py ``ingress_for``), else 403; clearing one is allowed;
* the owner's write is the approval, pinned to the exact text
  (``scan_metadata["command_approvals"][field]["sha256"]``);
* every executor runs only :func:`approved_command` — a command with no
  approval (set before this change) or edited in the database is skipped;
* a deploy approval carries the hashes and is re-checked when it runs.

Only harmless commands (echo/exit/rm of a temp file) run here, in tmp_path.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
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
# Spelled out, not read from the module: these are the fields that run on the host.
COMMANDS = ["backup_check_command", "deploy_command", "rollback_command", "smoke_command"]


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _approved(meta: dict) -> dict:
    return reg.approve_commands(meta, "owner:api_key")


# ── the pin itself ───────────────────────────────────────────────────────


def test_a_command_set_before_approvals_existed_does_not_run():
    assert reg.approved_command({"backup_check_command": "exit 0"}, "backup_check_command") is None


def test_an_approved_command_edited_in_the_database_does_not_run():
    meta = _approved({"deploy_command": "echo deploy"})
    assert reg.approved_command(meta, "deploy_command") == "echo deploy"
    meta["deploy_command"] = "echo something else"
    assert reg.approved_command(meta, "deploy_command") is None


@pytest.mark.parametrize("field", COMMANDS)
def test_a_non_owner_cannot_set_a_command(field):
    meta: dict = {}
    with pytest.raises(reg.CommandApprovalError, match=field):
        reg.apply_command_settings(meta, {field: "echo hi"}, approved_by=None)
    assert meta == {}


@pytest.mark.parametrize("field", COMMANDS)
def test_the_owner_sets_a_command_and_its_approval_is_pinned(field):
    meta: dict = {}
    reg.apply_command_settings(meta, {field: "echo hi"}, approved_by="device:phone-1")
    record = meta["command_approvals"][field]
    assert meta[field] == "echo hi"
    assert record["sha256"] == _sha("echo hi")
    assert record["approved_by"] == "device:phone-1"
    assert record["approved_at"]
    assert reg.approved_command(meta, field) == "echo hi"


@pytest.mark.parametrize("field", COMMANDS)
def test_anyone_may_clear_a_command(field):
    meta = _approved({field: "echo hi"})
    reg.apply_command_settings(meta, {field: ""}, approved_by=None)
    assert field not in meta and "command_approvals" not in meta


def test_resending_the_approved_command_is_a_no_op_but_a_legacy_one_needs_the_owner():
    meta = _approved({"smoke_command": "echo ok"})
    before = dict(meta)
    reg.apply_command_settings(meta, {"smoke_command": "echo ok"}, approved_by=None)
    assert meta == before
    with pytest.raises(reg.CommandApprovalError):
        reg.apply_command_settings(
            {"smoke_command": "echo ok"}, {"smoke_command": "echo ok"}, approved_by=None
        )


def test_command_texts_are_hidden_from_non_owners_but_not_whether_one_is_set():
    project = {"scan_metadata": _approved({"deploy_command": "TOKEN=s3cret ./deploy"})}
    shown = reg.redact_commands(project)["scan_metadata"]
    assert shown["deploy_command"] == reg.HIDDEN_COMMAND
    assert "command_approvals" in shown
    assert project["scan_metadata"]["deploy_command"] == "TOKEN=s3cret ./deploy"


# ── the API routes ───────────────────────────────────────────────────────


def _project_row(meta: dict) -> Project:
    now = datetime.now(UTC)
    return Project(
        id=uuid.uuid4(),
        tenant_id="t1",
        name="shop",
        path="/srv/shop",
        scan_metadata=meta,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr("life_graph.watchers.provision.ensure_config", AsyncMock())

    def make(meta: dict | None = None):
        row = _project_row(meta or {})
        session = FakeSession(row)
        return reg.ProjectRegistry(session_factory=lambda: session), row, session

    return make


async def _patch(registry_svc, row, key, **fields):
    from life_graph.api.kernel import ProjectUpdate, update_project

    with tenant_scope("t1"):
        return await update_project(
            row.id, ProjectUpdate(**fields), fake_request(api_key=key), registry_svc
        )


@pytest.mark.parametrize("field", COMMANDS)
async def test_patch_with_a_service_key_cannot_set_a_command(registry, field):
    svc, row, session = registry()
    with pytest.raises(HTTPException) as exc:
        await _patch(svc, row, SERVICE_KEY, **{field: "echo hi"})
    assert exc.value.status_code == 403
    assert "owner" in exc.value.detail
    assert field not in row.scan_metadata
    assert session.commits == 0


async def test_patch_with_a_service_key_still_sets_other_settings(registry):
    # A harmless setting. (This used health_url; setting one is now owner-only
    # as well, since the host probes it hourly: test_project_safety_settings.py.)
    svc, row, _ = registry()
    await _patch(svc, row, SERVICE_KEY, description="x", sandbox_test_timeout=600)
    assert row.scan_metadata == {"sandbox_test_timeout": 600}


async def test_patch_with_a_service_key_may_clear_a_command(registry):
    svc, row, _ = registry(_approved({"backup_check_command": "exit 0"}))
    await _patch(svc, row, SERVICE_KEY, backup_check_command="")
    assert row.scan_metadata == {}


@pytest.mark.parametrize("field", COMMANDS)
async def test_patch_with_the_owner_key_sets_and_approves_a_command(registry, field):
    svc, row, _ = registry()
    out = await _patch(svc, row, OWNER_KEY, **{field: "echo hi"})
    assert row.scan_metadata[field] == "echo hi"
    assert row.scan_metadata["command_approvals"][field]["approved_by"] == "owner:api_key"
    assert reg.approved_command(row.scan_metadata, field) == "echo hi"
    assert out["data"]["scan_metadata"][field] == "echo hi"  # the owner sees it


async def test_a_paired_device_counts_as_the_owner(registry):
    from life_graph.api.kernel import ProjectUpdate, update_project

    svc, row, _ = registry()
    with tenant_scope("t1"):
        await update_project(
            row.id,
            ProjectUpdate(deploy_command="echo deploy"),
            fake_request(device_id="phone-1"),
            svc,
        )
    assert row.scan_metadata["command_approvals"]["deploy_command"]["approved_by"] == (
        "device:phone-1"
    )


async def test_get_project_hides_command_texts_from_a_service_key(registry):
    from life_graph.api.kernel import get_project

    svc, row, _ = registry(_approved({"deploy_command": "TOKEN=s3cret ./deploy"}))
    with tenant_scope("t1"):
        other = await get_project(row.id, fake_request(api_key=SERVICE_KEY), svc)
        owner = await get_project(row.id, fake_request(api_key=OWNER_KEY), svc)
    assert other["data"]["scan_metadata"]["deploy_command"] == reg.HIDDEN_COMMAND
    assert owner["data"]["scan_metadata"]["deploy_command"] == "TOKEN=s3cret ./deploy"


async def test_register_with_a_service_key_cannot_set_a_command(monkeypatch, registry):
    from life_graph.api.kernel import ProjectRegister, register_project

    monkeypatch.setattr(reg, "_confined_project_path", lambda p: p)
    svc, _, session = registry()
    body = ProjectRegister(name="shop", path="/srv/shop", backup_check_command="exit 0")
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await register_project(body, fake_request(api_key=SERVICE_KEY), svc)
    assert exc.value.status_code == 403
    assert session.added == []


async def test_register_with_the_owner_key_pins_the_command(monkeypatch, registry, tmp_path):
    from life_graph.api.kernel import ProjectRegister, register_project

    monkeypatch.setattr(reg, "_confined_project_path", lambda p: p)
    session = FakeSession(None)  # no project with that name yet
    svc = reg.ProjectRegistry(session_factory=lambda: session)
    body = ProjectRegister(name="shop", path=str(tmp_path), backup_check_command="exit 0")

    def refresh_sets_timestamps(obj, **_k):
        obj.created_at = obj.updated_at = datetime.now(UTC)
        obj.is_active = True

    session.refresh = AsyncMock(side_effect=refresh_sets_timestamps)
    with tenant_scope("t1"):
        await register_project(body, fake_request(api_key=OWNER_KEY), svc)
    (project,) = session.added
    assert reg.approved_command(project.scan_metadata, "backup_check_command") == "exit 0"


# ── the uptime watcher's backup check ────────────────────────────────────


@pytest.fixture
def shell(monkeypatch):
    calls: list[str] = []

    async def fake_run_shell(command, cwd, timeout):
        calls.append(command)
        return 0, "ok"

    monkeypatch.setattr("life_graph.services.approvals._run_shell", fake_run_shell)
    return calls


def _watcher():
    from life_graph.watchers import app_uptime_watcher as up

    return up.AppUptimeWatcher("t1", session_factory=None)


@pytest.mark.parametrize("case", ["legacy", "modified-in-db"])
async def test_the_watcher_refuses_an_unapproved_backup_check(shell, case):
    if case == "legacy":  # set before approvals existed
        meta = {"backup_check_command": "exit 0"}
    else:
        meta = {**_approved({"backup_check_command": "exit 0"}), "backup_check_command": "exit 1"}
    watcher = _watcher()
    project = {"id": "p1", "name": "shop", "path": "/srv/shop", "scan_metadata": meta}
    now = datetime.now(UTC)

    state = await watcher._check_backups(project, meta, {}, now)
    state = await watcher._check_backups(project, meta, state, now)

    assert shell == []
    assert state["backup_unapproved"] is True
    assert "backup_checked_at" not in state
    (event,) = watcher._events  # said once, not every hour
    assert "not approved" in event.title


async def test_the_watcher_runs_the_approved_backup_check(shell):
    watcher = _watcher()
    meta = _approved({"backup_check_command": "exit 0"})
    project = {"id": "p1", "name": "shop", "path": "/srv/shop", "scan_metadata": meta}

    state = await watcher._check_backups(
        project, meta, {"backup_unapproved": True}, datetime.now(UTC)
    )

    assert shell == ["exit 0"]
    assert state["backup_exit"] == 0 and "backup_unapproved" not in state


async def test_app_health_reports_an_unapproved_backup_check():
    from life_graph.services import app_health

    rows = [
        SimpleNamespace(id="a", name="legacy", scan_metadata={"backup_check_command": "exit 0"}),
        SimpleNamespace(id="b", name="ok", scan_metadata=_approved({"backup_check_command": "x"})),
    ]
    apps = await app_health.report(FakeSession(rows, None), "t1")
    by_name = {a["project"]: a["backup"] for a in apps}
    assert by_name == {"legacy": "not approved", "ok": "not checked yet"}
    assert "backup check not approved" in app_health.lines(apps)[0]


# ── driver_deploy: filing and running ────────────────────────────────────


@pytest.fixture
def events(monkeypatch):
    from life_graph.services import approvals as approvals_mod

    seen: list[dict] = []

    async def emit(_type, payload, **_k):
        seen.append(payload)

    monkeypatch.setattr(approvals_mod.event_bus, "emit", emit)
    return seen


def _merge_approval(project_id) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id="t1",
        payload={"project_id": str(project_id), "task_id": "task-1", "merge_commit": "abc12345"},
    )


async def _file_deploy(monkeypatch, meta) -> FakeSession:
    from life_graph.services import approvals as approvals_mod

    project = SimpleNamespace(id=uuid.uuid4(), name="shop", scan_metadata=meta)

    async def get_scoped(_session, _model, _pk, _tenant):
        return project

    monkeypatch.setattr(approvals_mod, "get_scoped", get_scoped)
    session = FakeSession()
    await approvals_mod.ApprovalService(session)._maybe_file_deploy_approval(
        _merge_approval(project.id)
    )
    return session


@pytest.mark.parametrize("case", ["legacy-deploy", "unapproved-smoke"])
async def test_no_deploy_is_filed_for_an_unapproved_command(monkeypatch, events, case):
    if case == "legacy-deploy":
        meta = {"deploy_on_merge": True, "deploy_command": "echo deploy"}
    else:
        meta = {
            "deploy_on_merge": True,
            **_approved({"deploy_command": "echo deploy"}),
            "smoke_command": "echo smoke",  # smoke set without approval
        }
    session = await _file_deploy(monkeypatch, meta)
    assert session.added == []
    (event,) = events
    assert event["kind"] == "deploy_command_unapproved"


async def test_a_filed_deploy_carries_the_approved_commands_and_their_hashes(monkeypatch, events):
    meta = {
        "deploy_on_merge": True,
        **_approved({"deploy_command": "echo deploy", "smoke_command": "echo smoke"}),
    }
    session = await _file_deploy(monkeypatch, meta)
    (appr,) = session.added
    assert appr.payload["deploy_command"] == "echo deploy"
    assert appr.payload["rollback_command"] is None
    assert appr.payload["command_sha256"] == {
        "deploy_command": _sha("echo deploy"),
        "smoke_command": _sha("echo smoke"),
    }


def _deploy_payload(tmp_path, **commands) -> dict:
    return {
        "project_id": str(uuid.uuid4()),
        "repo_path": str(tmp_path),
        "merge_commit": "abc12345",
        **commands,
        "command_sha256": {k: _sha(v) for k, v in commands.items()},
    }


async def _run_deploy(monkeypatch, tmp_path, payload, project_meta):
    from life_graph.services import approvals as approvals_mod
    from life_graph.tools._guards import confine_to

    monkeypatch.setattr(
        "life_graph.services.dev.production_findings.file_fix_task",
        AsyncMock(return_value={"queued": "fix-1"}),
    )
    svc = approvals_mod.ApprovalService(FakeSession())
    project = None if project_meta is None else {"scan_metadata": project_meta, "name": "shop"}
    monkeypatch.setattr(svc, "_project_dict", AsyncMock(return_value=project))
    appr = SimpleNamespace(
        id=uuid.uuid4(), tenant_id="t1", title="Deploy", payload=payload, resolution_note=None
    )
    with confine_to(tmp_path):
        await svc._apply_driver_deploy(appr, True)
    return appr


async def test_an_approved_deploy_with_smoke_and_rollback_runs(monkeypatch, tmp_path, events):
    commands = {
        "deploy_command": "echo deployed > deployed.txt",
        "smoke_command": "exit 3",
        "rollback_command": "rm deployed.txt",
    }
    appr = await _run_deploy(
        monkeypatch, tmp_path, _deploy_payload(tmp_path, **commands), _approved(commands)
    )
    assert appr.payload["smoke"]["exit"] == 3
    assert appr.payload["rollback"]["exit"] == 0
    assert not (tmp_path / "deployed.txt").exists()  # deployed, then rolled back


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"deploy_command": "echo other > deployed.txt"}, "deploy_command changed"),
        ({"smoke_command": "echo other"}, "smoke_command changed"),
        ({"rollback_command": "echo other"}, "rollback_command changed"),
    ],
)
async def test_a_command_changed_after_filing_is_refused(monkeypatch, tmp_path, change, reason):
    from life_graph.services.approvals import ApprovalActionError

    commands = {
        "deploy_command": "echo deployed > deployed.txt",
        "smoke_command": "echo smoke",
        "rollback_command": "echo rollback",
    }
    now = _approved({**commands, **change})  # the owner changed it since
    with pytest.raises(ApprovalActionError, match=reason):
        await _run_deploy(monkeypatch, tmp_path, _deploy_payload(tmp_path, **commands), now)
    assert not (tmp_path / "deployed.txt").exists()


async def test_a_command_edited_in_the_database_is_refused(monkeypatch, tmp_path):
    from life_graph.services.approvals import ApprovalActionError

    commands = {"deploy_command": "echo deployed > deployed.txt"}
    tampered = {**_approved(commands), "deploy_command": "echo pwned > deployed.txt"}
    payload = _deploy_payload(tmp_path, deploy_command="echo pwned > deployed.txt")
    with pytest.raises(ApprovalActionError, match="no longer owner-approved"):
        await _run_deploy(monkeypatch, tmp_path, payload, tampered)
    assert not (tmp_path / "deployed.txt").exists()


@pytest.mark.parametrize("case", ["payload-without-hashes", "legacy-project", "project-gone"])
async def test_unpinned_deploys_are_refused(monkeypatch, tmp_path, case):
    from life_graph.services.approvals import ApprovalActionError

    commands = {"deploy_command": "echo deployed > deployed.txt"}
    payload = _deploy_payload(tmp_path, **commands)
    meta: dict | None = _approved(commands)
    if case == "payload-without-hashes":  # filed before this change
        payload.pop("command_sha256")
    elif case == "legacy-project":
        meta = dict(commands)
    else:
        meta = None
    with pytest.raises(ApprovalActionError, match="not run"):
        await _run_deploy(monkeypatch, tmp_path, payload, meta)
    assert not (tmp_path / "deployed.txt").exists()
