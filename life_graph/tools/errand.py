"""run_browser_errand: Jarvis does a short errand in a browser, under the owner's say-so.

This is the chat-facing door onto ``services/browser_errand.py`` — the engine
that judges every browser step before it happens, resolves ``vault://``
handles against the origin the *driver* says it is on, and fences page text as
untrusted on the way back. Nothing about that judgement is re-decided here.
What this module adds is the two ends the engine deliberately leaves open:

1. **A browser, and specifically a contained one.** The engine takes a
   :class:`~life_graph.services.browser_errand.BrowserDriver` protocol and
   imports no browser at all. :func:`get_driver` is what decides which one an
   errand gets, and it has exactly one answer:
   :class:`~life_graph.services.browser_sandbox_driver.IsolatedBrowserDriver`,
   the sandboxed headless Chromium from ``compose.sandbox.yaml``. When that
   runtime is not configured or not reachable, the answer is ``None`` and the
   errand does not run. It is never :class:`MCPBrowserDriver` — the bridged
   Playwright MCP server drives whatever browser *it* owns, in practice one on
   the host beside the application's own credentials, and quietly using that
   when the contained one is missing would turn an isolation failure into an
   errand that ran anyway (``docs/AI_WORK_ORDER.md`` §3).
2. **A way to ask the owner.** A step the policy will not authorise on its own
   becomes a ``critical`` notification with Approve/Reject buttons on the phone
   (``services/notification_actions.py``). Tapping Approve issues an
   :class:`~life_graph.autonomy.approvals.AuthorizationCapability`; handing its
   id back as ``capability_id`` lets the same errand run through.

**The errand carries no owner mandate, and that is the point.** A
:class:`~life_graph.services.browser_errand.BrowserErrand`'s ``owner_request``
is *authority* — the engine's docstring says it may be set only by trusted,
owner-authenticated code. A tool handler is the opposite of that: its arguments
are model output, often written after the model read a web page. If ``goal``
and ``allowed_origins`` were turned into a mandate here, a page that said
"the owner authorised this transfer" would end up authorising it, which is the
one attack the whole engine exists to stop. So the mandate is left empty and
the owner's own tap is the only thing that widens an errand:

* ``navigate`` and ``read_page`` are read-only and run unasked;
* ``fill_field`` comes back ``needs_approval``;
* ``click`` and a ``vault://`` fill are outward and irreversible, so with
  nothing behind them the policy denies them outright — see :func:`_asking`
  for why that refusal still becomes a question on the phone.

``allowed_origins`` is therefore not authority but a *fence*: it can only
narrow where this errand may go, never widen what it may do.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from life_graph.services.browser_sandbox_driver import (
    MODE_ISOLATED,
    MODE_MOCK,
    SANDBOX_OFFLINE,
    IsolatedBrowserDriver,
    browser_sandbox_available,
    sandbox_mode,
)
from life_graph.services.sandbox import SandboxUnavailableError
from life_graph.tools.registry import tool

if TYPE_CHECKING:
    from life_graph.services.browser_errand import (
        BrowserDriver,
        BrowserErrand,
        BrowserStep,
        ErrandResult,
        StepResult,
    )

logger = logging.getLogger(__name__)

#: ``source_type`` (and metadata ``item``) on the card the phone shows. Kept in
#: step with ``services/notification_actions.py``, which reads both.
APPROVAL_SOURCE = "errand_approval"

#: Most steps one tool call may carry. The engine's own limit is fifty
#: (``MAX_ERRAND_STEPS``); a chat errand is a login and a download, and a
#: plan the owner has to read on a phone should fit on the screen.
MAX_STEPS = 12

#: Longest a ``goal`` may be. It is shown to the owner on the card and stored
#: in the notification's metadata; it never reaches a verdict.
MAX_GOAL_CHARS = 200

#: The bridged Playwright MCP tools, as ``mcp_bridge`` registers them.
MCP_PREFIX = "mcp_playwright_"

#: Reported when there is no isolated browser runtime to run the errand in.
#: One sentence, and no second option in it: the sandboxed browser is the only
#: browser an errand gets (:func:`get_driver`).
NO_BROWSER = SANDBOX_OFFLINE

#: ``reason`` on that reply. Machine-readable so a caller (or a test) can tell
#: "the sandbox is down" from "the plan was wrong" without reading prose.
SANDBOX_UNAVAILABLE = "sandbox_unavailable"

#: The policy's reason for "nothing the owner said covers this". The one
#: refusal that becomes a question on the phone rather than a dead end.
NO_MANDATE = "no_owner_mandate"

#: The policy's reason for "the owner said never". Never a question.
RULE_DENIES = "standing_rule_denies"


# ── The browser ──────────────────────────────────────────────────────────

#: An origin in whatever the page's own ``location.origin`` came back wrapped
#: in. Deliberately strict: this string decides which origin a password is
#: checked against, so a reply we cannot read cleanly is an error, not a guess.
_ORIGIN = re.compile(r"https?://[A-Za-z0-9._~%:\[\]-]+")


class MCPBrowserDriver:
    """A :class:`BrowserDriver` over the bridged Playwright MCP tools.

    **Not the driver an errand gets.** :func:`get_driver` never returns one of
    these: the bridged MCP server drives a browser this process does not own
    and cannot describe, which is the opposite of the containment §3 of the
    work order requires. It is kept because the bridge itself is still a real
    integration and because a driver over it is the clearest statement of what
    that integration *is*; reaching it takes deliberately passing one in
    through :func:`set_driver_override`, never a fallback.

    Playwright MCP addresses elements by *accessibility ref* (``e12``) taken
    from a snapshot, not by CSS selector, so a step's ``field`` and
    ``selector`` are those refs. They still go through the engine's
    ``_check_selector`` first, which is what keeps a "selector" from arriving
    as a ``javascript:`` payload for a driver that evaluates what it is handed.

    :meth:`current_origin` asks the page where it is and raises if the answer
    cannot be read. That fails closed twice over: the engine turns a raising
    ``current_origin`` into a failed step, and an origin that came back
    mangled would not match a mandate or a vault entry anyway.
    """

    def __init__(self, prefix: str = MCP_PREFIX) -> None:
        self._prefix = prefix

    async def _call(self, name: str, **args: Any) -> str:
        from life_graph.tools.registry import registry

        return await registry.execute(f"{self._prefix}{name}", args)

    async def navigate(self, url: str) -> None:
        await self._call("browser_navigate", url=url)

    async def fill_field(self, field: str, value: str) -> None:
        # The plaintext is an argument value, and the registry logs argument
        # *names* only (tools/registry.py) — the one reason this is safe to
        # hand to a bridged tool at all.
        await self._call("browser_type", ref=field, element=field, text=value)

    async def click(self, selector: str) -> None:
        await self._call("browser_click", ref=selector, element=selector)

    async def read_page(self) -> str:
        return await self._call("browser_snapshot")

    async def current_origin(self) -> str:
        out = await self._call("browser_evaluate", function="() => location.origin")
        found = _ORIGIN.search(out or "")
        if found is None:
            # No origin, not "about:blank" or "": a blank answer would be
            # normalised to a blank origin, which compares equal to nothing
            # and would quietly fail an origin check for the wrong reason.
            raise RuntimeError("the browser did not report an origin")
        return found.group(0)


def browser_available() -> bool:
    """True when the Playwright MCP bridge registered its tools this run.

    Reports on the *bridge*, not on whether an errand can run. It is
    deliberately not consulted by :func:`get_driver` any more: a registered
    MCP browser is not a contained browser, and the one question that decides
    whether an errand runs is
    :func:`~life_graph.services.browser_sandbox_driver.browser_sandbox_available`.
    """
    from life_graph.tools.registry import registry

    return f"{MCP_PREFIX}browser_navigate" in registry.tool_names


#: The seam. ``None`` in production; a test (or ``browser_sandbox_mode =
#: "mock"``) puts a driver here to run the whole tool without a container.
#: Explicit, module-level and single-valued on purpose: an override is
#: something a developer wrote down, not something a failure falls back to.
_driver_override: BrowserDriver | None = None


def set_driver_override(driver: BrowserDriver | None) -> None:
    """Make :func:`get_driver` return *driver* (or ``None`` to clear it)."""
    global _driver_override
    _driver_override = driver


def get_driver(errand_id: str | None = None, tenant_id: str | None = None) -> BrowserDriver | None:
    """The contained browser this errand runs in, or ``None``.

    ``None`` is the fail-closed answer, and the only alternative to a
    sandboxed driver. It is returned when the mode is ``disabled`` (or
    anything unrecognised), when no isolated browser endpoint is configured,
    and when a driver for this tenant and errand could not even be
    constructed. In every one of those cases
    :func:`run_browser_errand` reports :data:`SANDBOX_UNAVAILABLE` and stops.

    *tenant_id* and *errand_id* are the session's scope, not labels: they are
    what the sandbox keys this errand's cookies and storage to, so a driver is
    only built once the run has an id (after :func:`build_errand`), and a call
    without them gets ``None`` rather than an unscoped session.
    """
    if _driver_override is not None:
        return _driver_override
    mode = sandbox_mode()
    if mode == MODE_MOCK:
        # "mock" is the test mode and it has no built-in driver: whatever the
        # test injected through the seam above, or nothing.
        return None
    if mode != MODE_ISOLATED or not browser_sandbox_available():
        logger.info(
            "no isolated browser runtime (mode=%s, configured=%s): browser errands refused",
            mode,
            browser_sandbox_available(),
        )
        return None
    try:
        return IsolatedBrowserDriver(tenant_id=tenant_id, errand_id=errand_id)
    except (SandboxUnavailableError, ValueError) as exc:
        logger.warning("isolated browser driver could not be created: %s", exc)
        return None


# ── Reading the plan the model wrote ─────────────────────────────────────


def _text(value: Any, limit: int = 200) -> str | None:
    """A bounded string, or ``None`` for anything blank."""
    if value is None:
        return None
    out = str(value).strip()
    return out[:limit] or None


def _fenced(origin: str, fence: frozenset[str]) -> bool:
    """True when *origin* is inside the owner's ``allowed_origins``.

    An empty fence lets anything public through — the destination validator
    has already refused ``file:``, the loopback and the metadata addresses, and
    a fence is a narrowing, not the only thing standing in the way.
    """
    if not fence:
        return True
    if origin in fence:
        return True
    host = origin.split("://", 1)[-1].split(":", 1)[0]
    return any(
        entry.startswith("*.") and (host == entry[2:] or host.endswith(entry[1:]))
        for entry in fence
    )


class PlanError(ValueError):
    """The plan cannot be turned into steps. The message is for the model."""


async def build_errand(
    goal: str,
    start_url: str,
    steps: list[dict[str, Any]] | None,
    allowed_origins: list[str] | None,
    *,
    capability_id: str | None = None,
    errand_id: str | None = None,
) -> tuple[BrowserErrand, str]:
    """``(the errand, its id)`` from the model's plan, or :class:`PlanError`.

    *errand_id* resumes a run the owner has since approved: the capability
    minted from that approval is bound to it, so a resumed run has to be the
    same run. A fresh id is minted when none is given. Supplying someone
    else's id buys nothing — the step index, the element and the parameter
    digest are bound too, so claiming the approved run's id while doing
    something else is just a different denial
    (``autonomy/approvals/capability.py``).

    Every destination — ``start_url`` and each ``navigate`` step's ``url`` —
    is put through ``services/destination_validator.py`` here, before a driver
    exists, and then again by the engine at the moment the step runs. Twice on
    purpose: this pass is what lets a bad URL come back as a sentence the model
    can act on instead of a refused step halfway through an errand.
    """
    from life_graph.services import browser_errand as be
    from life_graph.services import vault
    from life_graph.services.destination_validator import (
        DestinationRefusedError,
        validate_destination_url_async,
    )

    if not _text(goal):
        raise PlanError("What is the errand for? Pass a short goal.")
    raw_steps = list(steps or [])
    if len(raw_steps) > MAX_STEPS:
        raise PlanError(f"Too many steps ({len(raw_steps)}): keep an errand under {MAX_STEPS}.")

    fence = frozenset(
        be.normalise_origin_entry(str(o)) for o in (allowed_origins or []) if _text(o)
    )

    async def destination(url: str | None, what: str) -> str:
        """*url*, canonical, checked against the validator and the fence."""
        if not _text(url):
            raise PlanError(f"{what} needs a url.")
        try:
            # The async variant: the same checks as validate_destination_url,
            # off the event loop, because it resolves the name.
            canonical = await validate_destination_url_async(str(url))
        except DestinationRefusedError as exc:
            raise PlanError(f"{what} is not somewhere I can send a browser: {exc}") from None
        if not _fenced(be.normalise_origin_entry(canonical), fence):
            raise PlanError(f"{what} is outside the origins this errand is allowed to visit.")
        return canonical

    built: list[BrowserStep] = [
        be.BrowserStep(kind=be.NAVIGATE, url=await destination(start_url, "start_url"))
    ]
    for index, raw in enumerate(raw_steps, start=2):
        if not isinstance(raw, dict):
            raise PlanError(f"step {index} is not an object.")
        kind = (str(raw.get("kind") or "")).strip().lower()
        if kind not in be.STEP_KINDS:
            raise PlanError(
                f"step {index}: unknown kind {kind!r:.40}. One of: {', '.join(be.STEP_KINDS)}."
            )
        value = raw.get("value")
        if raw.get("is_secret") and _text(value):
            # A secret is named, never carried. The handle is resolved by the
            # engine against the origin the browser is actually on, so naming
            # one here cannot aim it at a different site.
            text = str(value).strip()
            value = text if text.lower().startswith(vault.SCHEME) else f"{vault.SCHEME}{text}"
        # field and selector are accepted either way round: a model that calls
        # a click target a "field" meant the thing it is clicking.
        where = _text(raw.get("selector")) or _text(raw.get("field"))
        built.append(
            be.BrowserStep(
                kind=kind,
                url=await destination(raw.get("url"), f"step {index}")
                if kind == be.NAVIGATE
                else None,
                field=where if kind == be.FILL_FIELD else None,
                selector=where if kind == be.CLICK else None,
                value=_text(value, limit=500) if kind == be.FILL_FIELD else None,
                note=_text(raw.get("note")),
            )
        )
    # No owner_request: see the module docstring. capability_id is the only
    # authority an errand gets, and the policy re-verifies it against this
    # tenant, task, action type, origin, run, step, element and parameter
    # digest at every single step.
    run_id = _text(errand_id, limit=120) or f"errand_{uuid.uuid4().hex[:16]}"
    errand = be.BrowserErrand(
        steps=tuple(built),
        capability_id=_text(capability_id, limit=120),
        id=run_id,
    )
    return errand, run_id


# ── Asking the owner ─────────────────────────────────────────────────────


def _asking(result: ErrandResult) -> StepResult | None:
    """The step the owner has to answer, if there is one.

    ``needs_approval`` is the engine asking outright. A ``denied`` step whose
    reason is ``no_owner_mandate`` is the same question wearing a refusal: an
    outward, irreversible step with no mandate behind it is denied rather than
    queued (``autonomy/approvals/policy_checker.py``), and such a step did not
    run. Posting a card is asking the owner, not taking the action, so the
    question is worth putting to them.

    A step denied for any other reason is not a question and never becomes
    one — a standing rule saying never is the owner having already answered, a
    capability that did not verify is a credential being refused, and a
    malformed selector or unknown kind is a bug in the plan.
    """
    from life_graph.services import browser_errand as be

    for step in result.steps:
        if step.status == be.NEEDS_APPROVAL:
            return step
        if (
            step.status == be.DENIED
            and NO_MANDATE in step.reasons
            and RULE_DENIES not in step.reasons
        ):
            return step
    return None


def approval_notification(
    tenant_id: str, *, goal: str, errand_id: str, step: StepResult, now: datetime
) -> Any:
    """The card the phone shows, with Approve and Reject on it.

    ``critical`` is what ``api/jarvis.py`` renders as "urgent". The metadata
    carries only what the policy itself was allowed to read — the action type
    and the origin — plus the owner's own goal; no page text, and nothing a
    verdict rested on that the owner cannot see.

    It also carries the exact identity of the step: which run, which position
    in it, which element, and a digest of the whole action. Tapping Approve
    mints a capability bound to all four
    (``services/notification_actions.py``), so the tap authorises that one
    action and not the next plan that ends in a similar-looking click. The
    digest is not the value — nothing the owner typed or the vault holds is
    in this metadata.
    """
    from life_graph.models.db import Notification

    origin = step.target_origin or "the page"
    return Notification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        priority="critical",
        title=f"Approval needed: {step.kind} on {origin}"[:500],
        body=(
            f"Jarvis is executing '{goal}' and paused at step {step.index + 1} "
            f"({step.kind}) awaiting your confirmation."
        ),
        extra_metadata={
            "item": APPROVAL_SOURCE,
            "item_id": errand_id,
            "step_index": step.index,
            "action_type": step.action_type,
            "target_origin": step.target_origin,
            "target_selector": step.target_selector,
            "parameters_hash": step.parameters_hash,
            "goal": goal,
            "reasons": list(step.reasons),
            # Whether this run had already read outside content when it wrote
            # the plan. The owner is being asked to authorise someone's idea;
            # whose it might have been belongs in the question.
            "tainted": _tainted(),
        },
        # The phone polls for these, as services/due_notifications.py does.
        is_delivered=True,
        delivered_at=now,
        source_type=APPROVAL_SOURCE,
    )


def _tainted() -> bool:
    """True when this run has already read outside content (core/run_taint.py)."""
    try:
        from life_graph.core.run_taint import outside_content_seen

        return bool(outside_content_seen())
    except Exception:  # noqa: BLE001 - no run context: nothing read, nothing to flag
        return False


# ── The tool ─────────────────────────────────────────────────────────────


@tool(
    name="run_browser_errand",
    description=(
        "Run a short errand in a real browser: go to a page, read it, fill a"
        " field, click something. Use for things no API offers — checking a"
        " balance on a portal, downloading a statement, submitting a form the"
        " user asked you to submit."
        " `steps` is a list of objects, each {kind, ...}: 'navigate' {url},"
        " 'read_page' {}, 'fill_field' {field, value, is_secret}, 'click'"
        " {selector}. `field`/`selector` name an element from the last"
        " read_page. For a password or OTP set is_secret:true and put the"
        " vault handle (not the secret) in `value`."
        " `allowed_origins` restricts where the errand may go, e.g."
        " ['https://netbanking.hdfcbank.com']."
        " Reading pages runs straight away. Anything that types or clicks"
        " needs the user's tap: the result comes back"
        " status='needs_approval' and they get a notification with Approve"
        " and Reject. Tell them to check their phone; do not retry."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "What the errand is for, in the user's words,"
                " e.g. 'get this month's bank statement'. Shown to them on the"
                " approval notification.",
            },
            "start_url": {
                "type": "string",
                "description": "The page to open first. Must be http(s) and public.",
            },
            "steps": {
                "type": "array",
                "description": "The steps to run after opening start_url.",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["navigate", "read_page", "fill_field", "click"],
                        },
                        "url": {"type": "string", "description": "navigate: where to go."},
                        "field": {"type": "string", "description": "fill_field: which field."},
                        "selector": {"type": "string", "description": "click: which element."},
                        "value": {
                            "type": "string",
                            "description": "fill_field: the text, or the vault handle"
                            " when is_secret is true.",
                        },
                        "is_secret": {
                            "type": "boolean",
                            "description": "True when `value` is a vault handle, not a literal.",
                        },
                        "note": {"type": "string", "description": "For the audit trail only."},
                    },
                    "required": ["kind"],
                },
            },
            "allowed_origins": {
                "type": "array",
                "description": "Origins this errand may visit, e.g."
                " ['https://hdfc.com']. Leave empty for no extra restriction.",
                "items": {"type": "string"},
            },
            "capability_id": {
                "type": "string",
                "description": "Only when resuming an errand the user approved"
                " on their phone: the capability_id from that notification.",
            },
            "errand_id": {
                "type": "string",
                "description": (
                    "Only when resuming an approved errand: the errand_id this"
                    " tool returned when it paused. An approval is bound to"
                    " that run, so resuming without it is refused."
                ),
            },
        },
        "required": ["goal", "start_url", "steps"],
    },
    # A real browser on a real site: the registry's 15s default cuts off a
    # page that is still settling, as services/mcp_bridge.py found.
    timeout_seconds=90,
)
async def run_browser_errand(
    goal: str,
    start_url: str,
    steps: list[dict[str, Any]] | None = None,
    allowed_origins: list[str] | None = None,
    capability_id: str | None = None,
    errand_id: str | None = None,
) -> str:
    """Run one browser errand for the current tenant (JSON). Never raises."""
    from life_graph.autonomy.approvals import (
        ActionPolicyChecker,
        capability_store,
        rules_from_config,
    )
    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.services import browser_errand as be
    from life_graph.storage import database
    from life_graph.tools._guards import ToolDeniedError, check_tenant

    goal = (_text(goal, limit=MAX_GOAL_CHARS) or "").strip()
    ctx = get_current_task_context()
    if has_tenant_context():
        tenant_id = get_current_tenant_id()
    elif ctx is not None:
        tenant_id = ctx.tenant_id
    else:
        return json.dumps({"error": "run_browser_errand has no tenant context."})
    try:
        # The same gate as the host tools: an errand types the owner's real
        # passwords into a real page, which is not a thing a customer tenant
        # borrows (tools/_guards.py).
        check_tenant("run_browser_errand")
    except ToolDeniedError as exc:
        return json.dumps({"error": str(exc)})

    try:
        errand, errand_id = await build_errand(
            goal,
            start_url,
            steps,
            allowed_origins,
            capability_id=capability_id,
            errand_id=errand_id,
        )
    except PlanError as exc:
        return json.dumps({"error": str(exc), "goal": goal})

    # After build_errand, because the run now has an id and that id is the
    # scope of the browser session: this errand's cookies and storage belong to
    # this tenant and this run, and are gone when it ends.
    driver = get_driver(errand_id=errand_id, tenant_id=tenant_id)
    if driver is None:
        return json.dumps(
            {
                "status": be.FAILED,
                "reason": SANDBOX_UNAVAILABLE,
                "message": NO_BROWSER,
                # Kept alongside `message`: every other refusal this tool
                # returns is an "error", and a caller reading that key should
                # not have to special-case the one that is about isolation.
                "error": NO_BROWSER,
                "goal": goal,
                "errand_id": errand_id,
            }
        )

    task_id = str(ctx.root_task_id or ctx.task_id) if ctx is not None else None
    checker = ActionPolicyChecker(
        # The owner's configured rules, from the store trusted code writes —
        # never anything in the model's plan.
        standing_rules=rules_from_config(tenant_id),
        # The browser catalogue. A checker over the default one does not know
        # the browser action types and would deny every step as unknown.
        catalogue=be.BROWSER_ACTION_TYPES,
        tenant_id=tenant_id,
        task_id=task_id,
        capabilities=capability_store,
    )
    now = datetime.now(UTC)
    result: ErrandResult | None = None
    asking: StepResult | None = None
    failure: str | None = None
    try:
        async with database.async_session() as session:
            executor = be.BrowserErrandExecutor(
                driver=driver,
                session=session,
                tenant_id=tenant_id,
                checker=checker,
                task_id=task_id,
                capabilities=capability_store,
            )
            result = await executor.run(errand)
            asking = _asking(result)
            if asking is not None:
                session.add(
                    approval_notification(
                        tenant_id, goal=goal, errand_id=errand_id, step=asking, now=now
                    )
                )
            # One commit for both: a one-use secret is spent by the transaction
            # that used it (services/vault.py), and an errand that paused has
            # not spent one.
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        # Never the plan and never a page: both are personal, and a page is
        # also untrusted text that should not reach a log unfenced.
        logger.warning("run_browser_errand failed (%d steps): %s", len(errand.steps), exc)
        failure = f"The errand could not be run: {exc}"
    finally:
        # Every exit: finished, failed, denied, or paused waiting for the
        # owner's tap. A paused errand is over as far as this process is
        # concerned — resuming it is a new tool call with a new session — so
        # there is no path on which the browser context outlives the errand.
        cleaned = await _release(driver)

    if failure is not None:
        out: dict[str, Any] = {
            # Same shape as every other way this tool refuses, so a caller
            # does not have to tell "it threw" from "it was denied" by which
            # keys happen to be present.
            "status": be.FAILED,
            "error": failure,
            "goal": goal,
            "errand_id": errand_id,
        }
    else:
        out = _reply(result, goal=goal, errand_id=errand_id, asking=asking)
    if not cleaned:
        # Cookies or storage that outlive the errand that set them are the
        # isolation failing, so it is said out loud rather than logged and
        # forgotten. Only present when it happened.
        out["cleanup_failed"] = True
    return json.dumps(out, default=str)


async def _release(driver: Any) -> bool:
    """Close *driver*'s browser context. ``False`` when something was left behind.

    A :class:`~life_graph.services.browser_errand.BrowserDriver` is not
    required to have a ``close`` — a fake in a test owns nothing, and the
    protocol is five methods on purpose. A driver that *does* own a context
    raises from ``close`` when it could not clean up, and that is a security
    outcome, not a tidy-up detail: it comes back as ``False`` so the reply can
    say so. It is never re-raised, because an errand's result is still the
    errand's result and the owner should hear both.
    """
    close = getattr(driver, "close", None)
    if close is None:
        return True
    try:
        out = close()
        if inspect.isawaitable(out):
            await out
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "the errand's browser context could not be closed (%s): %s", type(exc).__name__, exc
        )
        return False
    return True


def _reply(
    result: ErrandResult, *, goal: str, errand_id: str, asking: StepResult | None
) -> dict[str, Any]:
    """What the model is told. Page text only; no verdict for it to argue with."""
    from life_graph.services import browser_errand as be

    if asking is not None:
        return {
            "status": be.NEEDS_APPROVAL,
            "message": (
                f"Paused at step {asking.index + 1}: confirmation requested via phone notification."
            ),
            "step": asking.index,
            "goal": goal,
            "errand_id": errand_id,
        }
    if result.status == be.DONE:
        pages = result.pages
        return {
            "status": be.DONE,
            # The last page this errand read, already fenced as untrusted by
            # the engine (core/trust.py).
            "extracted_data": pages[-1] if pages else None,
            "steps_completed": len(result.steps),
            "goal": goal,
        }
    blocked = next((s for s in result.steps if s.status not in (be.DONE, be.SKIPPED)), None)
    return {
        "status": be.FAILED,
        "error": (blocked.detail if blocked is not None else None)
        or (", ".join(blocked.reasons) if blocked is not None else "the errand did not finish"),
        "step": blocked.index if blocked is not None else None,
        "goal": goal,
    }


__all__ = [
    "APPROVAL_SOURCE",
    "MAX_GOAL_CHARS",
    "MAX_STEPS",
    "MCP_PREFIX",
    "NO_BROWSER",
    "SANDBOX_UNAVAILABLE",
    "IsolatedBrowserDriver",
    "MCPBrowserDriver",
    "PlanError",
    "approval_notification",
    "browser_available",
    "browser_sandbox_available",
    "build_errand",
    "get_driver",
    "run_browser_errand",
    "set_driver_override",
]
