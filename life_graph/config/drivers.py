"""Agent drivers and dev tasks: Claude Code / OpenCode, PRs, the sandboxes.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DriverSettings(BaseModel):
    """Agent drivers and dev tasks: Claude Code / OpenCode, PRs, the sandboxes."""

    # ── Agent drivers ──────────────────────────────────
    driver_land_verified_work: bool = True
    """Commit a verified dispatch onto an ``lg/task-<id>`` branch.

    The dispatch worktree is detached and removed unconditionally after the
    run, so without this a verified change is deleted and the pipeline
    reports success having landed nothing. Landing never merges, never
    pushes, and never touches the default branch -- it leaves a reviewable
    branch for the approval step."""

    drivers_dispatch_endpoint: bool = False
    """Serve ``POST /kernel/drivers/dispatch`` (a test hook, api/drivers.py).

    It runs a whole driver pipeline inside the HTTP request, outside the dev
    runner's lock, concurrency limits and budget check (audit L5). Off: the
    route answers 404. Real work goes through ``POST /kernel/drivers/tasks``."""

    # ── Agent Drivers ───────────────────────────────────
    driver_claude_code_bin: str = "claude"  # Claude Code CLI binary for the claude_code driver
    # Per-dispatch limit for the claude_code driver. The dispatcher's 300s
    # fallback cut a real plan-only run off mid-exploration of this repo;
    # 1200 matches the local driver.
    driver_claude_code_timeout_seconds: int = 1200
    # "oauth" = the personal Claude login; "api_key" = ANTHROPIC_API_KEY under
    # Anthropic's commercial terms, required for a service sold to others.
    # Prefer the env var to this setting for the key.
    driver_claude_code_auth: str = "oauth"
    driver_claude_code_api_key: str = ""
    # The login a SANDBOXED claude_code run uses in oauth mode: a long-lived
    # token from `claude setup-token`, handed to the container as
    # CLAUDE_CODE_OAUTH_TOKEN (by name, never on a command line). It does not
    # refresh, so nothing is copied in and nothing needs writing back.
    # Unset: sandboxed dispatch refuses, unless the legacy copy below is on.
    driver_claude_code_oauth_token: str = ""
    # OpenCode driver (drivers/opencode.py). Unavailable until the binary exists:
    #   npm install --prefix ~/.local/opencode opencode-ai
    # Parked 2026-11-18 (owner): in prod it completed fewer tasks than the local
    # driver (19/46 vs 46/90 over 60 days), it runs on the host with no shell,
    # and its config there was broken. Off: the driver reports unavailable and
    # failed nightly local runs are no longer escalated to it. The code stays;
    # the way back is moving it into the task runtime (ADR follow-up 3).
    driver_opencode_enabled: bool = False
    driver_opencode_bin: str = "opencode"
    driver_opencode_model: str = "ollama/qwen3-coder:30b"
    driver_opencode_ollama_base: str = "http://localhost:11434/v1"
    driver_opencode_timeout_seconds: int = 1200
    # The host is not sandboxed for this driver, so OpenCode's shell stays
    # denied unless this is set. Tests run in the verifier sandbox regardless.
    driver_opencode_allow_bash: bool = False
    # Subscription coding CLIs (drivers/codex.py, drivers/gemini.py; spec
    # agent-drivers.md, Phase 3a). Off until the owner opts in: each sends the
    # task and the code to its provider (never memories or preferences), and
    # runs on the host. On, a driver is still unavailable until its binary is
    # found (PATH or ~/.local/node/bin) and it is not signed out (`codex login`;
    # `gemini` once, Login with Google). Codex also needs driver_allow_host_shell:
    # its shell cannot be turned off and its sandbox does not confine reads.
    driver_codex_enabled: bool = False
    driver_codex_bin: str = "codex"
    driver_codex_model: str = ""  # empty = the CLI's own default model
    driver_codex_timeout_seconds: int = 1200
    driver_gemini_enabled: bool = False
    driver_gemini_bin: str = "gemini"
    driver_gemini_model: str = ""  # empty = the CLI's own default model
    driver_gemini_timeout_seconds: int = 1200
    # Agent accounts (services/agent_accounts; spec agent-drivers.md, Phase 3b):
    # several named logins per CLI, each in its own life-graph-managed home
    # under driver_accounts_home_root, tried in pool order, skipped while
    # cooling down after a rate limit. Off: every driver runs on the host's
    # single login exactly as before and the accounts table is never read.
    # On with no enabled account for a driver: that driver also runs as before.
    driver_accounts_enabled: bool = False
    driver_accounts_home_root: str = "~/.local/share/life-graph/agent-homes"
    # Cooldown after a rate limit that named no reset time.
    driver_accounts_default_cooldown_minutes: int = 15
    # Read Codex plan windows with `codex app-server` (account/rateLimits/read,
    # no prompt sent) when GET .../limits?refresh=true asks. Off: only the
    # windows the last run reported are shown. Claude is never polled (U4).
    driver_accounts_codex_probe_enabled: bool = False
    # Subscription budget (risk D4, Phase 3b part 2): an unattended run skips
    # a subscription account whose latest plan window (agent_account_limits)
    # is at or above this share of its limit, falling to the next account;
    # every account over it refuses the run as rate_limited until the window
    # resets (which parks the task when the owner's wait_for_reset is on).
    # Only applies with driver_accounts_enabled. 1.0 = never skip.
    driver_accounts_subscription_max_share: float = 0.9
    # continue_task (Phase 3b part 2): keep a dispatch's worktree and CLI
    # session so the owner (or race-app's PR-feedback loop) can continue the
    # task in place. Off: every worktree is removed after its dispatch, as
    # before. On: a kept worktree is removed once its task has no open PR
    # (or pending PR approval) and it is older than driver_continue_keep_hours.
    driver_continue_enabled: bool = False
    driver_continue_keep_hours: int = 24
    # Phase 4b (docs/specs/agent-drivers.md, "Phase 4b"): parallel plans. A plan
    # whose Tasks declare file scopes ("Files: a.py, src/**") runs its
    # non-overlapping tasks at once, at most this many per plan (also bounded by
    # the per-project WIP limit and dev_runner_max_concurrency), each ending on
    # its own branch, then ONE integration task files the single PR approval.
    # 1 = today's sequential, merge-gated fan-out, unchanged.
    driver_team_max_parallel: int = 1
    # Team upgrades (docs/specs/agent-drivers.md, "Team upgrades (2026-11-28)"):
    # a team worker that ends failed (or timed out) -- not one that was
    # cancelled -- is retried this many times as a fresh worker on the next
    # escalation rung (same rung when no higher one may run) before the team
    # fails. The other workers keep going meanwhile. 0 = the old behaviour: the
    # first failed worker cancels the rest.
    driver_team_worker_retries: int = Field(1, ge=0, le=3)
    # PR feedback loop (Phase 4b): for a task whose PR is open and whose
    # worktree is kept (driver_continue_enabled), read the PR with gh every
    # poll_minutes and hand new failing checks / review comments / merge
    # conflicts back to the task as one continue_task round, at most
    # max_rounds per PR (then "needs you"). Read-only on GitHub.
    driver_pr_feedback_enabled: bool = False
    driver_pr_feedback_poll_minutes: int = 10
    driver_pr_feedback_max_rounds: int = 3
    driver_pr_feedback_on_failing_checks: bool = True
    driver_pr_feedback_on_review_comments: bool = True
    driver_pr_feedback_on_conflicts: bool = True
    # Arena (Phase 4b): the owner races one instruction on several drivers or
    # accounts and picks the winner. Off: POST /kernel/drivers/arena is 409.
    driver_arena_enabled: bool = False
    # Escalation ladder (docs/specs/agent-drivers.md, "Escalation ladder,
    # starting floor, outcome log (2026-11-28)"): a bounce after failed
    # verification moves one rung UP instead of re-running the same driver.
    # Rungs are "driver[:model]", weakest first; empty = the default
    # local:qwen3:14b -> local:qwen3-coder:30b -> claude_code, minus rungs whose
    # driver isn't registered. A pin_required driver (cloud) is never a rung.
    # On by default: local rungs are free, a metered (api-billed) rung is
    # skipped unless driver_escalation_allow_metered, and the top rung is capped
    # below -- so no new dollar spend; a blocked climb bounces as before.
    driver_escalation_enabled: bool = True
    driver_escalation_ladder: str = ""
    driver_escalation_allow_metered: bool = False
    # Of a tenant's dispatches today (UTC), the share the ladder or the floor
    # may send to the top rung; the first driver_escalation_top_daily_min a day
    # are always allowed. Protects the one subscription from parking.
    driver_escalation_top_share: float = Field(0.25, ge=0.0, le=1.0)
    driver_escalation_top_daily_min: int = Field(2, ge=0)
    # Starting floor: a task touching a protected path, or whose project +
    # instruction failed within driver_start_floor_failure_days, starts at the
    # top rung (persona pins win; the top-rung cap applies).
    driver_start_floor_enabled: bool = True
    driver_start_floor_failure_days: int = Field(14, ge=1, le=365)
    # A plan approves itself only for a project with auto_approve_plans set,
    # at most this many tasks, and every other rule in services/dev/plan_policy.py.
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
    # it from running alongside the real one (services/dev/tasks.py).
    dev_task_runner_enabled: bool = True
    # Where dev tasks execute (services/dev/runner.py). "api": the API process
    # holding the runner lock runs them (an API restart interrupts them).
    # "worker": a separate `python -m life_graph.workers.dev_runner` process
    # holds the lock and runs them; API processes only queue and inspect, so a
    # deploy or API restart no longer cuts a running agent off.
    dev_task_runner_mode: str = "api"
    # Tasks one runner executes at once; at most one of them unattended
    # (queued/nightly work shares one local GPU). Interactive starts may use
    # the rest: 3 keeps two dashboard starts from waiting behind a nightly run.
    dev_runner_max_concurrency: int = 3
    # The runner refreshes properties.lease on each running task this often;
    # a lease older than dev_runner_lease_stale_seconds reads as "not alive".
    dev_runner_heartbeat_seconds: int = 30
    dev_runner_lease_stale_seconds: int = 180
    # How often the runner checks for cancel requests (also woken by NOTIFY).
    dev_runner_cancel_poll_seconds: int = 3
    # On SIGTERM the worker stops claiming and waits this long for running
    # tasks before cancelling them (they are then recovered on the next start).
    dev_runner_drain_seconds: int = 1500
    # Live session events (dev_task_events) are operational, not the study
    # record (agent_run_steps): expired after this many days at runner start.
    dev_task_events_retention_days: int = 14
    # Ceiling for a per-task timeout_seconds given at creation (Stage 4).
    dev_task_max_timeout_seconds: int = 3600
    # Who gets dev-task runtime health alerts (workers/runtime_health.py).
    # Comma-separated tenant ids; empty = every tenant that created a dev
    # task in the last 30 days.
    runtime_health_alert_tenants: str = ""

    # ── Agent runs: trajectories, review, PRs, sandboxes ──
    # Per-step content cap for recorded agent runs (services/dev/trajectories.py).
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
    # (services/dev/change_policy.py). Empty = the free cloud models, else the
    # local agent model; never a paid fallback. Code only leaves the machine.
    change_review_model: str = ""
    driver_pr_agent_bin: str = "pr-agent"  # the PR-Agent CLI backing the reviewer above
    # Two-model review panel on risky diffs (services/dev/review_panel.py):
    # "off" = never runs; "shadow" = runs in the background on risky landing
    # diffs and only records its verdict; "enforce" = an objection or a
    # not-reviewed verdict sends the task to a person (never approves).
    driver_review_panel_mode: Literal["off", "shadow", "enforce"] = "off"
    # Comma-separated local model ids; a non-local id is refused (not called).
    driver_review_panel_models: str = "ollama_chat/qwen3:14b,ollama_chat/qwen3-coder:30b"
    # Per-member time limit; a member that runs out is "not reviewed".
    driver_review_panel_timeout_seconds: float = Field(300.0, gt=0)
    # A diff with more changed lines (added + removed) than this is risky.
    driver_review_panel_min_lines: int = Field(150, ge=0)
    # Draft the PR description from the landed diff (one model call per landed
    # task, best-effort -- falls back to the instruction + agent summary).
    driver_pr_description_enabled: bool = True
    # Give the driver the definitions/callers/callees of symbols its
    # instruction names, from a stdlib-ast graph of the worktree (no model).
    driver_code_context_enabled: bool = True
    driver_pr_description_model: str | None = None  # None = agent_llm_model
    # GitHub CLI used to push approved task branches and open PRs; it must be
    # logged in (`gh auth login`) as the user this process runs as.
    driver_gh_bin: str = "gh"
    # Where verifiers execute agent-written code (tests, linters). "none" runs
    # them on the host as this process's user; "docker" runs each check in a
    # locked-down container (life_graph/services/dev/sandbox.py). With "docker",
    # a missing daemon or image makes checks inconclusive, never passing.
    # Only these values: anything else (a typo such as "Docker") stops startup
    # rather than quietly meaning "none" (Stage 0, 2026-11-25).
    verifier_sandbox: Literal["none", "docker"] = "none"
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
    # Cache GC for the bun-*/node-* dependency envs (sandbox.gc_envs): per
    # project and toolchain the newest `keep` stay; older ones are removed once
    # unused for the grace period, never while a setup holds their lock.
    verifier_sandbox_env_keep: int = Field(2, ge=1)
    verifier_sandbox_env_gc_grace_hours: float = Field(24.0, ge=0)
    # The sandbox's setup phase reads agent-edited manifests, so it runs on an
    # internal network whose only way out is the task runtime's egress proxy
    # (driver_runtime_egress_image), relaying only to these hosts on 443 per
    # toolchain, plus the project registry's sandbox_setup_allow hosts. The
    # manifests are also checked first (services/dev/setup_guard.py).
    verifier_setup_egress_python: str = "pypi.org,files.pythonhosted.org"
    verifier_setup_egress_node: str = "registry.npmjs.org"
    # sandbox_toolchain=bun: `bun install` fetches tarballs from the npm registry.
    verifier_setup_egress_bun: str = "registry.npmjs.org"
    # The Gradle wrapper (services.gradle.org redirects to downloads.gradle.org),
    # the plugin portal, Maven Central and Google's Maven (Android).
    verifier_setup_egress_jvm: str = (
        "services.gradle.org,downloads.gradle.org,downloads.gradle-dn.com,"
        "plugins.gradle.org,plugins-artifacts.gradle.org,repo.maven.apache.org,"
        "repo1.maven.org,dl.google.com,maven.google.com"
    )
    # Where the claude_code driver itself executes. "none" runs it on the
    # host as this process's user (scoped only by the CLI's own
    # --allowedTools/--permission-mode). "task" is the per-task runtime below
    # (network allowlisted through a proxy): use it. "docker" was an older
    # container on docker's open default network that skipped the container
    # policy check. It is fenced (owner decision D25, 2026-11-25): the value
    # still loads, but every claude_code dispatch refuses
    # (sandbox_unavailable) and runtime health reports driver_sandbox_fenced.
    # It never falls back to the host.
    # Only these values: before, an unknown one ("Task", "tasks") was not
    # "docker" or "task", so it silently meant host execution (Stage 0,
    # 2026-11-25). Now it stops startup.
    driver_claude_sandbox: Literal["none", "docker", "task"] = "none"
    driver_claude_sandbox_image: str = "life-graph-claude-driver:latest"
    driver_claude_sandbox_memory: str = "4g"
    driver_claude_sandbox_cpus: str = "4"
    # The CLI's own OAuth token file. Only with the legacy flag below is it
    # staged into a throwaway copy for each sandboxed dispatch
    # (life_graph/services/dev/sandbox.py:stage_credentials). Never mounted live.
    driver_claude_code_creds_path: str = "~/.claude/.credentials.json"
    # Legacy: copy the host's login file into each sandboxed run when no
    # driver_claude_code_oauth_token is set. Off because it revokes the host
    # login: if the host's access token has expired, the CLI in the container
    # refreshes it inside the throwaway copy, the refresh token rotates, and
    # the host's copy is dead (prod, 2026-11-19). On only for a throwaway
    # login you do not otherwise use.
    driver_claude_code_allow_staged_login: bool = False

    # ── Per-task execution runtime (services/dev/task_runtime.py) ──
    # driver_claude_sandbox="task" runs the claude_code driver in a per-task
    # runtime: its own internal network whose only way out is a per-task
    # egress proxy allowing just the hosts below, the worktree as the only
    # writable host path (refused unless it sits under the dispatch scratch
    # root), labels for audit and orphan cleanup, an in-container deadline,
    # and every spec checked by sandbox.validate_spec. docker (the older
    # open-network container) is fenced; none is the host. Roll back by
    # pointing driver_claude_sandbox_image at the previous image tag.
    driver_runtime_egress_image: str = "life-graph-sandbox-egress:dev"
    # Hostnames (optionally https://host[:port]) the driver may reach through
    # the proxy. The Claude CLI talks to the API and refreshes its OAuth
    # token; everything else (telemetry, update checks) is switched off.
    driver_runtime_egress_allowlist: str = (
        "api.anthropic.com,console.anthropic.com,platform.claude.com,claude.ai"
    )
    driver_runtime_pids_limit: int = 512
    # Grace between the in-container deadline and the host-side kill.
    driver_runtime_kill_grace_seconds: int = 15
    # Mount the project's cached verifier environment (the same one the
    # verifiers build with sandbox.prepare_env) read-only at /venv in the
    # driver's task runtime, so the agent can run its own tests offline. The
    # egress allowlist is unchanged: nothing is installed at run time.
    # Python toolchain only; needs verifier_sandbox=docker.
    driver_runtime_project_tools: bool = True
    # Where each runtime's internal network gets its subnet. Docker's default
    # address pools hold only ~31 networks and the other stacks on a shared
    # daemon use most of them (2026-11-19: the 12th concurrent runtime failed
    # with "all predefined address pools have been fully subnetted"). An
    # explicit /28 per network from this private range, which nothing else on
    # the host routes (checked 2026-11-19: WSL, docker, Tailscale, the Windows
    # LAN), lifts that ceiling to 4096 without touching the daemon config.
    # Must be RFC1918/private. Empty: docker picks from its default pools.
    driver_runtime_subnet_pool: str = "10.213.0.0/16"
    driver_runtime_subnet_prefix: int = 28

    # ── Host execution (no container) ──
    # With no driver sandbox, a coding CLI's shell runs on the host as this
    # process's user. Off: the claude_code driver's Bash tool is denied on
    # the host (OpenCode's bash already is, driver_opencode_allow_bash).
    # Turning this on is a statement that the host is a disposable dev box.
    # Also on the host, always: WebFetch/WebSearch are denied, and while the
    # shell is denied the CLI runs with --restricted, which keeps its file
    # tools inside the worktree (drivers/claude_code.py:_permission_args).
    # With this on, --restricted is left off (it would remove Bash too).
    driver_allow_host_shell: bool = False
    # Extra variable names a host-run driver CLI may inherit. Host-run
    # drivers otherwise get only PATH/HOME/locale-style variables -- never
    # the API process's database URL, tokens or LIFE_GRAPH_* configuration.
    driver_host_env_passthrough: str = ""
    # With verifier_sandbox="none", checks that EXECUTE the agent's code
    # (pytest, acceptance tests) or a binary found inside the agent's
    # worktree are inconclusive unless this is on: on the host they would run
    # agent-written code as this process's user.
    verifier_allow_host_execution: bool = False

    @property
    def driver_runtime_egress_allowlist_list(self) -> list[str]:
        return [h.strip() for h in self.driver_runtime_egress_allowlist.split(",") if h.strip()]

    @property
    def driver_host_env_passthrough_list(self) -> list[str]:
        return [n.strip() for n in self.driver_host_env_passthrough.split(",") if n.strip()]

    @property
    def trajectory_opt_out_tenants_list(self) -> list[str]:
        """Tenants opted out of step recording (services/dev/trajectories.py)."""
        return [t.strip() for t in self.trajectory_opt_out_tenants.split(",") if t.strip()]
