"""Chat commands for the Telegram bridge.

Split from :mod:`router` because the router's job is the security ordering —
private chat, binding, rate limit — and these run only after all of that has
passed. Every handler here is already inside a ``tenant_scope``.

Two rules shape this module:

* **Chat history lives on Telegram's servers indefinitely and is not
  end-to-end encrypted in ordinary cloud chats.** Replies therefore carry
  index lines rather than memory bodies, and everything outbound goes through
  ``redact_secrets``.
* **A tap in a chat app is not sufficient authority to run a dangerous
  action.** ``/approve`` is off unless ``LIFE_GRAPH_TELEGRAM_ALLOW_APPROVALS``
  is set, and even then it takes a second, explicit confirmation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.scoring.ranking import to_index
from life_graph.services.approvals import ApprovalAlreadyResolvedError, ApprovalService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

RECALL_LIMIT = 5
PENDING_LIMIT = 10

# How long an /approve request waits for its confirmation reply. The spec sets
# two minutes: long enough to read the detail, short enough that a phone left
# on a table cannot confirm an action the user has stopped thinking about.
CONFIRM_TTL_SECONDS = 120
_CONFIRM_KEY = "telegram:confirm:{chat_id}"

_APPROVALS_DISABLED = (
    "Approvals over chat are turned off.\n\n"
    "Open the dashboard to decide — a tap in a chat app isn't enough "
    "authority to run an action that was flagged as dangerous."
)


async def handle(
    chat_id: int,
    tenant_id: str,
    text: str,
    session: AsyncSession,
    reply,  # noqa: ANN001 - injected so the router owns transport and redaction
) -> None:
    """Dispatch one slash command. Never raises."""
    parts = text.split()
    command = parts[0].lower().lstrip("/").split("@")[0]
    argument = text[len(parts[0]) :].strip()

    try:
        if command == "recall":
            await _recall(chat_id, argument, reply)
        elif command == "pending":
            await _pending(chat_id, tenant_id, session, reply)
        elif command in {"approve", "reject"}:
            await _decide(chat_id, tenant_id, command, argument, session, reply)
        elif command in {"yes", "confirm"}:
            await _confirm(chat_id, tenant_id, session, reply)
        else:
            return  # router handles /help, /unlink and the unknown case
    except Exception:
        logger.warning("telegram: /%s failed", command, exc_info=True)
        await reply(chat_id, f"Something went wrong running /{command}. It's been logged.")


# ── /recall ───────────────────────────────────────────────────────


async def _recall(chat_id: int, query: str, reply) -> None:  # noqa: ANN001
    if not query:
        await reply(chat_id, "Usage: /recall <what you're looking for>")
        return

    from life_graph.api.dependencies import get_memory_manager, get_store

    manager = get_memory_manager()
    embedding = await manager._generate_embedding(query)
    if embedding is None:
        # Same honest failure the search endpoint gives when the embedding
        # provider is down — not "no results", which would be a lie.
        await reply(chat_id, "Search is unavailable right now (no embedding provider).")
        return

    store = get_store()
    try:
        hits = await store.hybrid_search(
            embedding=embedding,
            query_text=query,
            limit=RECALL_LIMIT,
            statuses=("active",),
        )
    except Exception:
        logger.warning("telegram: hybrid search failed, falling back to vector", exc_info=True)
        rows = await store.search_similar(
            embedding=embedding, limit=RECALL_LIMIT, include_embedding=False
        )
        hits = [(row, 0.0) for row in rows]

    if not hits:
        await reply(chat_id, f"Nothing found for “{query}”.")
        return

    await reply(chat_id, _render_index(query, hits))


def _render_index(query: str, hits: list[tuple[Any, float]]) -> str:
    """Render hits as progressive-disclosure index lines, not memory bodies."""
    flat: list[dict[str, Any]] = []
    for obj, score in hits:
        read = obj.get if isinstance(obj, dict) else (lambda k, _o=obj: getattr(_o, k, None))
        flat.append(
            {
                "id": read("id"),
                "content": read("content"),
                "tags": read("tags"),
                "status": read("status"),
                "final_score": score,
            }
        )

    lines = [f"Top {len(flat)} for “{query}”:", ""]
    for i, item in enumerate(to_index(flat), start=1):
        lines.append(f"{i}. {item['content']}")
        if item["tags"]:
            lines.append(f"   {' '.join('#' + t for t in item['tags'][:5])}")
        # The short id is enough to open the memory in the dashboard, and
        # keeps the full uuid out of a chat log.
        lines.append(f"   id {item['id'][:8]}")
    return "\n".join(lines)


# ── /pending ──────────────────────────────────────────────────────


async def _pending(chat_id: int, tenant_id: str, session: AsyncSession, reply) -> None:  # noqa: ANN001
    approvals = await ApprovalService(session).list_approvals(
        tenant_id, status="pending", limit=PENDING_LIMIT
    )
    if not approvals:
        await reply(chat_id, "Nothing waiting on you.")
        return

    lines = [f"{len(approvals)} waiting:", ""]
    for appr in approvals:
        risk = (appr.get("payload") or {}).get("risk_level")
        suffix = f" [{risk}]" if risk else ""
        lines.append(f"• {appr['title']}{suffix}")
        lines.append(f"   {appr['kind']} · id {appr['id'][:8]}")

    if settings.telegram_allow_approvals:
        lines += ["", "Decide with /approve <id> or /reject <id>."]
    else:
        lines += ["", "Open the dashboard to decide on these."]
    await reply(chat_id, "\n".join(lines))


# ── /approve and /reject ──────────────────────────────────────────


async def _decide(
    chat_id: int,
    tenant_id: str,
    command: str,
    argument: str,
    session: AsyncSession,
    reply,  # noqa: ANN001
) -> None:
    if not settings.telegram_allow_approvals:
        await reply(chat_id, _APPROVALS_DISABLED)
        return

    prefix = argument.split()[0] if argument else ""
    if not prefix:
        await reply(chat_id, f"Usage: /{command} <id>  (the short id from /pending)")
        return

    match = await _match_pending(tenant_id, prefix, session)
    if match is None:
        await reply(chat_id, f"No pending item starting with {prefix}. Try /pending.")
        return
    if match == "ambiguous":
        await reply(chat_id, f"More than one pending item starts with {prefix}. Use more of it.")
        return

    await _remember_confirmation(chat_id, command, match["id"])
    verb = "Approve" if command == "approve" else "Reject"
    await reply(
        chat_id,
        f"{verb} this?\n\n{match['title']}\n{match['detail'] or ''}\n\n"
        f"Reply /yes within {CONFIRM_TTL_SECONDS // 60} minutes to go ahead. "
        f"Anything else cancels it.",
    )


async def _confirm(chat_id: int, tenant_id: str, session: AsyncSession, reply) -> None:  # noqa: ANN001
    pending = await _take_confirmation(chat_id)
    if pending is None:
        await reply(chat_id, "Nothing waiting to be confirmed.")
        return
    if not settings.telegram_allow_approvals:
        # The flag could have been turned off between the request and the
        # confirmation. Fail closed.
        await reply(chat_id, _APPROVALS_DISABLED)
        return

    command, approval_id = pending
    service = ApprovalService(session)
    try:
        result = await service.resolve(
            tenant_id,
            approval_id,
            "approve" if command == "approve" else "reject",
            note="Decided over Telegram",
            # Recorded so the audit trail can tell a chat decision from a
            # dashboard one — the spec asks for exactly this.
            resolved_by="telegram",
        )
    except LookupError:
        await reply(chat_id, "That item is gone. Try /pending.")
        return
    except ApprovalAlreadyResolvedError as exc:
        await reply(chat_id, f"Already {exc.args[0] if exc.args else 'resolved'}.")
        return

    await session.commit()
    await reply(chat_id, f"{result['status'].capitalize()}: {result['title']}")


async def _match_pending(tenant_id: str, prefix: str, session: AsyncSession):
    """Resolve a short id prefix to one pending approval for this tenant."""
    approvals = await ApprovalService(session).list_approvals(
        tenant_id, status="pending", limit=PENDING_LIMIT
    )
    matches = [a for a in approvals if a["id"].startswith(prefix)]
    if not matches:
        return None
    if len(matches) > 1:
        return "ambiguous"
    return matches[0]


# ── Confirmation state ────────────────────────────────────────────


async def _remember_confirmation(chat_id: int, command: str, approval_id: str) -> None:
    """Park a pending decision in Redis with a TTL.

    Redis rather than a module dict because the poller may be restarted or
    replaced between the request and the confirmation, and an expiry we get
    for free is better than one we have to sweep.
    """
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return
    await redis.set(
        _CONFIRM_KEY.format(chat_id=chat_id),
        f"{command}:{approval_id}",
        ex=CONFIRM_TTL_SECONDS,
    )


async def _take_confirmation(chat_id: int) -> tuple[str, str] | None:
    """Read and delete the parked decision — single use, like a pairing code."""
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return None
    key = _CONFIRM_KEY.format(chat_id=chat_id)
    raw = await redis.get(key)
    if not raw:
        return None
    await redis.delete(key)
    value = raw.decode() if isinstance(raw, bytes) else str(raw)
    command, _, approval_id = value.partition(":")
    if not approval_id:
        return None
    return command, approval_id
