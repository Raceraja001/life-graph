"""Suggested predictions: capture → suggestion → accept/dismiss → resolve.

Also covers the outcome resolver's ask-once rule and question expiry, which
decide whether an unanswered prediction ever leaves ``pending``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.core.events import EventType
from life_graph.models.db import InterviewQuestion, Prediction
from life_graph.services.capture_processors import CaptureProcessors
from life_graph.services.judgment import SUGGESTED, JudgmentService
from life_graph.services.outcome_resolver import QUESTION_TTL_DAYS, OutcomeResolver


class _Bus:
    def __init__(self):
        self.events = []

    async def emit(self, event_type, payload):
        self.events.append((event_type, payload))


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _Session:
    """Answers each execute() with the next queued row list."""

    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result(self.results.pop(0) if self.results else [])

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        pass


def _prediction(outcome="pending", **kw):
    return Prediction(
        id=kw.pop("id", uuid.uuid4()),
        tenant_id="t1",
        statement=kw.pop("statement", "The migration lands by Friday"),
        confidence=kw.pop("confidence", 0.8),
        domain_tags=[],
        outcome=outcome,
        **kw,
    )


# ── JudgmentService ──────────────────────────────────────────


async def test_suggested_prediction_is_stored_quietly():
    bus = _Bus()
    session = _Session()
    p = await JudgmentService(session, bus).create_prediction(
        tenant_id="t1", statement="Client signs", confidence=0.7, suggested=True
    )
    assert p.outcome == SUGGESTED
    assert session.added == [p]
    assert bus.events == []  # not a prediction until the user confirms it


async def test_regular_prediction_still_announces_itself():
    bus = _Bus()
    p = await JudgmentService(_Session(), bus).create_prediction(
        tenant_id="t1", statement="Client signs", confidence=0.3
    )
    assert (p.outcome, p.statement, p.confidence) == ("pending", "NOT: Client signs", 0.7)
    assert [e[0] for e in bus.events] == [EventType.PREDICTION_CREATED]


async def test_accept_confirms_and_applies_corrections():
    bus = _Bus()
    p = _prediction(SUGGESTED)
    due = datetime(2026, 10, 1, tzinfo=UTC)
    accepted = await JudgmentService(_Session([p]), bus).accept_suggestion(
        "t1",
        p.id,
        statement="Migration lands by 1 Oct",
        confidence=1.4,
        resolve_by=due,
        domain_tags=["infra"],
    )
    assert accepted.outcome == "pending"
    assert accepted.statement == "Migration lands by 1 Oct"
    assert accepted.confidence == 0.99  # clamped
    assert (accepted.resolve_by, accepted.domain_tags) == (due, ["infra"])
    assert bus.events[0][0] == EventType.PREDICTION_CREATED
    assert bus.events[0][1]["statement"] == "Migration lands by 1 Oct"


@pytest.mark.parametrize("outcome", ["pending", "correct"])
async def test_accept_and_dismiss_only_touch_suggestions(outcome):
    p = _prediction(outcome)
    svc = JudgmentService(_Session([p], [p]))
    with pytest.raises(ValueError, match="not a suggestion"):
        await svc.accept_suggestion("t1", p.id)
    with pytest.raises(ValueError, match="not a suggestion"):
        await svc.dismiss_suggestion("t1", p.id)


async def test_dismiss_deletes_the_suggestion():
    p = _prediction(SUGGESTED)
    session = _Session([p])
    await JudgmentService(session).dismiss_suggestion("t1", p.id)
    assert session.deleted == [p]


async def test_missing_prediction_is_not_found():
    with pytest.raises(ValueError, match="not found"):
        await JudgmentService(_Session([])).accept_suggestion("t1", uuid.uuid4())


async def test_default_listing_hides_suggestions_but_status_filter_shows_them():
    session = _Session([], [])
    svc = JudgmentService(session)
    await svc.list_predictions("t1")
    await svc.list_predictions("t1", status=SUGGESTED)
    default_sql, filtered_sql = (str(s.compile()) for s in session.statements)
    assert "predictions.outcome !=" in default_sql
    assert "predictions.outcome =" in filtered_sql and "!=" not in filtered_sql


# ── OutcomeResolver ──────────────────────────────────────────


async def test_resolving_a_suggestion_asks_for_acceptance_first():
    p = _prediction(SUGGESTED)
    with pytest.raises(ValueError, match="accept it"):
        await OutcomeResolver(_Session([p])).resolve_prediction(
            "t1", p.id, outcome="correct", source="manual"
        )
    assert p.outcome == SUGGESTED


async def test_expired_predictions_are_asked_about_once_with_an_expiry():
    asked_before = _prediction(resolve_by=datetime.now(UTC) - timedelta(days=3))
    new = _prediction(resolve_by=datetime.now(UTC) - timedelta(hours=1))
    session = _Session(
        [asked_before, new],
        [({"prediction_id": str(asked_before.id)},), ({"gap_id": "x"},)],
    )
    questions = await OutcomeResolver(session).check_expired_predictions("t1")

    assert [q.origin_ref["prediction_id"] for q in questions] == [str(new.id)]
    q = questions[0]
    assert isinstance(q, InterviewQuestion)
    ttl = q.expires_at - datetime.now(UTC)
    assert timedelta(days=QUESTION_TTL_DAYS - 1) < ttl <= timedelta(days=QUESTION_TTL_DAYS)


async def test_no_expired_predictions_skips_the_question_lookup():
    session = _Session([])
    assert await OutcomeResolver(session).check_expired_predictions("t1") == []
    assert len(session.statements) == 1


# ── Capture spine ────────────────────────────────────────────


@pytest.fixture
def judgment_calls(monkeypatch):
    calls = {"created": [], "open": set()}

    async def has_open(self, tenant_id, statement):
        return statement in calls["open"]

    async def create(self, **kw):
        calls["created"].append(kw)

    monkeypatch.setattr(JudgmentService, "has_open_prediction", has_open)
    monkeypatch.setattr(JudgmentService, "create_prediction", create)
    return calls


def _capture(surface="dashboard", trust_tier="self"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        surface=surface,
        trust_tier=trust_tier,
        created_at=datetime(2026, 9, 16, 10, tzinfo=UTC),
    )


TEXT = "I'm 80% sure the migration lands by Friday. Also 70% chance the client signs this month."


async def test_capture_of_own_words_suggests_predictions(judgment_calls):
    evt = _capture()
    n = await CaptureProcessors(_Bus())._suggest_predictions(_Session(), TEXT, evt, "t1")
    assert n == 2
    first = judgment_calls["created"][0]
    assert first["suggested"] is True
    assert first["statement"] == "The migration lands by Friday"
    assert first["confidence"] == 0.8
    assert first["resolve_by"].date().isoformat() == "2026-09-18"
    assert first["capture_event_id"] == evt.id
    assert first["resolution_criteria"]["quote"].startswith("I'm 80% sure")


@pytest.mark.parametrize("tier", ["external", "hostile_possible"])
async def test_untrusted_capture_suggests_nothing(judgment_calls, tier):
    n = await CaptureProcessors(_Bus())._suggest_predictions(
        _Session(), TEXT, _capture(trust_tier=tier), "t1"
    )
    assert n == 0
    assert judgment_calls["created"] == []


async def test_capture_skips_claims_already_tracked(judgment_calls):
    judgment_calls["open"].add("The migration lands by Friday")
    n = await CaptureProcessors(_Bus())._suggest_predictions(_Session(), TEXT, _capture(), "t1")
    assert n == 1
    assert judgment_calls["created"][0]["statement"] == "The client signs this month"


async def test_detection_failure_never_breaks_capture(monkeypatch, judgment_calls):
    def boom(*a, **k):
        raise RuntimeError("regex exploded")

    monkeypatch.setattr("life_graph.services.prediction_detection.detect_predictions", boom)
    n = await CaptureProcessors(_Bus())._suggest_predictions(_Session(), TEXT, _capture(), "t1")
    assert n == 0
