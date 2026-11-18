"""The agent runtime: agent loop, kernel, autonomy, self-improvement, tools, MCP.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

import json
import os

from pydantic import BaseModel


class AgentSettings(BaseModel):
    """The agent runtime: agent loop, kernel, autonomy, self-improvement, tools, MCP."""

    # ── Shadow Mode: dry-run rung on the autonomy ladder (D7.4) ──
    # New autonomous actors record 'would-have-done' reports instead of acting,
    # until they soak long enough and are graded well enough to graduate.
    shadow_mode_enabled: bool = True
    shadow_min_days: int = 14
    shadow_min_samples: int = 5
    shadow_good_rate: float = 0.8

    # ── MCP (Model Context Protocol) Client Bridge ──────
    # JSON list of external MCP servers to bridge tools from. Two shapes:
    # stdio (default, spawned as a subprocess of this process):
    #   {"name": ..., "command": ..., "args": [...], "env": {...}}
    # http (connects to an already-running server, e.g. its own container):
    #   {"name": ..., "transport": "http", "url": "http://host:port/mcp"}
    mcp_servers: str = "[]"

    # ── Life Graph's own MCP tools over HTTP (api/mcp_http.py) ─────
    # Off by default. On, the tools of life_graph/mcp_server.py answer at
    # /mcp/ behind the same service-key check as the API (device tokens are
    # refused): each call goes on to the API as the caller, with their key and
    # tenant. self_url is where those calls go (this API, on loopback).
    mcp_http_enabled: bool = False
    mcp_http_self_url: str = "http://127.0.0.1:8080"
    # Host headers the MCP endpoint answers (DNS-rebinding guard), e.g. the
    # tailnet name a `tailscale serve` proxy sends.
    mcp_http_allowed_hosts: str = "localhost,127.0.0.1"

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

    # ── Autonomous AI (Era 8) ─────────────────────────────
    autonomy_trust_decay_days: int = 30  # Trust decays if no activity for this many days
    autonomy_trust_decay_rate: float = 0.05  # Decay per period
    autonomy_trust_failure_penalty: float = 0.5  # Multiply trust by this on failure
    autonomy_trust_success_boost: float = 0.02  # Add this on success
    autonomy_approval_timeout_hours: int = 24  # Auto-expire unapproved actions
    # A pending approval nobody answered for this long is marked stale (never
    # approved): on 2026-10-24, 20 command approvals had waited since 4 Oct.
    # 0 = keep waiting forever.
    autonomy_approval_stale_days: int = 14
    autonomy_max_auto_actions_per_hour: int = 10  # Rate limit for safe actions
    autonomy_max_blast_radius: int = 3  # Max files/services affected per auto-action
    autonomy_default_level: str = "L0"  # L0=ask everything, L1=safe auto, L2=moderate auto, L3=full

    # ── Host Tools (run_command / file_read / file_write) ──
    # These tools execute against the host filesystem and shell. Every
    # control below is ENFORCED in life_graph/tools/_guards.py — the module
    # docstrings used to claim a "personal tenant only" restriction that no
    # code implemented.
    tool_shell_enabled: bool = True  # master switch for run_command
    # allowlist = read-only programs run without a shell
    # (tools/shell_allowlist.py); full = an arbitrary shell string, denylist
    # only. The code default is the safe one (CHARTER invariant 5: a missing
    # setting asks, it does not act); a deployment opts into "full" in .env.
    tool_shell_mode: str = "allowlist"
    # Tenants permitted to use host tools. Empty string = every tenant,
    # which is only sane for a single-tenant personal deployment.
    tool_privileged_tenants: str = "default"
    # Filesystem roots the file_* tools may touch. Empty = the home
    # directory only. Comma-separated absolute paths.
    tool_fs_roots: str = ""

    # ── Durable authorisation (autonomy/approvals/durable_store.py) ─────────
    # Keep issued capabilities and the owner's standing rules in Postgres
    # (migration 059) instead of in one process's memory. On, because the
    # approval queue is real: a capability minted by the API when the owner
    # taps Approve on their phone has to be resolvable by the ARQ worker that
    # resumes the errand, and "one use" has to mean once across the whole
    # deployment rather than once per process.
    #
    # Turning it off is a single-process fallback, not a performance knob: an
    # in-memory mandate is invisible to every other worker, so an errand
    # resumed anywhere else is denied.
    durable_authorization: bool = True

    @property
    def mcp_servers_list(self) -> list[dict]:
        """Parse JSON list of configured external MCP servers."""
        try:
            parsed = json.loads(self.mcp_servers) if self.mcp_servers else []
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    @property
    def tool_privileged_tenants_list(self) -> list[str]:
        """Tenants allowed to use host tools; empty list means no restriction."""
        return [t.strip() for t in self.tool_privileged_tenants.split(",") if t.strip()]

    @property
    def tool_fs_roots_list(self) -> list[str]:
        """Roots the file_* tools may touch. Defaults to the home directory."""
        roots = [r.strip() for r in self.tool_fs_roots.split(",") if r.strip()]
        return roots or [os.path.expanduser("~")]

    def context_tokens_for(self, model: str | None) -> int:
        """The context window to budget a run against (agent_context_tokens_by_model)."""
        import json

        try:
            overrides = json.loads(self.agent_context_tokens_by_model or "{}")
        except ValueError:
            overrides = {}
        value = overrides.get(model or "") if isinstance(overrides, dict) else None
        return int(value) if isinstance(value, int) and value > 0 else self.agent_context_tokens
