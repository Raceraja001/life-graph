"""Jarvis, the lead: which model and tools a request gets.

docs/design/11_persona_roster_plan.md. Jarvis is the only persona the owner
talks to. Its model is picked per request, by the owner's rule (2026-10-20):
personal data is handled by the local model; other work may use the free or
subscription cloud models, with personal details hidden.

* **personal** — the request touches the owner's own data (calendar, mail,
  money, documents, memories, family, health) or carries a personal detail the
  scrub recognises, or an earlier turn of the conversation did. It runs on the
  local model, pinned so it cannot fail over to a cloud one, with every tool
  except the ones that hand work to a cloud worker.
* **general** — everything else. It runs on Jarvis's configured model, and if
  that model leaves the machine the personal tools are not offered at all, the
  message and history are scrubbed, and no connector context is added. A
  personal question misjudged as general therefore gets "I can't see that from
  here", never the data.

The owner can say which: a message starting ``personal:`` runs locally,
``cloud:`` runs on the configured model (the scrub and the tool cut still
apply).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from life_graph.config import settings
from life_graph.connectors.locality import model_is_local
from life_graph.core.personal_run import PERSONAL_INPUT_KEY

LEAD = "jarvis"

# Tools that read or change the owner's own data, or hand work to personas
# that do (delegation); never offered to a model that leaves the machine.
PERSONAL_TOOLS = frozenset(
    {
        "memory_search",
        "memory_save",
        "memory_forget",
        "memory_about",
        "reminder_set",
        "ask_schedule",
        "approvals_waiting",
        "calendar_events",
        "calendar_next",
        "email_waiting",
        "email_search",
        "email_read",
        "contact_lookup",
        "code_inbox",
        "bills_due",
        "tasks_due",
        "documents_expiring",
        "spending_summary",
        "money_checkin",
        "app_health",
        "watch_page",
        "list_page_monitors",
        "make_study_cards",
        "study_cards_due",
        "study_progress",
        "draft_study_cards",
        "invoices_status",
        "delegate_to_persona",
    }
)

# What a temporary chat may not use (docs/specs/web-chat-wave1.md, F5): it
# teaches memory nothing and leaves nothing behind — no saves, no forgets, no
# reminders or schedules, no files, and no hand-off to a persona that could.
TEMPORARY_BLOCKED_TOOLS = frozenset(
    {
        "memory_save",
        "memory_forget",
        "reminder_set",
        "ask_schedule",
        "make_study_cards",
        "draft_study_cards",
        "watch_page",
        "delegate_to_persona",
        "file_write",
        "code_edit",
    }
)
TEMPORARY_REASON = "temporary chat: stays on your PC"
# A task delegate_to_persona started from a personal run (core/personal_run.py).
DELEGATED_REASON = "handed on from a personal conversation: stays on your PC"

# Tools that send work to a cloud worker (services/workers.py): fine for
# general work, not from a personal conversation, whose query could carry
# details the scrub does not know (names, places).
CLOUD_WORKER_TOOLS = frozenset({"research_web"})

_DOMAIN = (
    r"bills?|calendar|schedule|agenda|meetings?|appointments?|reminders?|e-?mails?|mails?|inbox"
    r"|money|spend\w*|expens\w*|budget|salary|bank|accounts?|cards?|loans?|emi|tax(?:es)?"
    r"|documents?|passport|licen[cs]e|polic(?:y|ies)|insurance|health|doctor|medicines?"
    r"|family|wife|husband|son|daughter|kids?|children|mother|father|mom|dad|amma|appa"
    r"|notes?|memor(?:y|ies)|tasks?|todos?|invoices?|clients?|contacts?|subscriptions?"
    r"|study|flash ?cards|exams?"
    r"|codes?|passwords?|pins?|lockers?|address|birthday|anniversary|car|bike|house|home"
)
_PERSONAL = re.compile(
    rf"\b(?:my|our|mine)\s+(?:\w+\s+)?(?:{_DOMAIN})\b"
    r"|\b(?:calendar|inbox|bills?|spending|study cards|flash ?cards|invoices?"
    r"|appointments?|reminders?)\b"
    r"|\b(?:remember|recall|remind me|what did i|did i|have i|i told you|about me)\b"
    # Asking for something to be kept: memory_save is a personal tool, and the
    # phone's extractor leaves these to it (capture_saved_by_tool_surfaces), so
    # one routed to the cloud model was not saved by anything (review 2026-10-24).
    r"|\b(?:don'?t forget|do not forget|never forget|keep in mind|make a note"
    r"|note (?:this|that|it|down)|jot\b|write (?:this|that|it) down|save (?:this|that|it))\b"
    # "what's my locker code?": a question about the owner's own anything
    # (went to the cloud model, which cannot see memories, 2026-10-23).
    r"|\b(?:what|where|when|which|who|how)(?:'s|\s+is|\s+are|\s+was|\s+were|\s+do)\s+my\b",
    re.IGNORECASE,
)
_SWITCH = re.compile(r"^\s*(personal|private|local|cloud)\s*:\s*", re.IGNORECASE)


@dataclass
class Route:
    kind: str  # personal | general
    reason: str
    model: str | None
    tools: list[str] | None
    message: str
    history: list[dict[str, Any]] = field(default_factory=list)
    # Models the run may fail over to; None = the usual chain.
    pinned: list[str] | None = None

    def as_record(self) -> dict[str, Any]:
        return {"kind": self.kind, "reason": self.reason, "model": self.model}


def is_personal(text: str) -> str | None:
    """Why *text* is personal, or None. Errs towards personal: a wrong
    "personal" costs a weaker model, a wrong "general" a refusal."""
    from life_graph.services.scrub import scrub

    if not text:
        return None
    m = _PERSONAL.search(text)
    if m:
        return f"mentions {m.group(0).strip().lower()!r}"
    if scrub(text) != text:
        return "carries a personal detail"
    return None


def local_model() -> str:
    from life_graph.connectors.locality import model_is_local

    if settings.lead_local_model:
        return settings.lead_local_model
    if model_is_local(settings.agent_llm_model):
        return settings.agent_llm_model
    return "ollama_chat/qwen3:14b"


def route(persona: dict[str, Any], input_data: dict[str, Any]) -> Route:
    """The model, tools and (possibly scrubbed) conversation for one request."""
    from life_graph.connectors.locality import model_is_local, run_is_local
    from life_graph.services.scrub import scrub

    message = str(input_data.get("message") or "")
    history = list(input_data.get("history") or [])
    tools = persona.get("allowed_tools")
    configured = persona.get("model")

    switch = _SWITCH.match(message)
    if switch:
        message = message[switch.end() :]
    wanted = switch.group(1).lower() if switch else None

    if input_data.get("temporary"):
        # Local whatever the message says: "cloud:" does not lift it.
        reason = TEMPORARY_REASON
    elif input_data.get(PERSONAL_INPUT_KEY):
        # Nor here: the brief came out of a personal conversation.
        reason = DELEGATED_REASON
    elif wanted in ("personal", "private", "local"):
        reason = "you asked for local"
    elif wanted == "cloud":
        reason = None
    else:
        reason = is_personal(message) or next(
            (
                f"an earlier turn {why}"
                for h in history
                if h.get("role") == "user" and (why := is_personal(str(h.get("content") or "")))
            ),
            None,
        )

    if run_is_local(configured):
        # Already local: nothing leaves the machine whichever it is.
        kind = "personal" if reason else "general"
        return Route(kind, reason or "local model", configured, tools, message, history)

    if reason:
        model = local_model()
        pinned = [model, *(m for m in settings.llm_fallback_chain_list if model_is_local(m))]
        kept = None if tools is None else [t for t in tools if t not in CLOUD_WORKER_TOOLS]
        return Route("personal", reason, model, kept, message, history, pinned=pinned)

    cut = None if tools is None else [t for t in tools if t not in PERSONAL_TOOLS]
    clean = [{**h, "content": scrub(str(h.get("content") or ""))} for h in history]
    return Route(
        "general",
        "you asked for cloud" if wanted == "cloud" else "nothing personal in it",
        configured,
        cut,
        scrub(message),
        clean,
    )


class LocalOnlyRefusedError(RuntimeError):
    """A personal task would have to run on a model that leaves the machine."""


def local_only_refusal(agent_name: str, model: str | None) -> str:
    """What the delegating persona (and, through it, the owner) is told."""
    return (
        f"{agent_name} runs on {model or 'an unknown model'}, which is not a local"
        " model, and this task comes from a personal conversation, which stays on"
        f" your PC. Do it without {agent_name}, or put {agent_name} on a local model."
    )


def personal_pin(agent_name: str, model: str | None) -> list[str]:
    """The models a non-Jarvis task delegated from a personal run may use.

    The persona's own model, if it is local, then the local models of the
    fallback chain -- the same pin as Jarvis's personal route (route()), so a
    failure cannot fail over to a cloud model. Raises
    :class:`LocalOnlyRefusedError` when the persona's model is not local:
    the task fails with that message rather than running on the cloud.
    Jarvis itself needs none of this: route() sends it to its local model.
    """
    if not model or not model_is_local(model):
        raise LocalOnlyRefusedError(local_only_refusal(agent_name, model))
    chain = settings.llm_fallback_chain_list
    return [model, *(m for m in chain if model_is_local(m) and m != model)]


# Said to the model when it runs without the personal tools.
GENERAL_NOTE = (
    "## This conversation\nYou are running on a cloud model, so the user's own data"
    " (calendar, mail, money, documents, memories, contacts, study cards) is not"
    " available here. If the request needs it, say so in one line and tell the user"
    " to ask again starting with 'personal:'."
)


def resolve_run_tools(
    persona: dict[str, Any] | None,
    override: list[str] | None = None,
    *,
    cloud: bool,
    temporary: bool,
    registry: Any = None,
) -> list[str] | None:
    """The tool names one agent run may use; ``None`` means the whole registry.

    The one place this is decided (audit M14). ``kernel/process_manager.py``
    (chat and kernel tasks) and ``drivers/local.py`` (dispatched dev tasks)
    each had a copy, and the driver's -- which said it mirrored the other --
    applied neither cut below.

    * *override*, when not None, REPLACES the persona's ``allowed_tools``
      (scheduled action-role runs are forced onto a read-only set this way).
    * *cloud*: the run's model leaves the machine, so :data:`PERSONAL_TOOLS`
      are cut. Neither an override nor "all tools" (None) brings them back.
    * *temporary*: a temporary chat leaves nothing behind, so
      :data:`TEMPORARY_BLOCKED_TOOLS` are cut the same way.

    A cut expands "all tools" to every name in *registry* (default: the live
    tool registry; read only then) minus the cut, so the result is then
    always a list.
    """
    allow = override if override is not None else (persona or {}).get("allowed_tools")
    blocked: frozenset[str] = frozenset()
    if cloud:
        blocked |= PERSONAL_TOOLS
    if temporary:
        blocked |= TEMPORARY_BLOCKED_TOOLS
    if not blocked:
        return None if allow is None else list(allow)
    if allow is None:
        if registry is None:
            from life_graph.tools.registry import registry
        allow = registry.tool_names
    return [t for t in allow if t not in blocked]
