"""The app itself: identity, profile, auth keys, CORS, plans, tracing, seeding.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

# The logger every setting used before the split, so log filters still match.
logger = logging.getLogger("life_graph.config")


class CoreSettings(BaseModel):
    """The app itself: identity, profile, auth keys, CORS, plans, tracing, seeding."""

    # ── Application ────────────────────────────────────
    app_name: str = "Life Graph"
    version: str = "1.0.0"
    environment: str = "development"  # development | staging | production
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "text"  # text (dev) | json (prod)
    profile: Literal["memory_core", "full"] = "memory_core"
    """Which parts of the API this process serves (docs/modular_memory_service_plan.md).

    ``memory_core``: the memory engine only (memories, search, preferences,
    identity, capture, graph, sessions, intentions, health); no ARQ pool, no
    agent drivers, personas, connectors or delivery handlers at startup.
    ``full``: everything, as before 2026-10-29. The owner's live stack sets
    ``LIFE_GRAPH_PROFILE=full`` in .env (Jarvis, kernel and the rest live there)."""

    @property
    def is_full_profile(self) -> bool:
        return self.profile == "full"

    edition: str = ""
    """Which copy of Life Graph this is on a machine that runs two: "prod" (the
    owner's daily one, on a pinned release) or "dev" (the one development
    changes). Only a label, shown by /health, so nobody mistakes one for the other."""
    worker_cron_enabled: bool = True
    """Whether the ARQ worker runs the scheduled jobs (brief, nudges, Memory check,
    connector sync, night shift, ...). Off for a development copy beside the
    owner's daily one: the same jobs on a copy of the same data would message the
    owner twice and sync the same accounts twice. Queued jobs still run."""

    # ── Authentication (Service-to-Service) ────────────
    api_key: str | None = None  # Legacy single key (dev mode)
    service_api_keys: str = ""  # Comma-separated: "key1,key2,key3"
    # The subset of service keys that belong to the owner's *own* surfaces —
    # the dashboard and the CLI. Holding a service key proves a caller is
    # configured, not that it is the owner: the same list is handed to MCP
    # servers, watchers and integrations, which is why core/trust.py grades
    # those surfaces EXTERNAL. A key named here (plus a paired phone's own
    # device token) is what lets an ingress claim a first-party source_type
    # (api/auth.py ingress_for, core/trust.py classify_ingress). Unset in
    # production means no HTTP caller is the owner and every privileged
    # provenance claim is floored at EXTERNAL — fail closed, by design.
    owner_api_keys: str = ""  # Comma-separated: LIFE_GRAPH_OWNER_API_KEYS
    # POST /approvals/{id}/approve|reject and /autonomy/approvals/{id}/resolve
    # and /autonomy/approvals/batch only from the owner: a key in
    # owner_api_keys or a paired phone (api/approval_identity.py). Off by
    # default: turn it on once the dashboard's key is listed in owner_api_keys,
    # or the dashboard gets 403 and only the phone can decide. Startup logs a
    # WARNING, and GET /kernel/observability/system shows "approvals", when it
    # is on with no owner key and no paired phone (services/owner_enforcement.py).
    approvals_require_owner: bool = False
    # The /admin routes that change the deployment or export a tenant's data
    # (tenants, webhooks, export, bulk delete/import, consolidation and job
    # runs) only from the owner: an owner key or (for the caller's own tenant)
    # a paired phone (api/admin.py). Off by default, for the same reason as
    # approvals_require_owner: turn the two on together once the dashboard's key
    # is in owner_api_keys. GET /admin/stats and /admin/gaps stay open. Reaching
    # ANOTHER tenant through /admin needs an owner key whatever this says.
    admin_require_owner: bool = False
    # A paired phone's token stops working after this many days unused
    # (services/devices.py authenticate; re-pair to get a new one). 0 = never.
    device_token_idle_days: int = Field(default=60, ge=0)
    # Where the release script puts the phone app's APK and its latest.json
    # ({"version_code", "version_name", "file", "notes"}), served to paired
    # phones by GET /jarvis/app/latest and /jarvis/app/download/{file}.
    # Empty = no update offered (404).
    app_release_dir: str = ""

    # ── Rate Limiting & Tenant Plans ───────────────────
    default_plan: str = "free"
    tenant_plans: str = "{}"  # JSON: {"tenant_abc": "pro", "tenant_def": "free"}

    # ── CORS ───────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # ── Langfuse (LLM tracing — auto-enabled by LiteLLM)
    langfuse_public_key: str = ""  # Set LIFE_GRAPH_LANGFUSE_PUBLIC_KEY
    langfuse_secret_key: str = ""  # Set LIFE_GRAPH_LANGFUSE_SECRET_KEY
    langfuse_host: str = "http://localhost:3001"

    # ── Observability ──────────────────────────────────
    metrics_enabled: bool = True

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

    @property
    def service_api_keys_list(self) -> list[str]:
        """Parse comma-separated service API keys."""
        if not self.service_api_keys:
            return []
        return [k.strip() for k in self.service_api_keys.split(",") if k.strip()]

    @property
    def owner_api_keys_list(self) -> list[str]:
        """Parse comma-separated owner API keys (see :attr:`owner_api_keys`)."""
        if not self.owner_api_keys:
            return []
        return [k.strip() for k in self.owner_api_keys.split(",") if k.strip()]

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
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def seed_tenants_list(self) -> list[str]:
        """Tenants to seed at startup, in the order given."""
        return [t.strip() for t in self.seed_tenants.split(",") if t.strip()]

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
