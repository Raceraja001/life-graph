# tests/unit/test_transcript_redaction.py
"""Unit tests for the secret redactor (external transcript distillation).

Named to avoid colliding with the pre-existing tests/unit/test_redaction.py,
which covers the unrelated life_graph.core.redaction module (tool-exhaust
observation redaction). See task-1-report.md for details.
"""

from __future__ import annotations

from life_graph.services.redaction import redact


def test_redacts_bearer_token():
    assert "REDACTED" in redact("Authorization: Bearer sk-abcDEF1234567890abcdef")
    assert "sk-abcDEF1234567890abcdef" not in redact("Bearer sk-abcDEF1234567890abcdef")


def test_redacts_openai_style_key():
    out = redact("my key is sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX please")
    assert "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX" not in out
    assert "please" in out


def test_redacts_aws_access_key():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("AKIAIOSFODNN7EXAMPLE")


def test_redacts_google_api_key():
    key = "AIzaSyA1234567890abcdefghijklmnopqrstuvw"
    out = redact(f"key={key}")
    assert key not in out
    # Regression: an exact-length {35} pattern only consumed the first 39 of
    # this 40-char key, leaving the trailing "w" dangling right after the
    # marker (a substring check on the full key alone wouldn't catch that).
    # The whole "key=<key>" text must collapse to exactly one marker.
    assert out == "key=«REDACTED:google_key»"


def test_redacts_pem_private_key():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOwIBAAJB\n-----END RSA PRIVATE KEY-----"
    out = redact(pem)
    assert "MIIBOwIBAAJB" not in out


def test_redacts_env_secret_assignment():
    assert "hunter2secretvalue" not in redact("DATABASE_PASSWORD=hunter2secretvalue")
    assert "topsecrettoken123" not in redact("MY_API_KEY: topsecrettoken123")


def test_leaves_ordinary_code_intact():
    code = "def add(a, b):\n    return a + b  # simple helper"
    assert redact(code) == code


def test_does_not_redact_lowercase_secret_shaped_code():
    # Regression: the env_secret pattern previously used (?i), which made it
    # match ordinary lowercase code that merely mentions "token"/"password"/
    # "api_key" as an identifier, not just real UPPER_CASE env-var
    # assignments.
    assert redact("token = get_token()") == "token = get_token()"
    assert redact("password = hash(pw)") == "password = hash(pw)"
    assert redact("api_key = load_from_vault()") == "api_key = load_from_vault()"


def test_non_string_safe():
    assert redact("") == ""
