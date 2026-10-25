"""GET /jarvis/app/latest and /jarvis/app/download/{file}: the in-app update
(life-graph-android docs/PLAN-v4.md, A1.6 and S1.3). No folder set, a bad
latest.json, or any name but the one it gives: 404. No database."""

from __future__ import annotations

import json
import os

import pytest
from fastapi import HTTPException

from life_graph.api import jarvis

APK = b"PK\x03\x04 not really an apk"


@pytest.fixture
def release(tmp_path, monkeypatch):
    from life_graph.config import settings

    folder = tmp_path / "release"
    folder.mkdir()
    (folder / "jarvis-1.4.0.apk").write_bytes(APK)
    monkeypatch.setattr(settings, "app_release_dir", str(folder))
    return folder


def _latest(folder, **over):
    meta = {
        "version_code": 14,
        "version_name": "1.4.0",
        "file": "jarvis-1.4.0.apk",
        "notes": "Today screen.",
        **over,
    }
    (folder / "latest.json").write_text(json.dumps(meta), encoding="utf-8")


async def _status(coro) -> int:
    try:
        await coro
    except HTTPException as exc:
        return exc.status_code
    return 200


@pytest.mark.asyncio
async def test_latest_gives_the_version_and_where_to_download(release):
    _latest(release)
    body = await jarvis.app_latest()
    assert body == {
        "data": {
            "version_code": 14,
            "version_name": "1.4.0",
            "url": "/api/v1/jarvis/app/download/jarvis-1.4.0.apk",
            "notes": "Today screen.",
        }
    }
    _latest(release, notes=None)
    assert (await jarvis.app_latest())["data"]["notes"] == ""


@pytest.mark.asyncio
async def test_no_folder_set_means_no_update(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "app_release_dir", "")
    assert await _status(jarvis.app_latest()) == 404
    assert await _status(jarvis.app_download("jarvis-1.4.0.apk")) == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "over",
    [
        {"version_code": "14"},
        {"version_code": True},
        {"version_code": 0},
        {"version_name": None},
        {"file": "../jarvis-1.4.0.apk"},
        {"file": "sub/jarvis-1.4.0.apk"},
        {"file": ".hidden.apk"},
        {"file": "jarvis-1.4.0.zip"},
        {"file": "missing.apk"},
        {"notes": ["x"]},
    ],
)
async def test_a_bad_latest_json_is_no_update(release, over):
    _latest(release, **over)
    assert await _status(jarvis.app_latest()) == 404


@pytest.mark.asyncio
async def test_unreadable_or_not_an_object_is_no_update(release):
    assert await _status(jarvis.app_latest()) == 404  # no latest.json yet
    (release / "latest.json").write_text("{not json", encoding="utf-8")
    assert await _status(jarvis.app_latest()) == 404
    (release / "latest.json").write_text("[1, 2]", encoding="utf-8")
    assert await _status(jarvis.app_latest()) == 404


@pytest.mark.asyncio
async def test_a_symlink_out_of_the_folder_is_refused(release, tmp_path):
    outside = tmp_path / "secret.apk"
    outside.write_bytes(b"not for phones")
    try:
        os.symlink(outside, release / "link.apk")
    except OSError:
        pytest.skip("symlinks not available here")
    _latest(release, file="link.apk")
    assert await _status(jarvis.app_latest()) == 404
    assert await _status(jarvis.app_download("link.apk")) == 404


@pytest.mark.asyncio
async def test_download_streams_only_the_named_apk(release):
    _latest(release)
    (release / "other.apk").write_bytes(b"older")
    resp = await jarvis.app_download("jarvis-1.4.0.apk")
    assert resp.media_type == "application/vnd.android.package-archive"
    assert str(resp.path).endswith("jarvis-1.4.0.apk")
    assert 'filename="jarvis-1.4.0.apk"' in resp.headers["content-disposition"]
    for name in ("other.apk", "latest.json", "../release/jarvis-1.4.0.apk", "JARVIS-1.4.0.apk"):
        assert await _status(jarvis.app_download(name)) == 404, name


def test_the_update_routes_are_jarvis_routes_so_a_device_token_opens_them():
    from life_graph.api.device_access import device_may_call

    assert device_may_call("GET", "/api/v1/jarvis/app/latest")
    assert device_may_call("GET", "/api/v1/jarvis/app/download/jarvis-1.4.0.apk")
    assert not device_may_call("GET", "/api/v1/jarvis/app/download/../latest.json")
