"""Who is deciding an approval, as the server sees it — shared by both approval routers.

Two approval systems take an approve/reject over HTTP:

* the unified feed, ``POST /approvals/{id}/approve|reject`` (api/approvals.py);
* the autonomy queue, ``POST /autonomy/approvals/{id}/resolve`` and
  ``POST /autonomy/approvals/batch`` (autonomy/approvals/router.py).

Both record *who decided* from :func:`resolver` (built on api/auth.py
``ingress_for``), never from the request body: any client holding a service
key — the MCP server, a Claude Code hook, a watcher — could otherwise write
the owner's name there. A name the body does carry is kept only as an
unverified line in the note (:func:`note_with_claim`).

With ``approvals_require_owner`` on, :func:`require_owner` refuses anyone but
the owner (an owner key, a paired phone, or a dev stack with auth off).
Whatever the setting, :func:`refuse_self_approval` stops a non-owner caller
from approving an approval for work that same caller asked for, and
:func:`owner_only` keeps changes to trust, autonomy levels and the like to the
owner alone.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

from life_graph.api.auth import extract_api_key, ingress_for
from life_graph.config import settings

if TYPE_CHECKING:
    from life_graph.core.trust import Ingress

OWNER_REQUIRED = "Approving or rejecting needs the owner: an owner API key or a paired phone."
SELF_APPROVAL = (
    "This caller asked for the work this approval is about, so it cannot also "
    "decide it. The owner decides it: an owner API key, a paired phone or Telegram."
)


def key_label(request: Request) -> str:
    """A stable, non-secret name for the service key a caller presented.

    Keys have no names in configuration, so the audit trail gets a short
    fingerprint: enough to tell two keys apart, useless for recovering one.
    """
    key = extract_api_key(request.headers, request.query_params)
    if not key:
        return "service-key"
    return f"service-key:{hashlib.sha256(key.encode()).hexdigest()[:8]}"


def resolver(request: Request, _body: object | None = None) -> str:
    """Who is calling, as the server saw it (api/auth.py ``ingress_for``).

    ``phone:<device id>`` for a paired phone, ``owner`` for an owner key
    (``owner:local`` on a dev stack with auth off), and otherwise the
    fingerprint of the service key used. Nothing from the body is read; the
    second argument exists only so older call sites keep working.
    """
    return label_of(ingress_for(request), request)


def label_of(ingress: Ingress, request: Request) -> str:
    """:func:`resolver`'s label for an ``ingress`` already worked out."""
    if ingress.device_id:
        return f"phone:{ingress.device_id}"
    if ingress.actor == "owner:api_key":
        return "owner"
    if ingress.owner_verified:
        return ingress.actor  # "owner:local": no credential configured at all
    return key_label(request)


def require_owner(request: Request) -> None:
    """403 unless the caller is the owner — only when the setting is on."""
    if settings.approvals_require_owner and not ingress_for(request).is_owner:
        raise HTTPException(status_code=403, detail=OWNER_REQUIRED)


def owner_only(request: Request, what: str) -> None:
    """403 unless the caller is the owner — whatever ``approvals_require_owner`` says.

    For changes to how much the system may do on its own (trust scores,
    autonomy levels, safety rules, resuming autonomy, grading shadow runs,
    running a rollback): unlike deciding one approval, these are the owner's
    alone from the start, the same as setting a project's host commands
    (#294). A dev stack with auth off counts as the owner (``owner:local``).
    """
    if not ingress_for(request).is_owner:
        raise HTTPException(
            status_code=403,
            detail=f"{what} needs the owner: an owner API key or a paired phone.",
        )


def refuse_self_approval(request: Request, requested_by: str | None) -> None:
    """403 when a non-owner caller approves an approval for work it asked for.

    Not tied to ``approvals_require_owner``: with the setting off any service
    key may still decide, but not on its own request — an agent that started a
    dev task through MCP must not be the one to approve that task's plan, PR,
    merge or deploy. The owner is never refused here (the owner deciding on
    the owner's own request is the normal case), and nothing is refused when
    the approval does not say who asked (``requested_by`` is None).
    """
    if not requested_by:
        return
    if ingress_for(request).is_owner:
        return
    if requested_by == resolver(request):
        raise HTTPException(status_code=403, detail=SELF_APPROVAL)


def note_with_claim(note: str | None, claimed: str | None) -> str | None:
    """The note, plus whatever name the client claimed (kept, but unverified)."""
    if not claimed:
        return note
    line = f"(client said: {claimed})"
    return f"{note}\n{line}" if note else line
