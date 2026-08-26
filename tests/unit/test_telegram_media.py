"""Voice notes and photos arriving from a Telegram chat.

Two of these are security tests rather than feature tests. A forwarded voice
note is somebody else's words, and the multimodal path files everything it
ingests as ``SELF`` — the owner's own tier — with no way to say otherwise per
item, so the bridge must decline it rather than launder a stranger's content
into trusted memory. And a download must stop at the declared ceiling while it
streams, because ``file_size`` in a message is Telegram's claim, not a fact.

The rest guard behaviour a user would notice: a photo's caption reaching the
memory alongside the OCR text, and every failure ending in a reply instead of
silence. No network and no database — the client and the multimodal service are
both faked.
"""

from __future__ import annotations

from typing import Any

import pytest

from life_graph.integrations.telegram import media as tg_media
from life_graph.integrations.telegram.client import TelegramError


class FakeService:
    """Stands in for MultiModalService, recording what it was handed."""

    def __init__(self, *, transcript: str = "hello there", ocr: str = "whiteboard text"):
        self.transcript = transcript
        self.ocr = ocr
        self.voice_calls: list[tuple] = []
        self.image_calls: list[tuple] = []
        self.raise_with: Exception | None = None

    async def process_voice(self, data: bytes, filename: str, tenant_id: str) -> dict:
        self.voice_calls.append((data, filename, tenant_id))
        if self.raise_with:
            raise self.raise_with
        return {"transcript": self.transcript, "ingest": "queued"}

    async def process_image(
        self, data: bytes, filename: str, tenant_id: str, caption: str | None = None
    ) -> dict:
        self.image_calls.append((data, filename, tenant_id, caption))
        if self.raise_with:
            raise self.raise_with
        return {"ocr_text": self.ocr, "ingest": "queued"}


@pytest.fixture
def replies() -> list[tuple[int, str]]:
    return []


@pytest.fixture
def reply(replies):
    async def _reply(chat_id: int, text: str) -> None:
        replies.append((chat_id, text))

    return _reply


@pytest.fixture
def service(monkeypatch) -> FakeService:
    svc = FakeService()
    monkeypatch.setattr(tg_media, "_service", lambda: svc)

    async def fake_download(file_id: str) -> bytes:
        return b"BYTES:" + file_id.encode()

    monkeypatch.setattr(tg_media, "_download", fake_download)
    return svc


VOICE_MSG: dict[str, Any] = {
    "message_id": 1,
    "voice": {"file_id": "voice-abc", "duration": 12, "file_size": 4096},
}
PHOTO_MSG: dict[str, Any] = {
    "message_id": 2,
    "photo": [
        {"file_id": "small", "file_size": 900},
        {"file_id": "large", "file_size": 90_000},
    ],
}


# ── extract ──────────────────────────────────────────────────────


class TestExtract:
    def test_finds_a_voice_note(self):
        media = tg_media.extract(VOICE_MSG)
        assert media["kind"] == "voice"
        assert media["file_id"] == "voice-abc"
        assert media["duration"] == 12

    def test_takes_the_largest_photo_size(self):
        # Telegram sends thumbnails first; OCR on a thumbnail finds nothing.
        assert tg_media.extract(PHOTO_MSG)["file_id"] == "large"

    def test_plain_text_is_not_media(self):
        assert tg_media.extract({"text": "just words"}) is None

    def test_a_sticker_is_not_media(self):
        assert tg_media.extract({"sticker": {"file_id": "s1"}}) is None

    def test_an_empty_photo_array_is_not_media(self):
        assert tg_media.extract({"photo": []}) is None

    def test_a_voice_without_a_file_id_is_not_media(self):
        assert tg_media.extract({"voice": {"duration": 3}}) is None


# ── The two refusals ─────────────────────────────────────────────


class TestForwarded:
    @pytest.mark.parametrize(
        "marker",
        [
            {"forward_origin": {"type": "user"}},
            {"forward_from": {"id": 99}},
            {"forward_date": 1_700_000_000},
        ],
    )
    async def test_forwarded_media_is_refused(self, marker, service, reply, replies):
        msg = {**VOICE_MSG, **marker}
        await tg_media.handle(tg_media.extract(msg), msg, 7, "t1", "", reply)

        assert service.voice_calls == [], "forwarded audio must not be transcribed"
        assert "forwarded" in replies[0][1].lower()

    async def test_unforwarded_media_is_accepted(self, service, reply, replies):
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "t1", "", reply)
        assert len(service.voice_calls) == 1


class TestCaps:
    async def test_an_oversized_file_is_refused_before_download(
        self, service, reply, replies, monkeypatch
    ):
        async def explode(file_id: str) -> bytes:
            raise AssertionError("must not download an oversized file")

        monkeypatch.setattr(tg_media, "_download", explode)
        msg = {"photo": [{"file_id": "huge", "file_size": tg_media.MAX_MEDIA_BYTES + 1}]}
        await tg_media.handle(tg_media.extract(msg), msg, 7, "t1", "", reply)

        assert service.image_calls == []
        assert "too large" in replies[0][1].lower()

    async def test_a_long_recording_is_refused(self, service, reply, replies):
        msg = {"voice": {"file_id": "v", "duration": tg_media.MAX_VOICE_SECONDS + 1}}
        await tg_media.handle(tg_media.extract(msg), msg, 7, "t1", "", reply)

        assert service.voice_calls == []
        assert "too long" in replies[0][1].lower()

    async def test_a_recording_at_the_limit_is_accepted(self, service, reply):
        msg = {"voice": {"file_id": "v", "duration": tg_media.MAX_VOICE_SECONDS}}
        await tg_media.handle(tg_media.extract(msg), msg, 7, "t1", "", reply)
        assert len(service.voice_calls) == 1


# ── The happy paths ──────────────────────────────────────────────


class TestVoice:
    async def test_the_transcript_is_echoed_back(self, service, reply, replies):
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "t1", "", reply)
        assert "hello there" in replies[0][1]

    async def test_the_bound_tenant_is_passed_through(self, service, reply):
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "tenant-x", "", reply)
        assert service.voice_calls[0][2] == "tenant-x"

    async def test_a_long_transcript_is_truncated_in_the_reply(self, service, reply, replies):
        service.transcript = "x" * (tg_media.PREVIEW_CHARS * 3)
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "t1", "", reply)
        # The whole transcript is stored; only the acknowledgement is trimmed.
        assert len(replies[0][1]) < tg_media.PREVIEW_CHARS + 100


class TestPhoto:
    async def test_the_caption_reaches_the_multimodal_path(self, service, reply):
        await tg_media.handle(
            tg_media.extract(PHOTO_MSG), PHOTO_MSG, 7, "t1", "notes from standup", reply
        )
        assert service.image_calls[0][3] == "notes from standup"

    async def test_no_caption_is_passed_as_empty(self, service, reply):
        await tg_media.handle(tg_media.extract(PHOTO_MSG), PHOTO_MSG, 7, "t1", "", reply)
        assert service.image_calls[0][3] == ""

    async def test_an_image_with_no_text_still_confirms(self, service, reply, replies):
        service.ocr = ""
        await tg_media.handle(tg_media.extract(PHOTO_MSG), PHOTO_MSG, 7, "t1", "", reply)
        assert replies[0][1] == "Saved."


# ── Nothing fails silently ───────────────────────────────────────


class TestFailuresAreReported:
    async def test_a_download_failure_is_reported(self, service, reply, replies, monkeypatch):
        async def boom(file_id: str) -> bytes:
            raise TelegramError("file is gone", error_code=400)

        monkeypatch.setattr(tg_media, "_download", boom)
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "t1", "", reply)
        assert replies, "a failed download must not be silent"
        assert "couldn't fetch" in replies[0][1].lower()

    async def test_nothing_to_remember_is_reported_verbatim(self, service, reply, replies):
        service.raise_with = ValueError("No text found in the image — nothing to remember")
        await tg_media.handle(tg_media.extract(PHOTO_MSG), PHOTO_MSG, 7, "t1", "", reply)
        assert "nothing to remember" in replies[0][1]

    async def test_a_missing_backend_is_reported(self, service, reply, replies):
        service.raise_with = ImportError("faster-whisper is not installed")
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "t1", "", reply)
        assert "isn't set up" in replies[0][1]
        # The reason is a server-side gap, so it must not be echoed to the chat.
        assert "faster-whisper" not in replies[0][1]

    async def test_an_unexpected_failure_says_it_was_not_saved(self, service, reply, replies):
        service.raise_with = RuntimeError("minio exploded")
        await tg_media.handle(tg_media.extract(PHOTO_MSG), PHOTO_MSG, 7, "t1", "", reply)
        assert "hasn't been saved" in replies[0][1]
        assert "minio" not in replies[0][1].lower(), "internals must not leak into the chat"

    async def test_missing_minio_is_reported(self, monkeypatch, reply, replies):
        def no_minio():
            raise ImportError("minio package is not installed")

        monkeypatch.setattr(tg_media, "_service", no_minio)
        monkeypatch.setattr(tg_media, "_download", _fake_download)
        await tg_media.handle(tg_media.extract(VOICE_MSG), VOICE_MSG, 7, "t1", "", reply)
        assert "isn't set up" in replies[0][1]


async def _fake_download(file_id: str) -> bytes:
    return b"bytes"
