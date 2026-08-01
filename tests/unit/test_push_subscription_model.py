"""Push subscription model + VAPID settings exist."""

from life_graph.config import settings
from life_graph.models.db import PushSubscription


def test_vapid_settings_exist():
    assert hasattr(settings, "vapid_public_key")
    assert hasattr(settings, "vapid_private_key")
    assert hasattr(settings, "vapid_subject")


def test_push_subscription_columns():
    cols = PushSubscription.__table__.columns.keys()
    assert {"id", "tenant_id", "endpoint", "p256dh", "auth", "user_agent", "created_at"} <= set(cols)
