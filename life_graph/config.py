"""Application configuration using Pydantic Settings.

Supports multi-tenant SaaS mode with service-to-service auth,
Redis, rate limiting, and environment profiles.
"""

from __future__ import annotations

import json
import logging
import os

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Life Graph application settings.

    All settings can be overridden via environment variables
    prefixed with LIFE_GRAPH_ (e.g., LIFE_GRAPH_DATABASE_URL).
    """

    # ── Application ────────────────────────────────────
    app_name: str = "Life Graph"
    version: str = "1.0.0"
    environment: str = "development"  # development | staging | production
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "text"  # text (dev) | json (prod)

    # ── Authentication (Service-to-Service) ────────────
    api_key: str | None = None  # Legacy single key (dev mode)
    service_api_keys: str = ""  # Comma-separated: "key1,key2,key3"

    # ── Database ───────────────────────────────────────
    database_url: str = "postgresql+asyncpg://life_graph:life_graph@localhost:5432/life_graph"
    database_url_sync: str = "postgresql://life_graph:life_graph@localhost:5432/life_graph"
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)

    # ── Redis ──────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Knowledge Graph (Apache AGE) ───────────────────
    graph_enabled: bool = True
    """Whether the Apache AGE knowledge graph is available.

    AGE is a *compiled* Postgres extension needing ``shared_preload_libraries
    = age``, so it cannot be installed on managed Postgres (Supabase, Neon,
    RDS) or on the stock ``pgvector/pgvector:pg16`` image. Setting this to
    ``False`` short-circuits every graph call to an empty result instead of a
    connection attempt, and search degrades from vector+BM25+graph to
    vector+BM25. Nothing is lost in correctness: the graph leg only ever adds
    a proximity *boost* on top of the vector+BM25 score, so ranking is
    unchanged in kind, only in the ordering of entity-adjacent hits. Leave it
    ``True`` on a self-hosted server built from ``Dockerfile.postgres``; the
    runtime probes for AGE anyway and disables itself if it is missing."""

    # ── Embeddings ─────────────────────────────────────
    # Modern multilingual local embedder (D6). Dimension is the single source of
    # truth for the pgvector columns (Vector(settings.embedding_dimension)) and
    # the null-and-rebuild migration — keep the two in sync when swapping models.
    # When no embedding backend is reachable the service used to return empty
    # vectors and log a warning, so semantic search silently stopped working
    # while ingestion still reported success. For a memory system that is the
    # wrong failure mode: refuse to start instead. Set false to opt into the
    # degraded mode deliberately (e.g. a keyword-only deployment).
    require_embedding_backend: bool = True
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    # ── LLM (via LiteLLM) ─────────────────────────────
    # Primary "cheap" model for extraction + synthesis. A free OpenRouter model
    # is the default so a keyless self-host works out of the box; ResilientLLM
    # fails over to `llm_fallback_chain` from here. Override via LIFE_GRAPH_LLM_MODEL_CHEAP.
    llm_model_cheap: str = "openrouter/openai/gpt-oss-20b:free"
    llm_model_expensive: str = "gemini/gemini-3.6-flash"
    llm_daily_budget_usd: float = 1.0

    # ── Proactive Recall ───────────────────────────────
    recall_max_session_start: int = 5
    recall_max_during_session: int = 2
    recall_cooldown_days: int = 7
    recall_confidence_threshold: float = 0.7

    # ── Progressive disclosure ─────────────────────────
    # Two halves of the same protocol: an index line names a memory cheaply,
    # then a batch expand fetches the ones that matter.
    #
    # How much of a memory's text a compact index line carries when search or
    # recall is called with index_only. Long enough to recognise a memory,
    # short enough that the line costs ~12 tokens instead of the ~150 a full
    # memory object costs.
    recall_index_content_chars: int = 120
    # Cap on one POST /api/v1/memories/batch expand. Recall hands back at most
    # a few dozen index lines, so a caller with a legitimate reason to expand
    # more than this is really asking for a list endpoint.
    memory_batch_max: int = 50

    # ── Agent drivers ──────────────────────────────────
    driver_land_verified_work: bool = True
    """Commit a verified dispatch onto an ``lg/task-<id>`` branch.

    The dispatch worktree is detached and removed unconditionally after the
    run, so without this a verified change is deleted and the pipeline
    reports success having landed nothing. Landing never merges, never
    pushes, and never touches the default branch -- it leaves a reviewable
    branch for the approval step."""

    # ── Decay ──────────────────────────────────────────
    decay_archive_threshold: float = 0.01
    """Effective-importance floor below which removal is *proposed*.

    A memory's effective importance is ``importance * exp(-decay_rate *
    days_since_activity)``. Falling below this floor makes it a candidate for
    an archive approval -- nothing is archived without one. With the default
    ``memories.decay_rate`` of 0.0217 the horizon is ~180 days since last
    activity for importance 0.5, ~212 days for 1.0. Recall never touches this:
    ranking demotes stale memories on its own recency curve."""

    decay_proposal_limit: int = 50
    # Unreviewed memories older than this are rejected by the nightly decay job
    # (reversible: approve brings one back). 0 = keep waiting forever.
    pending_memory_expiry_days: int = 14
    # The local model that decides which searched memories answer a question
    # (services/memory_retrieval.py). Small is enough for "does this note help",
    # and it shares the GPU with speech. Empty = lm_extraction_model.
    memory_judge_model: str = ""
    """Most archive proposals one decay sweep may queue for a tenant.

    Decay proposes rather than archives, so an unbounded first sweep over a
    long-neglected corpus would bury the approval queue. Lowest effective
    importance first, so the clearest candidates surface soonest."""
    decay_default_lambda: float = 0.1

    # ── Deduplication ──────────────────────────────────
    dedup_enabled: bool = True
    dedup_threshold: float = 0.92  # cosine similarity threshold for near-duplicate detection
    # Contradiction check (services/contradiction.py): only active memories at
    # or above this cosine similarity to a new fact are compared with it. Was a
    # hard-coded 0.75 in the module until 2026-10-22.
    contradiction_similarity_threshold: float = 0.75

    # Merge suggestions: nightly, additive. Active pairs whose similarity lands in
    # [merge_review_low, dedup_threshold) coexist today (below the auto-merge line);
    # the producer queues them as merge approvals for the user to confirm.
    merge_review_low: float = 0.85
    merge_suggest_scan_limit: int = 200  # max active memories scanned per tenant per run

    # ── Capture Quality ──────────────────────────────────────
    capture_llm_clean: bool = True  # LLM as primary extractor on the capture path
    extraction_language_guard: bool = True  # skip English NER on non-Latin text
    extraction_tag_only_entities: bool = True  # entities/tech become tags, not memories
    extraction_min_confidence: float = 0.45  # drop facts below this before storing
    extraction_llm_min_words: int = 20  # legacy 3-tier LLM gate (non-capture callers)
    extraction_llm_confidence_threshold: float = 0.5  # legacy 3-tier LLM gate

    # Surfaces whose captures are an activity trail, not content: the event row
    # is kept, but extraction, memory storage and the decision/procedure regexes
    # are skipped. Without this, every tool call became several LLM-written
    # "facts" about shell commands, which drowned real memories in the review
    # queue and in recall. Comma-separated; empty string extracts everything.
    # assistant_message too: the assistant's own replies narrate work in hand
    # and produced 3,502 of 3,668 pending memories (2026-10-22). The owner's
    # memory is learnt from the owner's words; the replies stay in the trail.
    capture_no_extract_surfaces: str = "tool_exhaust,assistant_message"

    # ── Cold Start ─────────────────────────────────────
    cold_start_min_memories: int = 50

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

    # ── MinIO / Object Storage ─────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "life-graph"

    # ── LM Studio (local inference — embeddings + extraction)
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_api_key: str = "lm-studio"
    lm_extraction_model: str = "qwen2.5-3b-instruct"
    lm_synthesis_model: str = "qwen2.5-coder-7b-instruct"
    lm_embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    use_local_llm: bool = True
    lm_structured_output: bool = True
    """Constrain local extraction output to its JSON schema (``json_schema``
    response format). Supported by LM Studio and Ollama >= 0.5. Without it,
    small models often echo the schema instead of answering (2/8 usable on
    qwen3:4b vs 8/8 constrained). A runtime that rejects it gets one retry in
    the older ``json_object`` mode; set false to skip straight to that."""
    lm_reasoning_effort: str | None = None
    """Sent as ``reasoning_effort`` on local chat calls when set. Use "none" for
    thinking models served by Ollama (Qwen3, gpt-oss): without it they can burn
    the entire token budget on hidden reasoning and return empty content."""

    # ── OpenRouter (cloud inference — fast synthesis) ──
    openrouter_api_key: str = ""  # Set LIFE_GRAPH_OPENROUTER_API_KEY
    openrouter_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat"
    use_hybrid_llm: bool = False

    # ── Vertex AI (cloud inference — Gemini via a separate GCP project's
    # billing/quota; additive only, does not replace the OpenRouter/direct-
    # Gemini settings above) ──
    vertex_project: str = "work-update-467706"
    vertex_location: str = "global"
    vertex_credentials_path: str = ""  # Set LIFE_GRAPH_VERTEX_CREDENTIALS_PATH

    # ── Personal AI: Advisor ──────────────────────────────────
    advisor_models: str = "openrouter/openai/gpt-4o-mini,openrouter/deepseek/deepseek-chat,openrouter/meta-llama/llama-3.1-8b-instruct"
    advisor_timeout_seconds: int = 10
    advisor_max_cost_per_query: float = 0.01

    # ── Resilient LLM failover ────────────────────
    llm_fallback_chain: str = "openrouter/deepseek/deepseek-chat,gemini/gemini-3.5-flash-lite"
    llm_cooldown_429_seconds: int = 60
    llm_cooldown_error_seconds: int = 30
    llm_cooldown_max_seconds: int = 900
    llm_health_ttl_seconds: int = 3600
    llm_paid_fallback_model: str | None = None

    # ── OmniRoute (local multi-provider LLM gateway — its own 4-tier
    # auto-fallback across subscription/API/cheap/free providers behind one
    # OpenAI-compatible endpoint). Additive to the free chain above, not a
    # replacement: ResilientLLM already does ordered failover + cooldowns +
    # health tracking, so this is ONE more entry in that chain rather than a
    # second competing router. Empty api key = not configured, entry never
    # added to the chain. Get a key from the OmniRoute dashboard
    # (http://localhost:20128 by default) under Endpoints.
    omniroute_api_key: str = ""  # Set LIFE_GRAPH_OMNIROUTE_API_KEY
    omniroute_url: str = "http://localhost:20128/v1"
    omniroute_model: str = "openai/auto"

    # ── Personal AI: Research ────────────────────────────
    research_stale_days: int = 30
    research_max_per_run: int = 5
    research_monthly_budget_usd: float = 0.60
    research_confidence_threshold: float = 0.7

    # ── The Governor: unified budget kernel (D7.3) ───────
    # One monthly cap over all autonomous spenders. Autonomous spend is
    # throttled (low-priority first) past the soft threshold and denied at the
    # cap; interactive/user-initiated requests are never blocked.
    monthly_budget_usd: float = 10.0
    budget_soft_threshold: float = 0.8

    # ── Shadow Mode: dry-run rung on the autonomy ladder (D7.4) ──
    # New autonomous actors record 'would-have-done' reports instead of acting,
    # until they soak long enough and are graded well enough to graduate.
    shadow_mode_enabled: bool = True
    shadow_min_days: int = 14
    shadow_min_samples: int = 5
    shadow_good_rate: float = 0.8

    # ── Impact Scoring (Feature 5) ─────────────────────
    impact_boost_on_success: float = 0.1
    impact_penalty_on_failure: float = 0.05
    impact_default: float = 0.5

    # ── Rate Limiting & Tenant Plans ───────────────────
    default_plan: str = "free"
    tenant_plans: str = "{}"  # JSON: {"tenant_abc": "pro", "tenant_def": "free"}

    # ── MCP (Model Context Protocol) Client Bridge ──────
    # JSON list of external MCP servers to bridge tools from. Two shapes:
    # stdio (default, spawned as a subprocess of this process):
    #   {"name": ..., "command": ..., "args": [...], "env": {...}}
    # http (connects to an already-running server, e.g. its own container):
    #   {"name": ..., "transport": "http", "url": "http://host:port/mcp"}
    mcp_servers: str = "[]"

    # ── CORS ───────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # ── Agent System ──────────────────────────────────
    agent_llm_model: str = "gemini/gemini-3.6-flash"
    agent_llm_temperature: float = 0.7
    agent_llm_max_tokens: int = 4096
    agent_fallback_model: str = "gemini/gemini-3.5-flash-lite"
    agent_max_iterations: int = 5
    # Long runs (docs/specs/agent-condenser.md). The context window the
    # condenser budgets against: Ollama here serves every model at
    # OLLAMA_CONTEXT_LENGTH=32768 and silently drops the START of a longer
    # prompt. Per-model overrides are JSON, quoted as a whole in .env.
    agent_condenser_enabled: bool = True
    agent_context_tokens: int = 32768
    agent_context_tokens_by_model: str = "{}"
    agent_stuck_detection: bool = True

    # ── OS Kernel ──────────────────────────────────────────
    # Must stay > ProcessManager.MAX_DELEGATION_DEPTH (currently 5): each
    # delegate_to_persona(wait=True) hop blocks its parent's semaphore
    # permit while waiting on the child, so a full-depth delegation chain
    # needs depth+1 permits held simultaneously to avoid deadlocking until
    # the ~600s delegate timeout. ProcessManager asserts this at startup.
    kernel_max_concurrent_tasks: int = 8
    kernel_default_timeout: int = 300  # seconds
    kernel_default_max_retries: int = 2
    kernel_task_cleanup_days: int = 30  # archive tasks older than this
    kernel_enable_scheduler: bool = True
    kernel_max_consecutive_failures: int = 3

    # ── Tavily (web search tool) ──────────────────────
    tavily_api_key: str = ""  # Set LIFE_GRAPH_TAVILY_API_KEY
    # auto = SearXNG if searxng_url is set, then Tavily if keyed, then the
    # keyless DuckDuckGo HTML endpoint. Or name one: searxng|tavily|duckduckgo.
    web_search_provider: str = "auto"
    searxng_url: str = ""  # e.g. http://localhost:8888 (JSON format enabled)
    web_search_max_results: int = 6
    # Hosts agent fetches may reach even though they resolve to a private
    # address (services/safe_fetch.py). Comma-separated host names.
    fetch_allow_hosts: str = ""
    # Personas whose answers must cite URLs a tool returned in the same run
    # (services/sources.py). Comma-separated persona names.
    require_sources_personas: str = "scout,rex"

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

    # ── Langfuse (LLM tracing — auto-enabled by LiteLLM)
    langfuse_public_key: str = ""  # Set LIFE_GRAPH_LANGFUSE_PUBLIC_KEY
    langfuse_secret_key: str = ""  # Set LIFE_GRAPH_LANGFUSE_SECRET_KEY
    langfuse_host: str = "http://localhost:3001"

    # ── Observability ──────────────────────────────────
    metrics_enabled: bool = True

    # ── Self-Improving Agent ─────────────────────────
    # The loop learns capture extraction from the user's own review of the
    # memories it produces: approved facts (edited text where edited) are the
    # target, rejected ones are not. Candidates are few-shot variants of the
    # active prompt, run on the local extraction model — no cloud, no DSPy.
    self_improving_enabled: bool = False
    """Master switch for the nightly evaluate-and-optimize job."""
    self_improving_trace_enabled: bool = True
    """Record each local extraction (input, output, facts) as the loop's data.
    Cheap and independent of the switch above: data accumulates while the loop
    is off, so it has something to learn from when it is turned on."""
    self_improving_prompts_enabled: bool = True
    """Kill switch: false makes extraction ignore prompt_versions and use the
    built-in prompt, whatever is active."""
    eval_max_parallel: int = 5
    eval_accuracy_threshold_pct: float = 90.0
    optimization_min_improvement_pct: float = 2.0
    """Percentage points a candidate must beat the active prompt by, on the
    same held-out cases, before it is deployed."""
    optimization_max_regression_pct: float = 2.0
    optimization_max_few_shot: int = 3
    """Examples per few-shot candidate. Each one costs prompt tokens on every
    extraction, so small is deliberate."""
    optimization_candidates: int = 3
    """Candidate prompts tried per optimization run."""
    optimization_min_holdout: int = 20
    """Minimum held-out cases before a candidate may be deployed: a gate on a
    handful of cases would deploy noise."""
    eval_fact_match_threshold: float = 0.8
    """Cosine similarity at which a predicted fact counts as matching an
    expected one (fact_set_f1 scoring)."""
    eval_fact_pass_f1: float = 0.8
    """Per-case F1 at or above which an extraction case counts as passed."""
    eval_max_holdout_cases: int = 60
    """Most recent held-out cases kept active in the suite. Each optimization
    evaluates them once per candidate on the local model, so the cost has to
    stay bounded as reviews accumulate; older cases are deactivated, not lost."""

    # ── Agent Networks (Era 7) ────────────────────────────
    uzhavu_sync_url: str = "http://localhost:8001/api/v1/sync/preferences"
    internal_api_key: str = ""  # Set LIFE_GRAPH_INTERNAL_API_KEY

    # ── Ambient AI: Watchers (Era 6) ──────────────────────
    watcher_smtp_host: str = ""  # Set LIFE_GRAPH_WATCHER_SMTP_HOST
    watcher_smtp_port: int = 587
    watcher_smtp_user: str = ""
    watcher_smtp_password: str = ""
    watcher_smtp_from: str = "life-graph@localhost"
    watcher_digest_schedule: str = "0 8 * * *"  # Daily 8 AM
    watcher_webhook_secret: str = ""  # HMAC signing key for outgoing webhooks
    watcher_max_events_per_run: int = 100
    watcher_auto_disable_after_failures: int = 5

    # ── Autonomous AI (Era 8) ─────────────────────────────
    autonomy_trust_decay_days: int = 30  # Trust decays if no activity for this many days
    autonomy_trust_decay_rate: float = 0.05  # Decay per period
    autonomy_trust_failure_penalty: float = 0.5  # Multiply trust by this on failure
    autonomy_trust_success_boost: float = 0.02  # Add this on success
    autonomy_approval_timeout_hours: int = 24  # Auto-expire unapproved actions
    autonomy_max_auto_actions_per_hour: int = 10  # Rate limit for safe actions
    autonomy_max_blast_radius: int = 3  # Max files/services affected per auto-action
    autonomy_default_level: str = "L0"  # L0=ask everything, L1=safe auto, L2=moderate auto, L3=full

    # ── Agent Drivers ───────────────────────────────────
    driver_claude_code_bin: str = "claude"  # Claude Code CLI binary for the claude_code driver
    # Per-dispatch limit for the claude_code driver. The dispatcher's 300s
    # fallback cut a real plan-only run off mid-exploration of this repo;
    # 1200 matches the local driver.
    driver_claude_code_timeout_seconds: int = 1200
    # "oauth" = the personal Claude login (staged into the sandbox); "api_key"
    # = ANTHROPIC_API_KEY under Anthropic's commercial terms, required for a
    # service sold to others. Prefer the env var to this setting for the key.
    driver_claude_code_auth: str = "oauth"
    driver_claude_code_api_key: str = ""
    # OpenCode driver (drivers/opencode.py). Unavailable until the binary exists:
    #   npm install --prefix ~/.local/opencode opencode-ai
    driver_opencode_bin: str = "opencode"
    driver_opencode_model: str = "ollama/qwen3-coder:30b"
    driver_opencode_ollama_base: str = "http://localhost:11434/v1"
    driver_opencode_timeout_seconds: int = 1200
    # The host is not sandboxed for this driver, so OpenCode's shell stays
    # denied unless this is set. Tests run in the verifier sandbox regardless.
    driver_opencode_allow_bash: bool = False
    # A plan approves itself only for a project with auto_approve_plans set,
    # at most this many tasks, and every other rule in services/plan_policy.py.
    auto_plan_max_tasks: int = 3
    # Seconds a project's smoke_command may take after a deploy.
    post_deploy_smoke_timeout: int = 300
    # Idea -> app (services/bootstrap.py): where new apps are created (default:
    # the first tool root), and whether to create a private GitHub repo with gh
    # (off: a local bare repo stands in as origin).
    bootstrap_root: str = ""
    bootstrap_create_github: bool = False
    # Set false on a preview/secondary instance so it never even tries to be
    # the dev-task runner. Without it, the database advisory lock still keeps
    # it from running alongside the real one (services/dev_tasks.py).
    dev_task_runner_enabled: bool = True
    # Where queued coding work runs (services/compute_router.py). The one GPU
    # is the user's while he is active (speech models), so queued tasks then go
    # to a free cloud model or wait; local runs happen while he is away.
    # Code may leave the machine this way; personal data never does (the
    # cloud driver strips preferences/procedures/memories).
    dev_route_queue: bool = True
    # Free cloud coding models, in failover order. Only free ones are accepted
    # (openrouter/...:free, nvidia_nim/...); a model whose provider has no key
    # is skipped, so with no keys the cloud route is simply off.
    dev_cloud_models: str = (
        "openrouter/poolside/laguna-s-2.1:free,"
        "openrouter/nvidia/nemotron-3-super-120b-a12b:free,"
        "openrouter/cohere/north-mini-code:free"
    )
    # The user counts as active for this long after his last chat message,
    # Telegram message or voice capture.
    user_active_minutes: int = 30
    # Ollama model-name fragments that mean speech is in use (comma-separated).
    speech_models: str = "gemma3"
    ollama_api_base: str = "http://localhost:11434"
    # Local coding only in these hours of user_timezone, e.g. "23-7"; empty
    # means whenever the user is away.
    dev_local_hours: str = ""
    # OpenCode with a 30B model needs this much free RAM (WSL stalled with
    # swap full during a 30B run, 2026-10-17); below it the task waits.
    opencode_min_free_gb: float = 12.0
    # After the free cloud models are exhausted (rate limit), stop routing to
    # them for this long; the task goes back on the queue.
    cloud_rate_limit_cooldown_seconds: int = 3600
    # NVIDIA build.nvidia.com free API (LiteLLM's nvidia_nim/ provider).
    nvidia_nim_api_key: str = ""
    # Job 1, free LLM offers (services/llm_offers.py, docs/specs/free-llm-offers.md).
    # Tenants it runs for (comma-separated); empty = off.
    offers_tenants: str = ""
    # News searches for new free tiers, credits and promotions (one per line).
    offers_news_queries: str = (
        "free LLM API tier\n"
        "free LLM API credits developers\n"
        "new free model OpenRouter\n"
        "free AI inference API promotion"
    )
    offers_max_pages: int = 8  # new pages read per news scan
    offers_max_evals_per_day: int = 2  # coding benchmarks per day
    # Requests per provider per UTC day before the router skips it (JSON).
    # OpenRouter's free tier allows ~1000/day with credit on the account.
    provider_daily_limits: str = '{"openrouter": 900, "nvidia_nim": 1000}'
    # Jobs 6 and 10 (services/web_research.py, docs/specs/research-and-tech-watch.md).
    research_max_pages: int = 5  # result pages read for one question
    research_page_chars: int = 8_000  # text kept per page (all go to one worker)
    # Free cloud models to try first for research workers (comma-separated);
    # only reorders the free cloud list (services/workers.envelope_models).
    research_models: str = ""
    # Tech watch: tenants it runs for (comma-separated; empty = off) and the
    # topics, as JSON: topic name -> list of search queries, or -> {"queries":
    # [...], "kind": "model" | "tool", "max_memory_gb": N} to have findings of
    # another kind, or needing more memory, dropped in code ("{month}" becomes
    # e.g. "October 2026", see services/web_research.dated_queries).
    tech_watch_tenants: str = ""
    tech_watch_topics: str = (
        '{"Open models that fit 16 GB": {"kind": "model", "max_memory_gb": 16, "queries": ['
        '"new open weight model Ollama {month}", '
        '"new small open source LLM release {month}"]}, '
        '"AI coding agents": {"kind": "tool", "queries": ['
        '"AI coding agent new release {month}", '
        '"coding agent CLI new version {month}"]}}'
    )
    tech_watch_max_pages: int = 6  # new pages read per topic per day
    tech_watch_digest_per_topic: int = 6  # findings per topic in the Monday brief
    # Per-step content cap for recorded agent runs (services/trajectories.py).
    # One whole-file read can be megabytes; the real length is kept alongside.
    trajectory_step_max_chars: int = 16_000
    # Tenants whose agent runs are NOT recorded step by step (consent: a
    # customer may opt out). Comma-separated tenant ids.
    trajectory_opt_out_tenants: str = ""
    # Dissenting cheap-model review before an auto-verified task lands.
    # Off by default — pure LLM overhead until agents run unattended.
    driver_second_opinion_enabled: bool = False
    driver_second_opinion_model: str | None = None  # None = agent_llm_model
    # The second-opinion review before a code change lands unattended
    # (services/change_policy.py). Empty = the free cloud models, else the
    # local agent model; never a paid fallback. Code only leaves the machine.
    change_review_model: str = ""
    driver_pr_agent_bin: str = "pr-agent"  # the PR-Agent CLI backing the reviewer above
    # Draft the PR description from the landed diff (one model call per landed
    # task, best-effort -- falls back to the instruction + agent summary).
    driver_pr_description_enabled: bool = True
    # Give the driver the definitions/callers/callees of symbols its
    # instruction names, from a stdlib-ast graph of the worktree (no model).
    driver_code_context_enabled: bool = True
    driver_pr_description_model: str | None = None  # None = agent_llm_model
    # Where verifiers execute agent-written code (tests, linters). "none" runs
    # them on the host as this process's user; "docker" runs each check in a
    # locked-down container (life_graph/services/sandbox.py). With "docker",
    # a missing daemon or image makes checks inconclusive, never passing.
    # GitHub CLI used to push approved task branches and open PRs; it must be
    # logged in (`gh auth login`) as the user this process runs as.
    driver_gh_bin: str = "gh"
    verifier_sandbox: str = "none"
    verifier_sandbox_image: str = "life-graph-verifier:py3.12"
    # Projects whose registry sets sandbox_toolchain=node are checked here
    # instead (docker build -t life-graph-verifier:node22 docker/verifier-node).
    verifier_sandbox_node_image: str = "life-graph-verifier:node22"
    # Projects whose registry sets sandbox_toolchain=jvm (Kotlin, Java, Android
    # with Gradle) are checked here (docker build -t life-graph-verifier:jvm17
    # docker/verifier-jvm). Gradle and the Kotlin compiler need more memory.
    verifier_sandbox_jvm_image: str = "life-graph-verifier:jvm17"
    verifier_sandbox_jvm_memory: str = "6g"
    verifier_sandbox_cache_dir: str = ""  # cached project venvs; "" = ~/.cache/life-graph/...
    verifier_sandbox_memory: str = "4g"
    verifier_sandbox_cpus: str = "4"
    # Where the claude_code driver itself executes. "none" runs it on the
    # host as this process's user (scoped only by the CLI's own
    # --allowedTools/--permission-mode). "docker" runs it in a container
    # (life_graph/services/sandbox.py:run_driver) with the worktree mounted
    # read-write, only its own OAuth token available (a throwaway copy, not
    # the live ~/.claude), and no other host path visible. Unlike the
    # verifier sandbox this needs network (the CLI calls the Anthropic API),
    # so isolation is filesystem + capabilities, not network denial. With
    # "docker", a missing daemon or image fails the dispatch rather than
    # silently falling back to unsandboxed host execution.
    driver_claude_sandbox: str = "none"
    driver_claude_sandbox_image: str = "life-graph-claude-driver:latest"
    driver_claude_sandbox_memory: str = "4g"
    driver_claude_sandbox_cpus: str = "4"
    # The CLI's own OAuth token file, staged into a throwaway copy for each
    # sandboxed dispatch (life_graph/services/sandbox.py:stage_credentials).
    # Never mounted live — see driver_claude_sandbox's docstring above.
    driver_claude_code_creds_path: str = "~/.claude/.credentials.json"

    # ── Host Tools (run_command / file_read / file_write) ──
    # These tools execute against the host filesystem and shell. Every
    # control below is ENFORCED in life_graph/tools/_guards.py — the module
    # docstrings used to claim a "personal tenant only" restriction that no
    # code implemented.
    tool_shell_enabled: bool = True  # master switch for run_command
    # full = an arbitrary shell string (denylist only); allowlist = read-only
    # programs run without a shell (tools/shell_allowlist.py).
    tool_shell_mode: str = "full"
    # Tenants permitted to use host tools. Empty string = every tenant,
    # which is only sane for a single-tenant personal deployment.
    tool_privileged_tenants: str = "default"
    # Filesystem roots the file_* tools may touch. Empty = the home
    # directory only. Comma-separated absolute paths.
    tool_fs_roots: str = ""

    # ── Capture Spine: Interview + Daily Brief ─────────
    interview_max_questions_per_day: int = 3  # Hard daily budget — never nag
    interview_question_ttl_days: int = 7  # Unanswered questions expire after this
    brief_hour_utc: int = 2  # Daily brief composition hour (02:00 UTC ≈ 07:30 IST)

    # ── Web Push Notifications ──────────────────────────
    vapid_public_key: str = ""  # Set LIFE_GRAPH_VAPID_PUBLIC_KEY
    vapid_private_key: str = ""  # Set LIFE_GRAPH_VAPID_PRIVATE_KEY (VM only, never git)
    vapid_subject: str = "mailto:tolokanathan@gmail.com"  # VAPID contact

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

    # ── Invoices (services/invoices.py) ────────────────
    invoice_seller_name: str = ""  # shown on invoices and signed under emails
    invoice_seller_details: str = ""  # address, tax id… separated by "|"

    # ── Startup Seeding ─────────────────────────────────
    # Which tenants get the built-in personas, ambient jobs and safety rules at
    # startup. This was the literal "default" in three places, so every other
    # tenant came up with an empty action_safety_rules table — and the
    # classifier treats an action it cannot match as dangerous, which left a
    # real tenant unable to take a single autonomous action with nothing in the
    # logs to say why.
    #
    # Named tenants rather than every tenant seen, because seeding also sets
    # the ambient project to L1 (safe actions run without asking). Granting
    # that is a decision, so it is made here, deliberately.
    seed_tenants: str = "default"

    # ── Derived Properties ─────────────────────────────

    @property
    def service_api_keys_list(self) -> list[str]:
        """Parse comma-separated service API keys."""
        if not self.service_api_keys:
            return []
        return [k.strip() for k in self.service_api_keys.split(",") if k.strip()]

    @property
    def tenant_plans_dict(self) -> dict[str, str]:
        """Parse JSON tenant plan mapping.

        A malformed value silently demoted every tenant to the free plan and
        its 60 requests a minute. The cause here was a `.env` line written as
        ``LIFE_GRAPH_TENANT_PLANS={"a":"enterprise"}``: dotenv strips the inner
        quotes from an unquoted value, so the setting arrived as
        ``{a:enterprise}``, failed to parse, and the only visible symptom was
        the dashboard 429-ing itself. Quote the whole value in `.env`. Either
        way the failure is now logged rather than swallowed.
        """
        if not self.tenant_plans:
            return {}
        try:
            return json.loads(self.tenant_plans)
        except json.JSONDecodeError:
            logger.warning(
                "LIFE_GRAPH_TENANT_PLANS is not valid JSON (%r) — every tenant "
                "falls back to the %r plan. In .env, quote the whole value: "
                'LIFE_GRAPH_TENANT_PLANS=\'{"tenant":"enterprise"}\'',
                self.tenant_plans,
                self.default_plan,
            )
            return {}

    @property
    def mcp_servers_list(self) -> list[dict]:
        """Parse JSON list of configured external MCP servers."""
        try:
            parsed = json.loads(self.mcp_servers) if self.mcp_servers else []
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def tool_privileged_tenants_list(self) -> list[str]:
        """Tenants allowed to use host tools; empty list means no restriction."""
        return [t.strip() for t in self.tool_privileged_tenants.split(",") if t.strip()]

    @property
    def trajectory_opt_out_tenants_list(self) -> list[str]:
        """Tenants opted out of step recording (services/trajectories.py)."""
        return [t.strip() for t in self.trajectory_opt_out_tenants.split(",") if t.strip()]

    @property
    def tool_fs_roots_list(self) -> list[str]:
        """Roots the file_* tools may touch. Defaults to the home directory."""
        roots = [r.strip() for r in self.tool_fs_roots.split(",") if r.strip()]
        return roots or [os.path.expanduser("~")]

    @property
    def capture_no_extract_surfaces_list(self) -> list[str]:
        """Surfaces that are logged as capture events but never extracted."""
        return [s.strip() for s in self.capture_no_extract_surfaces.split(",") if s.strip()]

    def context_tokens_for(self, model: str | None) -> int:
        """The context window to budget a run against (agent_context_tokens_by_model)."""
        import json

        try:
            overrides = json.loads(self.agent_context_tokens_by_model or "{}")
        except ValueError:
            overrides = {}
        value = overrides.get(model or "") if isinstance(overrides, dict) else None
        return int(value) if isinstance(value, int) and value > 0 else self.agent_context_tokens

    @property
    def seed_tenants_list(self) -> list[str]:
        """Tenants to seed at startup, in the order given."""
        return [t.strip() for t in self.seed_tenants.split(",") if t.strip()]

    @property
    def llm_fallback_chain_list(self) -> list[str]:
        """Parse comma-separated free-model fallback chain."""
        return [m.strip() for m in self.llm_fallback_chain.split(",") if m.strip()]

    @property
    def dev_cloud_models_list(self) -> list[str]:
        """Parse the comma-separated free cloud coding models."""
        return [m.strip() for m in self.dev_cloud_models.split(",") if m.strip()]

    @property
    def offers_tenants_list(self) -> list[str]:
        """Parse the tenants the free-LLM-offers job runs for."""
        return [t.strip() for t in self.offers_tenants.split(",") if t.strip()]

    @property
    def offers_news_queries_list(self) -> list[str]:
        """Parse the news queries, one per line."""
        return [q.strip() for q in self.offers_news_queries.splitlines() if q.strip()]

    @property
    def provider_daily_limits_map(self) -> dict[str, int]:
        """Parse the per-provider daily request limits; a bad value means none."""
        import json

        try:
            raw = json.loads(self.provider_daily_limits or "{}")
            return {str(k): int(v) for k, v in raw.items()}
        except (ValueError, TypeError, AttributeError):
            return {}

    @property
    def research_models_list(self) -> list[str]:
        """Parse the research workers' preferred free models."""
        return [m.strip() for m in self.research_models.split(",") if m.strip()]

    @property
    def tech_watch_tenants_list(self) -> list[str]:
        """Parse the tenants the tech watch runs for."""
        return [t.strip() for t in self.tech_watch_tenants.split(",") if t.strip()]

    @property
    def tech_watch_topics_map(self) -> dict[str, list[str]]:
        """Parse the tech-watch topics (name -> queries); a bad value means none."""
        return {name: spec["queries"] for name, spec in self.tech_watch_topic_specs.items()}

    @property
    def tech_watch_topic_specs(self) -> dict[str, dict]:
        """Each topic's queries and rules: {"queries", "kind", "max_memory_gb"}."""
        import json

        try:
            raw = json.loads(self.tech_watch_topics or "{}")
        except ValueError:
            return {}
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict] = {}
        for name, value in raw.items():
            spec = value if isinstance(value, dict) else {"queries": value}
            queries = spec.get("queries")
            if not str(name).strip() or not isinstance(queries, list):
                continue
            kind = spec.get("kind") if spec.get("kind") in ("model", "tool") else None
            try:
                limit = float(spec["max_memory_gb"]) if spec.get("max_memory_gb") else None
            except (TypeError, ValueError):
                limit = None
            out[str(name).strip()[:120]] = {
                "queries": [str(q).strip() for q in queries if str(q).strip()],
                "kind": kind,
                "max_memory_gb": limit,
            }
        return out

    @property
    def speech_models_list(self) -> list[str]:
        """Parse the comma-separated speech model-name fragments."""
        return [m.strip().lower() for m in self.speech_models.split(",") if m.strip()]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    # ── Plan Limits ────────────────────────────────────

    PLAN_LIMITS: dict[str, dict] = {
        "free": {
            "requests_per_min": 60,
            "max_memories": 1_000,
            "max_ask_per_day": 50,
        },
        "pro": {
            "requests_per_min": 300,
            "max_memories": 100_000,
            "max_ask_per_day": 500,
        },
        "enterprise": {
            "requests_per_min": 0,  # 0 = unlimited
            "max_memories": 0,
            "max_ask_per_day": 0,
        },
    }

    def get_plan_for_tenant(self, tenant_id: str) -> str:
        """Get the plan name for a given tenant."""
        return self.tenant_plans_dict.get(tenant_id, self.default_plan)

    def get_plan_limits(self, tenant_id: str) -> dict:
        """Get rate limit config for a tenant based on their plan."""
        plan = self.get_plan_for_tenant(tenant_id)
        return self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS["free"])

    model_config = {
        "env_prefix": "LIFE_GRAPH_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()


def sqlalchemy_sync_url(url: str) -> str:
    """*url* with the psycopg2 driver named, for a synchronous SQLAlchemy engine.

    SQLAlchemy 2.1 changed what a bare ``postgresql://`` URL means: its
    default driver went from psycopg2 to psycopg (v3). We depend on
    psycopg2-binary, so a fresh install (CI) failed migrations with "No module
    named 'psycopg'" while older local installs worked. Naming the driver
    makes the URL mean the same thing on every SQLAlchemy version. Only for
    SQLAlchemy: plain ``psycopg2.connect`` still wants the bare scheme.
    """
    for bare in ("postgresql://", "postgres://"):
        if url.startswith(bare):
            return "postgresql+psycopg2://" + url[len(bare) :]
    return url
