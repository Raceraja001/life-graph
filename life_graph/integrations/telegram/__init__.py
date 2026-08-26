"""Telegram bridge — phone as a capture surface and a delivery channel.

See docs/specs/telegram-bridge.md. Deliberately no re-exports at package level:
``poller`` starts a background loop and ``router`` pulls in the capture spine,
so importing either from here would drag both into any module that only wanted
the client.
"""
