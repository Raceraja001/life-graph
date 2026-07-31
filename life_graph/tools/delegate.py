"""Delegate-to-persona tool — lets a persona hand off a sub-task
to another persona and (by default) wait for its result.

Only usable by personas whose allowed_tools includes
"delegate_to_persona" (swe-lead, jarvis) — enforced by the
allowed_tools filtering added to ProcessManager._run_agent.
Delegation only works when running inside a kernel AgentTask
(i.e. spawned via ProcessManager), because it needs to know its
own task id to link the child into the delegation tree — see
core/task_context.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 2
_TERMINAL_STATUSES = {"completed", "failed", "timeout", "cancelled"}


@tool(
    name="delegate_to_persona",
    description=(
        "Delegate a sub-task to another persona and get their result back."
        " Use this when part of the request is better handled by a"
        " specialist persona than by you."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "persona": {
                "type": "string",
                "description": (
                    "Name of the persona to delegate to (e.g. 'cody',"
                    " 'rex', 'ops', 'tutor', 'scout', 'admin')."
                ),
            },
            "subtask": {
                "type": "string",
                "description": "Clear instructions for what the delegated persona should do.",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project UUID to scope the sub-task to.",
            },
            "wait": {
                "type": "boolean",
                "description": (
                    "If true (default), block until the delegated task"
                    " finishes and return its result. If false, return"
                    " immediately with the task id."
                ),
                "default": True,
            },
            "timeout_seconds": {
                "type": "integer",
                "description": (
                    "How long to wait for the delegated task when"
                    " wait=true, before returning still_running."
                    " Defaults to 600."
                ),
                "default": 600,
            },
        },
        "required": ["persona", "subtask"],
    },
)
async def delegate_to_persona(
    persona: str,
    subtask: str,
    project_id: str | None = None,
    wait: bool = True,
    timeout_seconds: int = 600,
) -> str:
    """Create a child AgentTask assigned to *persona* and optionally await it.

    Returns a JSON string. Never raises — errors are returned as
    {"error": "..."} so the calling persona's tool-loop can react
    to them like any other tool result.
    """
    from life_graph.api.dependencies import get_process_manager
    from life_graph.core.task_context import get_current_task_context

    ctx = get_current_task_context()
    if ctx is None:
        return json.dumps(
            {
                "error": (
                    "delegate_to_persona has no task context — it can only"
                    " be called from a persona running inside a kernel"
                    " AgentTask."
                ),
            }
        )

    pm = get_process_manager()

    parent_task = await pm.get_task(ctx.tenant_id, str(ctx.task_id))
    if parent_task is None:
        return json.dumps(
            {
                "error": f"Could not load parent task {ctx.task_id} to delegate from.",
            }
        )

    child_root_task_id = parent_task.root_task_id or parent_task.id
    child_depth = parent_task.depth + 1

    parsed_project_id: uuid.UUID | None = None
    if project_id:
        try:
            parsed_project_id = uuid.UUID(project_id)
        except ValueError:
            return json.dumps(
                {
                    "error": f"project_id {project_id!r} is not a valid UUID.",
                }
            )

    try:
        spawn_result = await pm.spawn(
            tenant_id=ctx.tenant_id,
            agent_name=persona,
            input_data={"message": subtask},
            task_name=f"delegated:{persona}",
            parent_task_id=ctx.task_id,
            root_task_id=child_root_task_id,
            depth=child_depth,
            project_id=parsed_project_id,
            # Retry/recovery decisions belong to the delegating
            # persona's own reasoning, not the kernel's automatic
            # retry — see docs/specs/personal-roles.md.
            max_retries=0,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    child_task_id = spawn_result["task_id"]

    if not wait:
        return json.dumps({"task_id": child_task_id, "status": "queued"})

    elapsed = 0
    while elapsed < timeout_seconds:
        task = await pm.get_task(ctx.tenant_id, child_task_id)
        if task is not None and task.status in _TERMINAL_STATUSES:
            if task.status == "completed":
                return json.dumps(
                    {
                        "status": "completed",
                        "result": task.result,
                    }
                )
            return json.dumps(
                {
                    "status": task.status,
                    "error": task.error,
                }
            )
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS

    return json.dumps(
        {
            "status": "still_running",
            "task_id": child_task_id,
        }
    )
