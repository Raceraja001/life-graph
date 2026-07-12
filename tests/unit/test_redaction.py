"""Unit tests for secret redaction (tool-exhaust observation storage)."""

from __future__ import annotations

from life_graph.core.redaction import REDACTED, redact_secrets, summarize_args


def test_redacts_key_value_secrets():
    assert "hunter2" not in redact_secrets("password=hunter2")
    assert "abc123" not in redact_secrets("API_KEY: abc123")
    assert "xyz" not in redact_secrets("db_secret='xyz'")


def test_keeps_key_name_but_hides_value():
    out = redact_secrets("api_key=sk-abcdefghijklmnop1234")
    assert "api_key" in out
    assert REDACTED in out
    assert "sk-abcdefghijklmnop1234" not in out


def test_redacts_bearer_header():
    out = redact_secrets("Authorization: Bearer eyJabcdefgh.ijklmnopqrst")
    assert REDACTED in out
    assert "eyJabcdefgh.ijklmnopqrst" not in out


def test_redacts_standalone_token_shapes():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact_secrets("key AKIAIOSFODNN7EXAMPLE here")
    assert "ghp_" not in redact_secrets("token ghp_0123456789abcdefghijklmnopqrstuv")


def test_non_secret_text_untouched():
    text = "git commit -m 'fix the thing'"
    assert redact_secrets(text) == text


def test_empty_is_safe():
    assert redact_secrets("") == ""
    assert redact_secrets(None) is None


def test_summarize_args_redacts_and_truncates():
    s = summarize_args({"cmd": "deploy", "token": "ghp_0123456789abcdefghij0123"})
    assert "ghp_0123456789abcdefghij0123" not in s
    long = summarize_args({"blob": "x" * 500}, max_len=50)
    assert len(long) <= 51  # 50 + ellipsis


def test_summarize_args_deterministic():
    a = summarize_args({"b": 1, "a": 2})
    b = summarize_args({"a": 2, "b": 1})
    assert a == b  # sort_keys
