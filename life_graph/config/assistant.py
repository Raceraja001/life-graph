"""The personal assistant: voice, connectors, watchers, brief, push, Telegram.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from pydantic import BaseModel


class AssistantSettings(BaseModel):
    """The personal assistant: voice, connectors, watchers, brief, push, Telegram."""

    # ── Multi-Modal (Voice / Whisper) ──────────────────
    whisper_model: str = "small"
    # Local speech-to-text over an OpenAI-compatible /v1/audio/transcriptions
    # server (speaches on :8010, the same one that speaks replies). When set,
    # local transcription goes there instead of loading faster-whisper into
    # this process. Must be on this machine or the private network: the phone
    # app's voice is transcribed "locally only" (services/multimodal.py).
    stt_base_url: str = ""  # LIFE_GRAPH_STT_BASE_URL, e.g. http://localhost:8010
    stt_model: str = "deepdml/faster-whisper-large-v3-turbo-ct2"
    # Cloudflare Workers AI transcription — preferred when BOTH are set
    # (handles Tamil/English code-switching via whisper-large-v3-turbo);
    # otherwise falls back to local faster-whisper. Token needs only the
    # "Workers AI" permission.
    cf_account_id: str = ""  # Set LIFE_GRAPH_CF_ACCOUNT_ID
    cf_ai_token: str = ""  # Set LIFE_GRAPH_CF_AI_TOKEN
    groq_api_key: str = ""  # LIFE_GRAPH_GROQ_API_KEY — Groq speech-to-text (fastest)

    # ── Connectors (calendar, email, … — docs/specs/connectors.md) ───────────
    # Replaces the unused google_credentials_json / google_delegated_user stubs:
    # accounts are added through /connectors, credentials live in files below.
    connectors_enabled: bool = True
    # The user's timezone (IANA name): "today" in the brief and the calendar
    # tools means this zone's day, not UTC's.
    user_timezone: str = "UTC"
    # Per-account credential files (mode 600), outside the repo and the DB.
    connector_secrets_dir: str = "~/.config/life-graph/connectors"
    # Extra LiteLLM model prefixes that run on this machine (comma-separated);
    # ollama/, ollama_chat/ and lm_studio/ are built in. Anything else is
    # treated as cloud when deciding what connector data a model may see.
    connector_local_model_prefixes: str = ""
    connector_sync_minutes: int = 15
    connector_email_retention_days: int = 90
    connector_event_past_days: int = 90
    connector_event_future_days: int = 365
    # "Waiting on you": unanswered direct mail older than this…
    connector_needs_reply_min_hours: int = 24
    # …and younger than this (older threads are treated as dropped, not urgent).
    connector_needs_reply_max_days: int = 14
    # Messages summarised per sync by the local model (the rest wait a round).
    connector_summaries_per_sync: int = 40
    # Bills found in mail, off the machine: "details" (payee, type, due date —
    # never the amount) or "counts" ("2 bills due this week").
    connector_bills_cloud: str = "details"
    # Where Google sends the browser back after sign-in: this API's own
    # address as the signing-in browser reaches it (a Desktop OAuth client
    # accepts any localhost port).
    connector_oauth_redirect_base: str = "http://localhost:8080"
    # Where the callback sends the browser afterwards (the dashboard).
    connector_oauth_return_url: str = "http://localhost:3001/settings"

    # ── Ambient AI: Watchers (Era 6) ──────────────────────
    watcher_smtp_host: str = ""  # Set LIFE_GRAPH_WATCHER_SMTP_HOST
    watcher_smtp_port: int = 587
    watcher_smtp_user: str = ""
    watcher_smtp_password: str = ""
    watcher_smtp_from: str = "life-graph@localhost"
    watcher_digest_schedule: str = "0 8 * * *"  # Daily 8 AM
    watcher_webhook_secret: str = ""  # HMAC signing key for outgoing webhooks
    watcher_max_events_per_run: int = 100
    # Important watcher events that were queued instead of sent
    # (watchers/notification_engine.py route_event) are gathered into one
    # notification held for the daily brief, once a day just before it
    # (workers/watcher_queue.py). One queued longer than this is marked
    # expired and never sent: news that old is noise, and it keeps a backlog
    # from flooding the brief. A day between runs plus two hours' slack, so
    # nothing queued just after one run has expired by the next.
    watcher_queue_max_age_hours: int = 26
    # At most this many per tenant per run; the rest stay queued.
    watcher_queue_max_per_run: int = 20
    watcher_auto_disable_after_failures: int = 5

    # ── Capture Spine: Interview + Daily Brief ─────────
    interview_max_questions_per_day: int = 3  # Hard daily budget — never nag
    interview_question_ttl_days: int = 7  # Unanswered questions expire after this
    brief_hour_utc: int = 2  # Daily brief composition hour (02:00 UTC ≈ 07:30 IST)
    # Bills, to-dos, expiring documents and timed reminders written as
    # notifications for the phone to post (services/notifications/due.py).
    # False keeps the phone quiet about them; the brief still lists them.
    phone_due_notifications: bool = True
    # Local hour (user_timezone) after which the daily "N study cards due" nudge
    # may go to the phone (services/study_nudge.py); -1 turns it off.
    study_nudge_hour: int = 18

    # ── Web Push Notifications ──────────────────────────
    vapid_public_key: str = ""  # Set LIFE_GRAPH_VAPID_PUBLIC_KEY
    vapid_private_key: str = ""  # Set LIFE_GRAPH_VAPID_PRIVATE_KEY (VM only, never git)
    # VAPID contact (RFC 8292: a mailto: or https: URI). The default is a
    # placeholder; a deployment sets its own via LIFE_GRAPH_VAPID_SUBJECT.
    vapid_subject: str = "mailto:owner@example.invalid"

    # ── Telegram Bridge ─────────────────────────────────
    # Empty token disables the bridge entirely: the poller never starts and the
    # notification channel reports itself unconfigured rather than failing.
    telegram_bot_token: str = ""  # Set LIFE_GRAPH_TELEGRAM_BOT_TOKEN (never git)
    telegram_poll_timeout: int = 25  # getUpdates long-poll seconds; < Telegram's 50s cap
    telegram_rate_limit_per_min: int = 20  # Inbound messages accepted per bound chat
    # Approving a dangerous action from a chat app is off by default: one
    # mistapped message should not be sufficient authority to run something
    # irreversible. /pending stays available regardless — reading is not deciding.
    telegram_allow_approvals: bool = False
    # Conversation from Telegram (/ask, /chat — services/assistant_chat.py).
    # Jarvis, the lead (services/lead.py); "assistant" is retired.
    telegram_assistant_persona: str = "jarvis"
    # The local model Jarvis runs personal requests on (services/lead.py).
    # Empty = agent_llm_model when that is local, else ollama_chat/qwen3:14b.
    lead_local_model: str = ""
    telegram_ask_timeout_seconds: int = 240
    # Spoken replies: an OpenAI-compatible /v1/audio/speech server (speaches
    # on :8010 locally). Empty = text replies only.
    tts_base_url: str = ""
    tts_model: str = "speaches-ai/Kokoro-82M-v1.0-ONNX"
    tts_voice: str = "af_heart"
    # speaches offers mp3|flac|wav|pcm (no opus); Telegram voice notes take mp3 or ogg/opus.
    tts_format: str = "mp3"

    # ── Invoices (services/finance/invoices.py) ────────────────
    invoice_seller_name: str = ""  # shown on invoices and signed under emails
    invoice_seller_details: str = ""  # address, tax id… separated by "|"
