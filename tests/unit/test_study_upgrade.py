"""Study upgrade (docs/research/study-helper-spec-2026-10.html): lapses, the review
log, drafts from one saved source, progress and the daily nudge."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from life_graph.models.assistant import Document, ReviewCard, StudyReview
from life_graph.services import study, study_nudge
from tests.unit.fakes import FakeSession, sql

TODAY = date(2026, 11, 1)
T = "tenant-a"


def card(**kw) -> ReviewCard:
    base = {
        "id": uuid.uuid4(),
        "tenant_id": T,
        "deck": "biology",
        "front": "What does the mitochondrion make?",
        "back": "ATP.",
        "ease": 2.5,
        "interval_days": 6,
        "repetitions": 2,
        "due_on": TODAY,
        "reviews": 2,
        "lapses": 0,
        "status": "active",
        "dedup_key": study.dedup_key("What does the mitochondrion make?"),
    }
    base.update(kw)
    return ReviewCard(**base)


# ── Scheduling: SM-2 unchanged, lapses and the review log added ─────────────


def test_the_worked_example_in_the_spec():
    c = card(ease=2.5, interval_days=0, repetitions=0, reviews=0)
    days = [TODAY]
    for grade in ("good", "good", "hard", "again", "good", "easy"):
        study.grade_card(c, grade, days[-1])
        days.append(c.due_on)
    assert days[1:] == [
        date(2026, 11, 2),
        date(2026, 11, 8),
        date(2026, 11, 23),
        date(2026, 11, 24),
        date(2026, 11, 25),
        date(2026, 12, 1),
    ]
    assert c.lapses == 1 and c.ease == pytest.approx(1.92)


def test_again_on_a_remembered_card_is_a_lapse_and_on_a_new_one_is_not():
    remembered = study.grade_card(card(repetitions=3), "again", TODAY)
    assert remembered.lapses == 1 and remembered.last_reviewed_on == TODAY
    fresh = study.grade_card(card(repetitions=0, lapses=None), "again", TODAY)
    assert fresh.lapses == 0
    assert study.grade_card(card(repetitions=3), "hard", TODAY).lapses == 0


def test_maturity_and_leech_flag():
    assert study.maturity(card(reviews=0, repetitions=0)) == "new"
    assert study.maturity(card(reviews=4, repetitions=0)) == "learning"
    assert study.maturity(card(interval_days=20)) == "young"
    assert study.maturity(card(interval_days=21)) == "mature"
    d = study.card_dict(card(lapses=8))
    assert d["leech"] is True and d["status"] == "active" and d["maturity"] == "young"
    assert study.card_dict(card(lapses=7))["leech"] is False


@pytest.mark.asyncio
async def test_review_logs_the_answer():
    session = FakeSession()
    c = card(interval_days=6, repetitions=2)
    now = datetime(2026, 11, 1, 12, tzinfo=UTC)
    await study.review(session, T, c, "good", TODAY, now)
    [log] = session.added
    assert isinstance(log, StudyReview)
    assert (log.tenant_id, log.card_id, log.deck, log.grade) == (T, c.id, "biology", "good")
    assert (log.reviewed_on, log.reviewed_at) == (TODAY, now)
    assert (log.interval_before, log.interval_after) == (6, 15)
    assert log.ease_after == c.ease


@pytest.mark.asyncio
async def test_review_refuses_drafts_other_tenants_and_bad_grades():
    session = FakeSession()
    with pytest.raises(ValueError, match="draft"):
        await study.review(session, T, card(status="draft"), "good", TODAY)
    with pytest.raises(ValueError, match="tenant"):
        await study.review(session, "tenant-b", card(), "good", TODAY)
    with pytest.raises(ValueError, match="grade must be one of"):
        await study.review(session, T, card(), "meh", TODAY)
    assert session.added == []


@pytest.mark.asyncio
async def test_only_active_cards_are_due_counted_or_in_deck_stats():
    for call, result in (
        (lambda s: study.due_cards(s, T, TODAY), []),
        (lambda s: study.count_due(s, T, TODAY), [0]),
        (lambda s: study.deck_stats(s, T, TODAY), []),
    ):
        session = FakeSession(result)
        await call(session)
        text = sql(session.statements[0])
        assert "status = 'active'" in text and f"'{T}'" in text


# ── Drafts ──────────────────────────────────────────────────────────────────


class LocalOnly:
    """A client with only the local path: a call to anything else fails the test."""

    def __init__(self, cards):
        self.cards = cards
        self.calls = []

    async def chat_local_only(self, **kw):
        self.calls.append(kw)
        return json.dumps({"cards": self.cards})

    def __getattr__(self, name):
        raise AssertionError(f"personal content must only go to chat_local_only, not {name}")


@pytest.mark.asyncio
async def test_drafts_from_a_memory_use_the_local_model_and_wait_for_the_owner():
    mem_id, new_id = uuid.uuid4(), uuid.uuid4()
    staged = card(id=new_id, status="draft", deck="notes", source_kind="memory", source_id=mem_id)
    session = FakeSession(
        "The mitochondrion makes ATP.",  # the memory
        new_id,  # first insert returns its id
        None,  # second is a duplicate front
        [staged],  # cards_by_ids
    )
    client = LocalOnly([{"front": "Q1?", "back": "A1"}, {"front": "Q2?", "back": "A2"}])
    out = await study.draft(
        session, T, today=TODAY, source="memory", source_id=mem_id, client=client
    )
    assert out["written"] == 2 and out["drafted"] == 1
    assert out["drafts"][0]["status"] == "draft"
    assert out["drafts"][0]["source_id"] == str(mem_id)
    assert "The mitochondrion makes ATP." in client.calls[0]["messages"][1]["content"]
    memory_sql = sql(session.statements[0])
    assert f"'{T}'" in memory_sql and str(mem_id) in memory_sql and "'active'" in memory_sql
    insert_sql = sql(session.statements[1])
    assert "'draft'" in insert_sql and "'memory'" in insert_sql and "ON CONFLICT" in insert_sql


@pytest.mark.asyncio
async def test_a_document_gives_its_title_and_notes_never_its_number():
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=T,
        kind="policy",
        title="Health insurance",
        issuer="Star Health",
        number_last4="9876",
        notes="Covers 5 lakh; waiting period 2 years for knee surgery.",
    )
    text, deck = await study.source_text(FakeSession(doc), T, "document", source_id=doc.id)
    assert "Health insurance" in text and "waiting period" in text and "Star Health" in text
    assert "9876" not in text
    assert deck == "Health insurance"


@pytest.mark.asyncio
async def test_a_missing_source_writes_nothing():
    client = LocalOnly([])
    out = await study.draft(
        FakeSession(None), T, today=TODAY, source="memory", source_id=uuid.uuid4(), client=client
    )
    assert out["drafted"] == 0 and client.calls == []
    with pytest.raises(ValueError):
        await study.draft(FakeSession(), T, today=TODAY, source="email", client=client)


@pytest.mark.asyncio
async def test_accept_and_reject_touch_only_this_tenants_drafts():
    ids = [uuid.uuid4()]
    session = FakeSession()
    await study.accept_drafts(session, T, TODAY, ids)
    await study.reject_drafts(session, T, None)
    accept, reject = (sql(s) for s in session.statements)
    for text in (accept, reject):
        assert f"'{T}'" in text and "status = 'draft'" in text
    assert str(ids[0]) in accept and "'2026-11-01'" in accept
    assert "DELETE" in reject
    empty = FakeSession()
    assert await study.accept_drafts(empty, T, TODAY, []) == 0
    assert empty.statements == []


@pytest.mark.asyncio
async def test_edit_checks_duplicates_and_status():
    c = card(status="draft")
    with pytest.raises(study.DuplicateCardError):
        await study.edit_card(FakeSession(uuid.uuid4()), T, c, front="Something else?")
    edited = await study.edit_card(FakeSession(None), T, c, front=" New? ", back="Yes", deck="")
    assert edited.front == "New?" and edited.dedup_key == study.dedup_key("New?")
    assert edited.deck == "general"
    with pytest.raises(ValueError, match="accept"):
        await study.edit_card(FakeSession(), T, c, status="active")
    active = card()
    await study.edit_card(FakeSession(), T, active, status="suspended")
    assert active.status == "suspended"
    with pytest.raises(ValueError):
        await study.edit_card(FakeSession(), T, active, status="draft")


# ── Progress ────────────────────────────────────────────────────────────────


def test_streak_counts_back_from_today_or_yesterday():
    d = lambda n: TODAY - timedelta(days=n)  # noqa: E731
    assert study.streak_days(set(), TODAY) == 0
    assert study.streak_days({d(0), d(1), d(2), d(4)}, TODAY) == 3
    assert study.streak_days({d(1), d(2)}, TODAY) == 2  # today not done yet
    assert study.streak_days({d(2), d(3)}, TODAY) == 0


@pytest.mark.asyncio
async def test_progress_counts_and_accuracy_per_deck():
    session = FakeSession(
        (
            12,
            5,
            1,
            30,
            10,
            4,
            2,
            1,
        ),  # due, new, learning, young, mature, drafts, suspended, leeches
        [TODAY, TODAY - timedelta(days=1)],  # days with reviews
        [7],  # reviewed today
        [("biology", 20, 18), ("history", 10, 5)],
    )
    p = await study.progress(session, T, TODAY)
    assert p["due"] == 12 and p["learned"] == 40 and p["mature"] == 10 and p["drafts"] == 4
    assert p["streak"] == 2 and p["reviewed_today"] == 7
    assert p["accuracy"] == round(23 / 30, 3)
    assert p["decks"] == [
        {"deck": "biology", "reviews": 20, "accuracy": 0.9},
        {"deck": "history", "reviews": 10, "accuracy": 0.5},
    ]
    for stmt in session.statements:
        assert f"'{T}'" in sql(stmt)
    text = study.progress_text(p)
    assert "Streak: 2 days" in text and "12 due" in text and "biology 90%" in text
    assert "4 drafts to check" in text and "1 leech" in text
    assert "biology" not in study.progress_text(p, with_decks=False)


# ── Telegram /drafts ────────────────────────────────────────────────────────


def test_numbers_and_the_drafts_list():
    assert study.parse_numbers(["1", "3"]) == [1, 3]
    assert study.parse_numbers(["1,2"]) == [1, 2]
    assert study.parse_numbers(["x"]) is None and study.parse_numbers(["0"]) is None
    text = study.drafts_text([card(front="Q?", back="A.")], 3)
    assert "1. [biology] Q: Q?" in text and "A: A." in text and "2 more" in text
    assert "No drafts" in study.drafts_text([], 0)


class _Redis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


@pytest.mark.asyncio
async def test_telegram_drafts_accepts_by_the_numbers_shown(monkeypatch):
    import life_graph.storage.database as db
    import life_graph.storage.redis as r

    first, second = card(status="draft"), card(status="draft", front="Other?")
    redis = _Redis()
    monkeypatch.setattr(r, "get_redis", lambda: redis)
    listing = FakeSession([first, second])
    monkeypatch.setattr(db, "async_session", lambda: listing)
    shown = await study.telegram_drafts(1, T, "", today=TODAY)
    assert "Drafts (2)" in shown

    accepting = FakeSession()
    monkeypatch.setattr(db, "async_session", lambda: accepting)
    assert "Pick numbers from 1 to 2" in await study.telegram_drafts(1, T, "accept 3", TODAY)
    await study.telegram_drafts(1, T, "accept 2", today=TODAY)
    text = sql(accepting.statements[-1])
    assert str(second.id) in text and str(first.id) not in text and f"'{T}'" in text
    assert accepting.commits == 1
    assert "Show them first" in await study.telegram_drafts(1, T, "drop 1", TODAY)


# ── The daily nudge ─────────────────────────────────────────────────────────

IST = ZoneInfo("Asia/Kolkata")


def at(hour: int) -> datetime:
    return datetime(2026, 11, 1, hour, 5, tzinfo=IST)


@pytest.mark.parametrize(
    ("now", "kw", "sent"),
    [
        (at(18), {"hour": 18, "sent_today": 0, "due": 12}, True),
        (at(17), {"hour": 18, "sent_today": 0, "due": 12}, False),  # too early
        (at(18), {"hour": 18, "sent_today": 1, "due": 12}, False),  # once a day
        (at(18), {"hour": 18, "sent_today": 0, "due": 0}, False),  # nothing due
        (at(18), {"hour": -1, "sent_today": 0, "due": 12}, False),  # off
        (at(22), {"hour": 18, "sent_today": 0, "due": 12}, False),  # quiet hours
        (at(23), {"hour": 7, "sent_today": 0, "due": 12}, False),
    ],
)
def test_should_send(now, kw, sent):
    assert study_nudge.should_send(now, **kw) is sent


@pytest.mark.asyncio
async def test_run_tenant_writes_one_count_only_notification():
    now = at(19).astimezone(UTC)
    session = FakeSession([0], [12])  # none sent today, 12 due
    assert await study_nudge.run_tenant(session, T, now, IST, hour=18) == 1
    [n] = session.added
    assert n.tenant_id == T and n.source_type == "study_due" and n.is_delivered
    assert n.body.startswith("12 cards due today")
    assert n.extra_metadata["dedup_key"] == "study_due:2026-11-01"
    assert all(f"'{T}'" in sql(s) for s in session.statements)

    again = FakeSession([1])
    assert await study_nudge.run_tenant(again, T, now, IST, hour=18) == 0
    assert again.added == [] and len(again.statements) == 1


# ── Tools: what a cloud model sees ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_tools_keep_card_text_and_decks_for_a_local_model(monkeypatch):
    import life_graph.storage.database as db
    from life_graph.connectors.locality import CLOUD, LOCAL, audience
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools import assistant as tools

    async def fake_draft(session, tenant, **kw):
        assert tenant == T and kw["source"] == "topic"
        drafts = [study.card_dict(card(status="draft", front="Q?", back="A."))]
        return {"written": 1, "drafted": 1, "drafts": drafts}

    async def fake_progress(session, tenant, today):
        return {"due": 3, "streak": 2, "decks": [{"deck": "biology"}]}

    monkeypatch.setattr(db, "async_session", lambda: FakeSession())
    monkeypatch.setattr(study, "draft", fake_draft)
    monkeypatch.setattr(study, "progress", fake_progress)
    with tenant_scope(T):
        with audience(CLOUD):
            cloud = json.loads(await tools.draft_study_cards("topic", topic="biology"))
            cloud_p = json.loads(await tools.study_progress())
        with audience(LOCAL):
            local = json.loads(await tools.draft_study_cards("topic", topic="biology"))
            local_p = json.loads(await tools.study_progress())
    assert "drafts" not in cloud and cloud["drafted"] == 1
    assert local["drafts"] == [{"front": "Q?", "back": "A.", "deck": "biology"}]
    assert "decks" not in cloud_p and cloud_p["due"] == 3
    assert local_p["decks"] == [{"deck": "biology"}]
    with tenant_scope(T):
        bad = json.loads(await tools.draft_study_cards("memory", source_id="nope"))
    assert "error" in bad


def test_new_tools_are_personal_and_drafting_is_blocked_in_temporary_chats():
    from life_graph.services.lead import PERSONAL_TOOLS, TEMPORARY_BLOCKED_TOOLS
    from life_graph.tools.assistant import READ_ONLY_TOOLS

    assert {"study_progress", "draft_study_cards"} <= PERSONAL_TOOLS
    assert "draft_study_cards" in TEMPORARY_BLOCKED_TOOLS
    assert "study_progress" in READ_ONLY_TOOLS and "draft_study_cards" not in READ_ONLY_TOOLS
