"""Settling a Jarvis capture by what its run saved (services/saved_by_tool.py).

The phone's capture of "Remember that my bike service is due on 3 November"
and Jarvis's run for the same words both learnt from it: memory_save stored
one memory, the extractor a reworded copy labelled "fact" that landed pending
next to it (2026-10-24). And when Jarvis did not call memory_save at all, the
extractor's explicit_save was dropped and nothing was saved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.extraction.rules import ExtractedFact
from life_graph.services import saved_by_tool
from life_graph.services.saved_by_tool import SavedMemory, drop_saved, is_run_for, run_saves

CONVERSATION = uuid.UUID("00000000-0000-0000-0000-00000000c0de")


def _capture(content: str = "Remember that my bike service is due on 3 November", **props):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        created_at=datetime.now(UTC),
        properties={"input": "text", "conversation_id": str(CONVERSATION), **props},
    )


def _fact(content: str, fact_type: str = "fact") -> ExtractedFact:
    return ExtractedFact(content=content, fact_type=fact_type, confidence=0.9)


class TestIsRunFor:
    def test_the_owner_message_is_the_captured_text(self):
        assert is_run_for(
            {"message": "Remember that my bike service is due on 3 November"}, _capture()
        )

    def test_whitespace_does_not_matter(self):
        assert is_run_for(
            {"message": "Remember that my bike  service\nis due on 3 November "}, _capture()
        )

    def test_a_turn_with_shared_text_is_matched_by_the_owner_message(self):
        run = {"message": "Remember … <shared>x</shared>", "owner_message": _capture().content}
        assert is_run_for(run, _capture())

    def test_another_message_is_another_run(self):
        assert not is_run_for({"message": "What's the weather?"}, _capture())

    def test_a_shared_capture_is_found_in_the_fenced_message(self):
        capture = _capture("Invoice 42 is due Friday", input="shared")
        run = {"message": "Save this\n\n<shared>\nInvoice 42 is due Friday\n</shared>"}
        assert is_run_for(run, capture)

    def test_an_empty_capture_matches_nothing(self):
        assert not is_run_for({"message": ""}, _capture(""))

    def test_a_long_capture_matches_its_untruncated_run(self):
        """_capture keeps the first 8,000 characters; the run has all of them."""
        text = "word " * 2000
        assert is_run_for({"message": text * 2}, _capture(text[:8000]))


class TestDropSaved:
    SAVED = [SavedMemory(uuid.uuid4(), "My bike service is due on 3 November 2026.", [1.0, 0.0])]

    @staticmethod
    def _embed(vectors: dict[str, list[float] | None]):
        return AsyncMock(side_effect=lambda text: vectors.get(text))

    @pytest.mark.asyncio
    async def test_a_reworded_copy_labelled_fact_is_dropped(self):
        copy = _fact("The owner's bike service is due on 3 November 2026.")
        other = _fact("The owner rides a Royal Enfield.")
        embed = self._embed({copy.content: [0.95, 0.31], other.content: [0.1, 0.99]})

        kept = await drop_saved([copy, other], self.SAVED, embed)

        assert kept == [other]

    @pytest.mark.asyncio
    async def test_the_same_words_are_dropped_without_an_embedding(self):
        same = _fact("my bike service is due on 3 november 2026", "explicit_save")

        assert await drop_saved([same], self.SAVED, self._embed({})) == []

    @pytest.mark.asyncio
    async def test_a_second_thing_asked_for_is_kept(self):
        """'Remember A and B', Jarvis saved only A: B is still saved, by the extractor."""
        b = _fact("The owner's insurance renews on 5 March 2027.", "explicit_save")

        kept = await drop_saved([b], self.SAVED, self._embed({b.content: [0.0, 1.0]}))

        assert kept == [b]

    @pytest.mark.asyncio
    async def test_nothing_saved_keeps_everything(self):
        facts = [_fact("x", "explicit_save"), _fact("y")]
        embed = self._embed({})

        assert await drop_saved(facts, [], embed) == facts
        embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_without_embeddings_only_the_explicit_save_is_dropped(self):
        """It cannot be compared; the run saved what was asked, so that is its likely copy."""
        asked = _fact("Bike service due 3 Nov", "explicit_save")
        other = _fact("Owner rides to work")

        kept = await drop_saved([asked, other], self.SAVED, self._embed({}))

        assert kept == [other]

    @pytest.mark.asyncio
    async def test_a_saved_memory_without_a_vector_is_embedded(self):
        saved = [SavedMemory(uuid.uuid4(), "My locker code is 4417.", None)]
        copy = _fact("The owner's locker code is 4417.")
        embed = self._embed({saved[0].content: [1.0, 0.0], copy.content: [0.99, 0.1]})

        assert await drop_saved([copy], saved, embed) == []


class TestRunSaves:
    @pytest.fixture
    def db(self, monkeypatch):
        monkeypatch.setattr(saved_by_tool, "POLL_SECONDS", 0.0)
        find = AsyncMock(return_value=None)
        saved = AsyncMock(return_value=[])
        monkeypatch.setattr(saved_by_tool, "_find_run", find)
        monkeypatch.setattr(saved_by_tool, "_saved_in", saved)
        return SimpleNamespace(find=find, saved=saved)

    @pytest.mark.asyncio
    async def test_a_finished_run_gives_its_saves(self, db):
        run = SimpleNamespace(id=uuid.uuid4(), status="completed")
        db.find.return_value = run
        db.saved.return_value = ["m"]

        assert await run_saves(_capture(), "acme", wait_seconds=5) == ["m"]
        db.saved.assert_awaited_once_with(run.id, "acme")

    @pytest.mark.asyncio
    async def test_it_waits_for_the_run_to_finish(self, db):
        run_id = uuid.uuid4()
        db.find.side_effect = [
            None,
            SimpleNamespace(id=run_id, status="running"),
            SimpleNamespace(id=run_id, status="completed"),
        ]

        assert await run_saves(_capture(), "acme", wait_seconds=5) == []
        assert db.find.await_count == 3
        db.saved.assert_awaited_once_with(run_id, "acme")

    @pytest.mark.asyncio
    async def test_a_young_capture_whose_run_is_unfinished_waits_for_the_sweep(self, db):
        db.find.return_value = SimpleNamespace(id=uuid.uuid4(), status="running")

        assert await run_saves(_capture(), "acme", wait_seconds=0) is None
        db.saved.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_young_capture_with_no_run_yet_waits_for_the_sweep(self, db):
        assert await run_saves(_capture(), "acme", wait_seconds=0) is None

    @pytest.mark.asyncio
    async def test_the_sweep_settles_with_what_was_saved_so_far(self, db):
        capture = _capture()
        capture.created_at = datetime.now(UTC) - timedelta(minutes=16)
        run = SimpleNamespace(id=uuid.uuid4(), status="running")
        db.find.return_value = run
        db.saved.return_value = ["m"]

        assert await run_saves(capture, "acme", wait_seconds=0) == ["m"]

    @pytest.mark.asyncio
    async def test_the_sweep_settles_a_capture_with_no_run_as_nothing_saved(self, db):
        capture = _capture()
        capture.created_at = datetime.now(UTC) - timedelta(minutes=16)

        assert await run_saves(capture, "acme", wait_seconds=0) == []
        db.saved.assert_not_awaited()


class TestConversationOf:
    def test_read_from_the_capture(self):
        assert saved_by_tool._conversation_of(_capture()) == CONVERSATION

    def test_a_new_chat_has_none(self):
        """A first message's capture is written before its conversation exists."""
        assert saved_by_tool._conversation_of(_capture(conversation_id=None)) is None
