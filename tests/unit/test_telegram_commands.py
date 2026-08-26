"""Unit tests for Telegram chat commands.

No DB and no network: the approval service and Redis are faked, so these
assert the decisions — what is disclosed in a chat log, and how much
authority a chat message carries — rather than storage behaviour.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.tenant import (
    get_current_tenant_id,
    has_tenant_context,
    set_tenant_context,
    tenant_scope,
)
from life_graph.integrations.telegram import commands as cmds

TENANT = "t1"
CHAT = 4242


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def get(self, key):
        return self.data.get(key)

    async def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("life_graph.storage.redis.get_redis", lambda: fake)
    return fake


@pytest.fixture
def sent():
    out: list[tuple[int, str]] = []

    async def reply(chat_id, text):
        out.append((chat_id, text))

    reply.sent = out  # type: ignore[attr-defined]
    return reply


def _approvals(monkeypatch, items, resolver=None):
    """Install a fake ApprovalService returning ``items``."""
    calls: list[dict] = []

    class FakeService:
        def __init__(self, session):
            pass

        async def list_approvals(self, tenant_id, status="pending", limit=100):
            return [a for a in items if a["tenant"] == tenant_id]

        async def resolve(self, tenant_id, approval_id, decision, note=None, resolved_by=None):
            calls.append(
                {
                    "tenant_id": tenant_id,
                    "id": approval_id,
                    "decision": decision,
                    "note": note,
                    "resolved_by": resolved_by,
                }
            )
            if resolver:
                return resolver(approval_id, decision)
            return {"status": "approved" if decision == "approve" else "rejected", "title": "T"}

    monkeypatch.setattr(cmds, "ApprovalService", FakeService)
    return calls


def _appr(id_, title="Delete stale memories", kind="archive", risk=None):
    return {
        "id": id_,
        "tenant": TENANT,
        "title": title,
        "kind": kind,
        "detail": "detail here",
        "payload": {"risk_level": risk} if risk else {},
    }


class FakeSession:
    async def commit(self):
        pass


# ── tenant_scope ──────────────────────────────────────────


def _in_clean_context(fn):
    """Run ``fn`` in a fresh thread and return its result.

    A thread starts with an empty context, so these tests neither inherit a
    tenant from whatever ran before them nor leave one behind. That matters
    twice over: contextvars set in a pytest test persist for the rest of the
    session, and several unrelated suites assert on the *absence* of a tenant
    context.
    """
    import threading

    box: dict = {}

    def runner():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            box["error"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def test_tenant_scope_restores_the_previous_tenant():
    """The poller handles many chats in one task; a leak would cross tenants."""

    def probe():
        set_tenant_context("outer", "u")
        with tenant_scope("inner", "telegram"):
            inside = get_current_tenant_id()
        return inside, get_current_tenant_id()

    assert _in_clean_context(probe) == ("inner", "outer")


def test_tenant_scope_restores_even_when_the_body_raises():
    def probe():
        set_tenant_context("outer", "u")
        try:
            with tenant_scope("inner"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        return get_current_tenant_id()

    assert _in_clean_context(probe) == "outer"


def test_tenant_scope_leaves_no_context_where_there_was_none():
    """A handler must not make the *absence* of a tenant look like a tenant.

    The storage layer treats a missing tenant very differently from a wrong
    one — it raises rather than querying — so restoring to "unset" is the
    behaviour that matters here, not merely restoring to some value.
    """

    def probe():
        before = has_tenant_context()
        with tenant_scope("inner"):
            inside = get_current_tenant_id()
        return before, inside, has_tenant_context()

    assert _in_clean_context(probe) == (False, "inner", False)


# ── /recall ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recall_without_a_query_explains_usage(sent):
    await cmds.handle(CHAT, TENANT, "/recall", FakeSession(), sent)
    assert "Usage: /recall" in sent.sent[0][1]


def test_render_index_uses_short_ids_and_truncated_content():
    """Index lines, not memory bodies — chat history is retained by Telegram."""
    row = SimpleNamespace(
        id="0f6c4b1e-1111-4000-8000-000000000000",
        content="x" * 5000,
        tags=["work", "deploy"],
        status="active",
    )
    text = cmds._render_index("deploy", [(row, 0.9)])
    assert "id 0f6c4b1e" in text
    assert "0f6c4b1e-1111-4000-8000-000000000000" not in text
    assert "#work" in text
    assert len(text) < 2000


def test_render_index_numbers_every_hit():
    rows = [
        SimpleNamespace(id=f"{i}0000000-0000-4000-8000-000000000000", content=f"m{i}", tags=[])
        for i in range(3)
    ]
    text = cmds._render_index("q", [(r, 0.5) for r in rows])
    assert "1. m0" in text and "3. m2" in text


# ── /pending ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pending_says_so_plainly_when_empty(monkeypatch, sent):
    _approvals(monkeypatch, [])
    await cmds.handle(CHAT, TENANT, "/pending", FakeSession(), sent)
    assert sent.sent[0][1] == "Nothing waiting on you."


@pytest.mark.asyncio
async def test_pending_lists_titles_short_ids_and_risk(monkeypatch, sent):
    _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000", risk="high")])
    await cmds.handle(CHAT, TENANT, "/pending", FakeSession(), sent)
    body = sent.sent[0][1]
    assert "Delete stale memories" in body
    assert "id abcd1234" in body
    assert "[high]" in body


@pytest.mark.asyncio
async def test_pending_points_at_the_dashboard_when_approvals_are_off(monkeypatch, sent):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", False)
    _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/pending", FakeSession(), sent)
    assert "dashboard" in sent.sent[0][1]


# ── /approve — the authority boundary ─────────────────────


@pytest.mark.asyncio
async def test_approve_is_refused_when_the_flag_is_off(monkeypatch, sent, redis):
    """Default-off: fail-closed autonomy is a charter invariant."""
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", False)
    calls = _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/approve abcd1234", FakeSession(), sent)
    assert "turned off" in sent.sent[0][1]
    assert calls == []
    assert redis.data == {}


@pytest.mark.asyncio
async def test_approve_asks_for_confirmation_and_does_not_resolve(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    calls = _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/approve abcd1234", FakeSession(), sent)
    assert "/yes" in sent.sent[0][1]
    assert calls == [], "nothing may be resolved before the confirmation"
    assert redis.data


@pytest.mark.asyncio
async def test_confirmation_resolves_and_records_the_chat_surface(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    calls = _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/approve abcd1234", FakeSession(), sent)
    await cmds.handle(CHAT, TENANT, "/yes", FakeSession(), sent)
    assert len(calls) == 1
    assert calls[0]["decision"] == "approve"
    # The audit trail must distinguish a chat decision from a dashboard one.
    assert calls[0]["resolved_by"] == "telegram"
    assert calls[0]["tenant_id"] == TENANT


@pytest.mark.asyncio
async def test_a_confirmation_can_only_be_spent_once(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    calls = _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/approve abcd1234", FakeSession(), sent)
    await cmds.handle(CHAT, TENANT, "/yes", FakeSession(), sent)
    await cmds.handle(CHAT, TENANT, "/yes", FakeSession(), sent)
    assert len(calls) == 1
    assert "Nothing waiting to be confirmed." in sent.sent[-1][1]


@pytest.mark.asyncio
async def test_turning_the_flag_off_mid_flow_fails_closed(monkeypatch, sent, redis):
    """A parked confirmation must not outlive the permission that created it."""
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    calls = _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/approve abcd1234", FakeSession(), sent)
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", False)
    await cmds.handle(CHAT, TENANT, "/yes", FakeSession(), sent)
    assert calls == []
    assert "turned off" in sent.sent[-1][1]


@pytest.mark.asyncio
async def test_yes_alone_confirms_nothing(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    calls = _approvals(monkeypatch, [])
    await cmds.handle(CHAT, TENANT, "/yes", FakeSession(), sent)
    assert calls == []
    assert "Nothing waiting" in sent.sent[0][1]


@pytest.mark.asyncio
async def test_unknown_id_prefix_is_refused(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/approve zzzz", FakeSession(), sent)
    assert "No pending item" in sent.sent[0][1]
    assert redis.data == {}


@pytest.mark.asyncio
async def test_ambiguous_id_prefix_is_refused_rather_than_guessed(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    _approvals(
        monkeypatch,
        [
            _appr("abcd1111-0000-4000-8000-000000000000"),
            _appr("abcd2222-0000-4000-8000-000000000000"),
        ],
    )
    await cmds.handle(CHAT, TENANT, "/approve abcd", FakeSession(), sent)
    assert "More than one" in sent.sent[0][1]
    assert redis.data == {}


@pytest.mark.asyncio
async def test_another_tenants_approval_is_not_matchable(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    other = _appr("abcd1234-0000-4000-8000-000000000000")
    other["tenant"] = "someone_else"
    _approvals(monkeypatch, [other])
    await cmds.handle(CHAT, TENANT, "/approve abcd1234", FakeSession(), sent)
    assert "No pending item" in sent.sent[0][1]


@pytest.mark.asyncio
async def test_reject_takes_the_same_confirmation_path(monkeypatch, sent, redis):
    monkeypatch.setattr(cmds.settings, "telegram_allow_approvals", True)
    calls = _approvals(monkeypatch, [_appr("abcd1234-0000-4000-8000-000000000000")])
    await cmds.handle(CHAT, TENANT, "/reject abcd1234", FakeSession(), sent)
    assert calls == []
    await cmds.handle(CHAT, TENANT, "/yes", FakeSession(), sent)
    assert calls[0]["decision"] == "reject"


@pytest.mark.asyncio
async def test_a_failing_handler_replies_instead_of_raising(monkeypatch, sent):
    """The poller advances its offset on return; a raise would replay forever."""

    class Boom:
        def __init__(self, session):
            pass

        async def list_approvals(self, *a, **k):
            raise RuntimeError("db down")

    monkeypatch.setattr(cmds, "ApprovalService", Boom)
    await cmds.handle(CHAT, TENANT, "/pending", FakeSession(), sent)
    assert "went wrong" in sent.sent[0][1]
