# Tool-Scoping & Real-Workdir Fixes for Agent-Task Dispatch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three residual gaps from the B2 final review — persona `allowed_tools` referencing unregistered tool names, `ClaudeCodeDriver` not honoring persona tool-scoping, and cody's `agent_task` dispatches verifying an empty temp directory instead of real changed files.

**Architecture:** Build `file_read`/`file_write` as real registered tools and reconcile every persona's `allowed_tools` against the actual tool registry. Extract `ClaudeCodeDriver`'s existing (dormant) git-worktree isolation logic into a shared `drivers/workdir.py` helper that `TaskDispatcher.dispatch_task` also uses, resolving ONE workdir for both the driver call and the verifier chain. `_run_action`'s agent_task branch looks up a real `Project` row by a well-known name and requests isolation; when none is registered, today's exact scratch-dir behavior is preserved. New diff-scoped verifier names (`build_ok_diff`/`lint_clean_diff`) avoid breaking `lint_clean` against this repo's pre-existing lint debt. `ClaudeCodeDriver` gets its own tool-scoping via the Claude Code CLI's `--allowedTools` flag, translated from the registry tool names.

**Tech Stack:** Python 3.11+ (dev interpreter `/c/Python314/python.exe`), FastAPI, SQLAlchemy 2.0 `mapped_column`, pytest (`tests/unit/`, `conftest` pgvector mock — no live Postgres needed for any test in this plan).

## Global Constraints

- **Base off master @ `5b9ca53`** (B2 merged). Work happens in the worktree `D:\DevTools\Projects\life-graph\.claude\worktrees\tool-scoping-fixes` on branch `feat/tool-scoping-workdir-fixes` (already created, spec already committed at `7ca1453`) — never build on master directly.
- **Every DB query tenant-scoped** (filter by `tenant_id`).
- **`file_read`/`file_write` take an LLM-supplied absolute path, unsandboxed** — same trust model as `run_command`/`git_status`. Do not add path-restriction logic; that would be a NEW, inconsistent trust model versus every other tool in this registry.
- **`docker`/`ssh`/`memory_search` stay unbuilt** — `docker`/`ssh` are dropped from persona `allowed_tools` entirely (redundant with `run_command`, which can already invoke either as a literal shell command); `memory_search` stays as an aspirational, documented-unregistered name in the personas that reference it (rex, scribe, tutor, scout, admin) — do not build it, do not remove it from those personas' lists.
- **`AutoAction.project_id` (the DB column) must never change** — it stays the literal string `"ambient"` for every agent_task action, used for trust/WIP-limit scoping (`AutonomyLevelService`). The real `Project` UUID this plan introduces is used ONLY as the `project_id` kwarg passed to `TaskDispatcher.dispatch_task` (for workdir/packet resolution), resolved fresh by `_run_action` right before that call — never written back onto the `AutoAction` row.
- **New diff-scoped verifier names, not changed existing ones** — `build_ok`/`lint_clean` (whole-tree) are used unmodified by `uzhavu-ops`/`dependency-updater`'s existing (out-of-scope) verify chains; do not touch their behavior. `build_ok_diff`/`lint_clean_diff` are new, additive registrations.
- **Isolation failure must never raise** — if `git worktree add` fails, fall back to the scratch temp dir (mirrors `ClaudeCodeDriver`'s existing, unchanged failure handling), logged as a warning.
- **No `Project` row named `"life-graph"` for a tenant = today's exact behavior** (scratch temp dir, no isolation, vacuous-but-harmless diff-scoped verifiers on an empty/non-git dir). Nothing regresses for a tenant that hasn't registered the repo.
- **Backend tests:** `/c/Python314/python.exe -m pytest` from the worktree root. Lint: `ruff check` + `ruff format` clean on touched files only (the repo carries pre-existing unrelated ruff errors — keep only YOUR touched lines clean).
- **Commit trailer EXACTLY** (own paragraph, two lines):

  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

- **Verified interfaces (against master @ `5b9ca53`, confirmed by direct file inspection — trust these over any assumption):**
  - Registered tool names today: `run_command`, `git_status`, `git_log`, `git_diff`, `git_branch`, `inspect_system`, `web_search`, `browse_web`, `browser_agent`, `calculator`, `get_current_datetime`, `delegate_to_persona` (`life_graph/tools/*.py`, each via `@tool(name=...)`, imported for registration side-effect in `life_graph/main.py:71-78`).
  - `ContextPacket` (`life_graph/drivers/base.py:16-56`) already has `persona_system_prompt: str | None = None` and `allowed_tools: list[str] | None = None` (added in the B2 fix wave) plus `project_context: dict`.
  - `TaskDispatcher.dispatch_task` (`life_graph/drivers/dispatcher.py:112-125`) current signature: `dispatch_task(self, tenant_id, task_id, instruction, task_type="general", project_id=None, session=None, persona_name=None, private=False, cost_cap_usd=DEFAULT_COST_CAP_USD, verify_chain=None, interactive=False) -> DriverResult`. `_coerce_project_uuid` (module-level, `dispatcher.py:52-73`) already handles non-UUID `project_id` gracefully.
  - `dispatch_task`'s current workdir line (`dispatcher.py:237`): `workdir = Path(tempfile.mkdtemp(prefix=f"lg_dispatch_{task_id[:8]}_"))`, immediately followed by `result = await driver.dispatch(packet, workdir, timeout=300)` (`:238`) and later `v_results = await verifier_chain.run_chain(verify_chain, workdir, task_context)` (`:257-259`) — the SAME `workdir` variable is reused for both, and passed to `_bounce_task(..., workdir=workdir, ...)` (`:280`) too.
  - `ClaudeCodeDriver._resolve_workdir`/`_remove_worktree` (`life_graph/drivers/claude_code.py:176-220`) — the exact logic to extract; neither references `self`.
  - `LocalDriver.dispatch` (`life_graph/drivers/local.py:34-127`) already builds `system_parts` starting with `packet.persona_system_prompt or "You are an AI agent executing a task."` (`:66`) and filters tools via `packet.allowed_tools` (`:87-94`).
  - `VerifierChain` (`life_graph/services/verifiers.py:32-94`): `register(name, func)`, `_register_builtins` registers 7 verifiers by name; each verifier is `async def f(workdir: Path, ctx: dict) -> tuple[bool, dict]`. `_verify_diff_within_scope` (`:146-163`) has the reusable `git diff --name-only HEAD` pattern (subprocess, `cwd=str(workdir)`, tolerant of failure — returns `passed=True` on any error/empty output, never raises).
  - `_run_action`'s agent_task `dispatch_task` call (`life_graph/autonomy/pipeline/service.py:311-321`) currently passes `project_id=auto_action.project_id` and `verify_chain=["build_ok", "lint_clean"]` — both change in this plan. `AutoFixService.__init__` (`service.py:97-123`) already holds `self._session_factory`.
  - `Project` model (`life_graph/models/db.py:1100-1170`): `id` (UUID, default), `tenant_id` (str, default `"legacy"`), `name` (str, **required**), `path` (Text, **required**) — no unique constraint on `name`, so a lookup must tolerate (and simply take the first of) duplicates.
  - `kernel/personas.py` current `allowed_tools` needing reconciliation (verbatim, verified): `cody`: `["file_read","file_write","terminal","git"]`; `ops`: `["terminal","docker","ssh"]`; `penny`: `["terminal","file_read","file_write"]`; `uzhavu-ops`: `["terminal","docker","ssh","git","web_search"]`; `dependency-updater`: `["terminal","git","file_read","file_write"]`; `swe-lead`: `["delegate_to_persona","terminal","git"]`. Unchanged (already valid or intentionally-deferred `memory_search`): `chief` (`None`), `rex`, `scribe`, `tutor`, `scout`, `admin`, `jarvis`.
  - `kernel/ambient.py`'s `AMBIENT_ACTION_READONLY_TOOLS` (`:31-39`) already lists `"file_read"` — it becomes real once Task 1 lands, no list change needed there, only its explanatory comment (`:17-30`).
  - Existing test fixture conventions to mirror: `tests/unit/test_driver_persona_scoping.py` (`_FakeSession`, `_SpyDriver`, `_FakePersona`, the `_wire()` monkeypatch helper for `TaskDispatcher` tests) and `tests/unit/test_agent_task_execution.py` (`_FakeSession` box-pattern, `make_auto_action()` for `_run_action` tests).

---

## File Structure

- **New tool** (Task 1): `life_graph/tools/filesystem.py` (`file_read`, `file_write`); registration import added to `life_graph/main.py`.
- **Persona reconciliation** (Task 2): `life_graph/kernel/personas.py` (6 personas' `allowed_tools`), `life_graph/kernel/ambient.py` (comment + new `AMBIENT_REPO_PROJECT_NAME` constant).
- **Shared workdir helper** (Task 3): new `life_graph/drivers/workdir.py` (`resolve_workdir`, `remove_worktree`); `life_graph/drivers/claude_code.py` updated to call it instead of its own private methods.
- **Dispatcher isolation wiring** (Task 4): `life_graph/drivers/dispatcher.py` (`dispatch_task`'s workdir resolution + cleanup).
- **LocalDriver workdir visibility** (Task 5): `life_graph/drivers/local.py`.
- **Diff-scoped verifiers** (Task 6): `life_graph/services/verifiers.py`.
- **Agent-task project resolution** (Task 7): `life_graph/autonomy/pipeline/service.py` (`AutoFixService`, `_run_action`).
- **ClaudeCodeDriver tool-scoping** (Task 8): `life_graph/drivers/claude_code.py`.
- **E2E + final verification** (Task 9): `tests/integration/test_agent_task_real_workdir_e2e.py`.

---

### Task 1: `file_read`/`file_write` tools

**Files:**
- Create: `life_graph/tools/filesystem.py`
- Modify: `life_graph/main.py` (tool registration import block)
- Test: `tests/unit/test_filesystem_tools.py`

**Interfaces:**
- Consumes: `life_graph.tools.registry.tool` decorator (existing).
- Produces: two registered tools, `file_read(path: str) -> str` and `file_write(path: str, content: str) -> str`, both returning a JSON string (matching `run_command`'s/`git_status`'s convention — `json.dumps({...})`, never raising).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_filesystem_tools.py
from __future__ import annotations

import json

import pytest

from life_graph.tools.filesystem import file_read, file_write


@pytest.mark.asyncio
async def test_file_read_returns_content(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world", encoding="utf-8")

    raw = await file_read(str(f))
    data = json.loads(raw)

    assert data["content"] == "hello world"
    assert data["truncated"] is False


@pytest.mark.asyncio
async def test_file_read_missing_file_returns_error():
    raw = await file_read("/definitely/does/not/exist.txt")
    data = json.loads(raw)

    assert "error" in data


@pytest.mark.asyncio
async def test_file_read_truncates_large_files(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 25000, encoding="utf-8")

    raw = await file_read(str(f))
    data = json.loads(raw)

    assert len(data["content"]) == 20000
    assert data["truncated"] is True


@pytest.mark.asyncio
async def test_file_write_creates_file_and_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / "out.txt"

    raw = await file_write(str(target), "written content")
    data = json.loads(raw)

    assert target.read_text(encoding="utf-8") == "written content"
    assert data["bytes_written"] == len("written content".encode("utf-8"))


@pytest.mark.asyncio
async def test_file_write_overwrites_existing_file(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old", encoding="utf-8")

    await file_write(str(f), "new")

    assert f.read_text(encoding="utf-8") == "new"


@pytest.mark.asyncio
async def test_file_write_rejects_oversized_content():
    raw = await file_write("/tmp/whatever.txt", "x" * 200001)
    data = json.loads(raw)

    assert "error" in data
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_filesystem_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_graph.tools.filesystem'`.

- [ ] **Step 3: Implement `life_graph/tools/filesystem.py`**

```python
"""Filesystem tools — read and write files on the host system.

Mirrors the trust model ``run_command``/``git_*`` already use: the LLM
supplies an absolute path, no sandboxing. A persona with ``file_write``
could already achieve the same effect via ``run_command`` shell redirection
if it also has that tool — this just gives a cheaper, structured,
non-shell path to the same capability, not a new privilege.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

MAX_READ_CHARS = 20000
MAX_WRITE_CHARS = 200000


@tool(
    name="file_read",
    description=(
        "Read the contents of a file on the host system. Provide an "
        "absolute path. Returns the file's text content, truncated if "
        "very large."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to read.",
            },
        },
        "required": ["path"],
    },
)
async def file_read(path: str) -> str:
    """Read a file and return its text content as a JSON string."""
    try:
        p = Path(path)
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        content = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > MAX_READ_CHARS
        return json.dumps(
            {"content": content[:MAX_READ_CHARS], "truncated": truncated}
        )
    except Exception as exc:
        logger.warning("file_read failed for %s: %s", path, exc)
        return json.dumps({"error": f"Read failed: {exc}"})


@tool(
    name="file_write",
    description=(
        "Write text content to a file on the host system, creating it "
        "(and parent directories) if needed, or overwriting it if it "
        "already exists. Provide an absolute path."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
)
async def file_write(path: str, content: str) -> str:
    """Write text content to a file, creating parent directories as needed."""
    if len(content) > MAX_WRITE_CHARS:
        return json.dumps(
            {
                "error": (
                    f"Content too large ({len(content)} chars, "
                    f"max {MAX_WRITE_CHARS})"
                )
            }
        )
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return json.dumps(
            {"bytes_written": len(content.encode("utf-8")), "path": str(p)}
        )
    except Exception as exc:
        logger.warning("file_write failed for %s: %s", path, exc)
        return json.dumps({"error": f"Write failed: {exc}"})
```

- [ ] **Step 4: Register the module for import side-effect**

In `life_graph/main.py`, in the tool-registration block (currently lines 71-78), add the new import alongside the others:

```python
        import life_graph.tools.calculator  # noqa: F401
        import life_graph.tools.datetime_tool  # noqa: F401
        import life_graph.tools.web_search  # noqa: F401
        import life_graph.tools.terminal  # noqa: F401
        import life_graph.tools.git  # noqa: F401
        import life_graph.tools.browser  # noqa: F401
        import life_graph.tools.delegate  # noqa: F401
        import life_graph.tools.system_inspect  # noqa: F401
        import life_graph.tools.filesystem  # noqa: F401
```

- [ ] **Step 5: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_filesystem_tools.py -v`
Expected: PASS (6/6).

- [ ] **Step 6: Confirm import side-effect works**

Run: `/c/Python314/python.exe -c "import life_graph.tools.filesystem; from life_graph.tools.registry import registry; assert 'file_read' in registry.tool_names; assert 'file_write' in registry.tool_names; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add life_graph/tools/filesystem.py life_graph/main.py tests/unit/test_filesystem_tools.py
git commit -m "feat(tool-scoping): add file_read/file_write tools"
```

---

### Task 2: Reconcile persona `allowed_tools` + `AMBIENT_REPO_PROJECT_NAME`

**Files:**
- Modify: `life_graph/kernel/personas.py` (`cody`, `ops`, `penny`, `uzhavu-ops`, `dependency-updater`, `swe-lead` entries)
- Modify: `life_graph/kernel/ambient.py` (comment + new constant)
- Test: `tests/unit/test_persona_tool_names_registered.py`

**Interfaces:**
- Consumes: the registered tool name set from Task 1 + pre-existing tools.
- Produces: `AMBIENT_REPO_PROJECT_NAME: str = "life-graph"` in `kernel/ambient.py`, importable by Task 7.

- [ ] **Step 1: Write the failing test** — a regression guard against this exact bug class recurring:

```python
# tests/unit/test_persona_tool_names_registered.py
"""Every persona's allowed_tools must name a real registered tool, OR be one
of the explicitly-deferred aspirational names (memory_search — see
kernel/personas.py). This is the regression guard for the bug found during
the B2 final review: several personas referenced "terminal"/"git"/
"file_read"/"file_write"/"docker"/"ssh" — none of which matched any
registered tool name, so persona tool-scoping silently produced an empty
toolset for most personas.
"""

from __future__ import annotations

import life_graph.tools.browser  # noqa: F401
import life_graph.tools.calculator  # noqa: F401
import life_graph.tools.datetime_tool  # noqa: F401
import life_graph.tools.delegate  # noqa: F401
import life_graph.tools.filesystem  # noqa: F401
import life_graph.tools.git  # noqa: F401
import life_graph.tools.system_inspect  # noqa: F401
import life_graph.tools.terminal  # noqa: F401
import life_graph.tools.web_search  # noqa: F401
from life_graph.kernel.personas import _BUILTIN_PERSONAS
from life_graph.tools.registry import registry

# Deferred, documented-unregistered names — NOT a bug, do not "fix" by
# removing these from personas.py. See kernel/ambient.py's comment.
DEFERRED_NAMES = {"memory_search"}


def test_every_persona_allowed_tool_is_registered_or_deferred():
    registered = set(registry.tool_names)
    unexplained = {}
    for defn in _BUILTIN_PERSONAS:
        allowed = defn.get("allowed_tools")
        if not allowed:
            continue
        bad = [
            name for name in allowed
            if name not in registered and name not in DEFERRED_NAMES
        ]
        if bad:
            unexplained[defn["name"]] = bad
    assert unexplained == {}, f"Unregistered, unexplained tool names: {unexplained}"


def test_cody_can_actually_read_and_write_files():
    cody = next(p for p in _BUILTIN_PERSONAS if p["name"] == "cody")
    assert "file_read" in cody["allowed_tools"]
    assert "file_write" in cody["allowed_tools"]
    assert "run_command" in cody["allowed_tools"]
    assert "terminal" not in cody["allowed_tools"]  # old, unregistered name gone


def test_ambient_repo_project_name_constant():
    from life_graph.kernel.ambient import AMBIENT_REPO_PROJECT_NAME

    assert AMBIENT_REPO_PROJECT_NAME == "life-graph"
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_persona_tool_names_registered.py -v`
Expected: FAIL — `test_every_persona_allowed_tool_is_registered_or_deferred` reports `cody`, `ops`, `penny`, `uzhavu-ops`, `dependency-updater`, `swe-lead` with bad names; `test_cody_can_actually_read_and_write_files` fails on the `"terminal" not in ...` assertion; `test_ambient_repo_project_name_constant` fails with `ImportError`.

- [ ] **Step 3: Edit `kernel/personas.py`** — change exactly these six `allowed_tools` lists (all other fields on these personas are unchanged):

```python
    # cody: "file_read","file_write","terminal","git" →
    "allowed_tools": [
        "file_read",
        "file_write",
        "run_command",
        "git_status",
        "git_log",
        "git_diff",
        "git_branch",
    ],
```
```python
    # ops: "terminal","docker","ssh" → (docker/ssh not built, dropped)
    "allowed_tools": ["run_command"],
```
```python
    # penny: "terminal","file_read","file_write" →
    "allowed_tools": [
        "run_command",
        "file_read",
        "file_write",
    ],
```
```python
    # uzhavu-ops: "terminal","docker","ssh","git","web_search" →
    "allowed_tools": [
        "run_command",
        "git_status",
        "git_log",
        "git_diff",
        "git_branch",
        "web_search",
    ],
```
```python
    # dependency-updater: "terminal","git","file_read","file_write" →
    "allowed_tools": [
        "run_command",
        "git_status",
        "git_log",
        "git_diff",
        "git_branch",
        "file_read",
        "file_write",
    ],
```
```python
    # swe-lead: "delegate_to_persona","terminal","git" →
    "allowed_tools": ["delegate_to_persona", "run_command", "git_status", "git_log", "git_diff", "git_branch"],
```

Do NOT change `chief`, `rex`, `scribe`, `tutor`, `scout`, `admin`, `jarvis` — their lists are already either `None` or reference only valid/deferred names.

- [ ] **Step 4: Edit `kernel/ambient.py`** — update the comment (the claim that `file_read` is aspirational is no longer true) and add the new constant:

```python
# Tools a scheduled AMBIENT_ACTION run is restricted to — read-only by construction,
# so an unattended ops/cody sweep can investigate but never mutate anything.
#
# This is an ALLOWLIST, intersected with the live tool registry at run time
# (see kernel/process_manager.py::_run_agent), so a name that is not registered
# is simply dropped. One name here is still aspirational — "memory_search" —
# because no memory-search tool is registered today; it is listed so the
# capability turns on automatically once that tool lands (see
# kernel/personas.py, which references it the same way). "file_read" is now
# a real, registered tool (life_graph/tools/filesystem.py).
AMBIENT_ACTION_READONLY_TOOLS: list[str] = [
    "inspect_system",
    "git_status",
    "git_log",
    "git_diff",
    "file_read",
    "memory_search",
    "get_current_datetime",
]

# Well-known Project.name that cody's agent_task dispatches look up (see
# autonomy/pipeline/service.py::AutoFixService._resolve_repo_project_id) to
# get a real filesystem path for the driver + verifier chain to operate on.
# Register a Project row with this exact name (any tenant that runs
# cody-ambient) via the existing project-registration flow. Unregistered =
# today's behavior: a scratch temp dir, no isolation, vacuous verifiers.
AMBIENT_REPO_PROJECT_NAME: str = "life-graph"
```

- [ ] **Step 5: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_persona_tool_names_registered.py -v`
Expected: PASS (3/3).

- [ ] **Step 6: Run the broader persona/seeding suite to confirm no regressions**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "persona or ambient" -q`
Expected: all pass (this touches `test_action_roles_config.py`, `test_cody_ambient_seed.py`, etc. — none of which assert on the OLD tool names, only on frozenset membership/job shape, so this should be a clean pass; if any test does assert on old tool-name strings, fix that test's expectation to match the new names, since the old names were themselves the bug).

- [ ] **Step 7: Commit**

```bash
git add life_graph/kernel/personas.py life_graph/kernel/ambient.py tests/unit/test_persona_tool_names_registered.py
git commit -m "fix(tool-scoping): reconcile persona allowed_tools with registered tool names"
```

---

### Task 3: Shared `resolve_workdir`/`remove_worktree` helper

**Files:**
- Create: `life_graph/drivers/workdir.py`
- Modify: `life_graph/drivers/claude_code.py` (use the shared helper instead of private methods)
- Test: `tests/unit/test_workdir_resolution.py`

**Interfaces:**
- Consumes: `ContextPacket` (existing).
- Produces: `async def resolve_workdir(packet: ContextPacket, fallback: Path) -> tuple[Path, Path | None]` and `async def remove_worktree(packet: ContextPacket, worktree: Path) -> None` — exact same behavior as the code being extracted, just as module-level functions instead of `ClaudeCodeDriver` private methods (drop `self`, no other change). Task 4 imports and uses both from `TaskDispatcher.dispatch_task`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_workdir_resolution.py
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.workdir import remove_worktree, resolve_workdir


def _packet(project_context: dict | None = None) -> ContextPacket:
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code",
        instruction="do it",
        project_context=project_context or {},
    )


@pytest.mark.asyncio
async def test_no_project_path_returns_fallback(tmp_path):
    packet = _packet()
    cwd, worktree = await resolve_workdir(packet, tmp_path)
    assert cwd == tmp_path
    assert worktree is None


@pytest.mark.asyncio
async def test_project_path_without_isolation_returns_path_directly(tmp_path):
    real_project = tmp_path / "proj"
    real_project.mkdir()
    packet = _packet({"path": str(real_project)})

    cwd, worktree = await resolve_workdir(packet, tmp_path / "scratch")

    assert cwd == real_project
    assert worktree is None


@pytest.mark.asyncio
async def test_isolation_creates_a_git_worktree(tmp_path):
    import subprocess

    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(real_repo), check=True, capture_output=True,
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_repo), "isolation": True})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is not None
    assert cwd == worktree
    assert worktree.is_dir()
    assert (worktree / ".git").exists()

    await remove_worktree(packet, worktree)
    assert not worktree.exists()


@pytest.mark.asyncio
async def test_isolation_failure_falls_back_to_project_path(tmp_path):
    # Not a git repo — "git worktree add" will fail.
    real_project = tmp_path / "not_a_repo"
    real_project.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_project), "isolation": True})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is None
    assert cwd == real_project
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_workdir_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_graph.drivers.workdir'`.

- [ ] **Step 3: Create `life_graph/drivers/workdir.py`** — extracted verbatim (logic-identical) from `ClaudeCodeDriver._resolve_workdir`/`_remove_worktree`:

```python
"""Shared workdir resolution — a real project's path, or an isolated git
worktree off it, for drivers/dispatch code that needs a real filesystem
location.

Extracted from ``ClaudeCodeDriver`` (its original, sole consumer) so
``TaskDispatcher.dispatch_task`` can resolve the SAME directory for both the
driver dispatch call and the verifier chain that inspects its output — a
verifier chain given a different workdir than the one the driver actually
wrote to would verify nothing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from life_graph.drivers.base import ContextPacket

logger = logging.getLogger(__name__)


async def resolve_workdir(
    packet: ContextPacket, fallback: Path
) -> tuple[Path, Path | None]:
    """Pick the execution directory for a dispatch.

    Returns ``(cwd, worktree)`` where ``worktree`` is non-``None`` only when
    an isolated git worktree was created (and must be removed after the
    dispatch via :func:`remove_worktree`).

    - No real, existing directory at ``packet.project_context["path"]`` →
      ``(fallback, None)``.
    - A real path, but ``packet.project_context["isolation"]`` is falsy →
      ``(that path, None)`` — operate directly on it.
    - A real path AND ``isolation`` truthy → create a throwaway
      ``git worktree`` off it under ``fallback`` and return that.
    - Worktree creation fails (e.g. not a git repo) → falls back to the
      project path directly, logged as a warning. Never raises.
    """
    project_path = packet.project_context.get("path")
    if not project_path or not Path(project_path).is_dir():
        return fallback, None

    project = Path(project_path)
    if not packet.project_context.get("isolation"):
        return project, None

    worktree = fallback / f"wt_{uuid.uuid4().hex[:8]}"
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "add", "--detach", str(worktree),
        cwd=str(project),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "Worktree isolation failed (%s) — using project dir directly",
            err.decode(errors="replace").strip()[:200],
        )
        return project, None
    return worktree, worktree


async def remove_worktree(packet: ContextPacket, worktree: Path) -> None:
    """Remove a worktree created by :func:`resolve_workdir`. Best-effort."""
    project_path = packet.project_context.get("path")
    if not project_path:
        return
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "remove", "--force", str(worktree),
        cwd=str(project_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
```

- [ ] **Step 4: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_workdir_resolution.py -v`
Expected: PASS (4/4). (Requires `git` on PATH — it already is, per this repo's own CI/dev usage of `git worktree` elsewhere.)

- [ ] **Step 5: Update `ClaudeCodeDriver` to use the shared helper**

In `life_graph/drivers/claude_code.py`:
- Add import: `from life_graph.drivers.workdir import remove_worktree, resolve_workdir`
- In `dispatch()`, replace `cwd, worktree = await self._resolve_workdir(packet, workdir)` with `cwd, worktree = await resolve_workdir(packet, workdir)`.
- In the `finally` block, replace `await self._remove_worktree(packet, worktree)` with `await remove_worktree(packet, worktree)`.
- Delete the now-unused private methods `_resolve_workdir` and `_remove_worktree` (lines 176-220) — their logic now lives in `drivers/workdir.py`.

- [ ] **Step 6: Run the existing ClaudeCodeDriver tests to confirm no regression**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "claude_code" -q`
Expected: all pass unchanged (behavior is identical, only the code's location moved).

- [ ] **Step 7: Commit**

```bash
git add life_graph/drivers/workdir.py life_graph/drivers/claude_code.py tests/unit/test_workdir_resolution.py
git commit -m "refactor(tool-scoping): extract shared workdir resolution from ClaudeCodeDriver"
```

---

### Task 4: `TaskDispatcher.dispatch_task` uses the shared workdir for driver + verifiers

**Files:**
- Modify: `life_graph/drivers/dispatcher.py`
- Test: `tests/unit/test_dispatcher_workdir_isolation.py`

**Interfaces:**
- Consumes: `resolve_workdir`/`remove_worktree` (Task 3).
- Produces: `dispatch_task` gains a new keyword-only parameter `isolate_workdir: bool = False` (default preserves current behavior for every existing caller). When `True` and the packet's `project_context` has a real `path`, `dispatch_task` sets `project_context["isolation"] = True` before resolving the workdir, so `driver.dispatch(packet, workdir, ...)` AND `verifier_chain.run_chain(verify_chain, workdir, ...)` both receive the SAME resolved directory (worktree when isolation succeeded, otherwise the existing scratch-temp-dir behavior, byte-identical to today when no project is set at all).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dispatcher_workdir_isolation.py
"""dispatch_task must resolve ONE workdir and hand it to both the driver
and the verifier chain — a verifier chain checking a different directory
than the one the driver wrote to verifies nothing (the bug this plan
closes: build_ok/lint_clean checking an always-empty scratch dir).
"""

from __future__ import annotations

import subprocess
import uuid

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher


class _FakeResult:
    def __init__(self, count: int = 0):
        self._count = count

    def scalar(self):
        return self._count

    def scalar_one_or_none(self):
        return None


class _FakeSession:
    async def execute(self, _stmt):
        return _FakeResult()

    def add(self, _obj):
        pass

    async def close(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _SpyDriver:
    name = "spy"

    def __init__(self):
        self.workdir_seen = None

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.workdir_seen = workdir
        return DriverResult(success=True, output="ran", cost_usd=0.0)


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True, throttled=False, reason="ok",
        spent_usd=0.0, cap_usd=10.0, remaining_usd=10.0,
    )


def _wire(disp, monkeypatch, driver, real_project_path=None):
    async def _packet(*_a, **kwargs):
        ctx = {"path": real_project_path} if real_project_path else {}
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
            instruction="fix it", project_context=ctx,
        )

    async def _pick(*_a, **_k):
        return driver

    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _noop)
    monkeypatch.setattr(disp, "_record_stats", _noop)
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)


@pytest.mark.asyncio
async def test_isolate_workdir_false_is_byte_identical_to_today(monkeypatch):
    """Default behavior: no project, no isolation — scratch temp dir."""
    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen is not None
    assert driver.workdir_seen.is_dir()


@pytest.mark.asyncio
async def test_isolate_workdir_true_with_real_project_creates_worktree(tmp_path, monkeypatch):
    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(real_repo), check=True, capture_output=True,
    )

    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver, real_project_path=str(real_repo))

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        project_id=str(uuid.uuid4()), isolate_workdir=True, verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen is not None
    assert (driver.workdir_seen / ".git").exists()
    assert driver.workdir_seen != real_repo  # isolated, not the real repo dir
    # cleaned up after dispatch
    assert not driver.workdir_seen.exists()


@pytest.mark.asyncio
async def test_isolate_workdir_true_without_project_falls_back(monkeypatch):
    """isolate_workdir=True with no real project path is a no-op — today's
    scratch-dir behavior, not an error."""
    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)  # no real_project_path

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        isolate_workdir=True, verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen is not None
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_dispatcher_workdir_isolation.py -v`
Expected: FAIL — `dispatch_task() got an unexpected keyword argument 'isolate_workdir'`.

- [ ] **Step 3: Implement in `dispatcher.py`**

Add the import at the top:

```python
from life_graph.drivers.workdir import remove_worktree, resolve_workdir
```

Add `isolate_workdir: bool = False` to `dispatch_task`'s signature (after `interactive: bool = False`).

Right after `owns_session = session is None` / before the `try:`, initialize the cleanup variable:

```python
        owns_session = session is None
        if owns_session:
            session = self._session_factory()

        worktree = None
```

Right after the persona-scoping block (after `packet.allowed_tools = ...`) and before `# Step 3: Select driver`, add:

```python
            # Step 2c: opt-in workdir isolation — only when the caller asked
            # for it AND a real project path resolved. A no-op flag on a
            # personaless/projectless dispatch (today's exact behavior).
            if isolate_workdir and packet.project_context.get("path"):
                packet.project_context["isolation"] = True
```

Replace the single line `workdir = Path(tempfile.mkdtemp(prefix=f"lg_dispatch_{task_id[:8]}_"))` with:

```python
            scratch = Path(tempfile.mkdtemp(prefix=f"lg_dispatch_{task_id[:8]}_"))
            workdir, worktree = await resolve_workdir(packet, scratch)
```

In the `finally` block at the very end of the method, add worktree cleanup before the existing session-close:

```python
        finally:
            if worktree is not None:
                await remove_worktree(packet, worktree)
            if owns_session:
                await session.close()
```

- [ ] **Step 4: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_dispatcher_workdir_isolation.py -v`
Expected: PASS (3/3).

- [ ] **Step 5: Run the full existing dispatcher/agent_task regression suite**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "dispatcher or agent_task" -q`
Expected: all pass, including `test_driver_persona_scoping.py` (Critical #1/#2 regression guards from the B2 final review) — this task must not reopen either.

- [ ] **Step 6: Commit**

```bash
git add life_graph/drivers/dispatcher.py tests/unit/test_dispatcher_workdir_isolation.py
git commit -m "feat(tool-scoping): dispatch_task resolves one workdir for driver and verifier chain"
```

---

### Task 5: `LocalDriver` tells the model its working directory

**Files:**
- Modify: `life_graph/drivers/local.py`
- Test: `tests/unit/test_local_driver_workdir_prompt.py`

**Interfaces:**
- Consumes: the `workdir: Path` parameter `LocalDriver.dispatch` already receives (previously unused — the docstring even says "unused by local orchestrator").
- Produces: the system prompt built inside `dispatch` includes an explicit "Your working directory is: {workdir}" line, so a model with `file_read`/`file_write`/`run_command`/`git_*` in its scoped toolset knows what absolute path to operate on (those tools all take an LLM-supplied path with no default project-aware behavior — see Task 1/2).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_local_driver_workdir_prompt.py
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.local import LocalDriver


async def _fake_run(**kwargs):
    """Minimal async generator standing in for AgentOrchestrator.run."""
    captured["system_prompt"] = kwargs.get("system_prompt")
    if False:
        yield  # pragma: no cover — makes this an async generator


captured: dict = {}


@pytest.mark.asyncio
async def test_dispatch_tells_the_model_its_workdir(monkeypatch, tmp_path):
    captured.clear()

    class _FakeOrchestrator:
        def run(self, **kwargs):
            return _fake_run(**kwargs)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.AgentOrchestrator", _FakeOrchestrator
    )

    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it",
    )
    driver = LocalDriver()
    workdir = tmp_path / "wt_abc123"
    workdir.mkdir()

    await driver.dispatch(packet, workdir)

    assert str(workdir) in captured["system_prompt"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_local_driver_workdir_prompt.py -v`
Expected: FAIL — `assert str(workdir) in captured["system_prompt"]` (workdir text not present).

- [ ] **Step 3: Implement in `local.py`**

Change the `system_parts` construction (currently starting with just the persona/generic prompt line) to also state the workdir, right after that first line:

```python
            # Build a system prompt from the context packet
            system_parts = [
                packet.persona_system_prompt or "You are an AI agent executing a task.",
                f"Your working directory is: {workdir}. Use this absolute path as "
                "the base for any file, git, or shell operations — pass it "
                "explicitly to tools that take a path/repo_path/"
                "working_directory argument.",
            ]
```

(The rest of the method — `project_context`/`preferences`/`procedures` appends — is unchanged.)

- [ ] **Step 4: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_local_driver_workdir_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full LocalDriver/persona-scoping regression suite**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "local_driver or persona_scoping" -q`
Expected: all pass — the persona-scoping (`allowed_tools`) behavior from the B2 fix wave must be completely unaffected by this prompt-text addition.

- [ ] **Step 6: Commit**

```bash
git add life_graph/drivers/local.py tests/unit/test_local_driver_workdir_prompt.py
git commit -m "feat(tool-scoping): LocalDriver surfaces its workdir in the system prompt"
```

---

### Task 6: Diff-scoped verifiers (`build_ok_diff`, `lint_clean_diff`)

**Files:**
- Modify: `life_graph/services/verifiers.py`
- Test: `tests/unit/test_diff_scoped_verifiers.py`

**Interfaces:**
- Consumes: nothing new — same `async def f(workdir: Path, ctx: dict) -> tuple[bool, dict]` shape every other verifier already uses; reuses `_verify_diff_within_scope`'s `git diff --name-only HEAD` subprocess pattern.
- Produces: two new verifier names registered in `VerifierChain._register_builtins`: `"build_ok_diff"` and `"lint_clean_diff"`. Consumed by Task 7's `verify_chain=["build_ok_diff", "lint_clean_diff"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_diff_scoped_verifiers.py
"""build_ok_diff/lint_clean_diff must check ONLY files changed since HEAD,
not the whole workdir tree — the whole-tree originals (build_ok/lint_clean)
would fail on this repo's pre-existing ruff debt the moment workdir points
at a real checkout instead of an always-empty scratch dir.
"""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )


@pytest.mark.asyncio
async def test_lint_clean_diff_ignores_pre_existing_issues_outside_the_diff(tmp_path):
    _init_repo(tmp_path)
    # A pre-existing, already-committed file with a lint issue (unused import) —
    # NOT part of this run's diff, must not fail lint_clean_diff.
    bad_file = tmp_path / "old.py"
    bad_file.write_text("import os\n", encoding="utf-8")
    subprocess.run(["git", "add", "old.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    # A NEW, clean file — the actual change under test. Staged (not committed)
    # so `git diff --name-only HEAD` picks it up — an untracked file would
    # NOT appear in that diff at all, which would make this test pass for
    # the wrong reason (nothing "changed" as far as git is concerned, rather
    # than old.py being correctly excluded by diff-scoping).
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_build_ok_diff_only_compiles_changed_files(tmp_path):
    _init_repo(tmp_path)
    # A pre-existing, already-committed file with a syntax error — not
    # part of the diff, must not fail build_ok_diff.
    broken = tmp_path / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    subprocess.run(["git", "add", "broken.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    # Staged (not committed) so `git diff --name-only HEAD` picks it up —
    # see the comment in test_lint_clean_diff_ignores_pre_existing_issues_
    # outside_the_diff for why an untracked file wouldn't prove anything here.
    (tmp_path / "new.py").write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_build_ok_diff_fails_on_a_syntax_error_in_the_diff(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("def f(:\n", encoding="utf-8")
    # Staged so git diff --name-only HEAD actually reports it as changed —
    # git add doesn't validate Python syntax, so this is fine to stage as-is.
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is False


@pytest.mark.asyncio
async def test_diff_scoped_verifiers_tolerate_a_non_git_directory(tmp_path):
    """No .git at all (the scratch-temp-dir fallback case) — must not raise,
    trivially passes (nothing to check)."""
    results = await verifier_chain.run_chain(
        ["build_ok_diff", "lint_clean_diff"], tmp_path, {}
    )

    assert all(r.passed for r in results)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_diff_scoped_verifiers.py -v`
Expected: FAIL — `Unknown verifier: build_ok_diff` / `Unknown verifier: lint_clean_diff`.

- [ ] **Step 3: Implement in `verifiers.py`**

Add a small shared helper near `_verify_diff_within_scope`, and the two new verifiers right after it:

```python
def _changed_python_files(workdir: Path) -> list[Path]:
    """Files changed since HEAD, filtered to ``*.py``, resolved under
    ``workdir``. Empty list (never raises) on any git failure — e.g. the
    scratch-temp-dir fallback, which is never a git repo at all."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workdir),
        )
        changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception:
        return []
    return [workdir / f for f in changed if f.endswith(".py") and (workdir / f).is_file()]


async def _verify_build_ok_diff(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Like build_ok, but only compiles files changed since HEAD."""
    import py_compile

    errors = []
    for py_file in _changed_python_files(workdir):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(e))
    passed = len(errors) == 0
    return passed, {"errors": errors[:10], "checked": len(_changed_python_files(workdir))}


async def _verify_lint_clean_diff(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Like lint_clean, but only lints files changed since HEAD."""
    changed = _changed_python_files(workdir)
    if not changed:
        return True, {"note": "No changed .py files"}
    try:
        result = subprocess.run(
            ["ruff", "check", "--no-fix", *[str(f) for f in changed]],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
        passed = result.returncode == 0
        return passed, {"issues": result.stdout[-500:], "returncode": result.returncode}
    except Exception as e:
        return False, {"error": str(e)}
```

Register both in `_register_builtins`:

```python
    def _register_builtins(self) -> None:
        """Register the built-in verifiers."""
        self.register("tests_pass", _verify_tests_pass)
        self.register("lint_clean", _verify_lint_clean)
        self.register("build_ok", _verify_build_ok)
        self.register("build_ok_diff", _verify_build_ok_diff)
        self.register("lint_clean_diff", _verify_lint_clean_diff)
        self.register("diff_within_scope", _verify_diff_within_scope)
        self.register("citations_present", _verify_citations_present)
        self.register("style_conforms", _verify_style_conforms)
        self.register("claims_evidenced", _verify_claims_evidenced)
```

- [ ] **Step 4: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_diff_scoped_verifiers.py -v`
Expected: PASS (4/4).

- [ ] **Step 5: Run the full verifier suite to confirm no regression to the existing (untouched) verifiers**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "verifier" -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add life_graph/services/verifiers.py tests/unit/test_diff_scoped_verifiers.py
git commit -m "feat(tool-scoping): add diff-scoped build_ok_diff/lint_clean_diff verifiers"
```

---

### Task 7: `_run_action` resolves the real repo project + requests isolation + diff-scoped verify chain

**Files:**
- Modify: `life_graph/autonomy/pipeline/service.py`
- Test: `tests/unit/test_agent_task_real_project.py`

**Interfaces:**
- Consumes: `AMBIENT_REPO_PROJECT_NAME` (Task 2), `dispatch_task(..., isolate_workdir: bool)` (Task 4), `verify_chain=["build_ok_diff", "lint_clean_diff"]` (Task 6).
- Produces: `AutoFixService._resolve_repo_project_id(self, tenant_id: str) -> str | None` — new method; `_run_action`'s agent_task branch calls it and passes its result as `dispatch_task`'s `project_id` kwarg (NOT written onto `auto_action.project_id`, which stays `"ambient"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_agent_task_real_project.py
"""_run_action's agent_task branch must resolve a real Project (by the
well-known AMBIENT_REPO_PROJECT_NAME) and pass ITS uuid to dispatch_task —
while auto_action.project_id (the DB column, "ambient") never changes.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from life_graph.autonomy.pipeline.service import AutoFixService
from life_graph.drivers.base import DriverResult


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    def __init__(self, box, project_id=None):
        self._box = box
        self._project_id = project_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def commit(self):
        pass

    async def execute(self, stmt):
        if isinstance(stmt, Update):
            action = self._box["action"]
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
            return _FakeResult(action)
        if isinstance(stmt, Select):
            return _FakeResult(self._project_id)
        return _FakeResult(None)


def make_auto_action(*, project_id: str = "ambient"):
    return MagicMock(
        id="a1", tenant_id="t1", kind="agent_task",
        instruction="fix the flaky test", action_command=None,
        action_name="cody_fix", agent_id="cody", project_id=project_id,
        risk_level="moderate",
    )


@pytest.mark.asyncio
async def test_resolve_repo_project_id_returns_none_when_unregistered():
    box = {"action": make_auto_action()}
    svc = AutoFixService(
        session_factory=lambda: _FakeSession(box, project_id=None),
        audit_service=MagicMock(log_auto_execute=AsyncMock()),
        approval_service=MagicMock(),
    )

    result = await svc._resolve_repo_project_id("t1")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_repo_project_id_returns_the_real_uuid_when_registered():
    real_id = uuid.uuid4()
    box = {"action": make_auto_action()}
    svc = AutoFixService(
        session_factory=lambda: _FakeSession(box, project_id=real_id),
        audit_service=MagicMock(log_auto_execute=AsyncMock()),
        approval_service=MagicMock(),
    )

    result = await svc._resolve_repo_project_id("t1")

    assert result == str(real_id)


@pytest.mark.asyncio
async def test_run_action_agent_task_passes_real_project_and_isolation_to_dispatch(monkeypatch):
    real_id = uuid.uuid4()
    box = {"action": make_auto_action(project_id="ambient")}
    dispatcher = MagicMock()
    dispatcher.dispatch_task = AsyncMock(
        return_value=DriverResult(success=True, output="done", cost_usd=0.1)
    )
    svc = AutoFixService(
        session_factory=lambda: _FakeSession(box, project_id=real_id),
        audit_service=MagicMock(log_auto_execute=AsyncMock()),
        approval_service=MagicMock(),
        dispatcher=dispatcher,
    )

    await svc._run_action("t1", box["action"], timeout_seconds=60)

    kwargs = dispatcher.dispatch_task.call_args.kwargs
    assert kwargs["project_id"] == str(real_id)
    assert kwargs["isolate_workdir"] is True
    assert kwargs["verify_chain"] == ["build_ok_diff", "lint_clean_diff"]
    # the AutoAction's OWN project_id column is untouched
    assert box["action"].project_id == "ambient"
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_agent_task_real_project.py -v`
Expected: FAIL — `AttributeError: 'AutoFixService' object has no attribute '_resolve_repo_project_id'`.

- [ ] **Step 3: Implement in `service.py`**

Add the import at the top (alongside the other `from life_graph...` imports):

```python
from sqlalchemy import select, update
```

(already present — no change needed there.)

Add the new method to `AutoFixService` (near `_get_lock`, before `process`):

```python
    async def _resolve_repo_project_id(self, tenant_id: str) -> str | None:
        """Look up the real ``Project`` row cody's agent_task work should run
        against, by the well-known name ``AMBIENT_REPO_PROJECT_NAME``.

        Returns its UUID as a string, or ``None`` if no such project is
        registered for this tenant — the caller then falls back to today's
        scratch-workdir, no-isolation dispatch behavior. Never raises: a
        lookup failure degrades the same way an absent project does.
        """
        from life_graph.kernel.ambient import AMBIENT_REPO_PROJECT_NAME
        from life_graph.models.db import Project

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Project.id)
                    .where(
                        Project.tenant_id == tenant_id,
                        Project.name == AMBIENT_REPO_PROJECT_NAME,
                    )
                    .limit(1)
                )
                project_id = result.scalar_one_or_none()
                return str(project_id) if project_id else None
        except Exception:
            logger.warning(
                "Failed to resolve repo project %r for tenant %s",
                AMBIENT_REPO_PROJECT_NAME, tenant_id, exc_info=True,
            )
            return None
```

In `_run_action`'s agent_task branch, change the `dispatch_task(...)` call. Before it (inside the `try:`, right before building the call), resolve the project:

```python
                try:
                    repo_project_id = await self._resolve_repo_project_id(tenant_id)
                    driver_result = await asyncio.wait_for(
                        self._dispatcher.dispatch_task(
                            tenant_id=tenant_id,
                            task_id=auto_action.id,
                            instruction=auto_action.instruction or "",
                            task_type="general",
                            project_id=repo_project_id,
                            persona_name=auto_action.agent_id,
                            verify_chain=["build_ok_diff", "lint_clean_diff"],
                            interactive=False,
                            cost_cap_usd=DEFAULT_AGENT_TASK_COST_CAP,
                            isolate_workdir=True,
                        ),
                        timeout=AGENT_TASK_DISPATCH_TIMEOUT_SECONDS,
                    )
```

Only `project_id=auto_action.project_id` → `project_id=repo_project_id`, `verify_chain=["build_ok", "lint_clean"]` → `verify_chain=["build_ok_diff", "lint_clean_diff"]`, and the new `isolate_workdir=True` line change. Nothing else in `_run_action` changes — `auto_action.project_id` itself (used for the lock key at `self._get_lock(auto_action.project_id)` and the audit log's `project_id=auto_action.project_id`) is read, never written, and stays `"ambient"`.

- [ ] **Step 4: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_agent_task_real_project.py -v`
Expected: PASS (3/3).

- [ ] **Step 5: Run the full agent_task/autonomy regression suite**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "agent_task or autonomy or autofix" -q`
Expected: all pass — including `test_agent_task_dispatch_failure.py` (Task 4 of the B2 plan, DispatchError/timeout handling) which must be completely unaffected by this change (it mocks `dispatch_task` at the `AutoFixService._dispatcher` boundary, same as this task's own tests).

- [ ] **Step 6: Commit**

```bash
git add life_graph/autonomy/pipeline/service.py tests/unit/test_agent_task_real_project.py
git commit -m "feat(tool-scoping): agent_task dispatch resolves a real repo project + requests isolation"
```

---

### Task 8: `ClaudeCodeDriver` tool-scoping via the CLI's own flags

**Files:**
- Modify: `life_graph/drivers/claude_code.py`
- Test: `tests/unit/test_claude_code_driver_tool_scoping.py`

**Interfaces:**
- Consumes: `packet.allowed_tools` / `packet.persona_system_prompt` (already on `ContextPacket`, set by `dispatch_task` — Task 4 doesn't change this, it was already wired in the B2 fix wave for `LocalDriver`; this task is the equivalent for `ClaudeCodeDriver`).
- Produces: `dispatch()` passes `--allowedTools <comma-separated-CLI-tool-names>` to the `claude` subprocess when `packet.allowed_tools is not None`, and prepends `packet.persona_system_prompt` to the rendered prompt when set.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_claude_code_driver_tool_scoping.py
"""ClaudeCodeDriver must translate a persona's allowed_tools into the Claude
Code CLI's own --allowedTools flag, and use the persona's real system
prompt — mirroring what LocalDriver already does via the Python tool
registry (ClaudeCodeDriver has no access to that registry; it shells out to
the CLI, which has its own, different tool vocabulary and its own flag for
restricting it).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver, _allowed_cli_tools


def test_allowed_cli_tools_maps_known_names():
    result = _allowed_cli_tools(["file_read", "file_write", "run_command"])
    assert result == sorted({"Read", "Write", "Bash"})


def test_allowed_cli_tools_none_means_unscoped():
    assert _allowed_cli_tools(None) is None


def test_allowed_cli_tools_unmapped_name_is_dropped_fail_closed():
    assert _allowed_cli_tools(["delegate_to_persona"]) == []


@pytest.mark.asyncio
async def test_dispatch_passes_allowed_tools_flag_to_the_cli(tmp_path, monkeypatch):
    driver = ClaudeCodeDriver(binary="claude")
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it", allowed_tools=["file_read", "run_command"],
        persona_system_prompt="You are Cody.",
    )

    captured_args = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"result": "ok", "session_id": "s1"}', b""

    async def _fake_exec(*args, **kwargs):
        captured_args["args"] = args
        return _FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await driver.dispatch(packet, tmp_path)

    assert result.success is True
    args = captured_args["args"]
    assert "--allowedTools" in args
    flag_index = args.index("--allowedTools")
    assert args[flag_index + 1] == "Bash,Read"
    assert "You are Cody." in args[args.index("-p") + 1]


@pytest.mark.asyncio
async def test_dispatch_omits_flag_when_unscoped(tmp_path, monkeypatch):
    driver = ClaudeCodeDriver(binary="claude")
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it",
    )

    captured_args = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"result": "ok"}', b""

    async def _fake_exec(*args, **kwargs):
        captured_args["args"] = args
        return _FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    await driver.dispatch(packet, tmp_path)

    assert "--allowedTools" not in captured_args["args"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_claude_code_driver_tool_scoping.py -v`
Expected: FAIL — `ImportError: cannot import name '_allowed_cli_tools'`.

- [ ] **Step 3: Verify the actual CLI flag name before implementing**

Run: `claude --help 2>&1 | grep -i allow` (or `claude -p --help`) if the `claude` binary is available in this environment. If it confirms `--allowedTools` (comma or space-separated tool names), proceed with Step 4 as written. If the actual flag differs, use the real name in place of `_ALLOWED_TOOLS_FLAG`'s value below — the constant is defined in one place specifically so this is a one-line change if the assumption is wrong. If the binary is not installed in this environment, proceed with `--allowedTools` as documented (matches the Claude Code CLI's published flag for headless/programmatic tool restriction) and note in your report that this should be re-verified against a real `claude` install before relying on it in production.

- [ ] **Step 4: Implement in `claude_code.py`**

Add near the top, after the existing constants:

```python
_ALLOWED_TOOLS_FLAG = "--allowedTools"

# life_graph tool registry name → Claude Code CLI's own tool name. The CLI
# has a different, coarser tool vocabulary (no separate git_status/git_diff/
# etc. — all shell-adjacent operations go through "Bash"). Names with no
# sensible CLI equivalent (delegate_to_persona, calculator,
# get_current_datetime, inspect_system) are simply absent — an allowed_tools
# list containing only those maps to an empty CLI allowlist, fail-closed,
# matching LocalDriver's behavior for an unmapped/unregistered name.
_TOOL_NAME_TO_CLI: dict[str, str] = {
    "run_command": "Bash",
    "git_status": "Bash",
    "git_log": "Bash",
    "git_diff": "Bash",
    "git_branch": "Bash",
    "file_read": "Read",
    "file_write": "Write",
    "web_search": "WebSearch",
    "browse_web": "WebFetch",
    "browser_agent": "WebFetch",
}


def _allowed_cli_tools(allowed_tools: list[str] | None) -> list[str] | None:
    """Translate life_graph tool names into Claude Code CLI tool names.

    Returns ``None`` when ``allowed_tools`` is ``None`` (no persona scoping —
    the CLI keeps its own default permissions, matching the "no scoping"
    contract ``ContextPacket.allowed_tools`` already documents). A present
    list — even if every name is unmapped — produces a (possibly empty)
    explicit CLI allowlist, fail-closed.
    """
    if allowed_tools is None:
        return None
    mapped = {
        _TOOL_NAME_TO_CLI[name] for name in allowed_tools if name in _TOOL_NAME_TO_CLI
    }
    return sorted(mapped)
```

In `dispatch()`, change the subprocess invocation to include the flag when scoped, and update `_format_prompt` to prepend the persona system prompt:

```python
        cwd, worktree = await resolve_workdir(packet, workdir)
        try:
            cli_tools = _allowed_cli_tools(packet.allowed_tools)
            args = [self._binary, "-p", prompt, "--output-format", "json"]
            if cli_tools is not None:
                args += [_ALLOWED_TOOLS_FLAG, ",".join(cli_tools)]

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
```

(This replaces the existing `proc = await asyncio.create_subprocess_exec(self._binary, "-p", prompt, "--output-format", "json", cwd=str(cwd), ...)` call — same shape, built from `args` now instead of positional literals, so the `--allowedTools` pair can be conditionally appended.)

In `_format_prompt`, add the persona prompt as the lead line:

```python
    @staticmethod
    def _format_prompt(packet: ContextPacket) -> str:
        """Render the context packet as a headless prompt.

        Private packets get instruction + project context only — memories
        and preferences never leave the local system. The persona's own
        system prompt (when the dispatch was pinned to one) leads the
        prompt, same as LocalDriver's system_prompt construction.
        """
        parts = []
        if packet.persona_system_prompt:
            parts.append(packet.persona_system_prompt)
        parts.append(packet.instruction)
        if packet.project_context:
            ...  # unchanged below this point
```

(Keep every line below the existing `parts = [packet.instruction]` exactly as-is — only that first line changes, from a literal list to the persona-prompt-then-instruction construction above.)

- [ ] **Step 5: Run tests — verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_claude_code_driver_tool_scoping.py -v`
Expected: PASS (5/5).

- [ ] **Step 6: Run the full ClaudeCodeDriver + workdir regression suite**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "claude_code or workdir" -q`
Expected: all pass — including Task 3's `test_workdir_resolution.py` and any pre-existing `claude_code` driver tests, confirming the `resolve_workdir` extraction (Task 3) still works correctly from within this now-modified `dispatch()`.

- [ ] **Step 7: Commit**

```bash
git add life_graph/drivers/claude_code.py tests/unit/test_claude_code_driver_tool_scoping.py
git commit -m "feat(tool-scoping): ClaudeCodeDriver scopes tools via the CLI's own flags"
```

---

### Task 9: Integration test + final verification

**Files:**
- Create: `tests/integration/test_agent_task_real_workdir_e2e.py`

**Interfaces:**
- Consumes: the full chain from Tasks 1-8.

- [ ] **Step 1: Write the E2E test** — drive the real chain (mocking only the LLM/orchestrator boundary and DB session, everything else real), following the style of `tests/integration/test_action_roles_agent_task_e2e.py` (B2's own E2E test):
  - With a `Project` row named `"life-graph"` registered for the tenant (mocked session returning it) and `AutoFixService._resolve_repo_project_id` reaching it: assert `_run_action`'s call into `TaskDispatcher.dispatch_task` (mocked at that boundary, matching B2's own E2E style) receives `project_id` equal to the real project's UUID, `isolate_workdir=True`, and `verify_chain=["build_ok_diff", "lint_clean_diff"]`.
  - Without a registered project: assert the same call receives `project_id=None` and the dispatch still succeeds (mocked `dispatch_task` returning a successful `DriverResult`) — today's fallback behavior, unbroken.
  - A real (non-mocked) `resolve_workdir` + `LocalDriver`-style flow: build a temp git repo, call `resolve_workdir(packet_with_isolation, scratch)` directly, confirm the returned workdir is a real worktree containing the repo's committed files, then run `verifier_chain.run_chain(["build_ok_diff", "lint_clean_diff"], workdir, {})` against it after writing one new clean `.py` file into the worktree — confirms the whole "isolate → verify only the diff" path holds together end-to-end without any dispatcher/service mocking in the middle.
  - Non-vacuous throughout: assert on real call kwargs and real filesystem state, not just "was called."

- [ ] **Step 2: Run — GREEN.**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_agent_task_real_workdir_e2e.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_agent_task_real_workdir_e2e.py
git commit -m "test(tool-scoping): real-workdir agent_task E2E — project resolution, isolation, diff-scoped verify"
```

---

## Final verification (after all tasks)

- [ ] Full unit + all new/touched integration tests: `/c/Python314/python.exe -m pytest tests/unit/ tests/integration/test_action_roles_end_to_end.py tests/integration/test_action_roles_agent_task_e2e.py tests/integration/test_agent_task_real_workdir_e2e.py -q`
- [ ] Regression sweep: `/c/Python314/python.exe -m pytest tests/ -k "dispatcher or driver or verifier or agent_task or persona or workdir or claude_code or filesystem" -q`
- [ ] `ruff check life_graph/ && ruff format --check life_graph/` — only touched lines must be clean; pre-existing errors elsewhere unchanged
- [ ] Imports clean: `/c/Python314/python.exe -c "import life_graph.main; import life_graph.workers.settings"`
- [ ] `/c/Python314/python.exe -c "import life_graph.tools.filesystem; from life_graph.tools.registry import registry; print(sorted(registry.tool_names))"` — confirm `file_read`/`file_write` present.
- [ ] Manual/documented step for the deploying admin (not automatable in this plan): register a `Project` row named `"life-graph"` (path = the actual repo checkout path on the target host) for the tenant that runs `cody-ambient`, via the existing project-registration API — until then, cody's agent_task dispatches keep today's exact scratch-dir, no-isolation, vacuous-verifier behavior.

## Notes / risks

- **`--allowedTools`'s exact name/semantics is a documented assumption** (Task 8, Step 3) — verify against the installed `claude` CLI version before relying on this in production; the constant is defined in one place (`_ALLOWED_TOOLS_FLAG`) specifically so a wrong guess is a one-line fix.
- **`memory_search` stays broken for rex/scribe/tutor/scout/admin** — explicitly out of scope (see spec). Do not "fix" this plan's scope creep by building it.
- **`docker`/`ssh` capability is genuinely reduced for `ops`/`uzhavu-ops`** (those literal tool names are dropped, not replaced) — mitigated by `run_command` already being able to invoke `docker`/`ssh` as shell commands for any persona that has it; not a net capability loss, just no longer double-counted as a separate (fictional) tool entry.
- **Isolation only benefits `LocalDriver`-routed dispatches with a registered `"life-graph"` Project** — `uzhavu-ops`/`dependency-updater` (pinned to `driver: claude_code`) are unaffected by Tasks 3-7; Task 8 gives `ClaudeCodeDriver` real tool-scoping independently of the workdir/isolation work.
