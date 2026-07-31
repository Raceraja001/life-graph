"""PushService — save/delete subscriptions, deliver via pywebpush, prune dead ones."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from life_graph.models.db import PushSubscription
from life_graph.services.webpush import PushService


class _FakeResult:
    """Minimal stand-in for a SQLAlchemy Result (see test_conversation_service.py)."""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Fake AsyncSession supporting the eq/in_ where-clauses PushService issues."""

    def __init__(self, store):
        self._store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def add(self, obj):
        self._store.append(obj)

    async def commit(self):
        pass

    async def execute(self, stmt):
        entity = stmt.table if hasattr(stmt, "table") else stmt.column_descriptions[0]["entity"]
        # `stmt.table` for Delete is a Table, not the mapped class — resolve via class name.
        if hasattr(stmt, "table"):
            rows = [o for o in self._store if type(o).__tablename__ == stmt.table.name]
        else:
            rows = [o for o in self._store if isinstance(o, entity)]

        where = stmt.whereclause
        if where is not None:
            col_name = getattr(where.left, "key", None)
            op_name = getattr(where.operator, "__name__", "")
            value = getattr(where.right, "value", None)
            if col_name is not None:
                if op_name == "in_op":
                    rows = [o for o in rows if getattr(o, col_name, None) in value]
                else:
                    rows = [o for o in rows if getattr(o, col_name, None) == value]

        if type(stmt).__name__ == "Delete":
            for row in list(rows):
                self._store.remove(row)
            return _FakeResult([])

        return _FakeResult(rows)


def _sub(endpoint="https://push.example/live", p256dh="p", auth="a"):
    return PushSubscription(
        tenant_id="t1", endpoint=endpoint, p256dh=p256dh, auth=auth, user_agent=None
    )


@pytest.mark.asyncio
async def test_save_subscription_upserts_no_dup_on_same_endpoint(monkeypatch):
    store = []

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr("life_graph.services.webpush.get_current_tenant_id", lambda: "t1")

    svc = PushService(session_factory)
    sub = {"endpoint": "https://push.example/a", "keys": {"p256dh": "p1", "auth": "a1"}}

    await svc.save_subscription(sub, user_agent="ua1")
    await svc.save_subscription(sub, user_agent="ua2")  # same endpoint again

    assert len(store) == 1
    assert store[0].tenant_id == "t1"
    assert store[0].p256dh == "p1"
    assert store[0].user_agent == "ua2"  # updated on second call


@pytest.mark.asyncio
async def test_delete_subscription_removes_by_endpoint(monkeypatch):
    store = [_sub(endpoint="https://push.example/a"), _sub(endpoint="https://push.example/b")]

    def session_factory():
        return _FakeSession(store)

    svc = PushService(session_factory)
    await svc.delete_subscription("https://push.example/a")

    assert [s.endpoint for s in store] == ["https://push.example/b"]


@pytest.mark.asyncio
async def test_send_to_tenant_noop_when_vapid_key_unset(monkeypatch):
    monkeypatch.setattr("life_graph.services.webpush.settings.vapid_private_key", "")

    def session_factory():
        raise AssertionError("should not open a session when VAPID key is unset")

    svc = PushService(session_factory)
    delivered = await svc.send_to_tenant("t1", "Title", "Body")

    assert delivered == 0


@pytest.mark.asyncio
async def test_send_prunes_dead_subscription(monkeypatch):
    # two subs; webpush raises 410 for the first -> it gets deleted, second delivers
    store = [
        _sub(endpoint="https://push.example/dead"),
        _sub(endpoint="https://push.example/live"),
    ]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr("life_graph.services.webpush.settings.vapid_private_key", "server-key")
    monkeypatch.setattr("life_graph.services.webpush.settings.vapid_subject", "mailto:a@b.com")

    with patch("life_graph.services.webpush.webpush") as mock_webpush:

        def side_effect(subscription_info, data, **kw):
            if "dead" in subscription_info["endpoint"]:
                from pywebpush import WebPushException

                resp = MagicMock()
                resp.status_code = 410
                raise WebPushException("gone", response=resp)

        mock_webpush.side_effect = side_effect

        svc = PushService(session_factory)
        delivered = await svc.send_to_tenant("t1", "T", "B")

    assert delivered == 1  # only the live one
    assert [s.endpoint for s in store] == ["https://push.example/live"]

    # verify the VAPID kwargs were passed through on the delivered call
    _, kwargs = mock_webpush.call_args_list[-1]
    assert kwargs["vapid_private_key"] == "server-key"
    assert kwargs["vapid_claims"] == {"sub": "mailto:a@b.com"}


@pytest.mark.asyncio
async def test_send_to_tenant_swallows_non_prune_errors(monkeypatch):
    """A non-404/410 WebPushException should be logged, not raised, and the
    subscription should NOT be pruned."""
    store = [_sub(endpoint="https://push.example/flaky")]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr("life_graph.services.webpush.settings.vapid_private_key", "server-key")

    with patch("life_graph.services.webpush.webpush") as mock_webpush:
        from pywebpush import WebPushException

        resp = MagicMock()
        resp.status_code = 500
        mock_webpush.side_effect = WebPushException("server error", response=resp)

        svc = PushService(session_factory)
        delivered = await svc.send_to_tenant("t1", "T", "B")

    assert delivered == 0
    assert len(store) == 1  # not pruned — transient error


@pytest.mark.asyncio
async def test_send_to_tenant_continues_after_transport_error(monkeypatch):
    """A non-WebPushException transport failure (ConnectionError, Timeout, DNS, ...) on one
    subscription must not abort delivery to the rest of the tenant's subscriptions."""
    store = [
        _sub(endpoint="https://push.example/flaky-transport"),
        _sub(endpoint="https://push.example/live"),
    ]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr("life_graph.services.webpush.settings.vapid_private_key", "server-key")

    with patch("life_graph.services.webpush.webpush") as mock_webpush:

        def side_effect(subscription_info, data, **kw):
            if "flaky-transport" in subscription_info["endpoint"]:
                raise ConnectionError("DNS resolution failed")

        mock_webpush.side_effect = side_effect

        svc = PushService(session_factory)
        delivered = await svc.send_to_tenant("t1", "T", "B")

    assert delivered == 1  # only the live one
    # transport error is not 404/410 — must NOT be pruned
    assert {s.endpoint for s in store} == {
        "https://push.example/flaky-transport",
        "https://push.example/live",
    }
