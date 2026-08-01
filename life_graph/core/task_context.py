"""Task-execution context propagation for the agent kernel.

Uses a Python contextvar to let code running inside a spawned
AgentTask (including tool handlers, which only receive
LLM-supplied arguments) discover which task and tenant it is
currently executing under — mirrors core/tenant.py's pattern.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass

_task_context_var: ContextVar["TaskContext | None"] = ContextVar(
    "task_context", default=None
)


@dataclass(frozen=True, slots=True)
class TaskContext:
    """The kernel task the current coroutine is executing under."""

    task_id: uuid.UUID
    tenant_id: str


def get_current_task_context() -> TaskContext | None:
    """Get the current task context, or None if not running inside a task."""
    return _task_context_var.get()


def set_task_context(task_id: uuid.UUID, tenant_id: str) -> None:
    """Set task context for the current coroutine tree.

    Called by ProcessManager._execute_task. Should not be called
    directly by application code.
    """
    _task_context_var.set(TaskContext(task_id=task_id, tenant_id=tenant_id))
