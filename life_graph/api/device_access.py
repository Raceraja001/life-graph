"""What a paired phone's token may call (docs/specs/device-access.md).

A device token (services/devices.py) opens the Jarvis endpoints
(``/api/v1/jarvis/*``, any method) and, beyond them, only the routes in
:data:`DEVICE_ALLOWLIST`: read-only GETs behind the app's dashboard screens
and four named actions (life-graph-android docs/PLAN-v4.md, S1). Everything
else stays service-key only. The tenant always comes from the device
(api/middleware.py TenantMiddleware).

How a request is matched, so no spelling of a path reaches more than its
entry says:

* The path is the one Starlette routes on (``scope["path"]``, already
  percent-decoded, so ``%2F`` is a slash by now), and must equal
  ``request.url.path``: a decoded ``?`` or ``#`` would make the two differ.
* It must be made of plain segments (letters, digits, ``-``, ``_``, dots only
  inside a segment): no ``.`` or ``..`` segment, no ``//``, no ``%`` left
  after decoding, nothing else. A proxy that normalises ``..`` would turn
  such a path into a different route than the one checked.
* Each entry is the route's own template with every ``{param}`` a UUID,
  matched against the whole path: no prefix matches, trailing-slash or case
  variants, and an id segment can never be a literal route like ``stats``.
* The method must be the entry's exactly: GET does not admit HEAD or OPTIONS.

tests/unit/test_device_access.py checks every entry against the app's real
routes and through the real middleware; tests/integration/test_device_access.py
with a real device token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request

#: The Jarvis endpoints (api/jarvis.py): every method a device token may use.
DEVICE_PATH_PREFIX = "/api/v1/jarvis/"

UUID_PATTERN = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_SEGMENT = r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*"
_CLEAN_PATH = re.compile(rf"(?:/{_SEGMENT})+/?")
_PARAM = re.compile(r"\{[a-z_]+\}")


@dataclass(frozen=True)
class Allowed:
    """One route a device token may call: the method and the route's template."""

    method: str
    route: str  # as registered, e.g. "/api/v1/approvals/{approval_id}/approve"
    feature: str
    pattern: re.Pattern[str]


def _allow(method: str, route: str, feature: str) -> Allowed:
    parts = _PARAM.split(route)
    regex = UUID_PATTERN.join(re.escape(p) for p in parts)
    return Allowed(method, route, feature, re.compile(regex))


def _get(route: str, feature: str) -> Allowed:
    return _allow("GET", "/api/v1" + route, feature)


def _post(route: str, feature: str) -> Allowed:
    return _allow("POST", "/api/v1" + route, feature)


# Reviewed list: add an entry only with its reason in docs/specs/device-access.md.
DEVICE_ALLOWLIST: tuple[Allowed, ...] = (
    # ── Read-only ──
    _get("/money/summary", "money"),
    _get("/money/transactions", "money"),
    _get("/money/budgets", "money"),
    _get("/money/categories", "money"),
    _get("/money/checkin", "money"),
    _get("/documents", "documents"),
    _get("/documents/expiring", "documents"),
    _get("/connectors/today", "bills, calendar, mail waiting"),
    _get("/monitors", "monitors"),
    _get("/study/due", "study"),
    _get("/study/decks", "study"),
    _get("/study/progress", "study"),
    _get("/study/drafts", "study"),
    _get("/invoices", "invoices"),
    _get("/invoices/{invoice_id}", "invoices"),
    _get("/memories/", "memories"),
    _get("/memories/pending/count", "memories"),
    _get("/memories/{memory_id}", "memories"),
    _get("/judgment/decisions", "decisions"),
    _get("/judgment/decisions/{decision_id}", "decisions"),
    _get("/judgment/calibration", "calibration"),
    _get("/judgment/calibration/curve", "calibration"),
    _get("/judgment/stats", "calibration"),
    _get("/research/runs", "research"),
    _get("/research/runs/{run_id}", "research"),
    _get("/tech-watch", "tech watch"),
    _get("/kernel/tasks", "tasks"),
    _get("/kernel/tasks/{task_id}", "tasks"),
    _get("/kernel/drivers/tasks", "dev tasks"),
    _get("/kernel/drivers/tasks/stats", "dev tasks"),
    _get("/kernel/drivers/tasks/{task_id}", "dev tasks"),
    _get("/kernel/drivers/tasks/{task_id}/steps", "dev tasks"),
    _get("/kernel/drivers/night-shift", "dev tasks"),
    _get("/approvals", "approvals"),
    _get("/kernel/observability/agents", "agents"),
    _get("/kernel/drivers/scorecards", "agents"),
    _get("/kernel/observability/budget", "agents"),
    _get("/watchers/events", "activity"),
    _get("/watchers/events/summary", "activity"),
    _get("/kernel/schedules", "schedules"),
    _get("/kernel/schedules/{schedule_id}", "schedules"),
    _get("/kernel/personas", "personas"),
    _get("/kernel/personas/{persona_id}", "personas"),
    _get("/apps/health", "app health"),
    _get("/llm-offers", "LLM offers"),
    # ── Actions ──
    _post("/approvals/{approval_id}/approve", "approve an approval"),
    _post("/approvals/{approval_id}/reject", "reject an approval"),
    _post("/study/cards/{card_id}/grade", "answer a study card"),
    # Mark a bill paid, approve or reject a memory: Jarvis endpoints already
    # (POST /jarvis/bills/{id}/paid, /jarvis/memories/{id}/approve|reject).
)


def route_path(request: Request) -> str | None:
    """The path Starlette routes this request on, or None when it is not a
    plain path (see the module docstring) and so no device may use it."""
    path = request.scope.get("path", "")
    if request.scope.get("root_path") or path != request.url.path:
        return None
    return path if _CLEAN_PATH.fullmatch(path) else None


def device_may_call(method: str, path: str | None) -> bool:
    """Whether a device token opens *method* *path* (a :func:`route_path`)."""
    if not path or not _CLEAN_PATH.fullmatch(path):
        return False
    if path.startswith(DEVICE_PATH_PREFIX):
        return True
    return any(e.method == method and e.pattern.fullmatch(path) for e in DEVICE_ALLOWLIST)
