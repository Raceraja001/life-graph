"""Voice notes and photos from a Telegram chat.

A phone is the one device always in the pocket, and on a phone the fastest way
to record a thought is to hold the mic button or point the camera. This module
is what makes those two gestures reach the same capture spine as typed text.

Both kinds of media take the same route: resolve the file id, download the
bytes, and hand them to :class:`~life_graph.services.multimodal.MultiModalService`
— the same transcription and OCR path the ``/ingest/voice`` and ``/ingest/image``
endpoints use. Nothing here re-implements either; a bug fixed in one place is
fixed for both surfaces.

Two deliberate refusals:

*Forwarded media is not saved.* The multimodal path derives a memory's trust
tier from its source, and both ``voice`` and ``image`` map to ``SELF`` — the
same tier as the owner's own typing. That is right for a note the user just
recorded and wrong for a voice message someone else sent them, which is
precisely the content an injection would arrive in. The path offers no way to
override the tier per item, so the honest answer is to decline and say why
rather than file a stranger's words as the user's own.

*Long recordings are declined.* Transcription runs inline in the poll loop,
which handles chats strictly one at a time, so a twenty-minute recording stalls
every other chat behind it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from life_graph.integrations.telegram.client import TelegramClient, TelegramError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Telegram's own getFile ceiling is 20 MB — a larger file cannot be fetched at
# all — so this states the limit rather than imposing a new one. It is enforced
# while streaming, because ``file_size`` is only Telegram's claim about the file.
MAX_MEDIA_BYTES = 20 * 1024 * 1024

# See the module docstring: the cap is about not blocking other chats.
MAX_VOICE_SECONDS = 300

_FORWARDED_REFUSAL = (
    "I don't save forwarded photos or voice notes yet — I can't record that "
    "the content came from someone else, and filing it as your own would be "
    "wrong. Describe it in your own words and I'll keep that."
)

_TOO_LONG = (
    f"That recording is longer than {MAX_VOICE_SECONDS // 60} minutes — "
    "too long to transcribe here."
)
_TOO_BIG = "That file is too large for me to fetch from Telegram."

# How much of a transcript or OCR result to echo back. Enough to see that the
# right thing was heard, short enough not to fill the chat with a wall of text.
PREVIEW_CHARS = 400


def extract(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Describe the voice note or photo in ``msg``, or ``None`` if neither.

    For photos Telegram sends an array of sizes, smallest first; the last is
    the largest available and the only one worth running OCR against.
    """
    voice = msg.get("voice")
    if isinstance(voice, dict) and voice.get("file_id"):
        return {
            "kind": "voice",
            "file_id": voice["file_id"],
            "file_size": voice.get("file_size"),
            "duration": voice.get("duration"),
            "filename": f"{voice['file_id']}.ogg",
        }

    photo = msg.get("photo")
    if isinstance(photo, list) and photo:
        largest = photo[-1]
        if isinstance(largest, dict) and largest.get("file_id"):
            return {
                "kind": "photo",
                "file_id": largest["file_id"],
                "file_size": largest.get("file_size"),
                "duration": None,
                "filename": f"{largest['file_id']}.jpg",
            }
    return None


async def handle(
    media: dict[str, Any],
    msg: dict[str, Any],
    chat_id: int,
    tenant_id: str,
    caption: str,
    reply: Callable[[int, str], Awaitable[None]],
) -> None:
    """Download one piece of media and put it through the multimodal path.

    Every failure below ends in a reply. A voice note that vanishes without a
    word is worse than one that is refused: the user has no copy of what they
    said and no reason to suspect it was lost.
    """
    if _is_forwarded(msg):
        await reply(chat_id, _FORWARDED_REFUSAL)
        return

    size = media.get("file_size")
    if isinstance(size, int) and size > MAX_MEDIA_BYTES:
        await reply(chat_id, _TOO_BIG)
        return

    duration = media.get("duration")
    if isinstance(duration, int) and duration > MAX_VOICE_SECONDS:
        await reply(chat_id, _TOO_LONG)
        return

    try:
        data = await _download(media["file_id"])
    except TelegramError as exc:
        logger.warning("telegram: media download failed — %s", exc.description)
        await reply(chat_id, "I couldn't fetch that from Telegram. Try sending it again.")
        return

    try:
        service = _service()
    except ImportError as exc:
        logger.warning("telegram: multimodal unavailable — %s", exc)
        await reply(chat_id, "Media isn't set up on this server yet.")
        return

    try:
        if media["kind"] == "voice":
            result = await service.process_voice(data, media["filename"], tenant_id)
            body = (result.get("transcript") or "").strip()
            await reply(chat_id, _confirm("Heard", body))
        else:
            result = await service.process_image(
                data, media["filename"], tenant_id, caption=caption
            )
            body = (result.get("ocr_text") or "").strip()
            await reply(chat_id, _confirm("Read", body) if body else "Saved.")
    except ValueError as exc:
        # The path raises this for "nothing to remember" — an image with no
        # text and no caption, or silence. Report it; it is the user's answer.
        await reply(chat_id, str(exc))
    except ImportError as exc:
        # Whisper or pytesseract missing. Distinct from a processing failure,
        # and the fix is on the server rather than in the message.
        logger.warning("telegram: multimodal backend missing — %s", exc)
        await reply(chat_id, "That kind of file isn't set up on this server yet.")
    except Exception:
        logger.exception("telegram: media processing failed for chat %s", chat_id)
        await reply(chat_id, "Something went wrong processing that. It hasn't been saved.")


# ── Helpers ───────────────────────────────────────────────────────


def _is_forwarded(msg: dict[str, Any]) -> bool:
    return bool(msg.get("forward_origin") or msg.get("forward_from") or msg.get("forward_date"))


def _confirm(verb: str, body: str) -> str:
    if not body:
        return "Saved."
    preview = body if len(body) <= PREVIEW_CHARS else body[:PREVIEW_CHARS].rstrip() + "…"
    return f"{verb}: {preview}\n\nSaved."


async def _download(file_id: str) -> bytes:
    async with TelegramClient() as client:
        if not client.configured:
            raise TelegramError("Telegram bot token is not configured")
        path = await client.get_file_path(file_id)
        return await client.download_file(path, max_bytes=MAX_MEDIA_BYTES)


def _service():  # noqa: ANN202
    """Build the multimodal service, reusing one instance per process.

    Deliberately not the factory in ``api/multimodal.py``: that one raises
    ``HTTPException`` for a missing MinIO client, which is the right answer to
    an HTTP request and meaningless inside a poll loop. The underlying
    ``ImportError`` is caught by the caller instead.
    """
    from life_graph.api.dependencies import get_extraction_pipeline
    from life_graph.core.events import event_bus
    from life_graph.services.multimodal import MultiModalService
    from life_graph.storage.minio_client import MinIOStorage

    if not hasattr(_service, "_instance"):
        _service._instance = MultiModalService(
            minio=MinIOStorage(),
            event_bus=event_bus,
            pipeline=get_extraction_pipeline(),
        )
    return _service._instance
