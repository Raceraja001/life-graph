# Autonomous Action Roles — Phase B1 Implementation Plan (command actions)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scheduled, opt-in **ops** role investigates read-only, proposes shell-**command** actions as structured JSON, and those flow through the already-built autonomy engine — classified, shadow-ramped, auto-executed when safe+trusted or queued for approval — surfaced in the mobile approvals inbox and pushed to the phone, with the previously-missing execute-on-approval built.

**Architecture:** Reuse the autonomy island (`AutoFixService.process`, `ActionClassifier`, `TrustScoreService`, `shadow_service`, `CommandExecutor`, `ApprovalQueueEntry`, `AuditService`) and Sub-project A's ticker/seeding/push/bridge patterns. Build the connective tissue: a read-only inspection tool, read-only propose-mode for the scheduled ops run, an `ActionProposalBridge` (proposal JSON → `AutoFixRequest` → `process`), the missing `execute_pending`, an approval→notification+feed bridge (so autonomy approvals appear in the existing `/m/approvals`), a shadow-log view, and startup seeding of safety rules + an ambient project at a raised autonomy level.

**Tech Stack:** Python 3.11+ (tests via `/c/Python314/python.exe`), FastAPI, SQLAlchemy 2.0 async, ARQ, Next.js dashboard. Base off `master @ 1eb87a0`.

## Global Constraints

- Run backend tests with `/c/Python314/python.exe -m pytest` from the worktree.
- **Every DB query filters by `tenant_id`.** Scheduled runs set `set_tenant_context(tenant_id, "system")`.
- **Nothing executes inline in the scheduled run.** The scheduled ops role runs with **read-only tools only** (a tool_override strips write tools); all execution happens through the gated engine.
- **Default-deny:** an action with no matching `ActionSafetyRule` classifies DANGEROUS → QUEUE. Never weaken this.
- Bridges/handlers are subscribed in BOTH the ARQ worker `on_startup` AND the web lifespan (worker-emitted events don't reach web subscribers — established in Sub-project A). Handler/bridge failures must never break task completion or startup (guarded try/except + log).
- Verified interfaces (copy exactly):
  - `AutoFixService.process(tenant_id: str, request: AutoFixRequest) -> AutoFixResponse`. `AutoFixRequest(agent_id, project_id, action_type, command, rollback_command=None, description="", timeout_seconds=60, metadata=None)` — `project_id` is REQUIRED. `AutoFixResponse(action: AutoActionResponse, routing: str, message: str)`; routing ∈ {`auto_executed`,`shadow_recorded`,`notify_before`,`queued_for_approval`}.
  - `get_autofix_service()` (`api/dependencies.py:451`, lru_cache) — constructs it fully.
  - `ActionClassifier`: `RiskLevel ∈ {safe,moderate,dangerous}`, `Recommendation ∈ {auto_execute,notify_before,queue_for_approval}`. `_get_autonomy_level` returns `"L0"` if `project_id is None` OR no `AutonomyLevel` row → L0 queues everything.
  - `AutoAction` status values: `pending|success|failure|skipped|rolled_back`. Outcome in `status`+`exit_code`+`stdout`/`stderr` (no `result` column). `approval_id` links to `ApprovalQueueEntry`.
  - `CommandExecutor().execute(command: str, timeout_seconds=60, cwd=None) -> ExecutionResult(exit_code, stdout, stderr, duration_ms, timed_out)`.
  - autonomy `ApprovalService.resolve(tenant_id, approval_id, decision, note, resolved_by, also_trust=False)` sets linked `AutoAction.status="pending"` on approve — **then nothing runs it** (the gap B1 fills).
  - `AUTONOMOUS_ACTION_PENDING` payload: `{"action_id","approval_id","project_id","risk_level"}`. `Event` uses `.type`/`.payload`; handler `async def h(event)`.
  - `NotificationEngine.create(tenant_id, title, body=None, *, priority, channel="terminal", source_type=None, source_id=None, metadata=None, deliver_at_brief=False)`; priority ∈ {critical,important,info}; `source_id` must be a UUID str or None. `PushService(async_session).send_to_tenant(tenant_id, title, body, url="/m")`.
  - Unified feed: `Approval` model (`models/db.py:2284`, table `approvals`): `id(UUID), tenant_id, kind, title, detail, status(pending|approved|rejected), source, source_ref, payload(JSONB), priority, resolved_by, resolution_note, resolved_at`. `services/approvals.py resolve()` dispatches by `if/elif appr.kind` (promotion/merge/contradiction) at ~`:166-171`.
  - `SafetyRuleService.seed_defaults(tenant_id, created_by="system")` (idempotent, 8 rules); `.create_rule(tenant_id, action_name, action_pattern, risk_level="dangerous", created_by="system", **kwargs)`. `ActionSafetyRule` NOT NULL no-default cols: `tenant_id, action_name, action_pattern, created_by`.
  - `AutonomyLevelService.set_manual(tenant_id, project_id, level, reason, by)`. `config.shadow_mode_enabled=True` (default).
- ruff line-length 100, double quotes; type hints + docstrings on public APIs.
- Commit trailer exactly:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## File Structure

- `life_graph/tools/system_inspect.py` **(new)** — `inspect_system` read-only, allowlisted inspection tool.
- `life_graph/kernel/ambient.py` **(modify)** — `AMBIENT_ACTION` constant, `AMBIENT_ACTION_READONLY_TOOLS`, an `ops-ambient` scheduled job def in `AMBIENT_JOBS` (opt-in/inactive).
- `life_graph/kernel/personas.py` **(modify)** — append the action-proposal JSON contract to `ops`' system_prompt.
- `life_graph/kernel/scheduler.py` **(modify)** — `fire_job` gains `tool_override`.
- `life_graph/kernel/process_manager.py` **(modify)** — thread `tool_override` into `_run_agent`'s tool filtering.
- `life_graph/workers/tasks.py` **(modify)** — ticker passes read-only `tool_override` for `AMBIENT_ACTION` roles.
- `life_graph/services/action_proposal_bridge.py` **(new)** — `ActionProposalBridge` (proposal JSON → `process`).
- `life_graph/autonomy/pipeline/service.py` **(modify)** — `execute_pending(tenant_id, auto_action_id)` public method (the missing executor).
- `life_graph/services/autonomous_approvals.py` **(new)** — the approval→notification+unified-feed producer (on `AUTONOMOUS_ACTION_PENDING`).
- `life_graph/services/approvals.py` **(modify)** — `elif kind=="autonomous_action"` branch + `_apply_autonomous_action`.
- `life_graph/main.py` + `life_graph/workers/settings.py` **(modify)** — startup seeding (safety rules + ambient project level) and bridge subscriptions.
- `dashboard/lib/api.ts` + `dashboard/lib/mobile-api.ts` **(modify)** + `dashboard/app/(mobile)/m/shadow/page.tsx` **(new)** + `dashboard/components/shadow-log.tsx` **(new)** — shadow-log view; risk badge on approvals.
- Tests under `tests/unit/` and `tests/integration/`.

---

### Task 1: Read-only system inspection tool

Give the scheduled ops role a safe way to investigate — an allowlisted read-only tool (no arbitrary shell).

**Files:**
- Create: `life_graph/tools/system_inspect.py`
- Modify: `life_graph/main.py` (import so the `@tool` registers, next to the other tool imports ~`:71-77`)
- Test: `tests/unit/test_system_inspect_tool.py`

**Interfaces:**
- Produces: an `@tool`-registered `inspect_system` with param `check: str` (one of a fixed allowlist) and optional `target: str`; returns `{"check","output","exit_code"}`. Read-only.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_system_inspect_tool.py
import pytest
from life_graph.tools import system_inspect as si


def test_rejects_unknown_check():
    # unknown check must not run anything
    import asyncio
    out = asyncio.get_event_loop().run_until_complete(si.inspect_system(check="rm_root"))
    assert out["exit_code"] != 0
    assert "not an allowed" in out["output"].lower()


def test_allowlist_maps_to_readonly_commands():
    # the allowlist must contain only read-only inspection commands
    for cmd in si._ALLOWED.values():
        assert not any(w in cmd for w in ("rm ", "restart", "stop", "kill", "push", ">", "mkfs"))
    assert set(si._ALLOWED) >= {"disk", "memory", "uptime", "docker_ps", "docker_logs", "git_status"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_system_inspect_tool.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the tool**

```python
# life_graph/tools/system_inspect.py
"""Read-only system inspection tool for ambient action roles.

Exposes a FIXED allowlist of read-only inspection commands so a scheduled ops
role can investigate system state WITHOUT any write capability. There is no
arbitrary-command path here by design.
"""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from life_graph.tools.registry import tool

# check-name -> read-only command template. `{target}` is filled from a
# shlex-quoted `target` arg; templates without `{target}` ignore it.
_ALLOWED: dict[str, str] = {
    "disk": "df -h",
    "memory": "free -h",
    "uptime": "uptime",
    "docker_ps": "docker ps --format '{{.Names}}: {{.Status}}'",
    "docker_logs": "docker logs --tail 50 {target}",
    "systemctl_status": "systemctl status {target}",
    "git_status": "git status --porcelain --branch",
}
_TIMEOUT = 20


@tool(
    name="inspect_system",
    description=(
        "Read-only system inspection. `check` must be one of: "
        + ", ".join(sorted(_ALLOWED))
        + ". Optional `target` names a container/service where relevant. "
        "Cannot modify anything."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "check": {"type": "string", "description": "One of the allowed checks."},
            "target": {"type": "string", "description": "Container/service name, if the check needs one."},
        },
        "required": ["check"],
    },
)
async def inspect_system(check: str, target: str = "") -> dict[str, Any]:
    """Run one allowlisted read-only inspection command."""
    template = _ALLOWED.get(check)
    if template is None:
        return {"check": check, "output": f"'{check}' is not an allowed check.", "exit_code": 2}
    command = template.replace("{target}", shlex.quote(target)) if "{target}" in template else template
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        return {"check": check, "output": out.decode("utf-8", "replace")[:8000], "exit_code": proc.returncode}
    except TimeoutError:
        return {"check": check, "output": f"timeout after {_TIMEOUT}s", "exit_code": 124}
    except Exception as exc:  # inspection must never raise into the agent loop
        return {"check": check, "output": f"error: {exc}", "exit_code": 1}
```

Add the import in `main.py` next to the other `from life_graph.tools import ...` lines so the `@tool` registers:
```python
from life_graph.tools import system_inspect  # noqa: F401  (registers inspect_system)
```
(Confirm the exact `@tool` decorator signature in `life_graph/tools/registry.py` and match it — the params above mirror the existing tools; adjust key names if the decorator differs.)

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_system_inspect_tool.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add life_graph/tools/system_inspect.py life_graph/main.py tests/unit/test_system_inspect_tool.py
git commit -m "feat(action-roles): read-only allowlisted inspect_system tool

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `tool_override` on the scheduled run (read-only enforcement)

The scheduled ops run must NOT carry write tools. Add a tool allowlist override threaded ticker → fire_job → spawn → `_run_agent`.

**Files:**
- Modify: `life_graph/kernel/scheduler.py` (`fire_job`), `life_graph/kernel/process_manager.py` (`spawn`, `_execute_task`, `_run_agent`)
- Test: `tests/unit/test_tool_override.py`

**Interfaces:**
- Produces: `fire_job(..., input_override=None, tool_override: list[str] | None = None)`; `spawn(..., tool_override: list[str] | None = None)`; `_run_agent` uses `tool_override` (if not None) as the allowlist instead of the persona's `allowed_tools`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_tool_override.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_run_agent_uses_tool_override(monkeypatch):
    """When tool_override is given, only those tools are passed to the orchestrator."""
    from life_graph.kernel import process_manager as pm_mod

    pm = pm_mod.ProcessManager.__new__(pm_mod.ProcessManager)
    captured = {}

    class _FakeReg:
        def get_tools(self):
            return [{"function": {"name": n}} for n in ("inspect_system", "run_command", "git_status")]

    async def fake_run(messages, system_prompt=None, tools=None):
        captured["tools"] = [t["function"]["name"] for t in (tools or [])]
        if False:
            yield ""
        return

    # Minimal persona with WRITE tools; override must win.
    persona = {"allowed_tools": ["run_command", "git_status"], "system_prompt": "x", "model": None,
               "temperature": 0.3, "max_tokens": 1024}
    with patch("life_graph.tools.registry.registry", _FakeReg()), \
         patch("life_graph.agents.orchestrator.AgentOrchestrator") as Orch:
        Orch.return_value.run = fake_run
        await pm._run_agent("t1", "ops", {"message": "go"}, persona, tool_override=["inspect_system", "git_status"])

    assert set(captured["tools"]) == {"inspect_system", "git_status"}  # run_command excluded
```

(Adapt the patch targets to how `_run_agent` imports the registry/orchestrator — inspect `process_manager.py:468-529` first; the test's intent is: `tool_override` replaces `allowed_tools` as the filter.)

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_tool_override.py -v`
Expected: FAIL — `_run_agent()` has no `tool_override` param.

- [ ] **Step 3: Implement the threading**

- `scheduler.py` `fire_job`: add `tool_override: list[str] | None = None`; pass it to `spawn(..., tool_override=tool_override)`.
- `process_manager.py` `spawn`: add `tool_override: list[str] | None = None`; store it on the task/pass through `_execute_task` → `_run_agent`.
- `process_manager.py` `_run_agent`: add `tool_override: list[str] | None = None`; change the tool-filter (~`:504-507`) to:
```python
allow = tool_override if tool_override is not None else persona.get("allowed_tools")
if allow is not None:
    allowed_set = set(allow)
    tools = [t for t in tool_registry.get_tools() if t["function"]["name"] in allowed_set]
else:
    tools = None
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_tool_override.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add life_graph/kernel/scheduler.py life_graph/kernel/process_manager.py tests/unit/test_tool_override.py
git commit -m "feat(action-roles): tool_override threads a read-only allowlist through fire_job -> _run_agent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: ops propose-mode contract + AMBIENT_ACTION + read-only tool set + scheduled job

**Files:**
- Modify: `life_graph/kernel/personas.py` (append proposal contract to `ops.system_prompt`)
- Modify: `life_graph/kernel/ambient.py` (add `AMBIENT_ACTION`, `AMBIENT_ACTION_READONLY_TOOLS`, an `ops-ambient` job in `AMBIENT_JOBS`)
- Modify: `life_graph/workers/tasks.py` (ticker passes `tool_override` for AMBIENT_ACTION roles)
- Test: `tests/unit/test_action_roles_config.py`

**Interfaces:**
- Consumes: `fire_job(..., tool_override=...)` (Task 2), `AMBIENT_ADVISORY`/`build_ambient_input` (Sub-project A).
- Produces: `AMBIENT_ACTION: frozenset[str] = frozenset({"ops"})`; `AMBIENT_ACTION_READONLY_TOOLS: list[str] = ["inspect_system","git_status","git_log","git_diff","memory_search","get_current_datetime"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_action_roles_config.py
from life_graph.kernel.ambient import AMBIENT_ACTION, AMBIENT_ACTION_READONLY_TOOLS, AMBIENT_JOBS
from life_graph.kernel.personas import _BUILTIN_PERSONAS


def test_ops_declares_action_proposal_contract():
    ops = next(p for p in _BUILTIN_PERSONAS if p["name"] == "ops")
    sp = ops["system_prompt"]
    assert "JSON array" in sp and '"command"' in sp and '"risk_hint"' in sp
    assert "propose" in sp.lower()


def test_readonly_toolset_has_no_write_tools():
    for t in AMBIENT_ACTION_READONLY_TOOLS:
        assert t not in ("run_command", "terminal", "docker", "ssh", "git", "browser_agent", "delegate_to_persona")


def test_ops_ambient_job_seeded_inactive():
    job = next(j for j in AMBIENT_JOBS if j["name"] == "ops-ambient")
    assert job["agent_name"] == "ops"
    assert job["active"] is False
    assert job["cron_expression"] == "0 1 * * *"
```

- [ ] **Step 2: Run to verify it fails.** Run: `/c/Python314/python.exe -m pytest tests/unit/test_action_roles_config.py -v` — FAIL (symbols/contract missing).

- [ ] **Step 3: Implement.**
- `ambient.py`: add near `AMBIENT_ADVISORY`:
```python
AMBIENT_ACTION: frozenset[str] = frozenset({"ops"})
AMBIENT_ACTION_READONLY_TOOLS: list[str] = [
    "inspect_system", "git_status", "git_log", "git_diff", "memory_search", "get_current_datetime",
]
```
and add to `AMBIENT_JOBS`:
```python
    {
        "name": "ops-ambient",
        "cron_expression": "0 1 * * *",
        "agent_name": "ops",
        "description": "Ambient infra sweep: proposes maintenance actions for your approval.",
        "input": {},
        "active": False,  # opt-in — acts on real infra
    },
```
- `personas.py`: append to `ops.system_prompt`:
```
" When run on a schedule you are in PROPOSE mode: investigate read-only, do"
" not perform any change, and end your reply with ONLY a JSON array of"
" proposed actions, each {\"name\": str, \"command\": str, \"rationale\":"
" str, \"risk_hint\": \"safe\"|\"moderate\"|\"dangerous\"}. Return [] if"
" nothing needs doing. Each command must be a single concrete shell command."
```
- `workers/tasks.py` `tick_scheduled_jobs` loop: extend the advisory-enrichment branch so AMBIENT_ACTION roles get the read-only override AND the ambient prompt:
```python
from life_graph.kernel.ambient import AMBIENT_ADVISORY, AMBIENT_ACTION, AMBIENT_ACTION_READONLY_TOOLS
...
    override_input = None
    tool_override = None
    if job["agent_name"] in AMBIENT_ADVISORY:
        override_input = await build_ambient_input(job["agent_name"], job.get("input") or {}, job["tenant_id"])
    elif job["agent_name"] in AMBIENT_ACTION:
        override_input = await build_ambient_input(job["agent_name"], job.get("input") or {}, job["tenant_id"])
        tool_override = AMBIENT_ACTION_READONLY_TOOLS
    await scheduler.fire_job(job["tenant_id"], job["id"], input_override=override_input, tool_override=tool_override)
```
(`build_ambient_input` already appends a novelty + a trailing contract reminder; the ops persona's own prompt carries the action-JSON contract, so the persona output shape is well-specified. If `build_ambient_input`'s advisory `_CONTRACT` wording conflicts, gate it to advisory only and add a neutral action preamble — verify during implementation.)

- [ ] **Step 4: Run to verify pass.** Run the test file — PASS.

- [ ] **Step 5: Commit.**
```bash
git add life_graph/kernel/ambient.py life_graph/kernel/personas.py life_graph/workers/tasks.py tests/unit/test_action_roles_config.py
git commit -m "feat(action-roles): ops propose-mode contract + read-only scheduled run + opt-in job

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `execute_pending` — the missing executor

Fill the execute-on-approval gap: a public method that runs an already-approved (`pending`) `AutoAction`.

**Files:**
- Modify: `life_graph/autonomy/pipeline/service.py` (add `execute_pending`)
- Test: `tests/unit/test_execute_pending.py`

**Interfaces:**
- Produces: `async def execute_pending(self, tenant_id: str, auto_action_id: str) -> AutoActionResponse` — loads the `AutoAction` (must be `status="pending"` and tenant-scoped), runs its `action_command` via `self._executor.execute(...)`, sets status `success`/`failure` + `exit_code`/`stdout`/`stderr`/`duration_ms`/`completed_at`, calls `self._audit_service.log_auto_execute(...)`, emits `AUTONOMOUS_ACTION_COMPLETED`. Reuses the exact body of the existing `_auto_execute` (refactor `_auto_execute` to call a shared `_run_action(tenant_id, auto_action, timeout)` so both paths share one implementation — DRY).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_execute_pending.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_execute_pending_runs_command_and_marks_success(monkeypatch):
    from life_graph.autonomy.pipeline.service import AutoFixService
    from life_graph.autonomy.pipeline.executor import ExecutionResult

    svc = AutoFixService.__new__(AutoFixService)
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(return_value=ExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=12.0))
    svc._audit_service = AsyncMock()
    # session_factory / _load returns a fake pending AutoAction; patch the loader you implement
    fake_action = MagicMock(id="a1", tenant_id="t1", status="pending", action_command="echo hi",
                            action_name="restart", project_id="ambient", agent_id="ops", risk_level="moderate")
    monkeypatch.setattr(svc, "_load_auto_action", AsyncMock(return_value=fake_action))
    monkeypatch.setattr(svc, "_persist_action", AsyncMock())  # your status-write helper
    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        resp = await svc.execute_pending("t1", "a1")

    svc._executor.execute.assert_awaited_once()
    assert fake_action.status == "success"
    bus.emit.assert_awaited()  # AUTONOMOUS_ACTION_COMPLETED
```

(Read `_auto_execute` (`service.py:210-274`) first and refactor its body into `_run_action`; `execute_pending` and `_auto_execute` both call it. Adapt the test's helper names to what you extract — the load-run-persist-audit-emit sequence is the contract. If a pending action is not found or not `pending`, raise `ValueError`.)

- [ ] **Step 2: Run to verify it fails.** — FAIL (`execute_pending` missing).

- [ ] **Step 3: Implement** `_run_action` (extracted from `_auto_execute`) + `execute_pending` (load + guard status + `_run_action` + audit + emit). Keep `_auto_execute` behavior identical by delegating to `_run_action`.

- [ ] **Step 4: Run to verify pass.** — PASS. Also run the existing autonomy pipeline tests to confirm no regression: `/c/Python314/python.exe -m pytest tests/ -k "autofix or pipeline or autonomy" -q`.

- [ ] **Step 5: Commit.**
```bash
git add life_graph/autonomy/pipeline/service.py tests/unit/test_execute_pending.py
git commit -m "feat(action-roles): AutoFixService.execute_pending fills the execute-on-approval gap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: ActionProposalBridge (proposal JSON → process)

**Files:**
- Create: `life_graph/services/action_proposal_bridge.py`
- Test: `tests/unit/test_action_proposal_bridge.py`

**Interfaces:**
- Consumes: `get_autofix_service().process(tenant_id, AutoFixRequest(...))`; `AMBIENT_ACTION`; `parse_findings`-style extraction (reuse `_extract_json_array` from `services/findings_bridge.py`, or a shared helper); `AgentTask` result (`result["response"]`); `TASK_COMPLETED` payload `{task_id,tenant_id,agent_name}`.
- Produces: `class ActionProposalBridge` with `async def process_result(self, tenant_id, agent_name, task_id, result_text) -> int` (count of proposals dispatched) + `ActionProposalHandler` singleton `action_proposal_handler` with `subscribe()` (gate on `AMBIENT_ACTION`). Constant `AMBIENT_PROJECT_ID = "ambient"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_action_proposal_bridge.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from life_graph.services.action_proposal_bridge import ActionProposalBridge, AMBIENT_PROJECT_ID


@pytest.mark.asyncio
async def test_each_proposal_becomes_an_autofix_request():
    autofix = AsyncMock()
    autofix.process = AsyncMock(return_value=MagicMock(routing="queued_for_approval"))
    notifier = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifier)

    text = ('[{"name":"restart_worker","command":"docker restart life_graph_worker",'
            '"rationale":"unhealthy 2h","risk_hint":"moderate"}]')
    n = await bridge.process_result("t1", "ops", "11111111-1111-1111-1111-111111111111", text)
    assert n == 1
    _, kwargs = autofix.process.call_args
    req = kwargs.get("request") or autofix.process.call_args.args[1]
    assert req.agent_id == "ops" and req.project_id == AMBIENT_PROJECT_ID
    assert req.command == "docker restart life_graph_worker"
    assert req.action_type == "restart_worker"


@pytest.mark.asyncio
async def test_malformed_json_creates_one_advisory_notification_no_execute():
    autofix = AsyncMock(); autofix.process = AsyncMock()
    notifier = AsyncMock(); notifier.create = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifier)
    n = await bridge.process_result("t1", "ops", "22222222-2222-2222-2222-222222222222", "no json here")
    assert n == 0
    autofix.process.assert_not_awaited()
    notifier.create.assert_awaited_once()  # advisory "could not parse proposals"


@pytest.mark.asyncio
async def test_empty_array_dispatches_nothing():
    autofix = AsyncMock(); autofix.process = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=AsyncMock())
    assert await bridge.process_result("t1", "ops", "33333333-3333-3333-3333-333333333333", "[]") == 0
    autofix.process.assert_not_awaited()
```

- [ ] **Step 2: Run to verify it fails.** — FAIL (module missing).

- [ ] **Step 3: Implement** `ActionProposalBridge`:
  - reuse `_extract_json_array` from `findings_bridge` (import it) to get the proposals list; each item needs `name` + `command` (skip items missing either).
  - for each: `AutoFixRequest(agent_id=agent_name, project_id=AMBIENT_PROJECT_ID, action_type=item["name"], command=item["command"], description=item.get("rationale",""))` → `await self._autofix.process(tenant_id, request)`; isolate per-proposal in try/except (one failure doesn't drop the rest).
  - if `_extract_json_array` returns `None` (no JSON) AND the text is non-empty → one advisory `notification_engine.create(tenant_id, "ops proposed actions could not be parsed", body=<truncated text>, priority="info", source_type="ops", deliver_at_brief=True)`; return 0.
  - empty array → return 0 (nothing to do).
  - Add `ActionProposalHandler` + singleton mirroring `FindingsBridgeHandler` (Task 2 of Sub-project A): subscribe `TASK_COMPLETED`, gate `agent_name in AMBIENT_ACTION`, load the `AgentTask` result, call `process_result`. Lazy-build the bridge from `get_autofix_service()` + `get_notification_engine()`.

- [ ] **Step 4: Run to verify pass.** — PASS.

- [ ] **Step 5: Commit.**
```bash
git add life_graph/services/action_proposal_bridge.py tests/unit/test_action_proposal_bridge.py
git commit -m "feat(action-roles): ActionProposalBridge routes proposals into the autonomy engine

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Approval → notification + unified-feed producer

When an autonomy action is queued/notify-before, push the user AND mirror it into the generic `Approval` feed so `/m/approvals` shows it.

**Files:**
- Create: `life_graph/services/autonomous_approvals.py`
- Test: `tests/unit/test_autonomous_approvals_producer.py`

**Interfaces:**
- Consumes: `AUTONOMOUS_ACTION_PENDING` payload `{action_id, approval_id, project_id, risk_level}`; the `ApprovalQueueEntry` + `AutoAction` rows (load for title/command); `NotificationEngine.create`; `PushService.send_to_tenant`; `Approval` model insert.
- Produces: `class AutonomousApprovalProducer` + singleton with `subscribe()`. On the event: (1) load the queue entry + auto_action (tenant-scoped) for the command/risk; (2) create a `Notification` (priority: dangerous→critical, moderate→important; body = command + rationale) + immediate `PushService.send_to_tenant`; (3) insert a generic `Approval` row `kind="autonomous_action", source="autonomy", source_ref=str(approval_id), title=f"{risk} action: {action_name}", detail=command, payload={"auto_action_id":..., "approval_id":..., "risk_level":...}, priority=<by risk>`.

- [ ] **Step 1: Write the failing test** (mock engine/push/session; assert notification priority maps by risk, push called for a dangerous action, and an `Approval` row with `kind="autonomous_action"` + `source_ref` is inserted).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** the producer + `subscribe()` (worker+web). Guard everything in try/except; push/notify failures swallowed. Idempotency: skip if an `Approval` with this `source_ref` already exists.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** (`feat(action-roles): approval->notification + unified-feed producer for autonomous actions`).

---

### Task 7: Unified feed side-effect for `autonomous_action`

Approving/rejecting in `/m/approvals` must resolve the autonomy entry and (on approve) execute.

**Files:**
- Modify: `life_graph/services/approvals.py` (`resolve` kind-dispatch + `_apply_autonomous_action`)
- Test: `tests/unit/test_unified_autonomous_action.py`

**Interfaces:**
- Consumes: the `Approval` row (`payload.auto_action_id`, `payload.approval_id`); autonomy `ApprovalService.resolve(...)`; `AutoFixService.execute_pending(tenant_id, auto_action_id)`.
- Produces: `_apply_autonomous_action(self, tenant_id, appr, approve: bool, resolved_by: str)` — approve → autonomy `resolve(decision="approve")` then `get_autofix_service().execute_pending(tenant_id, payload["auto_action_id"])`; reject → autonomy `resolve(decision="reject")`. Add the `elif appr.kind == "autonomous_action":` branch in `resolve()` (~`:166-171`).

- [ ] **Step 1: Write the failing test** — approve path calls autonomy resolve(approve) then `execute_pending`; reject path calls resolve(reject) and does NOT execute. Mock both services.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** the branch + handler (lazy import `get_approval_service`/`get_autofix_service` to avoid import cycles).
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** (`feat(action-roles): unified approve executes the autonomy action; reject skips it`).

---

### Task 8: Startup seeding — safety rules + ambient project autonomy level + bridge subscriptions

**Files:**
- Modify: `life_graph/main.py` (lifespan: seed safety rules, set ambient-project level, subscribe the two new bridges), `life_graph/workers/settings.py` (`on_startup`: subscribe the two new bridges)
- Create: `life_graph/autonomy/safety/ambient_rules.py` **(new)** — a small helper adding infra-specific rules on top of `seed_defaults`.
- Test: `tests/unit/test_action_roles_seeding.py`

**Interfaces:**
- Consumes: `SafetyRuleService.seed_defaults` + `.create_rule`; `AutonomyLevelService.set_manual(tenant, "ambient", "L1", reason, by)`; `action_proposal_handler.subscribe()`, `autonomous_approval_producer.subscribe()`.
- Produces: `async def seed_ambient_autonomy(tenant_id: str) -> None` — seeds default + infra safety rules and sets the `ambient` project to `L1` (idempotent). Infra rules (via `create_rule`): `docker_ps`/`disk`/`memory`/`git_status` = `safe` (thr 0.3); `restart_*`/`docker restart *` = `moderate` (thr 0.6); `delete_*`/`rm *`/`drop *`/migration patterns = `dangerous` + `is_guardrail=True`.

- [ ] **Step 1: Write the failing test** — `seed_ambient_autonomy` calls `seed_defaults`, creates the infra rules, and sets ambient level L1; idempotent on second call (mock the services).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** the seeder + wire into `main.py` lifespan (guarded, tenant `"default"`) next to the ambient-jobs seeding, and subscribe the two bridges in BOTH `main.py` and `workers/settings.py on_startup` (guarded).
- [ ] **Step 4: Run — PASS.** Also `/c/Python314/python.exe -c "import life_graph.workers.settings; import life_graph.main"` imports clean.
- [ ] **Step 5: Commit** (`feat(action-roles): seed safety rules + ambient L1 autonomy level; wire action bridges`).

> **Deploy note (out of band):** on the VM, also run `seed_ambient_autonomy("personal")` and re-sync the `ops` prompt into `agent_personas` for tenants `personal`+`default` (seeding skips existing personas); confirm `LIFE_GRAPH_SHADOW_MODE_ENABLED` is true; enable the `ops-ambient` job for tenant `personal` when ready. Rules/levels are the real control surface — review before enabling.

---

### Task 9: Shadow-log view (mobile) + risk badge on approvals

Let the user watch the shadow ramp and veto, and see risk on approvals.

**Files:**
- Modify: `dashboard/lib/api.ts` (add `autonomy.shadowRuns()` + `autonomy.gradeShadow(id, grade)` hitting the existing `/autonomy/shadow` router — verify its exact paths in `life_graph/autonomy/shadow/router.py`), `dashboard/lib/mobile-api.ts` (a `useShadowRuns` hook + `useApprovals` risk passthrough)
- Create: `dashboard/components/shadow-log.tsx`, `dashboard/app/(mobile)/m/shadow/page.tsx`
- Test: `tests/integration/test_action_roles_end_to_end.py` (backend E2E; the UI is verified by tsc+build)

**Interfaces:**
- Consumes: `/autonomy/shadow` list + grade endpoints (verify), `api.approvals` (existing).
- Produces: `/m/shadow` page listing shadow runs (what WOULD have run) with good/bad grade buttons; a risk badge rendered on autonomous-action approvals in `/m/approvals` (the `Approval.detail`/`payload.risk_level` from Task 6).

- [ ] **Step 1: Backend E2E test** `tests/integration/test_action_roles_end_to_end.py`: drive `ActionProposalBridge.process_result` with a proposal, mock `AutoFixService.process` to return `queued_for_approval`, assert one `process` call with the right `AutoFixRequest`; then simulate the `AUTONOMOUS_ACTION_PENDING` producer creating a notification + `Approval` row (mock session/engine/push). Assert the approve path (Task 7) calls `execute_pending`. Run → GREEN.
- [ ] **Step 2: Build the shadow-log client + hook** — verify `/autonomy/shadow` paths in `life_graph/autonomy/shadow/router.py`; add `api.autonomy = { shadowRuns: () => GET("/autonomy/shadow/runs"...), gradeShadow: (id, grade) => POST(...) }` matching the real routes; add `useShadowRuns` in `mobile-api.ts` with a `refetchInterval: 60000`.
- [ ] **Step 3: Build `shadow-log.tsx` + `m/shadow/page.tsx`** following existing mobile patterns (see `components/ambient-roles.tsx` from Sub-project A + `m/schedules/page.tsx`). Add a "Shadow log" entry to the mobile nav (mobile-shell) as done for `/m/schedules`. Render a risk badge on autonomous-action rows in the approvals component.
- [ ] **Step 4: Verify** — `cd dashboard && npx tsc --noEmit && npm run build`; run the backend E2E test.
- [ ] **Step 5: Commit** (`feat(action-roles): shadow-log mobile view + risk badge on approvals + E2E`).

---

## Final verification (after all tasks)

- [ ] Full unit + action-role integration: `/c/Python314/python.exe -m pytest tests/unit/ tests/integration/test_action_roles_end_to_end.py -q`
- [ ] Autonomy regression: `/c/Python314/python.exe -m pytest tests/ -k "autonomy or autofix or approval or pipeline" -q`
- [ ] `ruff check life_graph/ && ruff format --check life_graph/`
- [ ] `cd dashboard && npx tsc --noEmit && npm run build`
- [ ] Imports clean: `/c/Python314/python.exe -c "import life_graph.main; import life_graph.workers.settings"`

## Deploy checklist (out of band; batch-deploy — deploy only when told)

1. Rebuild app + worker + dashboard; reconnect `web` net on app.
2. `seed_ambient_autonomy("personal")` (safety rules + ambient L1); confirm `LIFE_GRAPH_SHADOW_MODE_ENABLED=true`.
3. Re-sync the `ops` `system_prompt` into `agent_personas` (personal+default) — seeding skips existing rows.
4. Seed the `ops-ambient` job for `personal`; **leave it inactive** until you've reviewed the seeded safety rules.
5. Enable `ops-ambient`; watch the shadow log; grade a few runs before anything graduates to real auto-execute.

## Notes / risks

- **Read-only enforcement** is load-bearing: the scheduled ops run gets `AMBIENT_ACTION_READONLY_TOOLS` via `tool_override`; if that override path breaks, ops could execute inline. Task 2's test pins it; the final review should re-verify.
- **Auto-execute only fires** when the ambient project is L1+ AND shadow has graduated the agent; until then everything queues — that's the intended safe default.
- **`build_ambient_input` reuse:** its advisory `_CONTRACT` wording is findings-oriented; for action roles the ops persona prompt carries the action contract. Verify the two don't produce a contradictory instruction; if they do, split the contract by role in Task 3.
- Phase **B2** (open-ended agent_task actions via `dispatch_task` + verifier chain + rollback) layers on this plumbing next.
