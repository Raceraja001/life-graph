"""Which promises to nudge now (services/nudge_pick.py, web-chat-wave1 T2.1)."""

from datetime import UTC, datetime, timedelta

from life_graph.services.nudge_pick import in_quiet_hours, pick

NOW = datetime(2026, 10, 27, 11, 0, tzinfo=UTC)


def _c(i, *, starts=-1, due=1, state="open", snoozed=None):
    return {
        "id": f"n{i}",
        "due_from": NOW + timedelta(hours=starts),
        "due_by": NOW + timedelta(days=due),
        "snoozed_until": snoozed,
        "state": state,
    }


def test_only_open_started_unsnoozed_ones_soonest_deadline_first():
    got = pick(
        [
            _c(1, due=3),
            _c(2, due=1),
            _c(3, starts=2),  # not yet
            _c(4, state="done"),
            _c(5, snoozed=NOW + timedelta(hours=1)),
            _c(6, due=-1),  # overdue still counts
        ],
        NOW,
        sent_today=0,
    )
    assert [c["id"] for c in got] == ["n6", "n2", "n1"]


def test_a_few_a_day_at_most():
    many = [_c(i) for i in range(6)]
    assert len(pick(many, NOW, sent_today=0)) == 3
    assert len(pick(many, NOW, sent_today=2)) == 1
    assert pick(many, NOW, sent_today=5) == []  # never negative


def test_none_in_quiet_hours_which_wrap_midnight():
    late = NOW.replace(hour=23)
    early = NOW.replace(hour=6, minute=59)
    assert pick([_c(1)], late.replace(hour=23), sent_today=0) == []
    assert pick([_c(1)], early, sent_today=0) == []
    assert in_quiet_hours(NOW.replace(hour=7), (22, 7)) is False
    assert in_quiet_hours(NOW.replace(hour=13), (12, 14)) is True
    assert in_quiet_hours(NOW, (0, 0)) is False
