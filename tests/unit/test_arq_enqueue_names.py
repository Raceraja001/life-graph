"""Every enqueue_job() name must be a registered ARQ function (full dotted path),
or the worker silently never runs the job.

Two complementary checks:
  * ``test_all_enqueue_names_are_registered`` — a repo-wide source scan for
    string-literal ``enqueue_job("name")`` calls, asserting each name is in
    ``WorkerSettings.functions``.
  * ``test_distill_enqueue_names_are_registered`` — the distill job is enqueued
    via a module constant (``pool.enqueue_job(DISTILL_JOB_NAME, ...)``), which the
    regex scan cannot see through, so it is checked on its *resolved* value.
"""

import re
from pathlib import Path

from life_graph.workers.distill import DISTILL_JOB_NAME
from life_graph.workers.settings import WorkerSettings

_ROOT = Path(__file__).resolve().parents[2] / "life_graph"
_CALL = re.compile(r'enqueue_job\(\s*"([^"]+)"')


def _registered_names() -> set[str]:
    return {f if isinstance(f, str) else getattr(f, "__qualname__", str(f))
            for f in WorkerSettings.functions}


def test_all_enqueue_names_are_registered():
    registered = _registered_names()
    offenders = []
    for py in _ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in _CALL.finditer(text):
            name = m.group(1)
            if name not in registered:
                offenders.append(f"{py.relative_to(_ROOT.parent)}: enqueue_job(\"{name}\")")
    assert not offenders, "Unregistered enqueue_job names:\n" + "\n".join(offenders)


def test_distill_enqueue_names_are_registered():
    # The enqueue constant must be the full dotted path...
    assert DISTILL_JOB_NAME == "life_graph.workers.distill.distill_conversation"
    # ...and it must be a registered function, or the enqueued job never runs.
    assert DISTILL_JOB_NAME in WorkerSettings.functions
    # The cron target must be registered too.
    assert "life_graph.workers.distill.distill_idle_conversations" in WorkerSettings.functions


def test_all_cron_targets_are_registered_and_callable():
    """A cron whose target is missing from ``functions`` is a job nobody runs.

    ARQ resolves a cron's dotted path at import time, so a typo'd module fails
    loudly. A *registered* path is a different matter: the repo's convention is
    that every cron target also appears in ``WorkerSettings.functions`` so the
    same job can be enqueued by hand (a backfill, a retry from the dashboard).
    Nothing enforces that at runtime, so it is enforced here.
    """
    registered = _registered_names()
    for job in WorkerSettings.cron_jobs:
        target = job.name.removeprefix("cron:")
        assert target in registered, f"cron target not in WorkerSettings.functions: {target}"
        assert callable(job.coroutine), f"cron target is not callable: {target}"
