# Autonomous Action Roles — Phase B2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add approved, open-ended **agent_task** autonomous actions — cody proposes code fixes on a schedule (read-only), they queue for your approval, and on approval a write-enabled cody run executes through the driver's verifier chain — layered on the B1 command pipeline.

**Architecture:** Extend the B1 autonomy pipeline with a `kind` discriminator (`'command'` | `'agent_task'`). agent_task proposals carry a natural-language `instruction` (new nullable column; `action_command` becomes nullable), are **always routed to QUEUE_FOR_APPROVAL** (no shadow/auto-execute in B2), and on approval `AutoFixService.execute_pending` branches on `kind` to call the existing-but-unwired `TaskDispatcher.dispatch_task` (LocalDriver → AgentOrchestrator, Governor budget gate, `build_ok`/`lint_clean` verifier chain, one-bounce). A `DriverResult`→`AutoAction` adapter reconciles the two result shapes. cody joins the ambient-action roles (opt-in, read-only-when-scheduled via `tool_override`).

**Tech Stack:** Python 3.11+ (dev interpreter `/c/Python314/python.exe`), FastAPI, SQLAlchemy 2.0 `mapped_column`, Alembic, pydantic v2, ARQ; Next.js 16 / React 19 dashboard; pytest (`httpx.AsyncClient` + `ASGITransport`, `conftest` pgvector mock).

## Global Constraints

- **Base off master @ `6cf115e`** (B1 merged). Work in an isolated worktree/branch; never build on master directly.
- **Every DB query tenant-scoped** (filter by `tenant_id`); scheduled runs use the existing ambient tenant context.
- **Read-only propose-mode is load-bearing:** the scheduled cody run must get `AMBIENT_ACTION_READONLY_TOOLS` via `tool_override` (cody's persona `allowed_tools` carry write tools — `file_write`/`terminal`/`git` — unconditionally; read-only-when-ambient is enforced ONLY by the scheduler override, exactly as ops in B1). Never let a scheduled cody run carry write tools.
- **agent_task NEVER auto-executes in B2** (decision B2-D2): the router forces `kind=='agent_task'` → `QUEUE_FOR_APPROVAL` regardless of risk/trust; no shadow ramp for agent_task. Command actions keep B1 behavior unchanged.
- **`kind` migration keeps shell semantics clean** (decision B2-D1): `action_command` nullable; new `kind` (default `'command'`) + `instruction` (nullable Text) on **both** `AutoAction` and `ApprovalQueueEntry`. `rollback()`/`CommandExecutor` never see an instruction as a shell string.
- **cody only** (decision B2-D3); swe-lead is out of scope.
- **`dispatch_task` CAN raise** (`DispatchError` on WIP-limit; driver errors) — unlike `CommandExecutor`, which never raises. The agent_task execution path must catch dispatch failures → mark `AutoAction` failed + notify, and never wedge the unified-feed `Approval` row unresolvable.
- **Backend tests:** `/c/Python314/python.exe -m pytest` from the worktree root. Lint: `ruff check` + `ruff format` clean on touched files (the repo carries ~834 pre-existing ruff errors unrelated to this branch — keep only YOUR touched lines clean, do not mass-fix).
- **Commit trailer EXACTLY** (own paragraph, two lines):

  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

- **Verified interfaces (against master @ 6cf115e — confirm before writing task code):**
  - `TaskDispatcher.dispatch_task(self, tenant_id: str, task_id: str, instruction: str, task_type: str = "general", project_id: str | None = None, session: AsyncSession | None = None, persona_name: str | None = None, private: bool = False, cost_cap_usd: float = 2.0, verify_chain: list[str] | None = None, interactive: bool = False) -> DriverResult` — `drivers/dispatcher.py`. Constructed as `TaskDispatcher(session_factory, event_bus=..., reviewer=None)`.
  - `DriverResult` (`drivers/base.py`): `success: bool, output: str, artifacts: list[dict], cost_usd: float, duration_ms: int, error: str | None, metadata: dict`. **No `exit_code`.**
  - `AutoFixRequest` (`autonomy/pipeline/schemas.py`): `agent_id, project_id, action_type, command, rollback_command=None, description="", timeout_seconds=60, metadata=None`. `metadata`/`timeout_seconds` are "not persisted" today.
  - `AutoFixService` (`autonomy/pipeline/service.py`): `process(tenant_id, request) -> AutoFixResponse`; `execute_pending(tenant_id, auto_action_id) -> AutoActionResponse`; `_run_action(tenant_id, auto_action, timeout_seconds=60)` is the single execution chokepoint (`self._executor.execute(command=auto_action.action_command, timeout_seconds=...)`). `self._executor = CommandExecutor()` in `__init__`.
  - `ActionProposalBridge.process_result(tenant_id, agent_name, task_id, result_text) -> int` (`services/action_proposal_bridge.py`) — currently `continue`s past any item without `item.get("command")`. `ActionProposalHandler` gates on `agent_name in AMBIENT_ACTION` + `task_name` prefix `"schedule:"`.
  - `ActionClassifier.classify(...)` (`autonomy/safety/classifier.py`) — glob-matches `action_name` against `ActionSafetyRule.action_pattern`; no rule ⇒ `DANGEROUS + QUEUE_FOR_APPROVAL`. Never inspects `action_type`.
  - Ambient: `AMBIENT_ACTION` frozenset + `AMBIENT_ACTION_READONLY_TOOLS` + `AMBIENT_JOBS` + `seed_ambient_jobs` in `kernel/ambient.py`; `AMBIENT_ACTION` branch in `workers/tasks.py::tick_scheduled_jobs`. Personas seeded in `kernel/personas.py` (`cody` exists with write tools, no propose contract). Safety-rule seeding in `autonomy/safety/ambient_rules.py` (`seed_ambient_autonomy`).
  - Unified feed: `services/approvals.py::_apply_autonomous_action` (approve → autonomy `resolve` + `execute_pending`); B1 idempotency swallow catches `ValueError` only. Producer `services/autonomous_approvals.py` writes `Approval` `payload={auto_action_id, approval_id, risk_level}`.
  - Dashboard: `/m/approvals` approvals component (risk badge from B1), `lib/mobile-api.ts` `useApprovals`.

---

## File Structure

- **Migration** (Task 1): new Alembic revision adding `kind` + `instruction` to `auto_actions` and `approval_queue`, and making `action_command` nullable on both. The autonomy ORM models live in `life_graph/autonomy/models.py` (edit there, not `models/db.py`).
- **Schema/model** (Task 1): `autonomy/models.py` (`AutoAction`, `ApprovalQueueEntry`), `autonomy/pipeline/schemas.py` (`AutoFixRequest`).
- **Router forces agent_task→queue** (Task 2): `autonomy/pipeline/service.py` `process()` routing.
- **Execution branch + adapter** (Task 3): `autonomy/pipeline/service.py` `_run_action` (+ a small `DriverResult`→result adapter), `TaskDispatcher` construction/injection.
- **Dispatch-failure robustness** (Task 4): `autonomy/pipeline/service.py` (catch dispatch raises) + `services/approvals.py` (`_apply_autonomous_action` broaden failure handling).
- **Shared propose contract + agent_task bridge branch** (Task 5): `kernel/ambient.py` (or a new `kernel/propose_contract.py`) shared constants; `services/action_proposal_bridge.py` `kind`-dispatch.
- **cody ambient role + prompt + job + safety rules** (Task 6): `kernel/ambient.py` (`AMBIENT_ACTION`, `AMBIENT_JOBS`), `kernel/personas.py` (cody propose paragraph), `autonomy/safety/ambient_rules.py` (cody rules), seeding wired in `main.py` already calls `seed_ambient_autonomy`/`seed_ambient_jobs` — confirm cody flows through.
- **Approvals UI: instruction rendering** (Task 7): `dashboard/components/*approvals*`, `dashboard/lib/mobile-api.ts`.
- **E2E + final verification** (Task 8): `tests/integration/test_action_roles_agent_task_e2e.py`.

---

### Task 1: `kind`/`instruction` migration + model + schema

**Files:**
- Modify: `life_graph/autonomy/models.py` (`AutoAction`, `ApprovalQueueEntry`)
- Modify: `life_graph/autonomy/pipeline/schemas.py` (`AutoFixRequest`)
- Create: `alembic/versions/<rev>_add_kind_instruction_to_autonomy.py`
- Test: `tests/unit/test_autonomy_kind_schema.py`

**Interfaces:**
- Consumes: existing `AutoAction`/`ApprovalQueueEntry`/`AutoFixRequest` definitions.
- Produces: `AutoAction.kind: Mapped[str]` (default `"command"`, NOT NULL, server_default `"command"`); `AutoAction.instruction: Mapped[str | None]` (Text, nullable); `AutoAction.action_command` becomes `Mapped[str | None]` (nullable). Same three changes on `ApprovalQueueEntry`. `AutoFixRequest.kind: str = "command"` and `AutoFixRequest.instruction: str | None = None` (pydantic fields).

- [ ] **Step 1: Write the failing test** — `tests/unit/test_autonomy_kind_schema.py`:

```python
import pytest
from life_graph.autonomy.pipeline.schemas import AutoFixRequest


def test_autofix_request_defaults_to_command_kind():
    req = AutoFixRequest(agent_id="ops", project_id="ambient", action_type="restart", command="docker restart x")
    assert req.kind == "command"
    assert req.instruction is None


def test_autofix_request_accepts_agent_task():
    req = AutoFixRequest(
        agent_id="cody", project_id="ambient", action_type="cody_fix",
        command=None, kind="agent_task", instruction="Fix the failing test in module X",
    )
    assert req.kind == "agent_task"
    assert req.instruction == "Fix the failing test in module X"
    assert req.command is None


def test_autofix_request_command_is_now_optional():
    # command may be None for agent_task; must not raise
    AutoFixRequest(agent_id="cody", project_id="ambient", action_type="t", kind="agent_task", instruction="do X")
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_autonomy_kind_schema.py -v`
Expected: FAIL — `AutoFixRequest` has no `kind`/`instruction`; `command` is required.

- [ ] **Step 3: Edit `AutoFixRequest`** (`autonomy/pipeline/schemas.py`)

Change `command` from required to `command: str | None = Field(None, ...)`; add `kind: str = Field("command", description="'command' | 'agent_task'")` and `instruction: str | None = Field(None, description="Natural-language task spec for agent_task")`. Keep all other fields. (Do NOT add a validator forcing command-xor-instruction yet — the router/bridge enforce shape; keep the schema permissive so tests of malformed input still 500-not-422 per repo convention.)

- [ ] **Step 4: Edit the models** (`autonomy/models.py`)

On `AutoAction` and `ApprovalQueueEntry`: add
```python
kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="command")
instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
```
and change `action_command` to `Mapped[str | None] = mapped_column(Text, nullable=True)` on both.

- [ ] **Step 5: Generate the migration**

Run: `/c/Python314/python.exe -m alembic revision --autogenerate -m "add kind instruction to autonomy actions"`
Then OPEN the generated file and verify it (a) adds `kind` (with server_default `"command"` so existing rows backfill), (b) adds `instruction` nullable, (c) alters `action_command` to nullable on both `auto_actions` and `approval_queue`, and NOTHING else (drop stray autogen noise — pgvector/AGE tables sometimes appear; remove unrelated ops). Ensure `downgrade()` reverses all three on both tables. If autogenerate can't reach a DB, hand-write the revision using an adjacent revision as the template (`op.add_column`, `op.alter_column(... nullable=True)`), setting `down_revision` to the current head (find it: `/c/Python314/python.exe -m alembic heads`).

- [ ] **Step 6: Run the schema tests green**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_autonomy_kind_schema.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add life_graph/autonomy/models.py life_graph/autonomy/pipeline/schemas.py alembic/versions/ tests/unit/test_autonomy_kind_schema.py
git commit -m "feat(action-roles-b2): kind/instruction on autonomy actions; action_command nullable"
```

---

### Task 2: Router forces agent_task → QUEUE_FOR_APPROVAL + persists kind/instruction

**Files:**
- Modify: `life_graph/autonomy/pipeline/service.py` (`process`)
- Test: `tests/unit/test_agent_task_routing.py`

**Interfaces:**
- Consumes: `AutoFixRequest.kind`/`.instruction` (Task 1); existing `process()` routing + `AutoAction` construction.
- Produces: `process()` writes `kind`/`instruction` onto the `AutoAction` (and onto the `ApprovalQueueEntry` when it queues); when `request.kind == "agent_task"`, the routing decision is forced to `QUEUE_FOR_APPROVAL` **before** any auto-execute/shadow branch, regardless of classifier output.

- [ ] **Step 1: Write the failing test** — mock the classifier to return an AUTO_EXECUTE-eligible recommendation and assert an agent_task still queues and persists instruction:

```python
async def test_agent_task_always_queues_even_when_classifier_says_auto(agent_task_autofix_service):
    svc, mocks = agent_task_autofix_service  # fixture: classifier -> AUTO_EXECUTE, executor mocked
    req = AutoFixRequest(agent_id="cody", project_id="ambient", action_type="cody_fix",
                         kind="agent_task", instruction="Fix failing test X")
    resp = await svc.process("t1", req)
    assert resp.routing == "queued_for_approval"
    # the executor / dispatcher must NOT have run
    mocks["executor"].execute.assert_not_called()
    # persisted kind + instruction
    saved = mocks["saved_auto_action"]
    assert saved.kind == "agent_task"
    assert saved.instruction == "Fix failing test X"
    assert saved.action_command is None


async def test_command_action_routing_unchanged(agent_task_autofix_service):
    svc, mocks = agent_task_autofix_service  # classifier -> AUTO_EXECUTE
    req = AutoFixRequest(agent_id="ops", project_id="ambient", action_type="restart",
                         command="docker restart x")  # kind defaults 'command'
    resp = await svc.process("t1", req)
    assert resp.routing == "auto_executed"  # B1 behavior preserved
```

(Model the fixture on the existing `AutoFixService` unit-test fixtures — reuse their session/classifier/trust/shadow mocks; add a mock for the dispatcher injected in Task 3, or `None` here since command path doesn't use it.)

- [ ] **Step 2: Run — FAIL** (`process` ignores `kind`; agent_task would follow the classifier to auto-execute).

Run: `/c/Python314/python.exe -m pytest tests/unit/test_agent_task_routing.py -v`

- [ ] **Step 3: Implement in `process()`**

Where `process()` builds the `AutoAction`, set `kind=request.kind`, `instruction=request.instruction`, `action_command=request.command` (now may be None). After classification but before the routing branch, add:
```python
# B2-D2: open-ended agent work never auto-executes — always human-approved.
if request.kind == "agent_task":
    routing = Routing.QUEUE_FOR_APPROVAL   # use the real enum/string the code uses
```
Ensure the queued `ApprovalQueueEntry` also carries `kind`/`instruction`. Do not touch the command path.

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5: Commit**

```bash
git add life_graph/autonomy/pipeline/service.py tests/unit/test_agent_task_routing.py
git commit -m "feat(action-roles-b2): agent_task always queues; persist kind/instruction through process()"
```

---

### Task 3: `_run_action` agent_task branch → `dispatch_task` + `DriverResult` adapter

**Files:**
- Modify: `life_graph/autonomy/pipeline/service.py` (`__init__`, `_run_action`; small private adapter)
- Test: `tests/unit/test_agent_task_execution.py`

**Interfaces:**
- Consumes: `TaskDispatcher.dispatch_task(...) -> DriverResult` (verified signature above); `AutoAction.kind`/`.instruction`.
- Produces: `AutoFixService` gains an injected/lazily-constructed `TaskDispatcher` (`self._dispatcher`); `_run_action` branches on `auto_action.kind`. New private `_driver_result_to_fields(result: DriverResult) -> tuple[int, str, str, int]` returning `(exit_code, stdout, stderr, duration_ms)` where `exit_code = 0 if result.success else 1`, `stdout = result.output`, `stderr = result.error or ""`, `duration_ms = result.duration_ms`.

- [ ] **Step 1: Write the failing test** — agent_task `_run_action` calls `dispatch_task` with the instruction/persona and adapts the result:

```python
async def test_run_action_agent_task_dispatches(agent_task_service_with_dispatcher):
    svc, disp = agent_task_service_with_dispatcher  # disp.dispatch_task -> DriverResult(success=True, output="done", cost_usd=0.4, duration_ms=1200)
    auto = make_auto_action(kind="agent_task", instruction="Fix test X", action_command=None,
                            agent_id="cody", project_id="ambient")
    await svc._run_action("t1", auto, timeout_seconds=60)
    disp.dispatch_task.assert_awaited_once()
    kwargs = disp.dispatch_task.call_args.kwargs
    assert kwargs["instruction"] == "Fix test X"
    assert kwargs["persona_name"] == "cody"
    assert kwargs["interactive"] is False
    assert auto.status == "success"
    assert auto.exit_code == 0
    assert auto.stdout == "done"


async def test_run_action_agent_task_failure_maps_exit_code_1(agent_task_service_with_dispatcher_failing):
    svc, disp = agent_task_service_with_dispatcher_failing  # DriverResult(success=False, error="verify failed")
    auto = make_auto_action(kind="agent_task", instruction="X", action_command=None, agent_id="cody")
    await svc._run_action("t1", auto, timeout_seconds=60)
    assert auto.status == "failure"
    assert auto.exit_code == 1
    assert auto.stderr == "verify failed"


async def test_run_action_command_path_unchanged(agent_task_service_with_dispatcher):
    svc, disp = agent_task_service_with_dispatcher
    auto = make_auto_action(kind="command", action_command="echo hi", instruction=None)
    await svc._run_action("t1", auto, timeout_seconds=60)
    disp.dispatch_task.assert_not_awaited()   # command path uses CommandExecutor
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement**

In `AutoFixService.__init__`, construct/inject the dispatcher: `self._dispatcher = dispatcher or TaskDispatcher(session_factory=<the same session_factory the service holds>, event_bus=<the service's event_bus if any>)`. (Check what `AutoFixService.__init__` already receives — reuse its `session_factory`/`event_bus`; add an optional `dispatcher=None` param so tests inject a mock.) In `_run_action`, branch at the top:
```python
if auto_action.kind == "agent_task":
    result = await self._dispatcher.dispatch_task(
        tenant_id=tenant_id,
        task_id=auto_action.id,
        instruction=auto_action.instruction or "",
        task_type="general",
        project_id=auto_action.project_id,
        persona_name=auto_action.agent_id,
        verify_chain=["build_ok", "lint_clean"],
        interactive=False,
        cost_cap_usd=DEFAULT_AGENT_TASK_COST_CAP,   # module const, e.g. 1.0 — conservative
    )
    exit_code, stdout, stderr, duration_ms = self._driver_result_to_fields(result)
    # persist onto auto_action exactly like the command branch does (status by exit_code, etc.)
else:
    # existing CommandExecutor path, unchanged
```
Keep the lock (`self._get_lock(project_id)`), the status/persist/audit logic, and `_emit_completed` semantics identical — only the *source* of `(exit_code, stdout, stderr, duration_ms)` differs. Define `DEFAULT_AGENT_TASK_COST_CAP = 1.0` as a module constant near the top (conservative; the Governor gate enforces it).

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5: Commit**

```bash
git add life_graph/autonomy/pipeline/service.py tests/unit/test_agent_task_execution.py
git commit -m "feat(action-roles-b2): _run_action dispatches agent_task via TaskDispatcher + DriverResult adapter"
```

---

### Task 4: Dispatch-failure robustness (dispatch_task can raise)

**Files:**
- Modify: `life_graph/autonomy/pipeline/service.py` (`_run_action` agent_task branch)
- Modify: `life_graph/services/approvals.py` (`_apply_autonomous_action` failure handling)
- Test: `tests/unit/test_agent_task_dispatch_failure.py`

**Interfaces:**
- Consumes: the Task 3 agent_task branch; B1 `_apply_autonomous_action` (approve → resolve → `execute_pending`).
- Produces: a raised `DispatchError` / unexpected exception from `dispatch_task` is caught inside the agent_task branch → `auto_action.status="failure"`, `error_message` set, `AUTONOMOUS_ACTION_COMPLETED` still emitted, notification of failure — and it does NOT propagate out of `execute_pending` to wedge the feed row. The unified `_apply_autonomous_action` treats a failed-but-completed execution as a resolved feed row (approve still marks the `Approval` resolved).

- [ ] **Step 1: Write the failing test**

```python
async def test_dispatch_raise_marks_failed_not_wedged(agent_task_service_raising):
    svc, disp = agent_task_service_raising  # disp.dispatch_task raises DispatchError("wip limit")
    auto = make_auto_action(kind="agent_task", instruction="X", action_command=None, agent_id="cody")
    # must NOT raise out of _run_action
    await svc._run_action("t1", auto, timeout_seconds=60)
    assert auto.status == "failure"
    assert "wip limit" in (auto.error_message or "")


async def test_execute_pending_agent_task_dispatch_raise_does_not_propagate(agent_task_execute_pending_raising):
    svc = agent_task_execute_pending_raising
    # execute_pending on an approved agent_task whose dispatch raises -> returns a failure response, no exception
    resp = await svc.execute_pending("t1", "auto-1")
    assert resp.status == "failure"
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement**

In the Task 3 agent_task branch, wrap the `dispatch_task` call in `try/except (DispatchError, Exception) as exc:` — on exception set `exit_code=1`, `stderr=str(exc)`, `status="failure"`, `error_message=str(exc)`, and continue through the same persist/emit path (so an `AutoAction` failure row + `AUTONOMOUS_ACTION_COMPLETED` still happen). Import `DispatchError` from `drivers/dispatcher.py`. (Catch `DispatchError` explicitly first for a clean message, then a broad `except Exception` as a backstop — the command path relies on `CommandExecutor` never raising, so this backstop is agent_task-only.)

In `services/approvals.py::_apply_autonomous_action`: today the approve path calls `execute_pending` and swallows only `ValueError` "Cannot execute action in status". Since `execute_pending` for agent_task now returns a failure response instead of raising (per the branch above), confirm the approve path still marks the generic `Approval` row resolved when `execute_pending` returns a failure status (a failed execution is still a *resolved* approval — the user approved; it ran; it failed). Add a test asserting the `Approval` row is marked resolved even when the underlying agent_task execution failed. Do NOT broaden the existing `ValueError` swallow to bare `Exception` — keep it narrow; the fix is that `execute_pending` no longer raises for this case.

- [ ] **Step 4: Run — PASS.** Also run the B1 unified-feed tests to confirm no regression: `/c/Python314/python.exe -m pytest tests/unit/test_unified_autonomous_action.py -v`.

- [ ] **Step 5: Commit**

```bash
git add life_graph/autonomy/pipeline/service.py life_graph/services/approvals.py tests/unit/test_agent_task_dispatch_failure.py
git commit -m "feat(action-roles-b2): agent_task dispatch failures mark AutoAction failed without wedging the feed"
```

---

### Task 5: Shared propose contract + `kind`-aware bridge branch

**Files:**
- Create: `life_graph/kernel/propose_contract.py` (shared constants)
- Modify: `life_graph/kernel/personas.py` (ops uses the shared constant — refactor, no behavior change) and `life_graph/kernel/ambient.py` if the contract text lives/injects there
- Modify: `life_graph/services/action_proposal_bridge.py` (`process_result` `kind`-dispatch)
- Test: `tests/unit/test_proposal_bridge_agent_task.py` + extend the existing bridge test

**Interfaces:**
- Consumes: `_extract_json_array` (existing); `AutoFixRequest` with `kind`/`instruction` (Task 1); `AutoFixService.process`.
- Produces: `COMMAND_PROPOSE_CONTRACT` and `AGENT_TASK_PROPOSE_CONTRACT` string constants in `kernel/propose_contract.py`. `process_result` dispatches per item: an item with `kind == "agent_task"` (or with `instruction` and no `command`) builds `AutoFixRequest(kind="agent_task", instruction=item["instruction"], command=None, action_type=item["name"], ...)`; a command item is unchanged. Malformed/typeless items still skipped (no execute), preserving B1's default-safe behavior.

- [ ] **Step 1: Write the failing tests**

```python
async def test_bridge_routes_agent_task_proposal(bridge_with_mock_autofix):
    bridge, autofix = bridge_with_mock_autofix
    text = 'Here you go. [{"kind":"agent_task","name":"cody_fix","instruction":"Fix test X","rationale":"broken","risk_hint":"moderate"}]'
    n = await bridge.process_result("t1", "cody", "schedule:cody-ambient", text)
    assert n == 1
    req = autofix.process.call_args.args[1]
    assert req.kind == "agent_task"
    assert req.instruction == "Fix test X"
    assert req.command is None
    assert req.action_type == "cody_fix"


async def test_bridge_still_routes_command_proposal(bridge_with_mock_autofix):
    bridge, autofix = bridge_with_mock_autofix
    text = '[{"name":"restart","command":"docker restart x","rationale":"stuck","risk_hint":"moderate"}]'
    n = await bridge.process_result("t1", "ops", "schedule:ops-ambient", text)
    assert n == 1
    req = autofix.process.call_args.args[1]
    assert req.kind == "command"
    assert req.command == "docker restart x"


async def test_bridge_skips_item_missing_both_command_and_instruction(bridge_with_mock_autofix):
    bridge, autofix = bridge_with_mock_autofix
    text = '[{"name":"noop","rationale":"nothing"}]'
    n = await bridge.process_result("t1", "cody", "schedule:cody-ambient", text)
    assert n == 0
    autofix.process.assert_not_called()
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement**

Create `kernel/propose_contract.py` with two constants: `COMMAND_PROPOSE_CONTRACT` (the exact text currently inline in the ops persona `system_prompt` — move it here verbatim) and `AGENT_TASK_PROPOSE_CONTRACT`:
```
" When run on a schedule you are in PROPOSE mode: investigate read-only, do"
" not perform any change, and end your reply with ONLY a JSON array of"
" proposed tasks, each {\"kind\": \"agent_task\", \"name\": str,"
" \"instruction\": str, \"rationale\": str, \"risk_hint\":"
" \"safe\"|\"moderate\"|\"dangerous\"}. Return [] if nothing needs doing."
" Each instruction is a concrete, self-contained task for an engineer agent."
```
Refactor the ops persona `system_prompt` in `personas.py` to reference/compose `COMMAND_PROPOSE_CONTRACT` (behavior-identical — verify the seeded prompt text is unchanged for ops by comparing before/after, since seeding skips existing rows on the VM but a fresh tenant must get the same text). In `action_proposal_bridge.py::process_result`, replace the single `if not ... item.get("command"): continue` with a `kind`-dispatch:
```python
kind = item.get("kind") or ("agent_task" if item.get("instruction") and not item.get("command") else "command")
if kind == "agent_task":
    if not item.get("name") or not item.get("instruction"):
        continue
    request = AutoFixRequest(agent_id=agent_name, project_id=AMBIENT_PROJECT_ID,
                             action_type=item["name"], command=None, kind="agent_task",
                             instruction=item["instruction"], description=item.get("rationale", ""))
else:
    if not item.get("name") or not item.get("command"):
        continue
    request = AutoFixRequest(agent_id=agent_name, project_id=AMBIENT_PROJECT_ID,
                             action_type=item["name"], command=item["command"],
                             description=item.get("rationale", ""))
await self._autofix.process(tenant_id, request)
```

- [ ] **Step 4: Run — PASS.** Also run the existing bridge tests: `/c/Python314/python.exe -m pytest tests/unit/test_action_proposal_bridge.py -v` (ops command path + scheduled-marker gate must stay green).

- [ ] **Step 5: Commit**

```bash
git add life_graph/kernel/propose_contract.py life_graph/kernel/personas.py life_graph/kernel/ambient.py life_graph/services/action_proposal_bridge.py tests/unit/test_proposal_bridge_agent_task.py tests/unit/test_action_proposal_bridge.py
git commit -m "feat(action-roles-b2): shared propose contract + kind-aware bridge routes agent_task proposals"
```

---

### Task 6: cody ambient role — membership, prompt, opt-in job, safety rules

**Files:**
- Modify: `life_graph/kernel/ambient.py` (`AMBIENT_ACTION` + `AMBIENT_JOBS`)
- Modify: `life_graph/kernel/personas.py` (cody propose-mode paragraph)
- Modify: `life_graph/autonomy/safety/ambient_rules.py` (cody action rules)
- Test: `tests/unit/test_cody_ambient_seed.py`

**Interfaces:**
- Consumes: `AGENT_TASK_PROPOSE_CONTRACT` (Task 5); `AMBIENT_ACTION_READONLY_TOOLS` + `tool_override` path (B1); `seed_ambient_jobs`, `seed_ambient_autonomy` (B1).
- Produces: `"cody"` in `AMBIENT_ACTION`; a `cody-ambient` job (`active: False`, cron e.g. `"0 2 * * *"` — one hour after ops so they don't collide, before is fine too as long as read-only); cody's `system_prompt` gains the agent_task propose paragraph; cody-namespaced `ActionSafetyRule`s seeded (e.g. `cody_fix` = moderate/dangerous — but note routing forces queue regardless per B2-D2, so these rules only set the displayed risk badge).

- [ ] **Step 1: Write the failing test**

```python
def test_cody_in_ambient_action():
    from life_graph.kernel.ambient import AMBIENT_ACTION
    assert "cody" in AMBIENT_ACTION

def test_cody_ambient_job_seeded_inactive():
    from life_graph.kernel.ambient import AMBIENT_JOBS
    job = next(j for j in AMBIENT_JOBS if j["name"] == "cody-ambient")
    assert job["active"] is False
    assert job["agent_name"] == "cody"

def test_cody_persona_has_agent_task_propose_contract():
    from life_graph.kernel.personas import _BUILTIN_PERSONAS
    cody = next(p for p in _BUILTIN_PERSONAS if p["name"] == "cody")
    assert "agent_task" in cody["system_prompt"]
    assert "instruction" in cody["system_prompt"]
```
Plus a safety-rule seeding test mirroring `test_action_roles_seeding.py`: `seed_ambient_autonomy` creates cody rules (assert a `cody_*` rule exists with a risk level).

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement**

Add `"cody"` to the `AMBIENT_ACTION` frozenset. Append a `cody-ambient` dict to `AMBIENT_JOBS` mirroring `ops-ambient` (`active: False`, `agent_name: "cody"`, its own cron, `input: {}`, description "Ambient code sweep: proposes fixes for failing tests / known issues for your approval."). Append `AGENT_TASK_PROPOSE_CONTRACT` to cody's `system_prompt` in `_BUILTIN_PERSONAS`. In `ambient_rules.py`, add a small set of cody action rules (e.g. `cody_fix`, `cody_refactor` → `moderate`; anything matching a destructive glob stays default-dangerous) via the same `create_rule` calls `seed_ambient_autonomy` already uses; keep it idempotent (name-diff, as B1 does). Confirm `main.py`/`workers/settings.py` already invoke `seed_ambient_jobs` + `seed_ambient_autonomy` for the ambient tenant so cody flows through with no new wiring (if the ambient tenant only seeds `default`, that's unchanged — cody rides the same call).

- [ ] **Step 4: Run — PASS.** Confirm imports clean: `/c/Python314/python.exe -c "import life_graph.main; import life_graph.workers.settings"`.

- [ ] **Step 5: Commit**

```bash
git add life_graph/kernel/ambient.py life_graph/kernel/personas.py life_graph/autonomy/safety/ambient_rules.py tests/unit/test_cody_ambient_seed.py
git commit -m "feat(action-roles-b2): cody ambient action role (opt-in) + agent_task propose contract + safety rules"
```

---

### Task 7: Approvals UI renders agent_task instruction

**Files:**
- Modify: `dashboard/lib/mobile-api.ts` (`useApprovals` / `mapApproval` — pass through `kind` + `instruction`)
- Modify: the `/m/approvals` approvals component (render instruction + verifier chain + cost cap for agent_task rows)
- Modify (backend, if needed): `life_graph/services/autonomous_approvals.py` producer payload and/or `services/approvals.py::_serialize` to include `kind` + `instruction` (B1's `_serialize` already returns `payload`; extend the producer's `payload` to carry `kind`/`instruction` so the client can render without a shell command)
- Test: covered by tsc + build; add a small backend unit test if the producer payload changes

**Interfaces:**
- Consumes: the generic `Approval` row `payload` (B1 returns it in `_serialize`); `ApprovalVM`/`mapApproval` (B1).
- Produces: agent_task approval rows show the natural-language instruction (never a blank/shell field), a "runs cody · build_ok, lint_clean" descriptor, and the risk badge; command rows unchanged.

- [ ] **Step 1: Backend — extend producer payload** (`services/autonomous_approvals.py`)

Where `_mirror_to_feed` builds `payload={auto_action_id, approval_id, risk_level}`, add `kind` and (when agent_task) `instruction`, read from the `AutoAction`/`ApprovalQueueEntry`. Add/extend a unit test in `tests/unit/test_autonomous_approvals_producer.py` asserting an agent_task entry's payload carries `kind == "agent_task"` + the instruction. Run it green.

- [ ] **Step 2: Client — pass through** (`lib/mobile-api.ts`)

In `mapApproval`, read `payload.kind` + `payload.instruction` (defensively typed, `typeof === "string" ? ... : null`) onto `ApprovalVM`. Non-breaking additive change (mirror B1's `riskLevel` passthrough).

- [ ] **Step 3: Component — render** the approvals component: for `kind === "agent_task"` rows, show the instruction text and a small "runs cody · build_ok, lint_clean" line instead of a shell-command preview; keep the risk badge; command rows unchanged.

- [ ] **Step 4: Verify** — `cd dashboard && npx tsc --noEmit && npm run build` (both clean).

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/autonomous_approvals.py tests/unit/test_autonomous_approvals_producer.py dashboard/lib/mobile-api.ts dashboard/components/
git commit -m "feat(action-roles-b2): approvals feed renders agent_task instruction + verifier/cost descriptor"
```

---

### Task 8: Backend E2E + final verification

**Files:**
- Create: `tests/integration/test_action_roles_agent_task_e2e.py`

**Interfaces:**
- Consumes: the full B2 chain (bridge → process → queue → approve → dispatch).

- [ ] **Step 1: Write the E2E test** — drive the agent_task loop with mocks (no real DB / no real agent):
  - Feed a cody agent_task proposal through `ActionProposalBridge.process_result` with `AutoFixService.process` mocked to assert it's called with `kind="agent_task"` + the instruction.
  - Then a `process`-level path (classifier mocked to AUTO_EXECUTE) asserting the routing is `queued_for_approval` (never auto).
  - Then the approve path (`_apply_autonomous_action`) with `execute_pending` reaching a **mocked** `TaskDispatcher.dispatch_task` returning `DriverResult(success=True)` → assert dispatch called with `persona_name="cody"`, `verify_chain=["build_ok","lint_clean"]`, `interactive=False`, and the AutoAction ends `success`.
  - A negative: dispatch raising `DispatchError` → AutoAction `failure`, feed row still resolved, no exception.
  Non-vacuous (assert real call args / routing), following `tests/integration/test_action_roles_end_to_end.py` (B1) for style.

- [ ] **Step 2: Run — GREEN.**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_action_roles_agent_task_e2e.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_action_roles_agent_task_e2e.py
git commit -m "test(action-roles-b2): agent_task end-to-end — propose -> queue -> approve -> dispatch"
```

---

## Final verification (after all tasks)

- [ ] Full unit + both action-role E2E: `/c/Python314/python.exe -m pytest tests/unit/ tests/integration/test_action_roles_end_to_end.py tests/integration/test_action_roles_agent_task_e2e.py -q`
- [ ] Autonomy regression: `/c/Python314/python.exe -m pytest tests/ -k "autonomy or autofix or approval or pipeline or driver or dispatch" -q`
- [ ] `ruff check life_graph/ && ruff format --check life_graph/` (only touched lines must be clean; pre-existing errors unchanged)
- [ ] `cd dashboard && npx tsc --noEmit && npm run build`
- [ ] Imports clean: `/c/Python314/python.exe -c "import life_graph.main; import life_graph.workers.settings"`
- [ ] Migration sanity: `/c/Python314/python.exe -m alembic heads` shows a single head; the new revision's `down_revision` chains to the prior head; `downgrade()` reverses all three column changes on both tables.

## Deploy checklist (out of band; batch-deploy — deploy only when told; deploys A + B1 + B2 together)

1. Rebuild app + worker + dashboard; reconnect `web` net on app.
2. **Run the Alembic migration on the VM** (`alembic upgrade head`) — mind the migration `search_path` gotcha noted in prior deploys.
3. `seed_ambient_autonomy("personal")` (adds cody safety rules) + confirm `LIFE_GRAPH_SHADOW_MODE_ENABLED=true` (commands only; agent_task always queues).
4. Re-sync `ops` + `cody` `system_prompt`s into `agent_personas` (personal+default) — seeding skips existing rows, so a prompt CHANGE needs an explicit re-sync (as in prior deploys).
5. Seed the `cody-ambient` job for `personal`; **leave it inactive** until you've reviewed cody's seeded safety rules and are comfortable approving agent runs.
6. Enable `cody-ambient`; the first proposals will queue in `/m/approvals`; approve one small fix and confirm the cody dispatch runs under the verifier chain + Governor budget cap before relying on it.

## Notes / risks

- **Read-only enforcement is load-bearing** (same as B1): the scheduled cody run gets `AMBIENT_ACTION_READONLY_TOOLS` via `tool_override`; if that override path breaks, cody (which carries write tools) could act inline. B1's `tool_override` retry-path test covers the mechanism; the final review should re-verify cody rides it.
- **agent_task never auto-executes in B2** — the router force-queues it. Do not "optimize" this into the classifier; it is the safety posture (B2-D2).
- **`dispatch_task` cost** — `DEFAULT_AGENT_TASK_COST_CAP` bounds spend per run via the Governor; the developer is cost-conscious, so keep it conservative (≈1.0 USD) and surface it in the approvals UI.
- **`DriverResult` has no `exit_code`** — the adapter (`0 if success else 1`) is the one place the two subsystems' result shapes meet; get it right or AutoAction status/audit will be wrong.
- **swe-lead deferred** — a later phase; its nested-delegation execution model is out of scope here.
