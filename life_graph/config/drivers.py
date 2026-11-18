"""Agent drivers and dev tasks: Claude Code / OpenCode, PRs, the sandboxes.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from pydantic import BaseModel


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
    # (life_graph/services/dev/sandbox.py:run_driver) with the worktree mounted
    # read-write, only its own OAuth token available (a throwaway copy, not
    # the live ~/.claude), and no other host path visible. Unlike the
    # verifier sandbox this needs network (the CLI calls the Anthropic API),
    # so isolation is filesystem + capabilities, not network denial. With
    # "docker", a missing daemon or image fails the dispatch rather than
    # silently falling back to unsandboxed host execution. "task" is the
    # per-task runtime below (network allowlisted through a proxy); prefer it.
    driver_claude_sandbox: str = "none"
    driver_claude_sandbox_image: str = "life-graph-claude-driver:latest"
    driver_claude_sandbox_memory: str = "4g"
    driver_claude_sandbox_cpus: str = "4"
    # The CLI's own OAuth token file, staged into a throwaway copy for each
    # sandboxed dispatch (life_graph/services/dev/sandbox.py:stage_credentials).
    # Never mounted live — see driver_claude_sandbox's docstring above.
    driver_claude_code_creds_path: str = "~/.claude/.credentials.json"

    # ── Per-task execution runtime (services/dev/task_runtime.py) ──
    # driver_claude_sandbox="task" runs the claude_code driver in a per-task
    # runtime: its own internal network whose only way out is a per-task
    # egress proxy allowing just the hosts below, the worktree as the only
    # writable host path (refused unless it sits under the dispatch scratch
    # root), labels for audit and orphan cleanup, an in-container deadline,
    # and every spec checked by sandbox.validate_spec. docker is the older
    # open-network container, kept as the rollback; none is the host.
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

    # ── Host execution (no container) ──
    # With no driver sandbox, a coding CLI's shell runs on the host as this
    # process's user. Off: the claude_code driver's Bash tool is denied on
    # the host (OpenCode's bash already is, driver_opencode_allow_bash).
    # Turning this on is a statement that the host is a disposable dev box.
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
