"""Application configuration using Pydantic Settings.

Supports multi-tenant SaaS mode with service-to-service auth,
Redis, rate limiting, and environment profiles.
"""

from __future__ import annotations

import json

from pydantic import Field
from pydantic_settings import BaseSettings


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

    # ── Embeddings ─────────────────────────────────────
    embedding_model: str = "all-mpnet-base-v2"
    embedding_dimension: int = 768

    # ── LLM (via LiteLLM) ─────────────────────────────
    llm_model_cheap: str = "gemini/gemini-2.0-flash"
    llm_model_expensive: str = "gemini/gemini-2.5-pro"
    llm_daily_budget_usd: float = 1.0

    # ── Proactive Recall ───────────────────────────────
    recall_max_session_start: int = 5
    recall_max_during_session: int = 2
    recall_cooldown_days: int = 7
    recall_confidence_threshold: float = 0.7

    # ── Decay ──────────────────────────────────────────
    decay_archive_threshold: float = 0.01
    decay_default_lambda: float = 0.1

    # ── Deduplication ──────────────────────────────────
    dedup_enabled: bool = True
    dedup_threshold: float = 0.92  # cosine similarity threshold for near-duplicate detection

    # ── Cold Start ─────────────────────────────────────
    cold_start_min_memories: int = 50

    # ── Multi-Modal (Voice / Whisper) ──────────────────
    whisper_model: str = "small"

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

    # ── OpenRouter (cloud inference — fast synthesis) ──
    openrouter_api_key: str = ""  # Set LIFE_GRAPH_OPENROUTER_API_KEY
    openrouter_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat"
    use_hybrid_llm: bool = False

    # ── Personal AI: Advisor ──────────────────────────────────
    advisor_models: str = "openrouter/openai/gpt-4o-mini,openrouter/deepseek/deepseek-chat,openrouter/meta-llama/llama-3.1-8b-instruct"
    advisor_timeout_seconds: int = 10
    advisor_max_cost_per_query: float = 0.01

    # ── Personal AI: Research ────────────────────────────
    research_stale_days: int = 30
    research_max_per_run: int = 5
    research_monthly_budget_usd: float = 0.60
    research_confidence_threshold: float = 0.7

    # ── Impact Scoring (Feature 5) ─────────────────────
    impact_boost_on_success: float = 0.1
    impact_penalty_on_failure: float = 0.05
    impact_default: float = 0.5

    # ── Rate Limiting & Tenant Plans ───────────────────
    default_plan: str = "free"
    tenant_plans: str = "{}"  # JSON: {"tenant_abc": "pro", "tenant_def": "free"}

    # ── CORS ───────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # ── Agent System ──────────────────────────────────
    agent_llm_model: str = "gemini/gemini-2.5-flash"
    agent_llm_temperature: float = 0.7
    agent_llm_max_tokens: int = 4096
    agent_fallback_model: str = "gemini/gemini-2.0-flash"
    agent_max_iterations: int = 5

    # ── OS Kernel ──────────────────────────────────────────
    kernel_max_concurrent_tasks: int = 5
    kernel_default_timeout: int = 300  # seconds
    kernel_default_max_retries: int = 2
    kernel_task_cleanup_days: int = 30  # archive tasks older than this
    kernel_enable_scheduler: bool = True
    kernel_max_consecutive_failures: int = 3

    # ── Tavily (web search tool) ──────────────────────
    tavily_api_key: str = ""  # Set LIFE_GRAPH_TAVILY_API_KEY

    # ── Google API (Gmail / Calendar tools) ───────────
    google_credentials_json: str = ""  # Set LIFE_GRAPH_GOOGLE_CREDENTIALS_JSON
    google_delegated_user: str = ""  # Set LIFE_GRAPH_GOOGLE_DELEGATED_USER

    # ── Langfuse (LLM tracing — auto-enabled by LiteLLM)
    langfuse_public_key: str = ""  # Set LIFE_GRAPH_LANGFUSE_PUBLIC_KEY
    langfuse_secret_key: str = ""  # Set LIFE_GRAPH_LANGFUSE_SECRET_KEY
    langfuse_host: str = "http://localhost:3001"

    # ── Observability ──────────────────────────────────
    metrics_enabled: bool = True

    # ── Self-Improving Agent ─────────────────────────
    optimization_model: str = "openrouter/google/gemini-2.5-flash"
    eval_max_parallel: int = 5
    eval_accuracy_threshold_pct: float = 90.0
    optimization_min_improvement_pct: float = 1.0
    optimization_max_regression_pct: float = 2.0
    optimization_max_few_shot: int = 8

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
    # Dissenting cheap-model review before an auto-verified task lands.
    # Off by default — pure LLM overhead until agents run unattended.
    driver_second_opinion_enabled: bool = False
    driver_second_opinion_model: str | None = None  # cheap model; None = client default

    # ── Capture Spine: Interview + Daily Brief ─────────
    interview_max_questions_per_day: int = 3  # Hard daily budget — never nag
    interview_question_ttl_days: int = 7  # Unanswered questions expire after this
    brief_hour_utc: int = 2  # Daily brief composition hour (02:00 UTC ≈ 07:30 IST)

    # ── Derived Properties ─────────────────────────────

    @property
    def service_api_keys_list(self) -> list[str]:
        """Parse comma-separated service API keys."""
        if not self.service_api_keys:
            return []
        return [k.strip() for k in self.service_api_keys.split(",") if k.strip()]

    @property
    def tenant_plans_dict(self) -> dict[str, str]:
        """Parse JSON tenant plan mapping."""
        try:
            return json.loads(self.tenant_plans) if self.tenant_plans else {}
        except json.JSONDecodeError:
            return {}

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
