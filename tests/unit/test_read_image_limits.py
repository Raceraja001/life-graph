"""POST /jarvis/read-image only decodes what it says it is, refuses
decompression bombs, and stops a slow OCR (security review 2026-10-24, M3).

Pillow and pytesseract are an optional extra (pyproject.toml), often absent
from a dev venv, so most of these run against a stand-in PIL module; the
ones that need the real decoder skip without it.
"""

from __future__ import annotations

import io
import sys
import time
import types

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64


class _FakeImage:
    def __init__(self, width, height):
        self.width, self.height = width, height

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_pil(monkeypatch):
    """A PIL stand-in: records the formats each open() allowed and pretends
    every image is ``state["size"]`` pixels."""
    opened: list = []
    state = {"size": (40, 20)}

    def open_(fp, formats=None):
        opened.append(formats)
        return _FakeImage(*state["size"])

    pil = types.ModuleType("PIL")
    image_mod = types.ModuleType("PIL.Image")
    image_mod.open = open_
    pil.Image = image_mod
    tess = types.ModuleType("pytesseract")
    tess.calls = []

    def image_to_string(image, lang=None, timeout=0):
        tess.calls.append(timeout)
        return " Fees due Friday \n"

    tess.image_to_string = image_to_string
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", image_mod)
    monkeypatch.setitem(sys.modules, "pytesseract", tess)
    return types.SimpleNamespace(opened=opened, state=state, tess=tess)


def _upload(data: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        io.BytesIO(data), filename="x", headers=Headers({"content-type": content_type})
    )


async def _status(data, content_type="image/png"):
    from life_graph.api.jarvis import read_image

    try:
        resp = await read_image(_upload(data, content_type))
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return 200, resp


def test_magic_bytes_decide_the_format():
    from life_graph.api.jarvis import _image_format

    assert _image_format(PNG) == "PNG"
    assert _image_format(JPEG) == "JPEG"
    assert _image_format(WEBP) == "WEBP"
    assert _image_format(GIF) is None
    assert _image_format(b"%PDF-1.7") is None


@pytest.mark.asyncio
async def test_a_png_opens_as_png_only_and_ocr_has_a_timeout(fake_pil):
    from life_graph.services.multimodal import OCR_TIMEOUT_SECONDS

    code, _ = await _status(JPEG, "image/png")  # the bytes decide, not the header
    assert code == 200
    assert fake_pil.opened[0] == ["JPEG"]
    assert fake_pil.tess.calls == [OCR_TIMEOUT_SECONDS]


@pytest.mark.asyncio
async def test_another_format_claiming_to_be_an_image_is_refused(fake_pil):
    assert (await _status(GIF, "image/png"))[0] == 415
    assert (await _status(b"%PDF-1.7 ...", "image/jpeg"))[0] == 415
    assert fake_pil.opened == []  # never handed to a decoder


@pytest.mark.asyncio
async def test_too_many_pixels_are_refused_before_ocr(fake_pil):
    from life_graph.services.multimodal import MAX_OCR_PIXELS, MultiModalService

    fake_pil.state["size"] = (8000, 6000)
    assert MAX_OCR_PIXELS < 8000 * 6000
    with pytest.raises(ValueError, match="too large"):
        MultiModalService._ocr_image(PNG)
    code, detail = await _status(PNG)
    assert code == 422 and "couldn't read" in detail
    assert fake_pil.tess.calls == []  # tesseract never ran


@pytest.mark.asyncio
async def test_tesseract_timing_out_is_a_504(fake_pil):
    def slow(image, lang=None, timeout=0):
        raise RuntimeError("Tesseract process timeout")

    fake_pil.tess.image_to_string = slow
    code, detail = await _status(PNG)
    assert code == 504 and "too long" in detail


@pytest.mark.asyncio
async def test_a_hung_ocr_is_cut_off_with_a_504(fake_pil, monkeypatch):
    from life_graph.services import multimodal

    def hang(image, lang=None, timeout=0):
        time.sleep(1.0)
        return "late"

    fake_pil.tess.image_to_string = hang
    monkeypatch.setattr(multimodal, "OCR_TIMEOUT_SECONDS", -4.9)  # wait_for gets 0.1 s
    code, _ = await _status(PNG)
    assert code == 504


@pytest.mark.asyncio
async def test_without_pillow_it_says_so(monkeypatch):
    monkeypatch.setitem(sys.modules, "PIL", None)
    code, detail = await _status(PNG)
    assert code == 503 and "not set up" in detail


# ── With the real decoder, when it is installed ───────────────


def _real_png(width=40, height=20, mode="RGB") -> bytes:
    image = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    image.new(mode, (width, height), 1 if mode == "1" else "white").save(buf, "PNG")
    return buf.getvalue()


def test_real_png_magic_on_garbage_does_not_open():
    from life_graph.api.jarvis import _read_words

    pytest.importorskip("PIL.Image")
    with pytest.raises(Exception):  # noqa: B017 - Pillow's own UnidentifiedImageError
        _read_words(PNG, "PNG")


def test_real_bomb_is_refused_before_decoding():
    pytest.importorskip("pytesseract")
    from life_graph.services.multimodal import MultiModalService

    bomb = _real_png(8000, 6000, mode="1")  # 48M pixels, a few KB on the wire
    assert len(bomb) < 200_000
    with pytest.raises(ValueError, match="too large"):
        MultiModalService._ocr_image(bomb)
