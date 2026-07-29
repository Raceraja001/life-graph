"""Conversation ORM models exist with the expected columns."""

from life_graph.models.db import Conversation, ConversationMessage


def test_conversation_columns():
    cols = Conversation.__table__.columns.keys()
    assert {"id", "tenant_id", "title", "created_at", "updated_at"} <= set(cols)


def test_conversation_message_columns():
    cols = ConversationMessage.__table__.columns.keys()
    assert {
        "id", "conversation_id", "tenant_id", "role", "content",
        "cited_memory_ids", "model", "created_at",
    } <= set(cols)
