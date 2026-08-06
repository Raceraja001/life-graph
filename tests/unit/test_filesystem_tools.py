from __future__ import annotations

import json

import pytest

from life_graph.tools.filesystem import file_read, file_write


@pytest.mark.asyncio
async def test_file_read_returns_content(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world", encoding="utf-8")

    raw = await file_read(str(f))
    data = json.loads(raw)

    assert data["content"] == "hello world"
    assert data["truncated"] is False


@pytest.mark.asyncio
async def test_file_read_missing_file_returns_error():
    raw = await file_read("/definitely/does/not/exist.txt")
    data = json.loads(raw)

    assert "error" in data


@pytest.mark.asyncio
async def test_file_read_truncates_large_files(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 25000, encoding="utf-8")

    raw = await file_read(str(f))
    data = json.loads(raw)

    assert len(data["content"]) == 20000
    assert data["truncated"] is True


@pytest.mark.asyncio
async def test_file_write_creates_file_and_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / "out.txt"

    raw = await file_write(str(target), "written content")
    data = json.loads(raw)

    assert target.read_text(encoding="utf-8") == "written content"
    assert data["bytes_written"] == len("written content".encode("utf-8"))


@pytest.mark.asyncio
async def test_file_write_overwrites_existing_file(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old", encoding="utf-8")

    await file_write(str(f), "new")

    assert f.read_text(encoding="utf-8") == "new"


@pytest.mark.asyncio
async def test_file_write_rejects_oversized_content():
    raw = await file_write("/tmp/whatever.txt", "x" * 200001)
    data = json.loads(raw)

    assert "error" in data
