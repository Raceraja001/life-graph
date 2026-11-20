"""P0 (2026-11-20): an approved action runs at most once.

Before: ``resolve()`` locked the row, ran the side effect (git push, a merge,
a deploy of up to ten minutes) inside the request's transaction, and the
caller committed afterwards. If the API process died, or lost its database
connection, after the side effect but before that commit, the row rolled
back to ``pending`` with no trace that anything had run, and the next
approve (or the auto-merge sweep) ran it again: a second deploy.

Now the kinds whose effect lives outside the transaction commit an execution
claim (``payload["execution"]``) first. A row left with a "started" claim is
refused (409) until the stale sweep turns it into "unknown"; then only an
explicit retry runs a non-idempotent effect again, while a merge or PR open
simply re-runs and finds it already done.

The session below keeps a committed copy of the row: ``commit()`` saves it,
``refresh()`` (the locking re-read) and a brand-new session read it back,
exactly as Postgres would after a rollback or a process restart. The real
two-connection versions are in tests/integration/test_approvals.py.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.services import approvals as approvals_mod
from life_graph.services.approvals import (
    ApprovalActionError,
    ApprovalAlreadyResolvedError,
    ApprovalNeedsRetryError,
    ApprovalService,
)
from tests.unit.fakes import FakeSession, session_factory, sql

_FIELDS = ("status", "payload", "resolution_note", "resolved_by", "resolved_at")


def _row(kind: str = "driver_deploy", payload: dict | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="t",
        kind=kind,
        status="pending",
        title=f"{kind} item",
        detail="",
        source="test",
        source_ref=None,
        payload=dict(payload or {}),
        created_at=None,
        resolved_by=None,
        resolved_at=None,
        resolution_note=None,
    )


class _Db:
    """The committed state of one approval row."""

    def __init__(self, row):
        self.row = row
        self.committed = {f: copy.deepcopy(getattr(row, f)) for f in _FIELDS}

    def session(self) -> _Session:
        """A new session (a new request, or the API after a restart)."""
        fresh = SimpleNamespace(**vars(self.row))
        for f in _FIELDS:
            setattr(fresh, f, copy.deepcopy(self.committed[f]))
        return _Session(self, fresh)


class _Session:
    def __init__(self, db: _Db, obj):
        self.db = db
        self.obj = obj
        self.commits = 0
        self.rollbacks = 0
        self.events: list[str] = []

    async def get(self, _model, _pk, **_kw):
        return self.obj

    async def refresh(self, obj, **_kw):
        self.events.append("lock")
        for f in _FIELDS:
            setattr(obj, f, copy.deepcopy(self.db.committed[f]))

    async def commit(self):
        self.commits += 1
        self.events.append("commit")
        self.db.committed = {f: copy.deepcopy(getattr(self.obj, f)) for f in _FIELDS}

    async def rollback(self):
        self.rollbacks += 1
        self.events.append("rollback")

    async def flush(self):
        self.events.append("flush")

    def add(self, _obj):
        pass


@pytest.fixture
def effects(monkeypatch):
    """Replace every durable kind's side effect with a recorder.

    ``effects.fail`` (an exception) makes the next call raise it after
    recording the call, i.e. the effect ran (part-way) and then failed."""
    state = SimpleNamespace(calls=[], fail=None, claim_seen=[])

    def make(kind):
        async def fake(self, *args):
            appr = next(a for a in args if hasattr(a, "payload"))
            if next(a for a in args if isinstance(a, bool)) is False:
                return  # reject: the real handlers do nothing (bar the autonomy mirror)
            state.calls.append(kind)
            state.claim_seen.append((appr.payload.get("execution") or {}).get("state"))
            # What the database holds while the effect runs:
            committed = self.session.db.committed["payload"].get("execution") or {}
            state.claim_seen.append(committed.get("state"))
            if state.fail is not None:
                exc, state.fail = state.fail, None
                raise exc

        return fake

    monkeypatch.setattr(ApprovalService, "_apply_driver_deploy", make("driver_deploy"))
    monkeypatch.setattr(ApprovalService, "_apply_driver_merge", make("driver_merge"))
    monkeypatch.setattr(ApprovalService, "_apply_driver_pr", make("driver_pr"))
    monkeypatch.setattr(ApprovalService, "_apply_driver_plan", make("driver_plan"))
    monkeypatch.setattr(ApprovalService, "_apply_autonomous_action", make("autonomous_action"))
    return state


async def _approve(db: _Db, **kw):
    session = db.session()
    result = await ApprovalService(session).resolve("t", str(db.row.id), "approve", **kw)
    await session.commit()  # what the API does after resolve() returns
    return result


# ── The claim is committed before the effect, and closed after ───────────


async def test_the_claim_is_committed_before_the_side_effect_runs(effects):
    db = _Db(_row("driver_deploy"))

    result = await _approve(db, resolved_by="owner")

    assert effects.calls == ["driver_deploy"]
    # In memory and in the database, the claim said "started" while it ran.
    assert effects.claim_seen == ["started", "started"]
    assert result["status"] == "approved"
    execution = db.committed["payload"]["execution"]
    assert execution["state"] == "done" and execution["by"] == "owner"
    assert execution["attempt"] == 1 and execution["finished_at"]


async def test_no_transaction_is_left_open_holding_the_lock_through_the_effect(effects):
    db = _Db(_row("driver_deploy"))
    session = db.session()

    await ApprovalService(session).resolve("t", str(db.row.id), "approve")

    # lock -> claim committed (lock released) -> effect -> result flushed for
    # the caller's commit. No SET LOCAL idle-timeout exemption is needed.
    assert session.events == ["lock", "commit", "flush"]


async def test_on_postgres_the_effects_own_transaction_is_exempt_from_the_idle_timeout(effects):
    """The deploy's pinned-command check reads the project, then the deploy
    may run 600 s: that later transaction (no row lock) is exempted so the
    outcome can still be recorded. The claim's own transaction is not."""
    db = _Db(_row("driver_deploy"))
    session = db.session()
    session.get_bind = lambda *_a, **_k: SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    async def execute(stmt, *_a, **_k):
        session.events.append(str(stmt))

    session.execute = execute

    await ApprovalService(session).resolve("t", str(db.row.id), "approve")

    assert session.events == [
        "lock",
        "commit",
        "SET LOCAL idle_in_transaction_session_timeout = 0",
        "flush",
    ]


@pytest.mark.parametrize("kind", ["promotion", "merge", "archive", "contradiction", "entity_alias"])
async def test_kinds_that_only_touch_this_transaction_take_no_claim(kind, monkeypatch):
    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr(ApprovalService, f"_apply_{kind}", noop)
    db = _Db(_row(kind))
    session = db.session()

    await ApprovalService(session).resolve("t", str(db.row.id), "approve")

    assert session.commits == 0  # one transaction, committed by the caller
    assert "execution" not in session.obj.payload


async def test_a_reject_runs_nothing_and_takes_no_claim(effects):
    db = _Db(_row("driver_deploy"))
    session = db.session()

    result = await ApprovalService(session).resolve("t", str(db.row.id), "reject")

    assert result["status"] == "rejected"
    assert effects.calls == [] and session.commits == 0


async def test_durable_claim_off_keeps_the_callers_transaction(effects):
    """The dispatcher's plan auto-approval: the row is in its own open
    transaction, so resolve() must not commit it."""
    db = _Db(_row("driver_plan"))
    session = db.session()

    await ApprovalService(session).resolve("t", str(db.row.id), "approve", durable_claim=False)

    assert effects.calls == ["driver_plan"] and session.commits == 0


# ── Crash after the effect, before the commit ────────────────────────────


async def test_a_crash_after_the_effect_leaves_a_claim_and_nothing_runs_it_again(effects):
    """The main gap. The process dies after the deploy but before the API's
    commit: the row is pending, the claim says "started"."""
    db = _Db(_row("driver_deploy"))
    dying = db.session()
    await ApprovalService(dying).resolve("t", str(db.row.id), "approve")
    # ... no commit: the process is gone.

    assert db.committed["status"] == "pending"
    assert db.committed["payload"]["execution"]["state"] == "started"

    # After the restart the owner (or a retrying client) approves again.
    with pytest.raises(ApprovalAlreadyResolvedError, match="being applied"):
        await _approve(db)
    with pytest.raises(ApprovalAlreadyResolvedError, match="being applied"):
        session = db.session()
        await ApprovalService(session).resolve("t", str(db.row.id), "reject")
    assert effects.calls == ["driver_deploy"]  # once


async def test_once_stale_a_deploy_needs_an_explicit_retry(effects):
    started = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    db = _Db(
        _row(
            "driver_deploy",
            {"execution": {"state": "started", "started_at": started, "attempt": 1}},
        )
    )

    with pytest.raises(ApprovalNeedsRetryError, match="retry"):
        await _approve(db)
    assert effects.calls == []

    result = await _approve(db, retry=True)

    assert effects.calls == ["driver_deploy"] and result["status"] == "approved"
    execution = db.committed["payload"]["execution"]
    assert execution["attempt"] == 2 and execution["previous"]["state"] == "started"


async def test_once_stale_an_idempotent_merge_simply_runs_again(effects):
    started = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    db = _Db(_row("driver_merge", {"execution": {"state": "started", "started_at": started}}))

    result = await _approve(db)

    assert effects.calls == ["driver_merge"] and result["status"] == "approved"


async def test_a_stale_item_may_be_rejected_by_the_owner(effects):
    db = _Db(_row("driver_deploy", {"execution": {"state": "unknown", "started_at": "2026-01-01"}}))
    session = db.session()

    result = await ApprovalService(session).resolve("t", str(db.row.id), "reject")

    assert result["status"] == "rejected" and effects.calls == []


# ── The effect fails part-way ────────────────────────────────────────────


async def test_a_failed_deploy_is_recorded_and_not_rerun_by_a_plain_approve(effects):
    db = _Db(_row("driver_deploy"))
    effects.fail = ApprovalActionError("deploy command timed out after 600s and was stopped")

    with pytest.raises(ApprovalActionError):
        await _approve(db)

    assert db.committed["status"] == "pending"
    execution = db.committed["payload"]["execution"]
    assert execution["state"] == "failed" and "timed out" in execution["error"]
    assert execution["rerun_safe"] is False

    with pytest.raises(ApprovalNeedsRetryError):
        await _approve(db)
    assert effects.calls == ["driver_deploy"]

    await _approve(db, retry=True)
    assert effects.calls == ["driver_deploy", "driver_deploy"]


async def test_an_unexpected_error_is_recorded_as_unknown(effects):
    db = _Db(_row("autonomous_action"))
    effects.fail = RuntimeError("connection reset")

    with pytest.raises(RuntimeError):
        await _approve(db)

    execution = db.committed["payload"]["execution"]
    assert execution["state"] == "unknown" and "RuntimeError" in execution["error"]
    with pytest.raises(ApprovalNeedsRetryError):
        await _approve(db)
    assert effects.calls == ["autonomous_action"]


async def test_a_failed_merge_may_be_approved_again_as_before(effects):
    """CI not green yet: merging is idempotent, so the old 'approve again once
    CI passes' flow still works without a retry flag."""
    db = _Db(_row("driver_merge"))
    effects.fail = ApprovalActionError("checks pending")

    with pytest.raises(ApprovalActionError):
        await _approve(db)
    assert db.committed["payload"]["execution"]["rerun_safe"] is True

    result = await _approve(db)
    assert result["status"] == "approved" and effects.calls == ["driver_merge"] * 2


async def test_a_plan_that_failed_its_checks_may_be_approved_again(effects):
    db = _Db(_row("driver_plan"))
    effects.fail = ApprovalActionError("project p1 no longer exists")

    with pytest.raises(ApprovalActionError):
        await _approve(db)
    await _approve(db)
    assert effects.calls == ["driver_plan"] * 2


# ── Concurrent approvals and the auto-merge sweep ────────────────────────


async def test_a_second_approve_after_the_claim_commit_gets_409_while_the_first_runs(
    effects, monkeypatch
):
    """The client retried after a proxy timeout; the first request is still
    deploying. NOWAIT covers the moment of the claim, the claim the rest."""
    db = _Db(_row("driver_deploy"))
    inner = {}

    async def slow(self, appr, approve):
        try:
            await _approve(db)
        except ApprovalAlreadyResolvedError as exc:
            inner["second"] = str(exc)
        effects.calls.append("driver_deploy")

    monkeypatch.setattr(ApprovalService, "_apply_driver_deploy", slow)

    await _approve(db)

    assert inner == {"second": "being applied"}
    assert effects.calls == ["driver_deploy"]


def _merge_row(**payload):
    return _row("driver_merge", {"auto_merge": True, "driver": "local", **payload})


async def test_the_sweep_never_retries_a_row_whose_attempt_is_running_or_unknown(monkeypatch):
    calls = []

    async def fake(self, appr, *_a):
        calls.append(appr.id)

    monkeypatch.setattr(ApprovalService, "maybe_auto_merge", fake)
    now = datetime.now(UTC).isoformat()
    running = _merge_row(execution={"state": "started", "started_at": now})
    unknown = _merge_row(execution={"state": "unknown", "started_at": now})
    failed = _merge_row(execution={"state": "failed", "started_at": now, "attempt": 1})
    session = FakeSession([running, unknown, failed], failed)

    result = await approvals_mod.retry_auto_merges(session_factory(session))

    assert calls == [failed.id] and result["tried"] == 1
    assert failed.payload["execution"]["attempt"] == 1  # declined: put back as it was


async def test_a_manual_approve_during_a_sweep_merge_gets_409(effects, monkeypatch):
    """retry_auto_merges vs a person: the sweep's claim is committed before gh
    runs, so the person's approve is refused rather than merging again."""
    row = _merge_row()
    db = _Db(row)
    inner = {}

    async def sweep_merge(self, appr, *_a):
        db.committed["payload"] = copy.deepcopy(appr.payload)  # the sweep's commit
        try:
            await _approve(db)
        except ApprovalAlreadyResolvedError as exc:
            inner["manual"] = str(exc)
        appr.status = "approved"

    monkeypatch.setattr(ApprovalService, "maybe_auto_merge", sweep_merge)
    session = FakeSession([row], row)

    await approvals_mod.retry_auto_merges(session_factory(session))

    assert inner == {"manual": "being applied"}
    assert effects.calls == []  # the person's approve never reached the merge


# ── Stale-claim sweep ────────────────────────────────────────────────────


async def test_the_stale_sweep_marks_dead_attempts_unknown_and_tells_the_owner(monkeypatch):
    from life_graph.core.events import event_bus

    emitted = []

    async def emit(event_type, data, source=None):
        emitted.append(data)

    monkeypatch.setattr(event_bus, "emit", emit)
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    fresh = datetime.now(UTC).isoformat()
    dead = _row("driver_deploy", {"execution": {"state": "started", "started_at": old}})
    running = _row("driver_merge", {"execution": {"state": "started", "started_at": fresh}})
    plain = _row("driver_pr")
    session = FakeSession([dead, running, plain], dead)

    flagged = await approvals_mod.flag_stale_claims(session_factory(session))

    assert flagged == 1
    assert dead.payload["execution"]["state"] == "unknown"
    assert dead.payload["execution"]["rerun_safe"] is False
    assert running.payload["execution"]["state"] == "started"
    assert dead.status == "pending"  # still in every client's pending list
    assert emitted and emitted[0]["kind"] == "approval_needs_attention"
    assert "retry" in emitted[0]["detail"]
    assert "FOR UPDATE SKIP LOCKED" in sql(session.statements[1])


async def test_a_deploy_claim_is_not_stale_while_a_deploy_could_still_run():
    from life_graph.services.approvals import DEPLOY_TIMEOUT_SECONDS, _is_stale

    started = datetime.now(UTC) - timedelta(seconds=DEPLOY_TIMEOUT_SECONDS * 2)
    assert not _is_stale({"state": "started", "started_at": started.isoformat()}, "driver_deploy")


# ── Idempotent re-run detects "already done" ─────────────────────────────


async def test_rerunning_a_merge_that_already_went_through_completes(monkeypatch):
    """The first attempt merged the PR and then the process died; the rerun
    finds the PR merged and resolves the item instead of failing."""
    from life_graph.services.dev import github_pr

    async def already(_payload):
        return {"merged": True, "already": True, "merge_commit": "abcdef1234567"}

    monkeypatch.setattr(github_pr, "merge_pull_request", already)
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    db = _Db(_row("driver_merge", {"execution": {"state": "unknown", "started_at": old}}))

    result = await _approve(db)

    assert result["status"] == "approved"
    assert "was already merged" in db.committed["resolution_note"]
    assert db.committed["payload"]["execution"]["state"] == "done"


def test_the_merge_approval_filed_by_a_pr_approve_does_not_inherit_its_claim():
    """Found by CI: merge_approval_fields copies the PR payload, so the new
    driver_merge row was born with the PR's "started" claim and every approve
    of it answered 409 "being applied"."""
    pr = _row(
        "driver_pr",
        {
            "task_id": "t1",
            "branch": "lg/task-1",
            "pr_url": "https://github.com/o/r/pull/1",
            "execution": {"state": "started", "attempt_id": "x"},
        },
    )
    session = FakeSession()

    merge = ApprovalService(session).file_merge_approval(pr)

    assert "execution" not in (merge.payload or {})
    assert merge.payload["pr_url"] == "https://github.com/o/r/pull/1"


# ── API and Telegram ─────────────────────────────────────────────────────


async def test_the_api_passes_retry_and_answers_409_for_needs_retry(monkeypatch):
    from fastapi import HTTPException

    from life_graph.api import approvals as api

    seen = {}

    async def needs_retry(self, *_a, **kw):
        seen.update(kw)
        raise ApprovalNeedsRetryError("attempted: check, then retry")

    monkeypatch.setattr(ApprovalService, "resolve", needs_retry)

    with pytest.raises(HTTPException) as info:
        await api._resolve(str(uuid.uuid4()), "approve", api.ResolveBody(), "t", None)
    assert info.value.status_code == 409 and "retry" in info.value.detail
    assert "retry" not in seen

    with pytest.raises(HTTPException):
        await api._resolve(str(uuid.uuid4()), "approve", api.ResolveBody(retry=True), "t", None)
    assert seen["retry"] is True


async def test_a_retried_deploy_still_passes_the_pinned_command_check_first(monkeypatch):
    """#294's hash re-check runs on the retry/recovery path too: a retry goes
    through the same _apply_driver_deploy, so an unpinned command never runs."""
    import asyncio
    from unittest.mock import AsyncMock

    ran = []

    async def no_shell(*a, **_k):
        ran.append(a)
        raise AssertionError("the command must not run")

    monkeypatch.setattr(asyncio, "create_subprocess_shell", no_shell)
    monkeypatch.setattr(
        ApprovalService,
        "_project_dict",
        AsyncMock(return_value={"id": "p1", "name": "p", "path": "/x", "scan_metadata": {}}),
    )
    db = _Db(
        _row(
            "driver_deploy",
            {
                "project_id": "p1",
                "deploy_command": "echo deployed",
                "execution": {"state": "failed", "attempt": 1, "started_at": "2026-11-20"},
            },
        )
    )

    with pytest.raises(ApprovalActionError, match="approval pin"):
        await _approve(db, retry=True)

    assert ran == []
    execution = db.committed["payload"]["execution"]
    assert execution["state"] == "failed" and execution["attempt"] == 2
    assert db.committed["status"] == "pending"


def _http_request(key: str):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/approvals/x/approve",
            "headers": [(b"authorization", f"Bearer {key}".encode())],
            "query_string": b"",
        }
    )


@pytest.fixture
def identity(monkeypatch):
    """#295's identity setup: one owner key, one plain service key."""
    from life_graph.api import approvals as api
    from life_graph.config import settings

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", "svc-key-0123456789,owner-key-0123456789")
    monkeypatch.setattr(settings, "owner_api_keys", "owner-key-0123456789")
    calls = []

    async def fake_resolve(self, *_a, **kw):
        calls.append(kw)
        return {"id": "x", "kind": "driver_deploy", "status": "approved", "title": "x"}

    async def no_emit(*_a, **_k):
        return None

    monkeypatch.setattr(ApprovalService, "resolve", fake_resolve)
    monkeypatch.setattr(api.event_bus, "emit", no_emit)
    return api, settings, calls


async def test_a_retry_needs_the_owner_exactly_like_an_approve(identity, monkeypatch):
    """retry: true re-runs a deploy, so it goes through the same
    require_owner gate as approve (it is only a field on /approve)."""
    from fastapi import HTTPException

    api, settings, calls = identity
    monkeypatch.setattr(settings, "approvals_require_owner", True)

    async def nobody_asked(*_a):
        return None

    monkeypatch.setattr(api, "_requested_by", nobody_asked)
    with pytest.raises(HTTPException) as info:
        await api.approve_approval(
            str(uuid.uuid4()),
            _http_request("svc-key-0123456789"),
            api.ResolveBody(retry=True),
            "t",
            FakeSession(),
        )
    assert info.value.status_code == 403 and calls == []

    await api.approve_approval(
        str(uuid.uuid4()),
        _http_request("owner-key-0123456789"),
        api.ResolveBody(retry=True),
        "t",
        FakeSession(),
    )
    assert calls == [{"note": None, "resolved_by": "owner", "retry": True}]


async def test_a_retry_of_ones_own_request_is_refused_like_an_approve(identity, monkeypatch):
    from fastapi import HTTPException

    api, _settings, calls = identity
    request = _http_request("svc-key-0123456789")
    me = api.resolver(request)

    async def asked_by_me(*_a):
        return me

    monkeypatch.setattr(api, "_requested_by", asked_by_me)
    with pytest.raises(HTTPException) as info:
        await api.approve_approval(
            str(uuid.uuid4()), request, api.ResolveBody(retry=True), "t", FakeSession()
        )
    assert info.value.status_code == 403 and calls == []


async def test_telegram_reports_a_failed_side_effect_instead_of_crashing(monkeypatch):
    from life_graph.integrations.telegram import commands

    async def fails(self, *_a, **_k):
        raise ApprovalActionError("gh is not logged in")

    async def take(_chat_id):
        return ("approve", str(uuid.uuid4()))

    monkeypatch.setattr(ApprovalService, "resolve", fails)
    monkeypatch.setattr(commands, "_take_confirmation", take)
    monkeypatch.setattr(commands.settings, "telegram_allow_approvals", True)
    replies = []

    async def reply(_chat, text):
        replies.append(text)

    session = FakeSession()
    await commands._confirm(1, "t", session, reply)

    assert replies == ["Could not do it: gh is not logged in"]
    assert session.commits == 0 and session.rollbacks == 1
