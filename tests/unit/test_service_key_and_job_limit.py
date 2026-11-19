"""Service keys are compared in constant time; /admin/jobs limit is bounded
(audit 2026-11-19, L10)."""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from life_graph.api import auth
from life_graph.config import settings


def _request(key: str):
    return SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/memories"),
        headers={"X-API-Key": key},
        query_params={},
    )


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "service_api_keys", "key-one-aaaaaaaa,key-two-bbbbbbbb")
    monkeypatch.setattr(settings, "api_key", "legacy-cccccccc")


@pytest.mark.parametrize("good", ["key-one-aaaaaaaa", "key-two-bbbbbbbb", "legacy-cccccccc"])
def test_valid_keys_accepted(keys, good):
    assert auth.verify_service_key(_request(good)) == good


@pytest.mark.parametrize("bad", ["key-one-aaaaaaa", "key-one-aaaaaaaaX", "ключ-é"])
def test_invalid_keys_rejected(keys, bad):
    with pytest.raises(HTTPException) as exc:
        auth.verify_service_key(_request(bad))
    assert exc.value.status_code == 401


def test_membership_check_uses_compare_digest_not_in():
    src = textwrap.dedent(inspect.getsource(auth.verify_service_key))
    tree = ast.parse(src)
    in_tests = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Compare) and any(isinstance(op, ast.NotIn | ast.In) for op in n.ops)
    ]
    assert not in_tests, "API keys must not be matched with `in`"


def test_job_runs_limit_is_bounded(monkeypatch):
    from life_graph.api import admin

    def _no_db():
        raise AssertionError("an out-of-range limit must be refused before the DB")

    monkeypatch.setattr(admin, "async_session", _no_db)
    app = FastAPI()
    app.include_router(admin.router)
    client = TestClient(app)
    assert client.get("/admin/jobs?limit=100000").status_code == 422
    assert client.get("/admin/jobs?limit=0").status_code == 422
