"""Buttons on the phone's notifications (life-graph-android docs/PLAN-v3.md).

``GET /jarvis/notifications`` gives each notification a ``kind`` and the
``actions`` it offers; ``POST /jarvis/notifications/{id}/action`` performs one
(api/jarvis.py). What a notification is comes from what wrote it:

* services/notifications/due.py rows (``source_type="due_item"``) name the
  item in their metadata (``item``, ``item_id``): bill, task, document,
  reminder. Rows written before ``item_id`` was stored are "other", without
  buttons: there is nothing for a button to find.
* the daily brief (services/brief.py, ``source_type="brief"``): "Listen".
* a paused browser errand (tools/errand.py, ``source_type="errand_approval"``):
  "Approve" / "Reject". This one is not a reminder about something — it is the
  owner's own say-so, and the only thing that widens an errand. Approving
  issues an ``AuthorizationCapability`` (autonomy/approvals/capability.py)
  for that one action type on that one origin; the errand is resumed by
  handing its ``capability_id`` back to ``run_browser_errand``. Nothing is
  resumed from here: a tap authorises, it does not act.

An action is taken once: it is recorded in the notification's metadata
(``action``), and a second tap gets "Already done." Listen is the exception:
it only opens the app, so it changes nothing and may be tapped again.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from life_graph.autonomy.kill_switch import PAUSED_REFUSAL, autonomy_stopped

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ITEM_KINDS = ("bill", "task", "document", "reminder", "errand_approval")
#: A browser errand waiting on the owner (tools/errand.py).
ERRAND_APPROVAL = "errand_approval"
SNOOZE_DAY_HOUR = 9  # "Tomorrow" means 09:00 tomorrow, in the owner's day

#: Per kind, the buttons in the order the phone shows them (at most 3).
ACTIONS: dict[str, list[tuple[str, str]]] = {
    "bill": [("paid", "Paid"), ("snooze_1d", "Tomorrow")],
    "reminder": [("done", "Done"), ("snooze_1h", "In 1 hour"), ("snooze_1d", "Tomorrow")],
    "task": [("snooze_1d", "Tomorrow")],
    "document": [],
    "brief": [("listen", "Listen")],
    # A browser errand paused on a step the policy will not authorise alone.
    "errand_approval": [("approve", "Approve"), ("reject", "Reject")],
    # Something the owner said they would do (services/nudges.py).
    "nudge": [("done", "Done"), ("snooze_1d", "Tomorrow"), ("drop", "Drop")],
    "other": [],
}
LISTEN_RESULT = "Open Jarvis to listen."
APPROVED_RESULT = "Approved: Jarvis is continuing the errand."
REJECTED_RESULT = "Rejected: Jarvis stopped the errand."
#: How long an errand approval stays good for. See :func:`_errand`.
ERRAND_CAPABILITY_TTL = timedelta(minutes=30)
#: Read-only browser actions an approved capability also names, so the handle
#: does not deny the steps that get the errand back to its page. See
#: :func:`_errand` for why this grants nothing.
ERRAND_RESUME_ACTIONS = ("browser_navigate", "read_page")
ALREADY_DONE = "Already done."
NOT_OFFERED = "That button isn't offered for this notification."


class ActionRefusedError(Exception):
    """The action cannot be taken; the message is a sentence for the owner (409)."""


class ActionNotFoundError(Exception):
    """What the notification points at is gone (404)."""


def utcnow() -> datetime:
    """The action endpoint's clock (a seam for tests that run the due job at a set time)."""
    return datetime.now(UTC)


def kind_of(source_type: str | None, meta: dict[str, Any] | None) -> str:
    from life_graph.services.notifications.due import SOURCE_TYPE

    meta = meta or {}
    if source_type == "brief":
        return "brief"
    if source_type == "nudge" and meta.get("item_id"):
        return "nudge"
    # Matched on either, because the card is written once with both set and
    # read back by rows that may predate one of them.
    if source_type == ERRAND_APPROVAL or meta.get("item") == ERRAND_APPROVAL:
        return ERRAND_APPROVAL
    if source_type == SOURCE_TYPE and meta.get("item") in ITEM_KINDS and meta.get("item_id"):
        return meta["item"]
    return "other"


def taken(meta: dict[str, Any] | None) -> bool:
    return bool((meta or {}).get("action"))


def actions_for(kind: str, meta: dict[str, Any] | None) -> list[dict[str, str]]:
    """The buttons to show; none once an action has been taken (bar Listen)."""
    if kind != "brief" and taken(meta):
        return []
    return [{"id": a, "label": label} for a, label in ACTIONS.get(kind, [])]


def offered(kind: str, action: str) -> bool:
    return any(a == action for a, _ in ACTIONS.get(kind, []))


#: The (kind, action) pairs that decide an authorization rather than tidy a
#: reminder: Approve mints a capability, Reject refuses one. The route gates
#: these like any approval (api/approval_identity.py). Every other button
#: (paid, done, snooze, drop, listen) only changes the owner's own list.
AUTHORITY_ACTIONS = frozenset({(ERRAND_APPROVAL, "approve"), (ERRAND_APPROVAL, "reject")})


def grants_authority(kind: str, action: str) -> bool:
    return (kind, action) in AUTHORITY_ACTIONS


def snooze_until(action: str, now: datetime, tz: Any) -> datetime:
    """When a snoozed item comes back: an hour from now, or 09:00 tomorrow."""
    if action == "snooze_1h":
        return (now + timedelta(hours=1)).astimezone(tz)
    tomorrow = now.astimezone(tz).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time(SNOOZE_DAY_HOUR, 0), tzinfo=tz)


def result_for(action: str, *, at: datetime | None, now: datetime, tz: Any) -> str:
    """The plain sentence the phone shows in place of the notification."""
    from life_graph.services.reminders import say_when

    if action == "approve":
        return APPROVED_RESULT
    if action == "reject":
        return REJECTED_RESULT
    if action == "paid":
        return "Marked paid."
    if action == "drop":
        return "Dropped: I won't bring it up again."
    if action == "done":
        return "Done."
    if action == "listen":
        return LISTEN_RESULT
    if at is not None:
        return f"I'll remind you {say_when(at, now, tz)}."
    return "Done."


async def perform(
    session: AsyncSession,
    tenant_id: str,
    notification: Any,
    action: str,
    now: datetime,
    tz: Any,
    *,
    decided_by: str | None = None,
) -> str:
    """Take *action* on *notification* (already this tenant's, locked by the caller).

    *decided_by* is who tapped, as the server recognised them
    (api/approval_identity.py ``resolver``); it is recorded as ``action.by``.

    Returns the result sentence; raises ActionRefusedError (409) or ActionNotFoundError
    (404). The caller commits.
    """
    meta = dict(notification.extra_metadata or {})
    kind = kind_of(notification.source_type, meta)
    if not offered(kind, action):
        raise ActionRefusedError(NOT_OFFERED)
    if action == "listen":
        return LISTEN_RESULT
    if taken(meta):
        raise ActionRefusedError(ALREADY_DONE)
    at = None
    if kind == ERRAND_APPROVAL:
        if action != "reject" and await autonomy_stopped(tenant_id):
            # Pausing revoked every live mandate; a tap must not mint a new one.
            raise ActionRefusedError(PAUSED_REFUSAL)
        meta = _errand(tenant_id, notification, meta, action, now)
    elif kind == "nudge":
        from life_graph.services import nudges

        row = await nudges.act(session, tenant_id, meta["item_id"], action, now, tz)
        if row is None:
            raise ActionNotFoundError("That is gone.")
        at = row.trigger_time if action == "snooze_1d" else None
    elif action == "paid":
        await _paid(session, tenant_id, meta["item_id"], now)
    elif kind == "reminder":
        at = await _reminder(session, tenant_id, meta["item_id"], action, now, tz)
    else:  # snooze_1d on a bill or to-do
        from life_graph.services.notifications.due import snooze_metadata

        at = snooze_until(action, now, tz)
        meta = snooze_metadata(meta, at, notification.id)
    meta["action"] = {"id": action, "at": now.astimezone(UTC).isoformat()}
    if decided_by:
        meta["action"]["by"] = decided_by
    notification.extra_metadata = meta  # a new dict, so the JSONB change is saved
    notification.is_read = True
    return result_for(action, at=at, now=now, tz=tz)


def _errand(
    tenant_id: str, notification: Any, meta: dict[str, Any], action: str, now: datetime
) -> dict[str, Any]:
    """Approve or reject a paused browser errand. Returns the new metadata.

    Approving does not resume anything — it *authorises*. It mints an
    :class:`~life_graph.autonomy.approvals.AuthorizationCapability` for the one
    action the card named, and leaves its id in the metadata;
    ``run_browser_errand`` resumes the errand by presenting that id, and the
    policy re-verifies every binding at every step
    (autonomy/approvals/policy_checker.py). Nothing here touches a browser, so
    a tap can never itself be the action.

    "The one action" is meant exactly. The capability is bound to the tenant,
    the action type, the origin, *and* the run it paused in, the step's
    position in that run, the element it acts on and a digest of the whole
    action (``services/browser_errand.canonical_parameters_hash``). It is also
    one-use, so performing it spends it. So the tap authorises the step the
    owner was shown on the card and nothing else: not the same click in a
    later plan, not a re-numbered step, not the same button with an edited
    value, and not twice.

    The scope comes from the card, which was written by the server from what
    the policy itself read — not from anything the model said at approval
    time. An unnamed action or origin is refused rather than widened: a
    capability for "any origin" is not what the owner was shown. The run and
    the step are required for the same reason — a capability with nothing to
    pin it to one action is not what the card described.
    """
    from life_graph.autonomy.approvals import capability_store

    if action == "reject":
        meta["rejected"] = True
        return meta
    action_type = str(meta.get("action_type") or "").strip()
    origin = str(meta.get("target_origin") or "").strip()
    if not action_type or not origin:
        raise ActionRefusedError("I can't tell what this would approve. Ask Jarvis again.")
    errand_id = str(meta.get("item_id") or "").strip()
    step_index = meta.get("step_index")
    if not errand_id or not isinstance(step_index, int) or isinstance(step_index, bool):
        # A card that cannot say which run and which step it is about cannot
        # be turned into a mandate for one action. Refused, not widened.
        raise ActionRefusedError("I can't tell what this would approve. Ask Jarvis again.")
    capability = capability_store.issue(
        tenant_id=tenant_id,
        # The step's own action type, plus the two read-only ones a resumed
        # errand needs to get back to the page it paused on. That is not a
        # widening: a presented handle is verified *before* the read-only
        # shortcut (autonomy/approvals/policy_checker.py), so a capability for
        # the click alone would make the handle itself deny the navigate that
        # has to come first — while navigating and reading are allowed with no
        # capability at all. Naming them here adds no authority, it only stops
        # the mandate getting in the way of what was already permitted.
        action_types=[action_type, *ERRAND_RESUME_ACTIONS],
        target_origins=[origin],
        # ERRAND_CAPABILITY_TTL, not the 15-minute default: the owner may tap
        # this while the phone is in their pocket and Jarvis resumes on its
        # next turn. Still far short of MAX_TTL, and still one action on one
        # origin — it is a mandate for this errand, not a standing permission.
        ttl=ERRAND_CAPABILITY_TTL,
        # The exact action, as the card described it. The selector and the
        # digest come from the engine's own reading of the step
        # (tools/errand.py wrote them into this metadata), never from a model.
        errand_id=errand_id,
        approval_id=str(getattr(notification, "id", "") or "") or None,
        step_index=step_index,
        target_selector=meta.get("target_selector"),
        parameters_hash=meta.get("parameters_hash"),
        # Spent by performing it: an approval for an outward, irreversible
        # action is not a budget to draw on twice.
        one_use=True,
        now=now,
    )
    meta["capability_id"] = capability.capability_id
    meta["capability_expires_at"] = capability.expires_at.isoformat()
    return meta


async def _paid(session: AsyncSession, tenant_id: str, item_id: str, now: datetime) -> None:
    from life_graph.connectors.bills import mark_paid

    if await mark_paid(session, tenant_id, item_id, now) is None:
        raise ActionNotFoundError("That bill is gone.")


async def _reminder(
    session: AsyncSession, tenant_id: str, item_id: str, action: str, now: datetime, tz: Any
) -> datetime | None:
    """Done, or a new time for the reminder. Returns the new time when snoozed."""
    from sqlalchemy import select

    from life_graph.models.db import Intention

    try:
        ident = uuid.UUID(str(item_id))
    except ValueError:
        raise ActionNotFoundError("That reminder is gone.") from None
    row = (
        await session.execute(
            select(Intention)
            .where(Intention.tenant_id == tenant_id, Intention.id == ident)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActionNotFoundError("That reminder is gone.")
    if row.status == "completed":
        raise ActionRefusedError(ALREADY_DONE)
    if row.status != "pending":
        raise ActionRefusedError("That reminder was cancelled.")
    if action == "done":
        row.status, row.completed_at = "completed", now
        return None
    at = snooze_until(action, now, tz)
    # A new time is a new dedup key (due_notifications.reminder_items): it is
    # posted again when that time comes.
    row.trigger_time = at
    return at
