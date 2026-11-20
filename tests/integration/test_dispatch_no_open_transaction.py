"""No database transaction stays open across a dispatch's slow steps.

The dispatch session's first read (the WIP check) began a transaction that
lasted the whole dispatch: the agent run, the verifier chain, the bounce, the
second-opinion review and the landing -- 10+ minutes "idle in transaction",
holding its snapshot and the verification row written before the bounce. Each
slow step now starts with the session's transaction committed.

Against the real database: the session must report ``in_transaction() is
False`` inside each slow step, and Postgres must show no connection idle in a
transaction while it runs.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text

from tests.integration.conftest import skip_on_db_error

TENANT = f"dispatch_tx_{uuid.uuid4().hex[:8]}"


async def _idle_in_transaction() -> list[str]:
    """The last query of each connection idle inside an open transaction."""
    from life_graph.services.dev import task_events
    from life_graph.storage.database import async_session

    # The dev-task event writer runs concurrently and is briefly between
    # statements of its own (short) batch transaction; let it finish first.
    await task_events.flush()
    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT query FROM pg_stat_activity "
                    "WHERE datname = current_database() AND state = 'idle in transaction'"
                )
            )
        ).all()
        await s.rollback()
        return [r[0][:200] for r in rows]


async def _task_row() -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        t = AgentTask(tenant_id=TENANT, agent_name="w", task_name="dispatch tx", status="running")
        s.add(t)
        await s.commit()
        return t.id


class _Driver:
    """Records the session's state while it "runs"; fails the first verify."""

    def __init__(self, session, seen):
        self.name = f"txcheck-{uuid.uuid4().hex[:4]}"
        self._session, self._seen = session, seen

    async def available(self):
        return True

    def capabilities(self):
        return ["research"]

    def cost_per_task(self):
        return 0.0

    async def dispatch(self, packet, workdir, timeout=None):
        from life_graph.drivers.base import DriverResult

        self._seen.append(("driver", self._session.in_transaction(), await _idle_in_transaction()))
        return DriverResult(success=True, output="done")


@pytest.fixture
def seen():
    return []


@pytest.fixture
def wired(monkeypatch, seen):
    """A dispatcher on the real session factory, with stand-in slow steps."""
    from life_graph.drivers import dispatcher as dmod
    from life_graph.drivers.registry import driver_registry
    from life_graph.services.dev.verifiers import VerifierResult
    from life_graph.storage.database import async_session

    session = async_session()
    driver = _Driver(session, seen)
    monkeypatch.setattr(driver_registry, "_drivers", {driver.name: driver})

    calls = {"n": 0, "fail_first": False}

    async def run_chain(chain, workdir, ctx):
        calls["n"] += 1
        seen.append(("verify", session.in_transaction(), await _idle_in_transaction()))
        # fail_first: the bounce (a second agent run) then follows right
        # after the attempt-1 verification row is written.
        passed = not (calls["fail_first"] and calls["n"] == 1)
        return [VerifierResult(verifier="check", passed=passed, evidence={})]

    async def no_autofix(*_a, **_k):
        return {}

    monkeypatch.setattr(dmod.verifier_chain, "run_chain", run_chain)
    monkeypatch.setattr(dmod, "mechanical_autofix", no_autofix)

    class _Reviewer:
        async def review(self, *_a):
            seen.append(("review", session.in_transaction(), await _idle_in_transaction()))
            return SimpleNamespace(ran=False, approved=True, concern=None)

    disp = dmod.TaskDispatcher(session_factory=async_session, reviewer=_Reviewer())
    return disp, session, calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fail_first", "expected_steps", "expected_attempts"),
    [
        # Checks pass: agent run, verify, second-opinion review.
        (False, ["driver", "verify", "review"], 1),
        # A check fails: agent run, verify, bounce (second run), re-verify.
        (True, ["driver", "verify", "driver", "verify"], 2),
    ],
)
@skip_on_db_error
async def test_slow_steps_run_with_no_open_transaction(
    wired, seen, fail_first, expected_steps, expected_attempts
):
    from life_graph.models.db import VerificationRun

    disp, session, calls = wired
    calls["fail_first"] = fail_first
    task_id = await _task_row()
    try:
        result = await disp.dispatch_task(
            tenant_id=TENANT,
            task_id=str(task_id),
            instruction="summarise the notes",
            task_type="research",
            session=session,
            interactive=True,
            verify_chain=["check"],
        )
        await session.commit()
    finally:
        await session.close()

    assert result.success, result.error
    steps = [name for name, *_ in seen]
    assert steps == expected_steps, steps
    for name, in_tx, idle in seen:
        assert in_tx is False, f"{name}: dispatch session still in a transaction"
        assert idle == [], f"{name}: connections idle in transaction: {idle}"

    # Every verification run was still recorded (attempt 1 before a bounce).
    from life_graph.storage.database import async_session

    async with async_session() as s:
        attempts = await s.scalar(select(func.count()).where(VerificationRun.task_id == task_id))
    assert attempts == expected_attempts
