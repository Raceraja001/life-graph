"""Unit tests for the ARQ cron entry points in ``life_graph/workers/tasks.py``.

This module wraps every scheduled job in the system and sat at 14% coverage:
the 03:00 consolidation, the hourly watcher sweep, the daily brief and digest,
trust decay, approval timeouts, and the per-minute scheduler tick. All of it
runs unattended in the worker process, where a failure surfaces only as a log
line nobody reads.

The tests below run without a database. ``async_session`` is replaced with a
recording fake and the lazily-imported dependency providers are monkeypatched
at their source module, which is where ``tasks.py`` imports them from.

The recurring assertion is **failure isolation**: these jobs loop over every
tenant, so one tenant raising must never stop the rest from being processed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.workers import tasks

# ── Fake session plumbing ─────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        # select(Model.col).distinct() yields 1-tuples
        return [r if isinstance(r, tuple) else (r,) for r in self._rows]

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, recorder, rows):
        self._recorder = recorder
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self._recorder["statements"].append(stmt)
        return _FakeResult(self._rows)

    def add(self, obj):
        self._recorder["added"].append(obj)

    async def commit(self):
        self._recorder["commits"] += 1


@pytest.fixture
def fake_session(monkeypatch):
    """Patch tasks.async_session; returns the recorder.

    Set ``recorder["rows"]`` before calling the task to control what the
    tenant-discovery query returns.
    """
    recorder = {"statements": [], "added": [], "commits": 0, "rows": []}

    def factory():
        return _FakeSession(recorder, recorder["rows"])

    monkeypatch.setattr(tasks, "async_session", factory)
    return recorder


def _redis():
    r = MagicMock()
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    return r


# ── run_all_consolidations ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_all_consolidations_no_tenants(fake_session):
    fake_session["rows"] = []
    assert await tasks.run_all_consolidations({}) == {"tenants": 0}


@pytest.mark.asyncio
async def test_run_all_consolidations_runs_each_tenant_without_redis(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "globex"]
    seen: list[str] = []

    async def _fake_one(ctx, tid):
        seen.append(tid)
        return {"ok": True}

    monkeypatch.setattr(tasks, "run_tenant_consolidation", _fake_one)

    out = await tasks.run_all_consolidations({})

    assert out["tenants"] == 2
    assert seen == ["acme", "globex"]


# ── run_tenant_consolidation ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_consolidation_skips_when_lock_held(fake_session):
    redis = _redis()
    redis.set = AsyncMock(return_value=False)  # NX failed -> already running

    out = await tasks.run_tenant_consolidation({"redis": redis}, "acme")

    assert out == {"status": "skipped", "reason": "already_running"}
    assert fake_session["added"] == [], "should not have opened a JobRun"


@pytest.mark.asyncio
async def test_consolidation_records_report_fields(fake_session, monkeypatch):
    from life_graph.jobs.consolidation import ConsolidationReport

    report = ConsolidationReport(
        gathered=7,
        clusters_found=3,
        duplicates_removed=2,
        principles_created=1,
        memories_archived=4,
        contradictions_found=1,
        llm_cost_usd=0.0031,
        duration_seconds=1.25,
    )
    pipeline = MagicMock()
    pipeline.run = AsyncMock(return_value=report)
    monkeypatch.setattr("life_graph.api.dependencies.get_consolidation_pipeline", lambda: pipeline)

    redis = _redis()
    out = await tasks.run_tenant_consolidation({"redis": redis}, "acme")

    assert out["gathered"] == 7
    assert out["clusters_found"] == 3
    assert out["duplicates_removed"] == 2
    assert out["principles_created"] == 1
    assert out["memories_archived"] == 4
    assert out["llm_cost_usd"] == pytest.approx(0.0031)
    redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidation_releases_lock_on_failure(fake_session, monkeypatch):
    pipeline = MagicMock()
    pipeline.run = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr("life_graph.api.dependencies.get_consolidation_pipeline", lambda: pipeline)

    redis = _redis()
    with pytest.raises(RuntimeError):
        await tasks.run_tenant_consolidation({"redis": redis}, "acme")

    redis.delete.assert_awaited_once(), "lock must be released even on failure"


@pytest.mark.asyncio
async def test_consolidation_works_without_redis(fake_session, monkeypatch):
    from life_graph.jobs.consolidation import ConsolidationReport

    pipeline = MagicMock()
    pipeline.run = AsyncMock(return_value=ConsolidationReport(gathered=1))
    monkeypatch.setattr("life_graph.api.dependencies.get_consolidation_pipeline", lambda: pipeline)

    out = await tasks.run_tenant_consolidation({}, "acme")
    assert out["gathered"] == 1


# ── run_all_merge_suggestions ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_merge_suggestions_isolates_tenant_failures(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "boom", "globex"]
    seen: list[str] = []

    async def _one(ctx, tid):
        seen.append(tid)
        if tid == "boom":
            raise RuntimeError("tenant exploded")
        return {"queued": 2}

    monkeypatch.setattr(tasks, "run_tenant_merge_suggestions", _one)

    out = await tasks.run_all_merge_suggestions({})

    assert seen == ["acme", "boom", "globex"], "a failure aborted the loop"
    assert out == {"tenants": 3, "queued": 4}


# ── run_all_research ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_research_no_tenants(fake_session):
    fake_session["rows"] = []
    assert await tasks.run_all_research({}) == {"tenants": 0}


@pytest.mark.asyncio
async def test_research_isolates_tenant_failures(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "boom"]

    engine = MagicMock()

    async def _cycle(tid):
        if tid == "boom":
            raise RuntimeError("no")
        return {"status": "ok"}

    engine.run_research_cycle = _cycle
    monkeypatch.setattr("life_graph.api.dependencies.get_research_engine", lambda: engine)

    out = await tasks.run_all_research({})

    assert out["tenants"] == 2
    assert out["results"]["acme"] == {"status": "ok"}
    assert out["results"]["boom"] == {"status": "error"}


# ── run_nightly_self_heal ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_self_heal_is_off_by_default(fake_session):
    """The loop auto-deploys prompts, so it runs only when explicitly enabled."""
    fake_session["rows"] = ["acme"]
    assert await tasks.run_nightly_self_heal({}) == {"skipped": "self_improving_enabled=false"}


@pytest.mark.asyncio
async def test_self_heal_no_tenants(fake_session, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "self_improving_enabled", True)
    fake_session["rows"] = []
    assert await tasks.run_nightly_self_heal({}) == {"tenants": 0}


# ── run_daily_digest ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_digest_isolates_failures(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "boom"]

    gen = MagicMock()

    async def _daily(tid):
        if tid == "boom":
            raise RuntimeError("nope")
        return {"sent": True}

    gen.generate_daily = _daily
    monkeypatch.setattr("life_graph.api.dependencies.get_digest_generator", lambda: gen)

    out = await tasks.run_daily_digest({})

    assert out["results"]["acme"] == {"sent": True}
    assert out["results"]["boom"] == {"status": "error"}


# ── decay_trust_scores ────────────────────────────────────────────────


def test_trust_score_model_import_location():
    """The worker imported TrustScore from models.db, where it does not live."""
    import life_graph.models.db as dbmod
    from life_graph.autonomy.models import TrustScore

    assert TrustScore.__tablename__ == "trust_scores"
    assert not hasattr(dbmod, "TrustScore"), (
        "models.db now exports TrustScore — recheck the worker import"
    )


def test_trust_service_exposes_decay_all_not_decay_scores():
    """The worker probed for a method name the service has never had."""
    from life_graph.autonomy.trust.service import TrustScoreService

    assert hasattr(TrustScoreService, "decay_all")
    assert not hasattr(TrustScoreService, "decay_scores")


@pytest.mark.asyncio
async def test_trust_decay_no_tenants(fake_session):
    fake_session["rows"] = []
    assert await tasks.decay_trust_scores({}) == {"tenants": 0}


@pytest.mark.asyncio
async def test_trust_decay_counts_and_commits(fake_session, monkeypatch):
    """decay_all() only flushes — the worker must commit or nothing persists."""
    fake_session["rows"] = ["acme", "globex"]

    service = MagicMock()
    service.decay_all = AsyncMock(return_value=5)
    monkeypatch.setattr("life_graph.autonomy.trust.service.TrustScoreService", lambda s: service)

    before = fake_session["commits"]
    out = await tasks.decay_trust_scores({})

    assert out["tenants"] == 2
    assert out["decayed"] == 10
    assert out["results"]["acme"] == {"decayed": 5}
    assert fake_session["commits"] - before == 2, "each tenant's decay must commit"


@pytest.mark.asyncio
async def test_trust_decay_isolates_tenant_failures(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "boom"]

    async def _decay(tid):
        if tid == "boom":
            raise RuntimeError("nope")
        return 3

    service = MagicMock()
    service.decay_all = _decay
    monkeypatch.setattr("life_graph.autonomy.trust.service.TrustScoreService", lambda s: service)

    out = await tasks.decay_trust_scores({})

    assert out["results"]["acme"] == {"decayed": 3}
    assert out["results"]["boom"] == {"status": "error"}
    assert out["decayed"] == 3


# ── approvals ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_approval_timeouts_success(monkeypatch):
    svc = MagicMock()
    svc.check_expirations = AsyncMock(return_value=3)
    monkeypatch.setattr("life_graph.api.dependencies.get_approval_service", lambda: svc)

    assert await tasks.check_approval_timeouts({}) == {"expired_count": 3}


@pytest.mark.asyncio
async def test_check_approval_timeouts_swallows_errors(monkeypatch):
    svc = MagicMock()
    svc.check_expirations = AsyncMock(side_effect=RuntimeError("db gone"))
    monkeypatch.setattr("life_graph.api.dependencies.get_approval_service", lambda: svc)

    assert await tasks.check_approval_timeouts({}) == {"status": "error"}


@pytest.mark.asyncio
async def test_send_approval_escalations_success(monkeypatch):
    svc = MagicMock()
    svc.send_escalations = AsyncMock(return_value=2)
    monkeypatch.setattr("life_graph.api.dependencies.get_approval_service", lambda: svc)

    assert await tasks.send_approval_escalations({}) == {"escalated_count": 2}


@pytest.mark.asyncio
async def test_send_approval_escalations_swallows_errors(monkeypatch):
    svc = MagicMock()
    svc.send_escalations = AsyncMock(side_effect=RuntimeError("nope"))
    monkeypatch.setattr("life_graph.api.dependencies.get_approval_service", lambda: svc)

    assert await tasks.send_approval_escalations({}) == {"status": "error"}


# ── run_daily_brief ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_brief_counts_composed_and_silent(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "quiet", "boom"]

    async def _compose(tid):
        if tid == "boom":
            raise RuntimeError("bad")
        return {"id": "brief-1"} if tid == "acme" else None

    composer = MagicMock()
    composer.compose_daily = _compose
    monkeypatch.setattr("life_graph.services.brief.BriefComposer", lambda *a, **k: composer)

    out = await tasks.run_daily_brief({})

    assert out["tenants"] == 3
    assert out["composed"] == 1
    assert out["results"]["acme"] == {"status": "composed", "id": "brief-1"}
    assert out["results"]["quiet"] == {"status": "silent"}
    assert out["results"]["boom"] == {"status": "error"}


# ── failure_pattern_mining ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failure_mining_sums_patterns(fake_session, monkeypatch):
    fake_session["rows"] = ["acme", "globex", "boom"]

    async def _run(tid):
        if tid == "boom":
            raise RuntimeError("llm down")
        return {"patterns_stored": 2}

    miner = MagicMock()
    miner.run = _run
    monkeypatch.setattr("life_graph.services.failure_mining.FailurePatternMiner", lambda **k: miner)
    monkeypatch.setattr(
        "life_graph.services.llm_client.LMStudioClient", lambda *a, **k: MagicMock()
    )

    out = await tasks.failure_pattern_mining({})

    assert out["tenants"] == 3
    assert out["patterns_stored"] == 4
    assert out["results"]["boom"] == {"status": "error"}


# ── tick_scheduled_jobs ───────────────────────────────────────────────


def _job(agent_name="plain", jid=None):
    return {
        "id": jid or str(uuid.uuid4()),
        "tenant_id": "acme",
        "agent_name": agent_name,
        "input": {},
    }


@pytest.mark.asyncio
async def test_tick_no_due_jobs(monkeypatch):
    sched = MagicMock()
    sched.get_due_jobs = AsyncMock(return_value=[])
    monkeypatch.setattr(tasks, "get_scheduler_service", lambda: sched)

    assert await tasks.tick_scheduled_jobs({}) == {"due": 0, "fired": 0, "failed": 0}


@pytest.mark.asyncio
async def test_tick_fires_each_job_and_isolates_failures(monkeypatch):
    good, bad = _job(jid="g"), _job(jid="b")
    sched = MagicMock()
    sched.get_due_jobs = AsyncMock(return_value=[good, bad])

    async def _fire(tenant_id, job_id, **kw):
        if job_id == "b":
            raise RuntimeError("fire failed")

    sched.fire_job = _fire
    monkeypatch.setattr(tasks, "get_scheduler_service", lambda: sched)

    out = await tasks.tick_scheduled_jobs({})
    assert out == {"due": 2, "fired": 1, "failed": 1}


@pytest.mark.asyncio
async def test_tick_applies_readonly_tools_for_ambient_action(monkeypatch):
    """Ambient ACTION agents must be fired with the read-only tool override."""
    from life_graph.kernel.ambient import AMBIENT_ACTION, AMBIENT_ACTION_READONLY_TOOLS

    if not AMBIENT_ACTION:
        pytest.skip("no ambient action agents configured")

    agent = next(iter(AMBIENT_ACTION))
    sched = MagicMock()
    sched.get_due_jobs = AsyncMock(return_value=[_job(agent_name=agent, jid="x")])
    captured: dict = {}

    async def _fire(tenant_id, job_id, **kw):
        captured.update(kw)

    sched.fire_job = _fire
    monkeypatch.setattr(tasks, "get_scheduler_service", lambda: sched)

    async def _build(agent_name, inp, tid):
        return {"built": True}

    monkeypatch.setattr(tasks, "build_ambient_input", _build)

    out = await tasks.tick_scheduled_jobs({})

    assert out["fired"] == 1
    assert captured["tool_override"] == AMBIENT_ACTION_READONLY_TOOLS
    assert captured["input_override"] == {"built": True}


@pytest.mark.asyncio
async def test_tick_plain_job_gets_no_overrides(monkeypatch):
    sched = MagicMock()
    sched.get_due_jobs = AsyncMock(return_value=[_job(agent_name="not-ambient")])
    captured: dict = {}

    async def _fire(tenant_id, job_id, **kw):
        captured.update(kw)

    sched.fire_job = _fire
    monkeypatch.setattr(tasks, "get_scheduler_service", lambda: sched)

    await tasks.tick_scheduled_jobs({})

    assert captured["input_override"] is None
    assert captured["tool_override"] is None


# ── learn_project_task ───────────────────────────────────────────────
#
# POST /kernel/projects/{id}/learn used to run project_learning.learn_project
# inline and block the request for however long git-history mining takes
# (minutes, for a real repo). It now just enqueues this job.


@pytest.mark.asyncio
async def test_learn_project_records_success_and_result(fake_session, monkeypatch):
    project = {"id": "p1", "name": "demo", "path": "/repo", "is_active": True}
    registry = MagicMock()
    registry.get_by_id = AsyncMock(return_value=project)
    monkeypatch.setattr("life_graph.api.dependencies.get_project_registry", lambda: registry)
    monkeypatch.setattr("life_graph.api.dependencies.get_preference_store", lambda: MagicMock())

    learn_result = {"project_id": "p1", "findings": 3, "created": 2, "updated": 1, "archived": 0}
    monkeypatch.setattr(
        "life_graph.services.project_learning.learn_project",
        AsyncMock(return_value=learn_result),
    )

    out = await tasks.learn_project_task({}, "acme", "p1", authors=["me"])

    assert out == learn_result
    # A JobRun opened as "running" and later updated to "success" — two
    # separate session uses (open, then update), matching consolidation.
    assert len(fake_session["added"]) == 1
    job = fake_session["added"][0]
    assert job.tenant_id == "acme" and job.job_name == "project_learn"
    assert job.status == "running"
    update_stmt = fake_session["statements"][-1]
    assert update_stmt.compile().params["status"] == "success"
    assert update_stmt.compile().params["result"] == learn_result


@pytest.mark.asyncio
async def test_learn_project_missing_project_is_recorded_as_failed(fake_session, monkeypatch):
    registry = MagicMock()
    registry.get_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr("life_graph.api.dependencies.get_project_registry", lambda: registry)

    with pytest.raises(ValueError, match="not found"):
        await tasks.learn_project_task({}, "acme", "missing")

    update_stmt = fake_session["statements"][-1]
    assert update_stmt.compile().params["status"] == "failed"
    assert "not found" in update_stmt.compile().params["error"]


@pytest.mark.asyncio
async def test_learn_project_inactive_project_is_recorded_as_failed(fake_session, monkeypatch):
    registry = MagicMock()
    registry.get_by_id = AsyncMock(return_value={"id": "p1", "is_active": False})
    monkeypatch.setattr("life_graph.api.dependencies.get_project_registry", lambda: registry)

    with pytest.raises(ValueError):
        await tasks.learn_project_task({}, "acme", "p1")

    assert fake_session["statements"][-1].compile().params["status"] == "failed"


@pytest.mark.asyncio
async def test_learn_project_analysis_failure_is_recorded_and_reraised(fake_session, monkeypatch):
    project = {"id": "p1", "name": "demo", "path": "/repo", "is_active": True}
    registry = MagicMock()
    registry.get_by_id = AsyncMock(return_value=project)
    monkeypatch.setattr("life_graph.api.dependencies.get_project_registry", lambda: registry)
    monkeypatch.setattr("life_graph.api.dependencies.get_preference_store", lambda: MagicMock())
    monkeypatch.setattr(
        "life_graph.services.project_learning.learn_project",
        AsyncMock(side_effect=RuntimeError("git history unreadable")),
    )

    with pytest.raises(RuntimeError, match="git history unreadable"):
        await tasks.learn_project_task({}, "acme", "p1")

    update_stmt = fake_session["statements"][-1]
    assert update_stmt.compile().params["status"] == "failed"
    assert "git history unreadable" in update_stmt.compile().params["error"]


# ── ARQ wiring ────────────────────────────────────────────────────────


def test_every_cron_coroutine_resolves():
    """A cron registered under a name that does not resolve never runs."""
    import importlib

    from life_graph.workers.settings import WorkerSettings

    unresolved = []
    for cj in getattr(WorkerSettings, "cron_jobs", []):
        coro = cj.coroutine
        if not isinstance(coro, str):
            continue
        mod_name, _, attr = coro.rpartition(".")
        try:
            if not hasattr(importlib.import_module(mod_name), attr):
                unresolved.append(coro)
        except ImportError:
            unresolved.append(coro)

    assert not unresolved, f"cron targets that do not resolve: {unresolved}"


def test_every_registered_function_resolves():
    import importlib

    from life_graph.workers.settings import WorkerSettings

    unresolved = []
    for fn in WorkerSettings.functions:
        if not isinstance(fn, str):
            continue
        mod_name, _, attr = fn.rpartition(".")
        try:
            if not hasattr(importlib.import_module(mod_name), attr):
                unresolved.append(fn)
        except ImportError:
            unresolved.append(fn)

    assert not unresolved, f"registered functions that do not resolve: {unresolved}"


# ── Import integrity across the package ───────────────────────────────


def test_no_module_imports_a_name_that_does_not_exist():
    """Every ``from life_graph.X import Y`` must resolve.

    Most of these imports are lazy — inside function bodies — so nothing
    executes them until that code path runs. Four production bugs of this
    exact shape were found in modules with no test coverage:

      watchers/notification_engine.py  Notification    (-> WatcherNotification)
      watchers/digest.py               Notification    (-> WatcherNotification)
      api/watchers.py                  Notification    (-> WatcherNotification)
      workers/tasks.py                 TrustScore      (wrong module)
      workers/embeddings.py            services.embedding (module never existed)

    Three were swallowed by a broad ``except`` and reported success.
    """
    import ast
    import importlib
    import pathlib

    root = pathlib.Path(tasks.__file__).resolve().parents[1]

    broken: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            mod_name = node.module
            if not mod_name or not mod_name.startswith("life_graph"):
                continue
            rel = path.relative_to(root.parent)
            try:
                mod = importlib.import_module(mod_name)
            except ImportError as e:
                broken.append(f"{rel}:{node.lineno} import {mod_name} -> {e}")
                continue
            for alias in node.names:
                if alias.name == "*" or hasattr(mod, alias.name):
                    continue
                try:
                    importlib.import_module(f"{mod_name}.{alias.name}")
                except ImportError:
                    broken.append(f"{rel}:{node.lineno} from {mod_name} import {alias.name}")

    assert not broken, "unresolvable imports:\n  " + "\n  ".join(broken)
