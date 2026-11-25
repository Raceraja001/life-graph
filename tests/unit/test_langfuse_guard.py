"""Langfuse tracing only goes to a self-hosted host unless the owner opts in.

Tracing sends every LiteLLM prompt and reply to ``langfuse_host``. Decision
2026-11-25: a host off this machine, the LAN or the tailnet is refused (with
a WARNING) unless ``langfuse_allow_remote`` is true.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from life_graph.core import startup_guards

LOGGER = "life_graph.core.startup_guards"


def _settings(host: str, *, key: str = "pk-lf-1", allow_remote: bool = False):
    return SimpleNamespace(
        langfuse_public_key=key,
        langfuse_secret_key="sk-lf-1",
        langfuse_host=host,
        langfuse_allow_remote=allow_remote,
    )


def test_allow_remote_defaults_to_off():
    from life_graph.config.core import CoreSettings

    assert CoreSettings().langfuse_allow_remote is False


LOCAL_HOSTS = [
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.8.9.10",
    "http://[::1]:3000",
    "http://10.0.0.5:3000",
    "http://172.20.1.2",
    "https://192.168.1.20",
    "http://100.101.102.103:3000",
    "https://langfuse.tail1234.ts.net",
    "http://langfuse:3000",
    "http://langfuse.localhost",
    "http://nas.local:3000",
]
REMOTE_HOSTS = [
    "https://cloud.langfuse.com",
    "https://us.cloud.langfuse.com",
    "https://langfuse.example.com",
    "http://8.8.8.8:3000",
    "http://[2001:4860:4860::8888]",
    "http://[::ffff:8.8.8.8]",
    "https://ts.net.evil.com",
    "localhost:3001",  # no scheme: no host to check
    "",
]


@pytest.mark.parametrize("host", LOCAL_HOSTS)
def test_self_hosted_host_is_allowed(host, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert startup_guards.langfuse_tracing_allowed(_settings(host)) is True
    assert not caplog.records


@pytest.mark.parametrize("host", REMOTE_HOSTS)
def test_remote_host_is_refused_by_default_with_a_warning(host, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert startup_guards.langfuse_tracing_allowed(_settings(host)) is False
    assert any("Langfuse tracing NOT enabled" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("host", REMOTE_HOSTS[:3])
def test_remote_host_is_allowed_with_the_flag(host, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert startup_guards.langfuse_tracing_allowed(_settings(host, allow_remote=True))
    assert not caplog.records


def test_no_key_means_no_tracing_and_no_warning(caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert not startup_guards.langfuse_tracing_allowed(
            _settings("https://cloud.langfuse.com", key="")
        )
    assert not caplog.records


def test_env_points_litellm_at_the_checked_host():
    """LiteLLM reads LANGFUSE_HOST, else defaults to Langfuse's cloud."""
    env = startup_guards.langfuse_env(_settings(" http://localhost:3001 "))
    assert env == {
        "LANGFUSE_HOST": "http://localhost:3001",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-1",
        "LANGFUSE_SECRET_KEY": "sk-lf-1",
    }


def test_main_uses_the_guard():
    """main.py's lifespan gates the LiteLLM callback on the guard, not the key."""
    import inspect

    import life_graph.main as main

    src = inspect.getsource(main.lifespan)
    assert "if langfuse_tracing_allowed(settings):" in src
    assert "os.environ.update(langfuse_env(settings))" in src
    assert "if settings.langfuse_public_key:" not in src
