"""The distill job is enqueued via a module constant (``DISTILL_JOB_NAME``),
not a string literal — ``pool.enqueue_job(DISTILL_JOB_NAME, ...)``. This test
asserts on the *resolved* constant against ``WorkerSettings.functions`` (a
class attribute: a list of full dotted-path strings), so a bare name, a typo,
or a constant that drifts out of sync with the registered function would fail
the test — unlike a source-text regex scan, which cannot see through the
constant reference and would pass vacuously regardless of its value.
"""

from life_graph.workers.distill import DISTILL_JOB_NAME
from life_graph.workers.settings import WorkerSettings


def test_distill_enqueue_names_are_registered():
    # The enqueue constant must be the full dotted path...
    assert DISTILL_JOB_NAME == "life_graph.workers.distill.distill_conversation"
    # ...and it must be a registered function, or the enqueued job never runs.
    assert DISTILL_JOB_NAME in WorkerSettings.functions
    # The cron target must be registered too.
    assert "life_graph.workers.distill.distill_idle_conversations" in WorkerSettings.functions
