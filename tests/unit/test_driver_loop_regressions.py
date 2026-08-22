"""Three defects found by driving one real task through the driver pipeline.

Nothing had ever run through it: before this, every row in ``agent_tasks``
belonged to a test tenant and ``driver_stats`` was empty. The unit tests all
passed, because each of these fails only against a real database, a real
persona row, or a real git repo.

1. The dispatcher wrote ``risk_level="medium"`` when escalating to human
   review. ``approval_queue`` has a CHECK allowing only moderate/dangerous,
   so every escalation raised CheckViolationError -- the driver's entire
   safety net failed closed and unlogged.
2. ``_select_driver`` read the persona's driver pin from ``properties``, but
   it lives in the ``driver`` column. Both pinned personas silently fell
   through to cheapest-capable selection.
3. Verified work was discarded. The worktree is created ``--detach`` and
   removed in a ``finally``, so the pipeline fixed the bug, proved it with
   the verifier chain, then deleted the change and reported success.
"""

import ast
import asyncio
import pathlib
import subprocess
import uuid

import pytest

from life_graph.autonomy.safety.classifier import RiskLevel
from life_graph.drivers.workdir import preserve_verified_work

ROOT = pathlib.Path(__file__).resolve().parents[2]
DISPATCHER_PY = ROOT / "life_graph" / "drivers" / "dispatcher.py"
MIGRATION_018 = ROOT / "alembic" / "versions" / "018_autonomous_ai.py"


# ── 1. risk_level must satisfy the database CHECK ──────────────────────


def _allowed_risk_levels() -> set[str]:
    """Values ck_aq_risk_level permits, read from the migration itself.

    Located by constraint NAME: migration 018 declares more than one
    ``risk_level IN (...)`` check and the audit log's allows "safe" too.
    """
    tree = ast.parse(MIGRATION_018.read_text())
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "CheckConstraint"):
            continue
        named = next(
            (k.value.value for k in node.keywords if k.arg == "name"),
            None,
        )
        if named != "ck_aq_risk_level":
            continue
        expr = node.args[0].value
        inner = expr[expr.index("(") + 1 : expr.rindex(")")]
        return {v.strip().strip("'\"") for v in inner.split(",")}
    raise AssertionError("migration 018 has no ck_aq_risk_level constraint")


def _risk_levels_written_by_dispatcher() -> set[str]:
    """Values the dispatcher assigns to risk_level=."""
    tree = ast.parse(DISPATCHER_PY.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "risk_level":
            continue
        v = node.value
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            found.add(v.value)
        elif isinstance(v, ast.Attribute) and v.attr == "value":
            # RiskLevel.MODERATE.value
            inner = v.value
            if isinstance(inner, ast.Attribute):
                found.add(getattr(RiskLevel, inner.attr).value)
    return found


def test_scan_sees_both_approval_sites():
    """Guard the guard — a scan finding nothing would pass vacuously."""
    assert len(_risk_levels_written_by_dispatcher()) >= 1
    assert _allowed_risk_levels() == {"moderate", "dangerous"}


def test_dispatcher_risk_levels_satisfy_the_check_constraint():
    written = _risk_levels_written_by_dispatcher()
    allowed = _allowed_risk_levels()
    assert written <= allowed, (
        f"dispatcher writes risk_level={sorted(written - allowed)} but "
        f"ck_aq_risk_level only allows {sorted(allowed)}; every escalation to "
        "human review will raise CheckViolationError"
    )


def test_medium_is_not_a_risk_level_at_all():
    """The old value was not even in the enum."""
    assert "medium" not in {r.value for r in RiskLevel}


# ── 2. The persona driver pin lives in a column, not in properties ─────


class _Persona:
    """Persona row shaped like the real one: driver column, empty properties."""

    def __init__(self, driver=None, properties=None):
        self.driver = driver
        self.properties = properties if properties is not None else {}
        self.system_prompt = "s"
        self.allowed_tools = None


class _Driver:
    def __init__(self, name):
        self.name = name

    async def available(self):
        return True

    def cost_per_task(self):
        return 0.0

    def capabilities(self):
        return ["code"]


@pytest.mark.asyncio
async def test_persona_driver_pin_is_read_from_the_column():
    from life_graph.drivers import dispatcher as dmod
    from life_graph.drivers.dispatcher import TaskDispatcher

    pinned = _Driver("claude_code")

    class _Registry:
        def get(self, name):
            return pinned if name == "claude_code" else None

        def available_for_task(self, task_type):
            return [_Driver("local")]

    original = dmod.driver_registry
    dmod.driver_registry = _Registry()
    try:
        d = TaskDispatcher(session_factory=lambda: None)
        chosen = await d._select_driver(
            "code", "dependency-updater", "t", None, persona=_Persona(driver="claude_code")
        )
    finally:
        dmod.driver_registry = original

    assert chosen is pinned, (
        "the persona pins claude_code in its `driver` column; reading only "
        "`properties` made the pin a no-op"
    )


@pytest.mark.asyncio
async def test_properties_pin_still_honoured_for_hand_configured_personas():
    from life_graph.drivers import dispatcher as dmod
    from life_graph.drivers.dispatcher import TaskDispatcher

    pinned = _Driver("claude_code")

    class _Registry:
        def get(self, name):
            return pinned if name == "claude_code" else None

        def available_for_task(self, task_type):
            return [_Driver("local")]

    original = dmod.driver_registry
    dmod.driver_registry = _Registry()
    try:
        d = TaskDispatcher(session_factory=lambda: None)
        chosen = await d._select_driver(
            "code", "p", "t", None, persona=_Persona(properties={"driver": "claude_code"})
        )
    finally:
        dmod.driver_registry = original
    assert chosen is pinned


# ── 3. Verified work must survive worktree removal ─────────────────────


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    (r / "f.txt").write_text("before\n")
    _git("init", "-q", ".", cwd=r)
    _git("add", "-A", cwd=r)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init", cwd=r)
    return r


def test_verified_work_survives_worktree_removal(repo, tmp_path):
    """Regression: the change was deleted with the worktree, success reported."""
    wt = tmp_path / "wt"
    assert _git("worktree", "add", "--detach", str(wt), cwd=repo).returncode == 0
    (wt / "f.txt").write_text("after\n")

    task_id = str(uuid.uuid4())
    branch = asyncio.run(
        preserve_verified_work(worktree=wt, repo_path=repo, task_id=task_id, summary="fix it")
    )
    assert branch == f"lg/task-{task_id[:8]}"

    # Remove the worktree exactly as the dispatcher's finally does.
    _git("worktree", "remove", "--force", str(wt), cwd=repo)

    # The change is still reachable from the origin repo...
    show = _git("show", f"{branch}:f.txt", cwd=repo)
    assert show.returncode == 0
    assert show.stdout == "after\n"


def test_landing_never_touches_the_default_branch(repo, tmp_path):
    wt = tmp_path / "wt"
    _git("worktree", "add", "--detach", str(wt), cwd=repo)
    (wt / "f.txt").write_text("after\n")
    asyncio.run(preserve_verified_work(worktree=wt, repo_path=repo, task_id="abcd1234"))
    _git("worktree", "remove", "--force", str(wt), cwd=repo)

    assert _git("show", "master:f.txt", cwd=repo).stdout == "before\n"


def test_no_changes_lands_nothing(repo, tmp_path):
    """A driver that changed no files is not a failure, and needs no branch."""
    wt = tmp_path / "wt"
    _git("worktree", "add", "--detach", str(wt), cwd=repo)
    assert asyncio.run(preserve_verified_work(worktree=wt, repo_path=repo, task_id="x")) is None
    assert "lg/task" not in _git("branch", cwd=repo).stdout


def test_landing_failure_is_never_fatal(tmp_path):
    """Landing is best-effort: it must not turn a verified run into a failure."""
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    assert (
        asyncio.run(preserve_verified_work(worktree=not_a_repo, repo_path=not_a_repo, task_id="x"))
        is None
    )
