"""Running migrations in-process must not silence the application's logging.

``alembic/env.py`` calls ``logging.config.fileConfig``, whose
``disable_existing_loggers`` argument defaults to ``True``: it sets
``.disabled`` on every logger that already exists. When ``alembic upgrade`` is
its own short-lived process that costs nothing. This suite migrates in-process
at session start, and there it used to mute every ``life_graph`` logger for the
remainder of the run — silently, since the symptom of broken logging is the
absence of output.

The visible damage was two ranking tests that assert on ``caplog``; the real
damage was that no warning or error from any code under test was reachable, so
any test asserting on a log line would pass or fail for the wrong reason.

These tests run after the session-scoped migration fixture in ``conftest.py``,
which is where the ``fileConfig`` call happens.
"""

from __future__ import annotations

import logging

from life_graph.scoring import ranking  # noqa: F401  - ensures the logger exists


def test_no_life_graph_logger_was_disabled():
    disabled = [
        name
        for name, logger in logging.Logger.manager.loggerDict.items()
        if name.startswith("life_graph") and getattr(logger, "disabled", False)
    ]
    assert not disabled, (
        "migrations disabled these loggers: "
        + ", ".join(sorted(disabled))
        + " — pass disable_existing_loggers=False in alembic/env.py"
    )


def test_an_application_log_line_is_still_reachable(caplog):
    """The symptom, rather than the mechanism: a log line must arrive."""
    logger = logging.getLogger("life_graph.scoring.ranking")
    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info("audible")
    assert [r for r in caplog.records if r.getMessage() == "audible"]
