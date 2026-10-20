"""Jobs 5 and 7 without the database: the check-in's periods and wording, the
app-health lines, and urgent watcher events going to the phone at once."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.services import app_health, money_checkin


def test_periods_compare_the_same_days_of_last_month():
    (s, e), (ls, le) = money_checkin.periods(date(2026, 10, 20))
    assert (s, e) == (date(2026, 10, 1), date(2026, 10, 21))
    assert (ls, le) == (date(2026, 9, 1), date(2026, 9, 21))
    # The 31st against a 30-day month takes all of it; January against December.
    assert money_checkin.periods(date(2026, 3, 31))[1] == (date(2026, 2, 1), date(2026, 3, 1))
    assert money_checkin.periods(date(2026, 1, 5))[1] == (date(2025, 12, 1), date(2025, 12, 6))


def _checkin(**over):
    base = {
        "period": {"start": "2026-10-01", "end": "2026-10-20"},
        "transactions": 12,
        "total_spent": 18500.0,
        "last_month_total": 20000.0,
        "total_change_percent": -8,
        "categories": [
            {
                "category": "food",
                "spent": 9000.0,
                "last_month": 6000.0,
                "change": 3000.0,
                "change_percent": 50,
                "budget": 8000.0,
                "percent_of_budget": 112,
            },
            {
                "category": "travel",
                "spent": 1500.0,
                "last_month": 6000.0,
                "change": -4500.0,
                "change_percent": -75,
                "budget": None,
                "percent_of_budget": None,
            },
            {
                "category": "shopping",
                "spent": 8000.0,
                "last_month": 8000.0,
                "change": 0.0,
                "change_percent": 0,
                "budget": 10000.0,
                "percent_of_budget": 80,
            },
        ],
        "over_budget": ["food"],
        "near_budget": ["shopping"],
        "biggest_changes": ["travel", "food"],
        "top_merchants": [{"merchant": "Swiggy", "spent": 4200.0}],
    }
    return {**base, **over}


def test_lines_with_amounts_for_the_owner():
    assert money_checkin.lines(_checkin(), amounts=True) == [
        "Month to date (01–20): spent ₹18,500, 8% less than the same days last month.",
        "Over budget: food 112% (₹9,000 of ₹8,000).",
        "Near budget: shopping 80% (₹8,000 of ₹10,000).",
        "Biggest changes: travel down 75% (−₹4,500), food up 50% (+₹3,000).",
        "Top merchants: Swiggy ₹4,200.",
    ]


def test_cloud_lines_carry_no_amounts_or_merchants():
    out = money_checkin.lines(_checkin(), amounts=False)
    assert out[0] == "Month to date (01–20): spending is 8% less than the same days last month."
    assert "Over budget: food 112%." in out
    joined = " ".join(out)
    assert "₹" not in joined and "Swiggy" not in joined and "9,000" not in joined


def test_nothing_imported_is_silence_and_new_categories_say_so():
    empty = _checkin(transactions=0, last_month_total=0.0)
    assert money_checkin.lines(empty, amounts=True) == []
    c = _checkin(total_change_percent=None, biggest_changes=["travel"])
    c["categories"][1]["change_percent"] = None
    out = money_checkin.lines(c, amounts=False)
    assert "no spending last month to compare with" in out[0]
    assert "Biggest changes: travel new this month." in out


def test_app_health_lines_put_problems_in_words():
    apps = [
        {
            "project": "uzhavu",
            "status": "down",
            "http_status": 502,
            "error": None,
            "cert_days_left": 5,
            "backup": "failing",
        },
        {
            "project": "his",
            "status": "up",
            "http_status": 200,
            "error": None,
            "cert_days_left": 60,
            "backup": "ok",
        },
    ]
    assert app_health.lines(apps) == [
        "uzhavu: down, HTTP 502, TLS expires in 5 days, backup failing",
        "his: up",
    ]
    assert app_health._status({}, True) == "not checked yet"
    assert app_health._status({"last": {"ok": False}}, True) == "failing"
    assert app_health._status({"down": True}, True) == "down"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("watcher", "severity", "urgent"),
    [
        ("app_uptime", "important", True),
        ("server_health", "important", True),
        ("dependency", "important", False),
        ("app_uptime", "info", False),
    ],
)
async def test_urgent_watcher_events_go_to_the_phone_now(watcher, severity, urgent):
    from life_graph.watchers.notification_engine import NotificationEngine

    engine = NotificationEngine.__new__(NotificationEngine)
    engine._session_factory = None
    event = {
        "id": "x",
        "severity": severity,
        "title": "shop is down",
        "watcher_name": watcher,
        "details": {"url": "https://shop/health"},
    }
    with (
        patch.object(NotificationEngine, "_queue_event", AsyncMock()) as queue,
        patch.object(NotificationEngine, "_send_urgent", AsyncMock(return_value=True)) as push,
    ):
        await engine.route_event("t", event)
    assert push.called is urgent
    if urgent:
        assert queue.call_args.kwargs["status"] == "sent"


@pytest.mark.asyncio
async def test_send_urgent_uses_push_and_telegram():
    from life_graph.watchers.notification_engine import NotificationEngine

    engine = NotificationEngine.__new__(NotificationEngine)
    engine._session_factory = None
    push = AsyncMock(return_value=0)
    tg = AsyncMock(return_value=True)
    with (
        patch("life_graph.services.webpush.PushService") as push_cls,
        patch("life_graph.watchers.channels.telegram_channel.TelegramChannel") as tg_cls,
    ):
        push_cls.return_value.send_to_tenant = push
        tg_cls.return_value.send = tg
        sent = await engine._send_urgent(
            "t", {"title": "shop is down", "details": {"url": "https://shop/health"}}
        )
    assert sent is True  # Telegram reached a chat though no device took the push
    assert push.call_args.args[:3] == ("t", "shop is down", "https://shop/health")
    assert tg.call_args.kwargs["severity"] == "important"
