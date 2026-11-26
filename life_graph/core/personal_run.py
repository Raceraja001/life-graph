"""Per-run mark: is this agent run working on the owner's personal data?

The charter: personal data is handled by local models only. Jarvis's personal
route (services/lead.py) keeps a personal conversation on local models, but
``delegate_to_persona`` used to start a fresh kernel task for the worker, and
that task ran on the worker's own model, cloud included, with whatever the
brief carried (review 2026-11-25, m8 stage 0 section 6).

So the mark travels like the taint does (core/run_taint.py):

* ``ProcessManager._run_agent`` sets the contextvar around a run that is
  personal -- Jarvis's personal route, or a task that arrived marked;
* ``delegate_to_persona`` reads it and marks the child's input with
  :data:`PERSONAL_INPUT_KEY`;
* the child's ``_run_agent`` then pins it to local models, or refuses.

Per run, never global: a contextvar, so concurrent runs on one event loop each
see their own.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

#: ``AgentTask.input`` key that makes a run personal: set by
#: ``delegate_to_persona`` on a child spawned from a personal run.
PERSONAL_INPUT_KEY = "personal_run"

_personal: ContextVar[bool] = ContextVar("run_is_personal", default=False)


def in_personal_run() -> bool:
    """True inside a run (and its tool calls) that works on personal data."""
    return _personal.get()


@contextmanager
def personal_run_scope(personal: bool) -> Iterator[None]:
    """Run a block as a personal run (or explicitly not one)."""
    token = _personal.set(personal)
    try:
        yield
    finally:
        _personal.reset(token)
