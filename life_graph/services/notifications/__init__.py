"""Reaching the owner: notifications, their buttons, and the delivery channels.

- approval: tell the owner a new approval needs them (was approval_notifications)
- due: the owner's due items as phone notifications (was due_notifications)
- actions: buttons on the phone's notifications (was notification_actions)
- push_delivery, webpush: the daily brief over Web Push (VAPID)
- telegram_delivery, telegram_binding: the brief over Telegram; chat pairing

Grouped here 2026-11-18; they were flat modules in life_graph/services/.
The old-name aliases
were deleted on 2026-11-24 (audit L1). Nothing is imported here, so
importing one submodule loads only that one.
"""
