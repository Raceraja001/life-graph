"""Per-run mark: is this agent run working on the owner's personal data?

The charter: personal data is handled by local models only. Jarvis's personal
route (services/lead.py) keeps a personal conversation on local models, but
``delegate_to_persona`` used to start a fresh kernel task for the worker, and
that task ran on the worker's own model, cloud included, with whatever the
brief carried (review 2026-11-25, m8 stage 0 section 6).

So the mark travels like the taint does (core/run_taint.py):

* ``ProcessManager._run_agent`` sets the contextvar around a run that is
  personal -- Jarvis's personal route, or a task that arrived marked;
* ``AgentOrchestrator.run`` also marks a run from its first call to a personal
  tool (services/lead.PERSONAL_TOOLS: memories, mail, calendar, money, ...)
  to its end, whatever its route: a general run that read a memory can put it
  in a brief. Only its delegations change; its own model does not;
* ``delegate_to_persona`` reads it and marks the child's input with
  :data:`PERSONAL_INPUT_KEY`;
* the child's ``_run_agent`` then pins it to local models, or refuses.

A personal run also hands nothing to a cloud worker (services/workers.py, the
``research_web`` tool): its query could carry a name or a place the scrub does
not know. ``_run_agent`` leaves those tools out of a run that starts personal
(lead.resolve_run_tools), and each such tool refuses with
:data:`CLOUD_WORKER_REFUSAL` while the mark is set, which covers a run that
becomes personal part-way through.

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

#: What a cloud-worker tool tells the model (and, through it, the owner).
CLOUD_WORKER_REFUSAL = (
    "Not in this conversation: it uses the owner's own data, and this tool sends"
    " its question to a cloud worker. Answer from what you have, or ask the user"
    " to ask again in a new conversation without the personal part."
)


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
