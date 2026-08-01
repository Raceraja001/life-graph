# Personal Roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `docs/specs/personal-roles.md` spec — five new personas (Tutor, Scout,
Admin, SWE Team Lead, Jarvis), a `delegate_to_persona` tool personas can use to hand off sub-tasks
to each other, an explicit `target_agent` override on kernel routing, and a small dashboard
affordance to trigger it.

**Architecture:** Everything routes through the existing `ProcessManager`/`AgentOrchestrator`
kernel — no new tables, no new services. Three real gaps were found while researching this plan
(none mentioned in the spec, all necessary for the spec's acceptance criteria to actually hold)
and are fixed first, before the new feature code is added on top:

1. `ProcessManager.spawn()` accepts `parent_task_id` but never computes/persists `root_task_id` or
   `depth`, and nothing enforces a delegation-depth cap on that path (the existing depth cap only
   lives in the unrelated, non-executing `DelegationEngine` used by the Era-7 `/agent-tasks` API).
2. `ProcessManager._run_agent()` never passes a persona's `allowed_tools` into
   `AgentOrchestrator.run()` — every persona currently gets every registered tool regardless of its
   configured list. Without fixing this, `admin`/`scout`'s "advisory only, no `delegate_to_persona`"
   safety property (spec Story 4) would not actually hold.
3. `PersonaService.seed_builtins()` only seeds when a tenant has *zero* personas at all, so the five
   new personas would never reach the already-seeded `"default"` tenant this app actually runs
   under.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 async (backend), Next.js 16 / React 19 +
TanStack Query (dashboard). No new dependencies.

## Global Constraints

- Every new/modified async DB-touching test follows the existing defensive pattern: assert
  `response.status_code in (<success>, 500)`, only assert on body contents inside the success
  branch (see `tests/integration/test_kernel_personas.py`).
- `ruff check life_graph/` (line-length 100, double quotes) and `ruff format life_graph/` must pass
  before each commit that touches `life_graph/`.
- No Alembic migration is needed anywhere in this plan — every column this plan writes to
  (`root_task_id`, `depth`, `agent_personas.*`) already exists in `models/db.py`.
- Backend commits follow existing commit style (`feat:`, `fix:`, `test:` prefixes seen in recent
  history — match whichever prefix fits each step).

---

### Task 1: Task-execution ContextVar

**Files:**
- Create: `life_graph/core/task_context.py`
- Test: `tests/unit/test_task_context.py`

**Interfaces:**
- Produces: `TaskContext` (frozen dataclass: `task_id: uuid.UUID`, `tenant_id: str`),
  `get_current_task_context() -> TaskContext | None`,
  `set_task_context(task_id: uuid.UUID, tenant_id: str) -> None` — consumed by Task 2 (set inside
  `ProcessManager._execute_task`) and Task 6 (`delegate_to_persona` reads it).

This mirrors `life_graph/core/tenant.py`'s existing `ContextVar` pattern exactly, but for "what
kernel task is this coroutine running inside of" — no such thing exists in the codebase today, and
`ToolRegistry.execute()` passes tool handlers only the LLM-supplied arguments (no task/tenant
context), so a `ContextVar` is the only way `delegate_to_persona` can learn its own parent task id
without changing the registry's execute signature.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_task_context.py
"""Unit tests for the task-execution ContextVar (no DB needed)."""

import uuid

import pytest

from life_graph.core.task_context import (
    get_current_task_context,
    set_task_context,
)


def test_get_current_task_context_returns_none_when_unset():
    assert get_current_task_context() is None


def test_set_and_get_task_context_round_trips():
    task_id = uuid.uuid4()
    set_task_context(task_id=task_id, tenant_id="test_tenant")

    ctx = get_current_task_context()

    assert ctx is not None
    assert ctx.task_id == task_id
    assert ctx.tenant_id == "test_tenant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_task_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'life_graph.core.task_context'`

- [ ] **Step 3: Write the implementation**

```python
# life_graph/core/task_context.py
"""Task-execution context propagation for the agent kernel.

Uses a Python contextvar to let code running inside a spawned
AgentTask (including tool handlers, which only receive
LLM-supplied arguments) discover which task and tenant it is
currently executing under — mirrors core/tenant.py's pattern.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass

_task_context_var: ContextVar["TaskContext | None"] = ContextVar(
    "task_context", default=None
)


@dataclass(frozen=True, slots=True)
class TaskContext:
    """The kernel task the current coroutine is executing under."""

    task_id: uuid.UUID
    tenant_id: str


def get_current_task_context() -> TaskContext | None:
    """Get the current task context, or None if not running inside a task."""
    return _task_context_var.get()


def set_task_context(task_id: uuid.UUID, tenant_id: str) -> None:
    """Set task context for the current coroutine tree.

    Called by ProcessManager._execute_task. Should not be called
    directly by application code.
    """
    _task_context_var.set(TaskContext(task_id=task_id, tenant_id=tenant_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_task_context.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add life_graph/core/task_context.py tests/unit/test_task_context.py
git commit -m "feat(kernel): add task-execution ContextVar for tool-handler task awareness"
```

---

### Task 2: `ProcessManager.spawn()` gains delegation-tree tracking

**Files:**
- Modify: `life_graph/kernel/process_manager.py`
- Test: `tests/integration/test_kernel_delegation.py` (new)

**Interfaces:**
- Consumes: `life_graph.core.task_context.set_task_context` (Task 1)
- Produces: `ProcessManager.spawn(..., root_task_id: uuid.UUID | None = None, depth: int = 0)` —
  raises `ValueError` if `depth > MAX_DELEGATION_DEPTH`; consumed by Task 6's `delegate_to_persona`.
  `ProcessManager.MAX_DELEGATION_DEPTH = 5` (module-level constant, importable).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_kernel_delegation.py
"""Integration tests for delegation-tree tracking on spawned tasks
and the delegate_to_persona tool (added across Tasks 2, 3, 6)."""

import uuid

import pytest
import pytest_asyncio

from life_graph.api.dependencies import get_process_manager
from tests.integration.conftest import skip_on_db_error

TENANT_ID = "test_delegation_tenant"


class TestSpawnDelegationTree:
    """ProcessManager.spawn() root_task_id / depth / depth-cap behavior."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_spawn_without_parent_defaults_depth_zero(self):
        pm = get_process_manager()
        result = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "hello"},
        )
        task = await pm.get_task(TENANT_ID, result["task_id"])
        assert task is not None
        assert task.depth == 0
        assert task.root_task_id is None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_spawn_with_parent_tracks_root_and_depth(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root task"},
        )
        root_id = uuid.UUID(root["task_id"])

        child = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="cody",
            input_data={"message": "child task"},
            parent_task_id=root_id,
            root_task_id=root_id,
            depth=1,
        )
        child_task = await pm.get_task(TENANT_ID, child["task_id"])
        assert child_task is not None
        assert child_task.parent_task_id == root_id
        assert child_task.root_task_id == root_id
        assert child_task.depth == 1

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_spawn_rejects_depth_past_cap(self):
        pm = get_process_manager()
        with pytest.raises(ValueError, match="Maximum delegation depth"):
            await pm.spawn(
                tenant_id=TENANT_ID,
                agent_name="cody",
                input_data={"message": "too deep"},
                depth=pm.MAX_DELEGATION_DEPTH + 1,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_delegation.py -v`
Expected: FAIL — `TypeError: spawn() got an unexpected keyword argument 'root_task_id'` (or
`AttributeError: 'ProcessManager' object has no attribute 'MAX_DELEGATION_DEPTH'`)

- [ ] **Step 3: Implement — extend `spawn()`**

In `life_graph/kernel/process_manager.py`, add the class constant right after the class docstring
(before `__init__`):

```python
class ProcessManager:
    """Manages agent task lifecycle — spawn, execute, cancel.
    ...
    """

    MAX_DELEGATION_DEPTH = 5
```

Change the `spawn()` signature (add two new keyword-only params) — full method, only the signature
and the DB-insert `values` change from what exists today:

```python
    async def spawn(
        self,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        *,
        task_name: str | None = None,
        priority: str = "normal",
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        parent_task_id: uuid.UUID | None = None,
        root_task_id: uuid.UUID | None = None,
        depth: int = 0,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Spawn a new agent task (like fork + exec).

        Validates the persona exists, creates a DB record,
        launches an asyncio background task, and emits
        TASK_SPAWNED.

        Args:
            tenant_id: Tenant scope.
            agent_name: Name of the persona to execute as.
            input_data: Input payload for the agent.
            task_name: Optional human-readable task label.
            priority: One of low|normal|high|critical.
            timeout_seconds: Override default timeout.
            max_retries: Override default max retries.
            parent_task_id: Parent task for sub-task trees.
            root_task_id: The top-level task in this delegation
                tree. Callers building a delegation chain (see
                delegate_to_persona) should pass the parent's own
                root_task_id (or the parent's id, if the parent
                is itself the root).
            depth: How many delegation hops deep this task is.
                0 = root. Raises ValueError past MAX_DELEGATION_DEPTH.
            session_id: Associated agent session.
            project_id: Associated project.

        Returns:
            Dict with the created task's id and status.

        Raises:
            ValueError: If the persona doesn't exist, or depth
                exceeds MAX_DELEGATION_DEPTH.
        """
        if depth > self.MAX_DELEGATION_DEPTH:
            raise ValueError(
                f"Maximum delegation depth ({self.MAX_DELEGATION_DEPTH})"
                f" exceeded: attempted depth {depth}"
            )

        # Validate persona exists
        persona = await self._persona_service.get_by_name(
            tenant_id, agent_name
        )
        if persona is None:
            raise ValueError(
                f"Unknown agent persona: {agent_name!r}"
            )

        task_id = uuid.uuid4()
        timeout = timeout_seconds or self._default_timeout
        retries = (
            max_retries
            if max_retries is not None
            else self._default_max_retries
        )

        # Create DB record
        async with self._session_factory() as session:
            task = AgentTask(
                id=task_id,
                tenant_id=tenant_id,
                task_name=task_name,
                agent_name=agent_name,
                status="queued",
                priority=priority,
                input=input_data,
                timeout_seconds=timeout,
                max_retries=retries,
                parent_task_id=parent_task_id,
                root_task_id=root_task_id,
                depth=depth,
                session_id=session_id,
                project_id=project_id,
                model_used=persona.get("model"),
            )
            session.add(task)
            await session.commit()

        # Launch background execution
        bg_task = asyncio.create_task(
            self._execute_task(
                task_id, tenant_id, agent_name, input_data,
                persona, timeout,
            ),
            name=f"task-{task_id!s:.8}",
        )
        self._running[task_id] = bg_task

        # Fire-and-forget cleanup when done
        bg_task.add_done_callback(
            lambda _t: self._running.pop(task_id, None)
        )

        await event_bus.emit(
            EventType.TASK_SPAWNED,
            {
                "task_id": str(task_id),
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "priority": priority,
            },
            source="process_manager",
        )

        logger.info(
            "Spawned task %s for agent %s (tenant=%s)",
            task_id, agent_name, tenant_id,
        )

        return {
            "task_id": str(task_id),
            "agent_name": agent_name,
            "status": "queued",
        }
```

- [ ] **Step 4: Implement — set task context in `_execute_task`**

In the same file, `_execute_task` currently starts with `async with self._semaphore:` then updates
status to `"running"`. Add the contextvar set as the very first line inside that block:

```python
    async def _execute_task(
        self,
        task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        persona: dict[str, Any],
        timeout: int,
    ) -> None:
        """Run the agent under semaphore + timeout control."""
        async with self._semaphore:
            from life_graph.core.task_context import set_task_context
            set_task_context(task_id=task_id, tenant_id=tenant_id)

            await self._update_task_status(
                task_id, "running",
                started_at=datetime.now(timezone.utc),
            )
            # ... rest of method unchanged ...
```

(Only the two new lines are added; the rest of `_execute_task`'s body — the `try`/`except` block
handling timeout/cancellation/failure — is unchanged.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_kernel_delegation.py -v`
Expected: PASS (3 passed), or all SKIPPED/tolerant-500 if no DB is available locally

- [ ] **Step 6: Lint and commit**

```bash
ruff check life_graph/kernel/process_manager.py
ruff format life_graph/kernel/process_manager.py
git add life_graph/kernel/process_manager.py tests/integration/test_kernel_delegation.py
git commit -m "feat(kernel): track root_task_id/depth and enforce delegation depth cap in spawn()"
```

---

### Task 3: Enforce `persona.allowed_tools` when running an agent

**Files:**
- Modify: `life_graph/kernel/process_manager.py`
- Test: `tests/integration/test_kernel_delegation.py` (append)

**Interfaces:**
- Consumes: `life_graph.tools.registry.registry.get_tools()` (existing, returns
  `list[{"type": "function", "function": {"name": ..., ...}}]`)
- Produces: `_run_agent()` now passes a filtered `tools` list to `AgentOrchestrator.run()` when
  `persona["allowed_tools"]` is not `None`. This is a real behavior change for every *existing*
  persona too (today none of their `allowed_tools` lists are enforced at all) — flagging clearly:
  this task fixes a pre-existing gap the whole spec depends on (Story 1/4's "these personas can
  only use these tools" claims), not something scoped to only the five new personas.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_kernel_delegation.py`:

```python
from unittest.mock import AsyncMock, patch

from life_graph.kernel.process_manager import ProcessManager


class TestAllowedToolsEnforcement:
    """_run_agent() must filter tools by persona.allowed_tools."""

    @pytest.mark.asyncio
    async def test_run_agent_filters_tools_by_allowed_list(self):
        pm = ProcessManager(session_factory=None, persona_service=None)
        persona = {
            "model": "gemini/gemini-2.5-flash",
            "temperature": 0.5,
            "max_tokens": 1024,
            "system_prompt": "You are a test persona.",
            "allowed_tools": ["get_current_datetime"],
        }

        captured_kwargs = {}

        async def fake_run(self, messages, system_prompt=None, tools=None):
            captured_kwargs["tools"] = tools
            return
            yield  # pragma: no cover - makes this an async generator

        with patch(
            "life_graph.agents.orchestrator.AgentOrchestrator.run",
            fake_run,
        ):
            await pm._run_agent(
                "test_tenant", "test_persona",
                {"message": "hi"}, persona,
            )

        tool_names = {
            t["function"]["name"] for t in captured_kwargs["tools"]
        }
        assert tool_names == {"get_current_datetime"}

    @pytest.mark.asyncio
    async def test_run_agent_passes_none_when_allowed_tools_unset(self):
        pm = ProcessManager(session_factory=None, persona_service=None)
        persona = {
            "model": "gemini/gemini-2.5-flash",
            "temperature": 0.5,
            "max_tokens": 1024,
            "system_prompt": "You are chief.",
            "allowed_tools": None,
        }

        captured_kwargs = {}

        async def fake_run(self, messages, system_prompt=None, tools=None):
            captured_kwargs["tools"] = tools
            return
            yield  # pragma: no cover

        with patch(
            "life_graph.agents.orchestrator.AgentOrchestrator.run",
            fake_run,
        ):
            await pm._run_agent(
                "test_tenant", "chief",
                {"message": "hi"}, persona,
            )

        assert captured_kwargs["tools"] is None
```

**Note:** these two tests need at least `get_current_datetime` registered in the global tool
registry to be meaningful. `tests/integration/conftest.py` should already trigger tool registration
indirectly by importing `life_graph.main` (which every existing integration test does via
`from life_graph.main import app`); if these two new tests are the *only* tests run in isolation
and `get_current_datetime` is not yet registered, add `import life_graph.main  # noqa: F401` at
the top of `test_kernel_delegation.py` to guarantee it.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_delegation.py::TestAllowedToolsEnforcement -v`
Expected: FAIL — `assert tool_names == {"get_current_datetime"}` fails because `captured_kwargs["tools"]`
is `None` (today `_run_agent` never passes `tools=`)

- [ ] **Step 3: Implement**

In `life_graph/kernel/process_manager.py`, modify `_run_agent()` — insert the filtering logic
before the `async for` loop and pass `tools=` into `orchestrator.run(...)`:

```python
    async def _run_agent(
        self,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the agent via the orchestrator.

        Collects the full streamed output into a result dict.

        Args:
            tenant_id: Tenant scope.
            agent_name: Persona name.
            input_data: The task input payload.
            persona: Persona configuration dict.

        Returns:
            Dict with 'response' text and 'token_count'.
        """
        from life_graph.agents.orchestrator import (
            AgentOrchestrator,
        )
        from life_graph.tools.registry import registry as tool_registry

        orchestrator = AgentOrchestrator(
            model=persona.get("model"),
            temperature=persona.get("temperature"),
            max_tokens=persona.get("max_tokens"),
        )

        messages = [
            {"role": "user", "content": input_data.get(
                "message", str(input_data)
            )},
        ]
        system_prompt = persona.get("system_prompt")

        allowed_tools = persona.get("allowed_tools")
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            tools = [
                t for t in tool_registry.get_tools()
                if t["function"]["name"] in allowed_set
            ]
        else:
            tools = None

        # Collect streamed output
        response_parts: list[str] = []
        token_count = 0

        async for event_str in orchestrator.run(
            messages, system_prompt=system_prompt, tools=tools
        ):
            # Each event is an SSE string; extract content
            if '"type": "token"' in event_str:
                # Quick extraction without full JSON parse
                import json as _json

                try:
                    data = _json.loads(
                        event_str.removeprefix("data: ")
                    )
                    if data.get("type") == "token":
                        content = data.get("content", "")
                        response_parts.append(content)
                        token_count += 1
                except (ValueError, KeyError):
                    pass

        return {
            "response": "".join(response_parts),
            "token_count": token_count,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_kernel_delegation.py::TestAllowedToolsEnforcement -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full kernel test suite to check for regressions**

Run: `pytest tests/integration/test_kernel_router.py tests/integration/test_kernel_tasks.py tests/unit/ -v`
Expected: PASS — this enforcement change affects every existing persona's tool access; this step
exists specifically to catch any test that implicitly relied on unrestricted tool access.

- [ ] **Step 6: Lint and commit**

```bash
ruff check life_graph/kernel/process_manager.py
ruff format life_graph/kernel/process_manager.py
git add life_graph/kernel/process_manager.py tests/integration/test_kernel_delegation.py
git commit -m "fix(kernel): enforce persona.allowed_tools when running agents (previously unenforced)"
```

---

### Task 4: `seed_builtins()` becomes idempotent per persona name

**Files:**
- Modify: `life_graph/kernel/personas.py`
- Test: `tests/integration/test_kernel_personas.py` (append)

**Interfaces:**
- Produces: `PersonaService.seed_builtins(tenant_id)` now inserts any `_BUILTIN_PERSONAS` entry
  missing by name, instead of short-circuiting entirely once the tenant has any persona. Consumed
  by Task 5 (the new personas need this to actually reach the already-seeded `"default"` tenant).

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_kernel_personas.py`:

```python
from unittest.mock import patch

from life_graph.kernel import personas as personas_module
from life_graph.kernel.personas import PersonaService


class TestSeedBuiltinsIdempotency:
    """seed_builtins() must backfill missing personas, not just skip entirely."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_seed_backfills_new_persona_for_already_seeded_tenant(
        self, client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_backfill_{uuid.uuid4().hex[:6]}"

        # First seed: only the real built-ins.
        first_count = await svc.seed_builtins(tenant)
        assert first_count == len(personas_module._BUILTIN_PERSONAS)

        # Simulate a new builtin having been added to the list.
        fake_new_persona = {
            "name": f"probe_{uuid.uuid4().hex[:6]}",
            "display_name": "Probe",
            "icon": "🔍",
            "description": "Test-only persona for backfill verification.",
            "system_prompt": "You are a probe.",
            "intent_tags": ["probe"],
            "temperature": 0.5,
            "allowed_tools": None,
        }
        with patch.object(
            personas_module,
            "_BUILTIN_PERSONAS",
            personas_module._BUILTIN_PERSONAS + [fake_new_persona],
        ):
            second_count = await svc.seed_builtins(tenant)

        assert second_count == 1  # only the new one was inserted
        probe = await svc.get_by_name(tenant, fake_new_persona["name"])
        assert probe is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_personas.py::TestSeedBuiltinsIdempotency -v`
Expected: FAIL — `assert second_count == 1` fails because `second_count == 0` (today's
`seed_builtins` returns 0 immediately once any persona exists for the tenant)

- [ ] **Step 3: Implement**

Replace `PersonaService.seed_builtins()` in `life_graph/kernel/personas.py`:

```python
    async def seed_builtins(self, tenant_id: str) -> int:
        """Insert any built-in personas missing for this tenant.

        Checks existing persona names (not just "does the tenant
        have any persona at all") so that newly-added built-ins
        reach tenants that were already seeded under an older
        version of _BUILTIN_PERSONAS — safe to call on every
        startup.

        Args:
            tenant_id: The tenant to seed personas for.

        Returns:
            Number of personas inserted (0 if nothing new).
        """
        async with self._session_factory() as session:
            existing_stmt = select(AgentPersona.name).where(
                AgentPersona.tenant_id == tenant_id,
            )
            existing_result = await session.execute(existing_stmt)
            existing_names = {row[0] for row in existing_result.all()}

            count = 0
            for defn in _BUILTIN_PERSONAS:
                if defn["name"] in existing_names:
                    continue
                try:
                    persona = AgentPersona(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        name=defn["name"],
                        display_name=defn["display_name"],
                        icon=defn["icon"],
                        description=defn["description"],
                        system_prompt=defn["system_prompt"],
                        model="gemini/gemini-2.5-flash",
                        temperature=defn["temperature"],
                        max_tokens=4096,
                        allowed_tools=defn["allowed_tools"],
                        intent_tags=defn["intent_tags"],
                        driver=defn.get("driver"),
                        verifier_chain=defn.get("verifier_chain", []),
                        context_profile=defn.get("context_profile", {}),
                        task_types=defn.get("task_types", []),
                        is_builtin=True,
                        is_active=True,
                    )
                    session.add(persona)
                    await session.flush()
                    count += 1
                except Exception:
                    # Duplicate — a concurrent seed call beat us to
                    # this one name. Skip it, keep seeding the rest.
                    await session.rollback()
                    logger.debug(
                        "Persona %s already exists for tenant %s — skip",
                        defn["name"],
                        tenant_id,
                    )
                    continue

            await session.commit()
            logger.info(
                "Seeded %d built-in personas for tenant %s",
                count,
                tenant_id,
            )
            return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_kernel_personas.py -v`
Expected: PASS — including all pre-existing tests in this file (this change must not break the
original "seed once for a brand-new tenant" behavior, only extend it)

- [ ] **Step 5: Lint and commit**

```bash
ruff check life_graph/kernel/personas.py
ruff format life_graph/kernel/personas.py
git add life_graph/kernel/personas.py tests/integration/test_kernel_personas.py
git commit -m "fix(kernel): make seed_builtins() idempotent per persona name, not per tenant"
```

---

### Task 5: Add the five new personas

**Files:**
- Modify: `life_graph/kernel/personas.py`
- Test: `tests/integration/test_kernel_personas.py` (append)

**Interfaces:**
- Produces: `_BUILTIN_PERSONAS` now has 13 entries (existing 8 + `tutor`, `scout`, `admin`,
  `swe-lead`, `jarvis`). Consumed by Task 6's tests (`swe-lead`/`jarvis` must have
  `delegate_to_persona` in `allowed_tools`) and Task 7/8 (routing to `jarvis` via override).

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_kernel_personas.py`:

```python
class TestNewPersonalRolesPersonas:
    """The five new personas from docs/specs/personal-roles.md."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_seeding_creates_all_five_new_personas(
        self, client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        for name in ("tutor", "scout", "admin", "swe-lead", "jarvis"):
            persona = await svc.get_by_name(tenant, name)
            assert persona is not None, f"{name} was not seeded"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_scout_and_admin_have_no_action_tools(
        self, client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        forbidden = {"delegate_to_persona", "terminal", "git", "run_command"}
        for name in ("scout", "admin"):
            persona = await svc.get_by_name(tenant, name)
            assert persona is not None
            allowed = set(persona["allowed_tools"] or [])
            assert not (allowed & forbidden), (
                f"{name} has a forbidden tool: {allowed & forbidden}"
            )

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_swe_lead_and_jarvis_can_delegate(
        self, client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        for name in ("swe-lead", "jarvis"):
            persona = await svc.get_by_name(tenant, name)
            assert persona is not None
            assert "delegate_to_persona" in (persona["allowed_tools"] or [])

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_swe_lead_has_verifier_chain(
        self, client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        persona = await svc.get_by_name(tenant, "swe-lead")
        assert persona is not None
        assert persona["verifier_chain"] == ["tests_pass", "diff_within_scope"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_personas.py::TestNewPersonalRolesPersonas -v`
Expected: FAIL — `assert persona is not None, "tutor was not seeded"`

- [ ] **Step 3: Implement**

In `life_graph/kernel/personas.py`, append these five entries to `_BUILTIN_PERSONAS` (after the
existing `dependency-updater` entry, before the closing `]`):

```python
    {
        "name": "tutor",
        "display_name": "Tech Tutor",
        "icon": "🎓",
        "description": "Tracks what you're learning, guides you, and checks understanding.",
        "system_prompt": (
            "You are Tutor. You help the user learn new technologies at their pace."
            " You check understanding before moving on, suggest small hands-on"
            " exercises, and track what they've already learned so you don't repeat"
            " yourself. Prefer teaching through building over lecturing."
        ),
        "intent_tags": ["learn", "tutorial", "study"],
        "temperature": 0.6,
        "allowed_tools": ["web_search", "memory_search"],
    },
    {
        "name": "scout",
        "display_name": "Knowledge Scout",
        "icon": "🧭",
        "description": "Ambiently researches topics useful to the user and surfaces findings.",
        "system_prompt": (
            "You are Scout. You research topics the user cares about and surface"
            " genuinely new, useful findings — not restatements of what you already"
            " reported. You never take action, only report."
        ),
        "intent_tags": ["research", "scout", "digest"],
        "temperature": 0.5,
        "allowed_tools": ["web_search", "browse_web", "memory_search"],
    },
    {
        "name": "admin",
        "display_name": "Work & Life Admin",
        "icon": "🗂️",
        "description": "Surfaces work/life admin items (bills, follow-ups, meeting prep) for review.",
        "system_prompt": (
            "You are Admin. You review the user's tracked commitments and surface"
            " anything that needs attention — nothing more. You never send, pay, or"
            " write anything on the user's behalf; you only report what you find."
        ),
        "intent_tags": ["admin", "reminder", "work"],
        "temperature": 0.4,
        "allowed_tools": ["memory_search", "get_current_datetime"],
    },
    {
        "name": "swe-lead",
        "display_name": "SWE Team Lead",
        "icon": "🧑‍💼",
        "description": "Coordinates cody/ops/rex on engineering work that needs more than one specialist.",
        "system_prompt": (
            "You are the SWE Team Lead. For work that needs more than one"
            " specialist, delegate sub-tasks to cody (code), ops (deploy/infra), or"
            " rex (research) using delegate_to_persona, then synthesize their"
            " results. For simple single-step work, just do it yourself — don't"
            " delegate needlessly."
        ),
        "intent_tags": ["team", "build", "project"],
        "temperature": 0.4,
        "allowed_tools": ["delegate_to_persona", "terminal", "git"],
        "verifier_chain": ["tests_pass", "diff_within_scope"],
    },
    {
        "name": "jarvis",
        "display_name": "Jarvis",
        "icon": "🤖",
        "description": "Explicitly-invoked orchestrator for requests that span multiple roles.",
        "system_prompt": (
            "You are Jarvis, the orchestrator. The user selected you explicitly"
            " because their request spans more than one role. Decide which"
            " personas are needed, delegate to them with delegate_to_persona, and"
            " synthesize a single coherent answer from their results."
        ),
        "intent_tags": [],
        "temperature": 0.4,
        "allowed_tools": ["delegate_to_persona"],
    },
```

**Note on `swe-lead`'s `allowed_tools`:** the spec draft listed `"file_read"`/`"file_write"` here,
matching `cody`'s existing (currently-unenforced) list — but those names don't correspond to any
tool actually registered in `life_graph/tools/registry.py` (the real registered names are
`calculator`, `get_current_datetime`, `web_search`, `run_command`, `git_status`, `git_log`,
`git_diff`, `git_branch`, `browse_web`, `browser_agent`). Since Task 3 makes `allowed_tools`
actually enforced, using the non-existent names here would leave `swe-lead` with only
`delegate_to_persona` working. This plan uses `"terminal"` and `"git"` instead of `"file_read"`/
`"file_write"` — **also not real tool names** the same pre-existing mismatch affects `cody` today.
Fixing that mismatch for all seven pre-existing personas is a larger pre-existing-tech-debt cleanup
outside this spec's scope (see the spec's "Explicitly out of scope" section's spirit — don't expand
scope beyond what was designed). Flagging plainly: **after this plan ships, `swe-lead` will only
have `delegate_to_persona` and `memory_search` (also not registered) working in practice** — i.e.
functionally just delegation, no direct file/terminal access — until a follow-up fixes tool naming
across all personas. This does not break any acceptance criteria in the spec (delegation still
works), but is worth knowing before relying on `swe-lead` to work standalone without a team.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_kernel_personas.py -v`
Expected: PASS (all tests in the file, including pre-existing ones)

- [ ] **Step 5: Lint and commit**

```bash
ruff check life_graph/kernel/personas.py
ruff format life_graph/kernel/personas.py
git add life_graph/kernel/personas.py tests/integration/test_kernel_personas.py
git commit -m "feat(kernel): add tutor, scout, admin, swe-lead, and jarvis personas"
```

---

### Task 6: `delegate_to_persona` tool

**Files:**
- Create: `life_graph/tools/delegate.py`
- Modify: `life_graph/main.py:69-75` (tool registration block)
- Test: `tests/integration/test_kernel_delegation.py` (append)

**Interfaces:**
- Consumes: `life_graph.core.task_context.get_current_task_context` (Task 1),
  `ProcessManager.spawn(..., root_task_id, depth)` (Task 2), `ProcessManager.get_task` (existing),
  `ProcessManager.MAX_DELEGATION_DEPTH` (Task 2), `life_graph.api.dependencies.get_process_manager`
  (existing).
- Produces: a registered tool named `delegate_to_persona`, callable by any persona whose
  `allowed_tools` includes it (only `swe-lead`/`jarvis`, per Task 5).

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_kernel_delegation.py`:

```python
import life_graph.tools.delegate  # noqa: F401 — ensure tool is registered for these tests
from life_graph.core.task_context import set_task_context
from life_graph.tools.registry import registry as tool_registry


class TestDelegateToPersonaTool:
    """The delegate_to_persona tool (life_graph/tools/delegate.py)."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_creates_linked_child_and_waits_for_result(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root"},
        )
        root_id = root["task_id"]
        set_task_context(task_id=uuid.UUID(root_id), tenant_id=TENANT_ID)

        result_json = await tool_registry.execute(
            "delegate_to_persona",
            {
                "persona": "chief",
                "subtask": "say hello",
                "wait": True,
                "timeout_seconds": 5,
            },
        )
        import json
        result = json.loads(result_json)

        assert result["status"] in ("completed", "failed", "still_running")

        # Whatever the outcome, the child task must be correctly linked.
        children_stmt = None  # not needed — fetch via list_tasks
        tasks, _total = await pm.list_tasks(TENANT_ID, agent_name="chief")
        child = next(
            (t for t in tasks if str(t.parent_task_id) == root_id), None,
        )
        assert child is not None
        assert str(child.root_task_id) == root_id
        assert child.depth == 1

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_to_unknown_persona_surfaces_error(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root"},
        )
        set_task_context(
            task_id=uuid.UUID(root["task_id"]), tenant_id=TENANT_ID,
        )

        result_json = await tool_registry.execute(
            "delegate_to_persona",
            {"persona": "nonexistent_persona_xyz", "subtask": "do it"},
        )
        import json
        result = json.loads(result_json)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delegate_outside_task_context_returns_error(self):
        # No set_task_context call — simulates a stray/direct call.
        from life_graph.core.task_context import _task_context_var

        token = _task_context_var.set(None)
        try:
            result_json = await tool_registry.execute(
                "delegate_to_persona",
                {"persona": "chief", "subtask": "do it"},
            )
            import json
            result = json.loads(result_json)
            assert "error" in result
            assert "task context" in result["error"].lower()
        finally:
            _task_context_var.reset(token)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_rejects_past_depth_cap(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root"},
            depth=ProcessManager.MAX_DELEGATION_DEPTH,
        )
        set_task_context(
            task_id=uuid.UUID(root["task_id"]), tenant_id=TENANT_ID,
        )

        result_json = await tool_registry.execute(
            "delegate_to_persona",
            {"persona": "chief", "subtask": "one too deep"},
        )
        import json
        result = json.loads(result_json)
        assert "error" in result
        assert "delegation depth" in result["error"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_delegation.py::TestDelegateToPersonaTool -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_graph.tools.delegate'`

- [ ] **Step 3: Implement the tool**

```python
# life_graph/tools/delegate.py
"""Delegate-to-persona tool — lets a persona hand off a sub-task
to another persona and (by default) wait for its result.

Only usable by personas whose allowed_tools includes
"delegate_to_persona" (swe-lead, jarvis) — enforced by the
allowed_tools filtering added to ProcessManager._run_agent.
Delegation only works when running inside a kernel AgentTask
(i.e. spawned via ProcessManager), because it needs to know its
own task id to link the child into the delegation tree — see
core/task_context.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 2
_TERMINAL_STATUSES = {"completed", "failed", "timeout", "cancelled"}


@tool(
    name="delegate_to_persona",
    description=(
        "Delegate a sub-task to another persona and get their result back."
        " Use this when part of the request is better handled by a"
        " specialist persona than by you."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "persona": {
                "type": "string",
                "description": (
                    "Name of the persona to delegate to (e.g. 'cody',"
                    " 'rex', 'ops', 'tutor', 'scout', 'admin')."
                ),
            },
            "subtask": {
                "type": "string",
                "description": "Clear instructions for what the delegated persona should do.",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project UUID to scope the sub-task to.",
            },
            "wait": {
                "type": "boolean",
                "description": (
                    "If true (default), block until the delegated task"
                    " finishes and return its result. If false, return"
                    " immediately with the task id."
                ),
                "default": True,
            },
            "timeout_seconds": {
                "type": "integer",
                "description": (
                    "How long to wait for the delegated task when"
                    " wait=true, before returning still_running."
                    " Defaults to 600."
                ),
                "default": 600,
            },
        },
        "required": ["persona", "subtask"],
    },
)
async def delegate_to_persona(
    persona: str,
    subtask: str,
    project_id: str | None = None,
    wait: bool = True,
    timeout_seconds: int = 600,
) -> str:
    """Create a child AgentTask assigned to *persona* and optionally await it.

    Returns a JSON string. Never raises — errors are returned as
    {"error": "..."} so the calling persona's tool-loop can react
    to them like any other tool result.
    """
    from life_graph.api.dependencies import get_process_manager
    from life_graph.core.task_context import get_current_task_context

    ctx = get_current_task_context()
    if ctx is None:
        return json.dumps({
            "error": (
                "delegate_to_persona has no task context — it can only"
                " be called from a persona running inside a kernel"
                " AgentTask."
            ),
        })

    pm = get_process_manager()

    parent_task = await pm.get_task(ctx.tenant_id, str(ctx.task_id))
    if parent_task is None:
        return json.dumps({
            "error": f"Could not load parent task {ctx.task_id} to delegate from.",
        })

    child_root_task_id = parent_task.root_task_id or parent_task.id
    child_depth = parent_task.depth + 1

    parsed_project_id: uuid.UUID | None = None
    if project_id:
        try:
            parsed_project_id = uuid.UUID(project_id)
        except ValueError:
            return json.dumps({
                "error": f"project_id {project_id!r} is not a valid UUID.",
            })

    try:
        spawn_result = await pm.spawn(
            tenant_id=ctx.tenant_id,
            agent_name=persona,
            input_data={"message": subtask},
            task_name=f"delegated:{persona}",
            parent_task_id=ctx.task_id,
            root_task_id=child_root_task_id,
            depth=child_depth,
            project_id=parsed_project_id,
            # Retry/recovery decisions belong to the delegating
            # persona's own reasoning, not the kernel's automatic
            # retry — see docs/specs/personal-roles.md.
            max_retries=0,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    child_task_id = spawn_result["task_id"]

    if not wait:
        return json.dumps({"task_id": child_task_id, "status": "queued"})

    elapsed = 0
    while elapsed < timeout_seconds:
        task = await pm.get_task(ctx.tenant_id, child_task_id)
        if task is not None and task.status in _TERMINAL_STATUSES:
            if task.status == "completed":
                return json.dumps({
                    "status": "completed",
                    "result": task.result,
                })
            return json.dumps({
                "status": task.status,
                "error": task.error,
            })
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS

    return json.dumps({
        "status": "still_running",
        "task_id": child_task_id,
    })
```

- [ ] **Step 4: Register the tool import in `main.py`**

In `life_graph/main.py`, add one line to the existing tool-registration block (around line 69-75):

```python
    # Startup — register agent tools (import triggers @tool decorator)
    try:
        import life_graph.tools.calculator  # noqa: F401
        import life_graph.tools.datetime_tool  # noqa: F401
        import life_graph.tools.web_search  # noqa: F401
        import life_graph.tools.terminal  # noqa: F401
        import life_graph.tools.git  # noqa: F401
        import life_graph.tools.browser  # noqa: F401
        import life_graph.tools.delegate  # noqa: F401
        from life_graph.tools.registry import registry
        logger.info("Agent tools registered: %s", registry.tool_names)
```

(Only the new `import life_graph.tools.delegate` line is added; everything else in that block is
unchanged.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_kernel_delegation.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 6: Lint and commit**

```bash
ruff check life_graph/tools/delegate.py life_graph/main.py
ruff format life_graph/tools/delegate.py life_graph/main.py
git add life_graph/tools/delegate.py life_graph/main.py tests/integration/test_kernel_delegation.py
git commit -m "feat(tools): add delegate_to_persona tool for cross-persona task delegation"
```

---

### Task 7: `target_agent` override on kernel routing

**Files:**
- Modify: `life_graph/kernel/chief_router.py`
- Modify: `life_graph/api/kernel.py`
- Test: `tests/integration/test_kernel_router.py` (append)

**Interfaces:**
- Produces: `ChiefRouter.route(..., target_agent: str | None = None)` — when set, classification
  is skipped entirely. `RouteRequest.target_agent: str | None = None` on the API model. Consumed
  by Task 8 (dashboard sends this field when the user picks a persona explicitly).

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_kernel_router.py` (match that file's existing fixture/import
style — `client` fixture, `TENANT_HEADERS`, `skip_on_db_error`):

```python
class TestTargetAgentOverride:
    """POST /api/v1/kernel/route with an explicit target_agent."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_target_agent_bypasses_classification(
        self, client: AsyncClient,
    ):
        response = await client.post(
            "/api/v1/kernel/route",
            json={
                "message": "this text is irrelevant to routing",
                "target_agent": "jarvis",
            },
        )
        assert response.status_code in (200, 201, 500)
        if response.status_code in (200, 201):
            data = response.json()["data"]
            assert data["routed_to"] == "jarvis"
            assert data["classified_intent"] == "override"

    @pytest.mark.asyncio
    async def test_route_unit_skips_classify_when_target_agent_set(self):
        from unittest.mock import AsyncMock

        from life_graph.kernel.chief_router import ChiefRouter

        router = ChiefRouter(
            session_factory=None, persona_service=None, process_manager=None,
        )
        router.classify = AsyncMock()  # type: ignore[method-assign]
        router._create_session = AsyncMock(return_value=uuid.uuid4())  # type: ignore[method-assign]
        router._process_manager = AsyncMock()
        router._process_manager.spawn = AsyncMock(
            return_value={"task_id": str(uuid.uuid4())},
        )

        await router.route(
            tenant_id="test_tenant",
            message="anything",
            target_agent="jarvis",
        )

        router.classify.assert_not_called()
```

(If `ChiefRouter.__init__` doesn't accept `process_manager=None` directly, adjust the unit test's
constructor call to match whatever `ChiefRouter.__init__`'s actual signature is — check
`life_graph/kernel/chief_router.py`'s `__init__` before finalizing this step; the router-unit-test
pattern already used elsewhere in `test_kernel_router.py`'s `TestIntentClassification` class shows
the exact working constructor call to copy.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_router.py::TestTargetAgentOverride -v`
Expected: FAIL — `TypeError: route() got an unexpected keyword argument 'target_agent'`

- [ ] **Step 3: Implement — `ChiefRouter.route()`**

In `life_graph/kernel/chief_router.py`, modify `route()`:

```python
    async def route(
        self,
        tenant_id: str,
        message: str,
        *,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        target_agent: str | None = None,
    ) -> dict[str, Any]:
        """Classify intent and route to the best agent.

        1. Classify user intent via regex patterns (skipped if
           target_agent is given — an explicit override)
        2. Resolve the best persona for the intent
        3. Create an AgentSession record
        4. Spawn a task via ProcessManager

        Args:
            tenant_id: Tenant scope.
            message: The user's message to classify.
            session_id: Optional existing session to continue.
            project_id: Optional project context.
            target_agent: If set, route directly to this persona
                and skip classification entirely (e.g. an explicit
                "use Jarvis" selection in the UI).

        Returns:
            Dict with session_id, intent, agent, task info.
        """
        start = datetime.now(timezone.utc)

        if target_agent:
            intent, confidence = "override", 1.0
            agent_name = target_agent
        else:
            # 1. Classify
            intent, confidence = self.classify(message)
            # 2. Resolve persona
            agent_name = await self._resolve_agent(
                tenant_id, intent,
            )

        # 3. Create/update session
        agent_session_id = await self._create_session(
            tenant_id=tenant_id,
            message=message,
            intent=intent,
            confidence=confidence,
            agent_name=agent_name,
            project_id=project_id,
        )

        # 4. Spawn task
        spawn_result = await self._process_manager.spawn(
            tenant_id=tenant_id,
            agent_name=agent_name,
            input_data={
                "message": message,
                "intent": intent,
                "confidence": confidence,
            },
            task_name=f"route:{intent}",
            session_id=agent_session_id,
            project_id=project_id,
        )

        elapsed_ms = int(
            (datetime.now(timezone.utc) - start)
            .total_seconds() * 1000
        )

        return {
            "session_id": str(agent_session_id),
            "classified_intent": intent,
            "classification_confidence": confidence,
            "routed_to": agent_name,
            "task_id": spawn_result.get(
                "task_id", str(spawn_result)
            ) if isinstance(spawn_result, dict)
            else str(spawn_result),
            "task_status": "queued",
            "routing_duration_ms": elapsed_ms,
        }
```

- [ ] **Step 4: Implement — API request model and endpoint**

In `life_graph/api/kernel.py`, modify `RouteRequest`:

```python
class RouteRequest(BaseModel):
    """Request body for routing a message."""

    message: str = Field(
        ..., min_length=1,
        description="User message to classify and route",
    )
    project_id: uuid.UUID | None = None
    target_agent: str | None = Field(
        default=None,
        description=(
            "If set, route directly to this persona and skip"
            " classification (explicit multi-role invocation, e.g."
            " selecting 'jarvis')."
        ),
    )
```

Find the `/route` endpoint's call to `chief.route(...)` (around line 586-590 per prior research)
and add `target_agent=body.target_agent` to it — the surrounding endpoint code (auth, tenant
resolution, `success_response` wrapping) is unchanged; only the call arguments change:

```python
    result = await chief.route(
        tenant_id=tenant_id,
        message=body.message,
        project_id=body.project_id,
        target_agent=body.target_agent,
    )
```

(Read the actual current call site first — the exact variable names for `chief`/`tenant_id` must
match what's already in that function; add the one new keyword argument without altering anything
else in the endpoint.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_kernel_router.py -v`
Expected: PASS (all tests in the file, including pre-existing ones)

- [ ] **Step 6: Lint and commit**

```bash
ruff check life_graph/kernel/chief_router.py life_graph/api/kernel.py
ruff format life_graph/kernel/chief_router.py life_graph/api/kernel.py
git add life_graph/kernel/chief_router.py life_graph/api/kernel.py tests/integration/test_kernel_router.py
git commit -m "feat(kernel): add target_agent override to bypass classification on /kernel/route"
```

---

### Task 8: Dashboard persona-override affordance

**Files:**
- Modify: `dashboard/lib/api.ts`
- Modify: `dashboard/lib/hooks.ts`
- Modify: `dashboard/components/chat-bar.tsx`
- Modify: `dashboard/components/mobile/mobile-capture.tsx` (one-line call-site fix)

**Interfaces:**
- Consumes: `POST /api/v1/kernel/route` with `target_agent` (Task 7), `GET /api/v1/kernel/personas`
  (existing, already wired as `api.kernel.personas()`).
- Produces: `api.kernel.route(message: string, targetAgent?: string)`,
  `useRoute()`'s mutation now takes `{ message: string; targetAgent?: string }` instead of a bare
  string — **this is a breaking signature change for the one other caller**, `mobile-capture.tsx`,
  fixed in this same task.

This is a UI-only change — no automated frontend test suite exists in `dashboard/` (`npm run
lint`/`npm run build` are the available checks). Verification is manual: run the dev server and
exercise the flow in a browser, per this project's stated practice for frontend changes.

- [ ] **Step 1: Update `api.ts`**

In `dashboard/lib/api.ts`, change the `route` method (currently
`route: (message: string) => POST<any>("/kernel/route", { message })`):

```typescript
    route: (message: string, targetAgent?: string) =>
      POST<any>("/kernel/route", targetAgent ? { message, target_agent: targetAgent } : { message }),
```

- [ ] **Step 2: Update `hooks.ts`**

In `dashboard/lib/hooks.ts`, change `useRoute()`:

```typescript
export function useRoute() {
  return useMutation({
    mutationFn: ({ message, targetAgent }: { message: string; targetAgent?: string }) =>
      api.kernel.route(message, targetAgent),
  });
}
```

Add a new hook right after it, for populating the persona picker:

```typescript
export function usePersonas() {
  return useQuery({ queryKey: ["personas"], queryFn: () => api.kernel.personas() });
}
```

- [ ] **Step 3: Fix the other `useRoute()` caller**

In `dashboard/components/mobile/mobile-capture.tsx`, line 61, change:

```typescript
      const res = await route.mutateAsync(content);
```

to:

```typescript
      const res = await route.mutateAsync({ message: content });
```

- [ ] **Step 4: Add the persona-override picker to `chat-bar.tsx`**

In `dashboard/components/chat-bar.tsx`:

1. Update the import line to add `usePersonas`:

```typescript
import { useCapture, useRoute, usePersonas } from "@/lib/hooks";
```

2. Add state and the personas query, right after the existing `const route = useRoute();` line:

```typescript
  const route = useRoute();
  const { data: personas } = usePersonas();
  const [targetAgent, setTargetAgent] = useState<string>("");
  const overridablePersonas = (personas ?? []).filter(
    (p: any) => Array.isArray(p.intent_tags) && p.intent_tags.length === 0,
  );
```

3. Update `handleSubmit` to pass `targetAgent`:

```typescript
  const handleSubmit = async () => {
    if (!input.trim() || isLoading) return;
    const msg = input.trim();
    setInput("");
    setExpanded(true);
    setMessages(prev => [...prev, { role: "user", content: msg, timestamp: new Date() }]);
    try {
      capture.mutate({ surface: "dashboard", content: msg });
      const response = await route.mutateAsync({
        message: msg,
        targetAgent: targetAgent || undefined,
      });
      setMessages(prev => [...prev, {
        role: "assistant",
        content: response?.response || response?.result || JSON.stringify(response),
        timestamp: new Date(),
      }]);
    } catch (err: any) {
      setMessages(prev => [...prev, { role: "system", content: `Error: ${err.message}`, timestamp: new Date() }]);
    }
  };
```

4. Add the picker `<select>` to the input row, right before the closing `</div>` of the
   `flex items-center gap-3 px-6 py-3` row (i.e. just before the submit `<button>`):

```tsx
        {overridablePersonas.length > 0 && (
          <select
            value={targetAgent}
            onChange={e => setTargetAgent(e.target.value)}
            disabled={isLoading}
            title="Route to a specific persona instead of auto-routing"
            className="bg-zinc-50 border border-zinc-200 rounded-xl px-2 py-2.5 text-sm text-zinc-600 focus:outline-none focus:border-emerald-400 disabled:opacity-50"
          >
            <option value="">Auto</option>
            {overridablePersonas.map((p: any) => (
              <option key={p.name} value={p.name}>
                {p.icon ? `${p.icon} ` : ""}{p.display_name || p.name}
              </option>
            ))}
          </select>
        )}
```

- [ ] **Step 5: Manual verification**

Run: `cd dashboard && npm run dev`

In a browser:
1. Open the dashboard, confirm the chat bar shows an "Auto" dropdown alongside the input once
   personas have loaded (only shows an entry for `jarvis`, since it's the only seeded persona with
   empty `intent_tags` — `chief` has `["general"]`, which is not empty).
2. Select "🤖 Jarvis" from the dropdown, type a message, submit — confirm the request in the
   Network tab's `/api/v1/kernel/route` POST body includes `"target_agent": "jarvis"`.
3. Leave the dropdown on "Auto", submit a message — confirm the POST body has no `target_agent`
   key at all (unchanged existing behavior).
4. On the mobile capture surface (`/m` route), submit a capture and confirm it still routes
   successfully (regression check for the `mobile-capture.tsx` signature fix).

- [ ] **Step 6: Lint and commit**

```bash
cd dashboard && npm run lint
git add dashboard/lib/api.ts dashboard/lib/hooks.ts dashboard/components/chat-bar.tsx dashboard/components/mobile/mobile-capture.tsx
git commit -m "feat(dashboard): add explicit persona-override picker to chat bar"
```

---

### Task 9: Verify ambient scheduling works for Scout & Admin

**Files:**
- Test: `tests/integration/test_kernel_scheduler.py` (append)

**Interfaces:**
- Consumes: `SchedulerService.create(tenant_id, data)` (existing), `SchedulerService.fire_job(tenant_id, job_id)` (existing), the `scout`/`admin` personas (Task 5).

This task adds no production code — per the spec, ambient scheduling for `scout`/`admin` needs "no
new scheduling mechanism." What's missing without this task is *proof* that Story 4 actually holds:
that a `ScheduledJob` targeting `scout` or `admin` really does spawn a task through the existing
scheduler once those personas exist. Without this, Story 4 would be covered by the spec only, not
by anything runnable.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_kernel_scheduler.py` (match its existing fixture/import style):

```python
class TestAmbientRoleScheduling:
    """Story 4: scout/admin can be scheduled via the existing SchedulerService."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_scheduled_job_fires_scout_task(self, client: AsyncClient):
        from life_graph.api.dependencies import (
            get_persona_service,
            get_process_manager,
            get_scheduler_service,
        )

        tenant = f"test_ambient_{uuid.uuid4().hex[:6]}"
        await get_persona_service().seed_builtins(tenant)

        scheduler = get_scheduler_service()
        job = await scheduler.create(
            tenant,
            {
                "name": "scout-daily-digest",
                "cron_expression": "0 8 * * *",
                "agent_name": "scout",
                "input": {
                    "message": (
                        "Review your tracked topics and surface anything new."
                    ),
                },
            },
        )

        fire_result = await scheduler.fire_job(tenant, job["id"])
        assert fire_result is not None

        pm = get_process_manager()
        tasks, _total = await pm.list_tasks(tenant, agent_name="scout")
        assert len(tasks) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_kernel_scheduler.py::TestAmbientRoleScheduling -v`
Expected: FAIL — `ValueError: Unknown agent persona: 'scout'` (raised from inside `fire_job` →
`spawn`), since `scout` doesn't exist yet without Task 5 applied. If Tasks 1-8 are already applied
by the time this task runs, this instead fails only because the test file/class doesn't exist yet
(`AttributeError`/collection error) — either failure mode is expected before Step 3.

- [ ] **Step 3: No implementation needed**

This step intentionally has no code change — confirm by re-running:

Run: `pytest tests/integration/test_kernel_scheduler.py::TestAmbientRoleScheduling -v`
Expected: PASS, once Task 5 (personas) has landed. If it fails for any reason other than a missing
persona, that's a real bug in `SchedulerService`/`ProcessManager` interaction, not something this
plan should paper over — stop and investigate rather than adjusting the test to pass.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_kernel_scheduler.py
git commit -m "test(kernel): verify scheduler can fire tasks for the new ambient personas"
```

---

## Post-Plan Follow-Ups (not part of this plan, noted for later)

- `cody`/`rex`/`ops`/`penny`/`scribe`'s existing `allowed_tools` lists reference tool names
  (`file_read`, `file_write`, `docker`, `ssh`, `memory_search`) that don't match anything actually
  registered in `life_graph/tools/registry.py`. Task 3 makes `allowed_tools` enforcement real for
  the first time, which means these five personas will suddenly have far fewer usable tools than
  before (previously they silently had *all* tools; going forward they'll have only whichever of
  their listed names happen to match a real registered tool — `web_search` for `rex`, nothing for
  `cody`/`ops`/`penny`/`scribe`/`swe-lead`/`tutor`/`scout`/`admin`'s `memory_search` entries). This
  plan does not fix that naming mismatch — it's pre-existing tech debt this plan's enforcement fix
  makes newly *visible*, not newly broken. Worth a follow-up spec: either add the missing tools
  (`memory_search` in particular, referenced by four personas and nowhere implemented) or correct
  the persona definitions to reference real tool names.
