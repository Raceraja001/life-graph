"""What a dev task's state means for automation (pure).

A *view* is the dev task's API shape (``services/dev/tasks.serialize``):
``status`` (queued / running / parked / completed / failed / cancelled) and
``stage`` (awaiting_pr, pr_open, awaiting_merge, merged, closed, pr_rejected,
needs_review, landed, no_changes, …).
"""

from __future__ import annotations

from typing import Any

#: The task is still to run or running: it holds a concurrency slot / overlaps.
ACTIVE_STATUSES = frozenset({"queued", "running", "parked"})
#: The task finished its work: a verified change is waiting for the owner, landed
#: or merged (race-app: "awaiting approval or completed"). A success for the
#: breaker, and what a chained job waits for.
FINISHED_STAGES = frozenset(
    {"awaiting_pr", "pr_open", "awaiting_merge", "merged", "landed", "completed", "no_changes"}
)
#: Status ``completed``, stage ``no_changes`` (services/dev/tasks.NO_CHANGES): the
#: run finished normally and said nothing needed changing (a nightly health check
#: that found the tree clean). Not a failure: it is in :data:`FINISHED_STAGES`, so
#: the breaker counts it as a success (it resets the count -- the failures before
#: it were not consecutive any more) and a chained job may follow it.
NO_CHANGES_STAGE = "no_changes"


def no_changes(view: dict[str, Any] | None) -> bool:
    """Whether the task ended as "no changes needed"."""
    return (
        bool(view)
        and (view or {}).get("status") == "completed"
        and (view or {}).get("stage") == NO_CHANGES_STAGE
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
    completed without a PR → done; "no changes needed" → skipped (nothing was
    done, nothing failed: restartable, and no "merged" issue comment); failed / cancelled / PR rejected or closed /
    missing → failed (an owner can start it again).
    """
    if not view:
        return "failed", "the task no longer exists"
    status, stage = view.get("status"), view.get("stage")
    if status in ("queued", "parked"):
        return "queued", None
    if status == "running":
        return "running", None
    if no_changes(view):
        summary = " ".join(str((view or {}).get("output") or "").split())
        reason = "no changes needed" + (f": {summary}" if summary else "")
        return "skipped", reason[:500]
    if stage in ("merged", "landed", "completed") and status == "completed":
        return "done", None
    if status == "failed":
        return "failed", str(view.get("error") or "the task failed")[:500]
    if status == "cancelled":
        return "failed", "the task was cancelled"
    if stage in ("pr_rejected", "closed"):
        return "failed", f"the change was {'rejected' if stage == 'pr_rejected' else 'closed'}"
    return "running", None
