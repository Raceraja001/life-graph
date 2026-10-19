"""Unit tests for ``build_transcript_snapshot``.

The function serialises a session, its turns and a list of memory IDs into a JSON
bytes payload.  It uses the ``_utcnow`` helper from ``life_graph.models.db`` to
stamp the snapshot and the ``redact`` helper from ``life_graph.services.redaction``
to scrub secrets from the turn text.

The tests patch ``_utcnow`` so the timestamp is deterministic and they use
``types.SimpleNamespace`` to provide a minimal session object with the required
attributes.
"""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from life_graph.services.redaction import redact
from life_graph.services.transcript_distiller import build_transcript_snapshot

# The ``_utcnow`` helper is imported in the module under test, so we patch it
# there to return a fixed timestamp.

FIXED_TIMESTAMP = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def patch_utcnow(monkeypatch):
    """Replace ``_utcnow`` in the service module with a deterministic value."""
    monkeypatch.setattr("life_graph.services.transcript_distiller._utcnow", lambda: FIXED_TIMESTAMP)


def test_build_transcript_snapshot_basic(patch_utcnow):
    session = SimpleNamespace(tool="gpt-4", external_id="sess123", tenant_id="tenantX")
    turns = [
        {"role": "user", "text": "Hello", "ts": "2023-01-01T00:00:00Z"},
        {
            "role": "assistant",
            "text": "sk-12345678901234567890",
            "ts": "2023-01-01T00:01:00Z",
        },
    ]
    mem_ids = [uuid.UUID("00000000-0000-0000-0000-000000000001")]

    snapshot = build_transcript_snapshot(session, turns, mem_ids)
    assert isinstance(snapshot, bytes)
    data = json.loads(snapshot.decode("utf-8"))

    assert data["tool"] == "gpt-4"
    assert data["external_id"] == "sess123"
    assert data["tenant_id"] == "tenantX"
    assert data["distilled_at"] == FIXED_TIMESTAMP.isoformat()

    assert len(data["turns"]) == 2
    # The assistant turn should be redacted by the ``redact`` helper
    assistant_text = data["turns"][1]["text"]
    assert "\u00abREDACTED:openai_key\u00bb" in assistant_text
    # The user turn should remain unchanged
    assert data["turns"][0]["text"] == "Hello"
    # Timestamps are preserved
    assert data["turns"][0]["ts"] == "2023-01-01T00:00:00Z"
    assert data["turns"][1]["ts"] == "2023-01-01T00:01:00Z"

    # Memory IDs are stringified
    assert data["distilled_memory_ids"] == ["00000000-0000-0000-0000-000000000001"]


def test_build_transcript_snapshot_empty(patch_utcnow):
    session = SimpleNamespace(tool="gpt-4", external_id="sess123", tenant_id="tenantX")
    snapshot = build_transcript_snapshot(session, [], [])
    data = json.loads(snapshot.decode("utf-8"))
    assert data["turns"] == []
    assert data["distilled_memory_ids"] == []
    assert data["distilled_at"] == FIXED_TIMESTAMP.isoformat()


def test_redaction_of_env_secret(patch_utcnow):
    session = SimpleNamespace(tool="gpt-4", external_id="sess123", tenant_id="tenantX")
    turns = [{"role": "user", "text": "API_TOKEN=secret_value", "ts": "2023-01-01T00:02:00Z"}]
    snapshot = build_transcript_snapshot(session, turns, [])
    data = json.loads(snapshot.decode("utf-8"))
    redacted = data["turns"][0]["text"]
    # The value should be replaced with the env_secret marker
    assert "\u00abREDACTED:env_secret\u00bb" in redacted
    assert "API_TOKEN=" in redacted  # prefix preserved
    assert redacted == "API_TOKEN=\u00abREDACTED:env_secret\u00bb"


# Ensure that the redact function itself behaves as expected for the secret
# pattern used above.  This is a sanity check that the test is exercising the
# correct behaviour.


def test_redact_env_secret():
    text = "API_TOKEN=secret_value"
    assert redact(text) == "API_TOKEN=\u00abREDACTED:env_secret\u00bb"


# Ensure that an openai key is redacted correctly.


def test_redact_openai_key():
    text = "sk-12345678901234567890"
    assert "\u00abREDACTED:openai_key\u00bb" in redact(text)


"""End of tests."""
