"""Audit M5: an API with no key must not start on a non-loopback address."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from life_graph.core.startup_guards import (
    InsecureStartupError,
    check_auth_exposure,
    detect_bind_host,
    is_loopback_host,
)


def _settings(*, keys: str = "", api_key: str | None = None, environment: str = "development"):
    return SimpleNamespace(
        service_api_keys_list=[k for k in keys.split(",") if k],
        api_key=api_key,
        environment=environment,
        is_development=environment == "development",
    )


@pytest.mark.parametrize("environment", ["development", "production", "staging"])
@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "100.64.0.7", "lifegraph.lan"])
def test_no_keys_on_non_loopback_refuses_whatever_the_environment(environment, host):
    with pytest.raises(InsecureStartupError, match="no API key"):
        check_auth_exposure(_settings(environment=environment), bind_host=host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20"])
def test_a_service_key_or_legacy_key_allows_any_bind(host, caplog):
    with caplog.at_level(logging.WARNING, logger="life_graph.core.startup_guards"):
        check_auth_exposure(_settings(keys="k1"), bind_host=host)
        check_auth_exposure(_settings(api_key="legacy"), bind_host=host)
    assert not caplog.records


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.1.1", "localhost", "::1", "[::1]"])
def test_no_keys_on_loopback_in_development_starts_with_a_loud_warning(host, caplog):
    with caplog.at_level(logging.WARNING, logger="life_graph.core.startup_guards"):
        check_auth_exposure(_settings(), bind_host=host)
    assert any("AUTH IS OFF" in r.getMessage() for r in caplog.records)


def test_no_keys_on_loopback_in_production_starts_quietly(caplog):
    # Auth fails closed there (401 "No API keys configured"), nothing is exposed.
    with caplog.at_level(logging.WARNING, logger="life_graph.core.startup_guards"):
        check_auth_exposure(_settings(environment="production"), bind_host="127.0.0.1")
    assert not caplog.records


def test_is_loopback_host():
    assert is_loopback_host("127.0.0.1") and is_loopback_host("::1")
    assert not is_loopback_host("0.0.0.0") and not is_loopback_host("")


@pytest.mark.parametrize(
    ("argv", "env", "expected"),
    [
        (["uvicorn", "life_graph.main:app", "--host", "0.0.0.0"], {}, "0.0.0.0"),
        (["uvicorn", "app", "--host=10.0.0.5", "--port", "8"], {}, "10.0.0.5"),
        # --host on the command line wins over the env var the scripts read.
        (
            ["uvicorn", "app", "--host", "127.0.0.1"],
            {"LIFE_GRAPH_BIND_HOST": "0.0.0.0"},
            "127.0.0.1",
        ),
        (["uvicorn", "app"], {"LIFE_GRAPH_BIND_HOST": "0.0.0.0"}, "0.0.0.0"),
        (["uvicorn", "app"], {}, "127.0.0.1"),
        (["uvicorn", "app", "--uds", "/tmp/lg.sock"], {}, "localhost"),
    ],
)
def test_detect_bind_host(argv, env, expected):
    assert detect_bind_host(argv, env) == expected


def test_default_call_uses_the_process_argv(monkeypatch):
    monkeypatch.setattr("sys.argv", ["uvicorn", "life_graph.main:app", "--host", "0.0.0.0"])
    monkeypatch.delenv("LIFE_GRAPH_BIND_HOST", raising=False)
    with pytest.raises(InsecureStartupError):
        check_auth_exposure(_settings())
