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
    assert key not in redact(f"key={key}")


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


def test_non_string_safe():
    assert redact("") == ""
