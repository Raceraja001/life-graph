"""What a dev task's state means for automation (pure).

A *view* is the dev task's API shape (``services/dev/tasks.serialize``):
``status`` (queued / running / parked / completed / failed / cancelled) and
``stage`` (awaiting_pr, pr_open, awaiting_merge, merged, closed, pr_rejected,
needs_review, landed, …).
"""

from __future__ import annotations

from typing import Any

#: The task is still to run or running: it holds a concurrency slot / overlaps.
ACTIVE_STATUSES = frozenset({"queued", "running", "parked"})
#: The task finished its work: a verified change is waiting for the owner, landed
#: or merged (race-app: "awaiting approval or completed"). A success for the
#: breaker, and what a chained job waits for.
FINISHED_STAGES = frozenset(
    {"awaiting_pr", "pr_open", "awaiting_merge", "merged", "landed", "completed"}
)


def _planned(view: dict[str, Any]) -> bool:
    """A plan task that filed its plan (``driver_plan``): it shows ``needs_review``
    while the plan waits for the owner, but its work is done."""
    return any(a.get("kind") == "driver_plan" for a in view.get("approvals") or [])


def finished(view: dict[str, Any] | None) -> bool:
    """Whether the task finished its work (see :data:`FINISHED_STAGES`)."""
    if not view or view.get("status") != "completed":
        return False
    return view.get("stage") in FINISHED_STAGES or _planned(view)


def active(view: dict[str, Any] | None) -> bool:
    return bool(view) and view.get("status") in ACTIVE_STATUSES


def failure_reason(view: dict[str, Any] | None) -> str | None:
    """The reason when the task failed (a breaker failure), else None.

    ``failed`` → its error; ``needs_review`` (its checks failed twice) counts
    too: an automation that keeps producing unverifiable work should stop.
    A cancelled task is not a failure of the automation.
    """
    if not view:
        return None
    if view.get("status") == "failed":
        return str(view.get("error") or "Task failed")
    if view.get("stage") == "needs_review" and not _planned(view):
        return "Checks failed twice; the change needs review"
    return None


def item_status_for(view: dict[str, Any] | None) -> tuple[str, str | None]:
    """A backlog item's status (and reason) from its task.

    queued / parked → queued; running, or finished and waiting for the owner
    (PR to approve, open, to merge; needs review) → running; merged, landed or
    completed without a PR → done; failed / cancelled / PR rejected or closed /
    missing → failed (an owner can start it again).
    """
    if not view:
        return "failed", "the task no longer exists"
    status, stage = view.get("status"), view.get("stage")
    if status in ("queued", "parked"):
        return "queued", None
    if status == "running":
        return "running", None
    if stage in ("merged", "landed", "completed") and status == "completed":
        return "done", None
    if status == "failed":
        return "failed", str(view.get("error") or "the task failed")[:500]
    if status == "cancelled":
        return "failed", "the task was cancelled"
    if stage in ("pr_rejected", "closed"):
        return "failed", f"the change was {'rejected' if stage == 'pr_rejected' else 'closed'}"
    return "running", None
