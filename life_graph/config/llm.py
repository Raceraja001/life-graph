"""Language models: providers, failover, budgets, compute routing, local models, offers.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from pydantic import BaseModel


class LLMSettings(BaseModel):
    """Language models: providers, failover, budgets, compute routing, local models, offers."""

    # ── LLM (via LiteLLM) ─────────────────────────────
    # Primary "cheap" model for extraction + synthesis. A free OpenRouter model
    # is the default so a keyless self-host works out of the box; ResilientLLM
    # fails over to `llm_fallback_chain` from here. Override via LIFE_GRAPH_LLM_MODEL_CHEAP.
    llm_model_cheap: str = "openrouter/openai/gpt-oss-20b:free"
    llm_model_expensive: str = "gemini/gemini-3.6-flash"
    llm_daily_budget_usd: float = 1.0

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

    # ── The Governor: unified budget kernel (D7.3) ───────
    # One monthly cap over all autonomous spenders. Autonomous spend is
    # throttled (low-priority first) past the soft threshold and denied at the
    # cap; interactive/user-initiated requests are never blocked.
    monthly_budget_usd: float = 10.0
    budget_soft_threshold: float = 0.8

    # ── Cloud API spend guardrails (NOD P4) ──────────────
    # A hard ceiling on *cloud* LLM spend, measured at the call site from token
    # counts (services/spend_guardrails.py). Distinct from the Governor above:
    # the Governor arbitrates between autonomous spenders against a ledger in
    # Postgres, this is a cheap in-process backstop that every cloud chat passes
    # through — when it trips, the call degrades to local inference instead of
    # failing. Local runtimes (LM Studio / Ollama) cost $0.00 and are never
    # gated. Set either cap to 0 to disable that scope's enforcement.
    monthly_spend_cap_usd: float = 10.0
    # Per-task ceiling, enforced only for calls made inside a kernel task (or an
    # explicit SpendTracker.task_scope); ambient calls count toward the monthly
    # total only, so no long-lived process can starve itself.
    per_task_spend_cap_usd: float = 0.50
    # Price assumed for a cloud model missing from the price table, USD per 1M
    # tokens (input, output) — deliberately non-zero so an unknown model cannot
    # spend invisibly.
    spend_unknown_model_input_per_mtok: float = 0.50
    spend_unknown_model_output_per_mtok: float = 1.50
    # Per-tenant ceiling over the tracker's accounting window (process
    # lifetime, like the per-task cap). 0 disables it, which is the right
    # default for the single-tenant self-host; a shared deployment sets it so
    # one tenant cannot eat the whole monthly cap.
    per_tenant_spend_cap_usd: float = 0.0
    # How long an in-flight spend reservation may live before it is treated as
    # orphaned (a crashed or abandoned worker) and its headroom returned. Must
    # exceed the slowest cloud call's timeout, or a long call's own reservation
    # is reclaimed while it is still running.
    spend_reservation_ttl_seconds: float = 900.0

    # ── Compute routing and local models (was under Agent Drivers) ──
    # Where queued coding work runs (services/llm/compute_router.py). The one GPU
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
    # How Life Graph asks Ollama to hold its local models (services/llm/local_runtime.py).
    # One context size for every Life Graph request, or Ollama loads a second copy.
    local_llm_num_ctx: int = 16384
    # Hours of user_timezone ("7-23") in which the model stays loaded until the
    # window ends; outside them, released after local_llm_idle_keep_alive.
    local_llm_warm_hours: str = "7-23"
    local_llm_idle_keep_alive: str = "5m"
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
    # Job 1, free LLM offers (services/llm/offers.py, docs/specs/free-llm-offers.md).
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
    def speech_models_list(self) -> list[str]:
        """Parse the comma-separated speech model-name fragments."""
        return [m.strip().lower() for m in self.speech_models.split(",") if m.strip()]
