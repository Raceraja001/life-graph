# Memory Approval Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every new memory starts as `status='pending'` and only becomes usable by agents/automation after the user approves it (`pending → active`); rejection (`pending → rejected`) hides it everywhere.

**Architecture:** Reuse the existing `memories.status` lifecycle column (values today: `active/archived/superseded/uncertain/retired`) — all automation already filters `status == "active"`, so pending/rejected rows are excluded from agents *by the existing mechanism*. The single write choke point is `PostgresMemoryStore.store()` (5 call sites converge there); it gains a `status` parameter defaulting to `"pending"`. Approve/reject are status transitions exposed as memory endpoints mirroring `api/approvals.py`. Dashboard search must *include* pending (visible-but-marked), so the search paths gain an explicit `statuses` filter.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async, pgvector, Alembic (no migration needed), Next.js 16 dashboard, pytest + httpx ASGITransport.

## Global Constraints

- Python: async everywhere, type hints + docstrings on public APIs, double quotes, ruff line-length 100.
- Tenant comes ONLY from the contextvar (`get_current_tenant_id()`); never hardcode or pass manually in API paths.
- Spec: docs/superpowers/specs/2026-07-23-memory-approval-gate-design.md. "Approved" in the spec = `status='active'` in code. New status values: `'pending'`, `'rejected'`.
- Dedup must see pending rows (`status IN ('active','pending')`) but NOT rejected ones.
- Automation (recall, context packets, consolidation, decay, watchers, brief, merge suggestions, contradiction) must consume `active` only.
- Dashboard-facing reads include `pending` (badged); `rejected` only when explicitly requested.
- Frontend: uzhavu-token inline styles in `components/mobile/*` (CSS vars, no new frameworks); Tailwind zinc idiom in desktop sidebar/table components.
- Commits end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- On Windows: ruff binary is blocked — verify with `python -m py_compile <files>` + pytest. Run pytest from the worktree ROOT (`python -m pytest tests/unit/ -v`) so the worktree's `life_graph/` shadows any installed copy. Unit tests need no Postgres (conftest mocks pgvector).
- Integration-test house style (see `tests/integration/test_approvals.py`): `ASGITransport` client fixture with tenant headers, `@skip_on_db_error`, assert `status_code in (200, 500)`-style tolerance — never bare 200-only asserts.
- Worktree: `<scratchpad>/hotfix-wt`, branch `feat/memory-approval` (spec committed at dd17fce).
- Deploy target: GCP VM `deploy@34.14.194.65` (key `D:\DevTools\gcloud-config\lg_deploy`). Base64-encode remote bash. **Build BOTH images**: `docker compose ... build app worker` (worker has its own image `life-graph-worker` — `build app` alone leaves it stale). After `--force-recreate` of app: `docker network connect web life_graph_app`. Never use literal `rm -f`; compose tracks containers by LABELS — remove stale ones with `docker stop` + `docker rm` (no -f), never rename-sweeps.

---

### Task 1: Gate the write path — `store()` defaults to pending, PATCH guard, events

**Files:**
- Modify: `life_graph/storage/postgres.py:30-72` (`store()`)
- Modify: `life_graph/core/events.py` (~line 34, Personal AI Events block)
- Modify: `life_graph/api/memories.py` (~line 97, PATCH handler)
- Test: `tests/integration/test_memory_approval.py` (new)

**Interfaces:**
- Consumes: existing `PostgresMemoryStore.store(memory, *, embedding=None, trust_tier=None)`.
- Produces: `store(memory, *, embedding=None, trust_tier=None, status: str = "pending") -> Memory`; `EventType.MEMORY_PENDING = "memory:pending"`, `EventType.MEMORY_APPROVED = "memory:approved"`, `EventType.MEMORY_REJECTED = "memory:rejected"`. Tasks 2–5 rely on these exact names.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_memory_approval.py` (mirror the fixture/decorator style of `tests/integration/test_approvals.py` — same `client` fixture, `TENANT_HEADERS`, `@skip_on_db_error`):

```python
"""Memory approval gate — every new memory starts pending.

House convention: tests tolerate DB-unreachable (500) but never accept 422
for valid input.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {"X-Tenant-ID": "test-approval"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


@skip_on_db_error
@pytest.mark.asyncio
async def test_new_memory_is_pending(client: AsyncClient):
    resp = await client.post("/api/v1/memories/", json={"content": "approval gate test alpha"})
    assert resp.status_code in (200, 201, 500)
    if resp.status_code in (200, 201):
        data = resp.json()["data"]
        row = data[0] if isinstance(data, list) else data
        assert row["status"] == "pending"


@skip_on_db_error
@pytest.mark.asyncio
async def test_patch_cannot_set_approval_statuses(client: AsyncClient):
    create = await client.post("/api/v1/memories/", json={"content": "approval gate test beta"})
    if create.status_code not in (200, 201):
        pytest.skip("DB unavailable")
    data = create.json()["data"]
    row = data[0] if isinstance(data, list) else data
    for forbidden in ("pending", "rejected", "active"):
        resp = await client.patch(
            f"/api/v1/memories/{row['id']}", json={"status": forbidden}
        )
        assert resp.status_code == 422, f"PATCH status={forbidden} must be rejected"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/integration/test_memory_approval.py -v`
Expected: `test_new_memory_is_pending` FAILS (status is `"active"`); the PATCH test FAILS (200 not 422). (If no local DB, tests skip — then rely on Step 5's unit-level assertion and the live E2E in Task 7.)

- [ ] **Step 3: Implement**

`life_graph/core/events.py` — in the Personal AI Events block (next to `MEMORY_CREATED`):

```python
    MEMORY_PENDING = "memory:pending"
    MEMORY_APPROVED = "memory:approved"
    MEMORY_REJECTED = "memory:rejected"
```

`life_graph/storage/postgres.py` — `store()` signature and row construction:

```python
    async def store(
        self,
        memory: MemoryCreate,
        *,
        embedding: list[float] | None = None,
        trust_tier: str | None = None,
        status: str = "pending",
    ) -> Memory:
```

Add `status=status,` to the `Memory(...)` constructor kwargs (next to `tenant_id=...`). After the existing commit/refresh, emit the pending event without ever letting event failure break storage:

```python
        if status == "pending":
            try:
                from life_graph.core.events import EventType, event_bus

                await event_bus.emit(
                    EventType.MEMORY_PENDING,
                    {
                        "id": str(row.id),
                        "source_type": row.source_type,
                        "preview": row.content[:80],
                        "tenant_id": row.tenant_id,
                    },
                    source="memory_store",
                )
            except Exception:  # pragma: no cover - events must never break writes
                logger.warning("MEMORY_PENDING emit failed", exc_info=True)
        return row
```

(Lazy import avoids a storage→events circular import; check the file's existing `logger` name.)

`life_graph/api/memories.py` — in `update_memory` (PATCH), before applying updates:

```python
    if body.status in ("pending", "rejected", "active"):
        raise HTTPException(
            status_code=422,
            detail="Approval status changes must use the approve/reject endpoints",
        )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/integration/test_memory_approval.py tests/unit/ -v`
Expected: new tests pass (or skip if no DB); **expect fallout in existing unit tests** that assert on `store.store(...)` call kwargs (e.g. `tests/unit/test_multimodal_service.py` fallback tests, `test_ingest_capture_job.py`) — update those assertions to include `status="pending"` is NOT needed (they assert positionally/by kwargs already given; only update if they fail). Fix any failures minimally. Full suite must be green.

- [ ] **Step 5: Commit**

```bash
git add life_graph/storage/postgres.py life_graph/core/events.py life_graph/api/memories.py tests/
git commit -m "feat(approval): all new memories start pending; PATCH cannot bypass the gate"
```

---

### Task 2: Dedup sees pending (but not rejected)

**Files:**
- Modify: `life_graph/storage/postgres.py:711-756` (`find_exact_duplicate`, `find_similar`)
- Test: extend `tests/integration/test_memory_approval.py`

**Interfaces:**
- Consumes: Task 1's pending-by-default writes.
- Produces: dedup queries filter `Memory.status.in_(("active", "pending"))`. `MemoryManager` callers unchanged.

- [ ] **Step 1: Write the failing test** (append to `test_memory_approval.py`):

```python
@skip_on_db_error
@pytest.mark.asyncio
async def test_duplicate_of_pending_is_deduped(client: AsyncClient):
    text = "approval dedup probe gamma 7731"
    first = await client.post("/api/v1/memories/", json={"content": text})
    if first.status_code not in (200, 201):
        pytest.skip("DB unavailable")
    second = await client.post("/api/v1/memories/", json={"content": text})
    assert second.status_code in (200, 201)
    listing = await client.get("/api/v1/memories/", params={"status": "pending", "limit": "50"})
    if listing.status_code == 200:
        rows = [r for r in listing.json()["data"] if r["content"] == text]
        assert len(rows) == 1, "second capture must dedup against the pending row"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/integration/test_memory_approval.py -v`
Expected: FAILS with 2 rows (dedup only checks `status == "active"` today).

- [ ] **Step 3: Implement** — in both `find_exact_duplicate` (line ~711) and `find_similar` (line ~722), replace:

```python
            Memory.status == "active",
```

with:

```python
            Memory.status.in_(("active", "pending")),
```

Rejected rows stay excluded — re-capturing rejected content must create a fresh pending row (spec).

- [ ] **Step 4: Run tests** — `python -m pytest tests/integration/test_memory_approval.py tests/unit/ -v` → green/skip.

- [ ] **Step 5: Commit**

```bash
git add life_graph/storage/postgres.py tests/integration/test_memory_approval.py
git commit -m "feat(approval): dedup checks pending rows too, rejected excluded"
```

---

### Task 3: Approve / reject / bulk / count endpoints + events

**Files:**
- Modify: `life_graph/api/memories.py` (new routes — **declare BEFORE the `/{memory_id}` dynamic routes** or FastAPI will capture `pending` as a memory id)
- Test: extend `tests/integration/test_memory_approval.py`

**Interfaces:**
- Consumes: Task 1's `EventType.MEMORY_APPROVED/MEMORY_REJECTED`; existing `store.retrieve/update/count_memories`, `success_response`, `get_current_tenant_id` DI already used in the file.
- Produces:
  - `POST /api/v1/memories/{id}/approve` → `{"data": MemoryResponse}` (pending|rejected → active; active idempotent-200)
  - `POST /api/v1/memories/{id}/reject` → pending → rejected; rejected idempotent-200; active → 409 (use `/deny`)
  - `POST /api/v1/memories/approvals/bulk` body `{"approve": [ids], "reject": [ids]}` → `{"data": {"approved": n, "rejected": n, "errors": [ids]}}`
  - `GET /api/v1/memories/pending/count` → `{"data": {"count": n}}`
  Task 6's frontend calls exactly these paths.

- [ ] **Step 1: Write the failing tests** (append):

```python
async def _create(client: AsyncClient, text: str) -> dict | None:
    resp = await client.post("/api/v1/memories/", json={"content": text})
    if resp.status_code not in (200, 201):
        return None
    data = resp.json()["data"]
    return data[0] if isinstance(data, list) else data


@skip_on_db_error
@pytest.mark.asyncio
async def test_approve_transitions_pending_to_active(client: AsyncClient):
    row = await _create(client, "approve me delta 1188")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post(f"/api/v1/memories/{row['id']}/approve")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"
    again = await client.post(f"/api/v1/memories/{row['id']}/approve")
    assert again.status_code == 200  # idempotent


@skip_on_db_error
@pytest.mark.asyncio
async def test_reject_and_active_reject_conflict(client: AsyncClient):
    row = await _create(client, "reject me epsilon 2299")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post(f"/api/v1/memories/{row['id']}/reject")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"
    row2 = await _create(client, "active then reject zeta 3311")
    await client.post(f"/api/v1/memories/{row2['id']}/approve")
    conflict = await client.post(f"/api/v1/memories/{row2['id']}/reject")
    assert conflict.status_code == 409


@skip_on_db_error
@pytest.mark.asyncio
async def test_bulk_and_count(client: AsyncClient):
    a = await _create(client, "bulk approval eta 4422")
    b = await _create(client, "bulk rejection theta 5533")
    if a is None or b is None:
        pytest.skip("DB unavailable")
    count_before = await client.get("/api/v1/memories/pending/count")
    assert count_before.status_code == 200
    assert count_before.json()["data"]["count"] >= 2
    resp = await client.post(
        "/api/v1/memories/approvals/bulk",
        json={"approve": [a["id"]], "reject": [b["id"]]},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["approved"] == 1 and body["rejected"] == 1
```

- [ ] **Step 2: Run to verify failure** — 404s (routes absent).

- [ ] **Step 3: Implement** in `api/memories.py`. Place the two static-path routes above `GET /{memory_id}`; mirror the emit-after-commit pattern of `api/approvals.py:63-73`:

```python
class BulkApprovalBody(BaseModel):
    approve: list[UUID] = []
    reject: list[UUID] = []


async def _transition(memory_id: UUID, action: str, store: PostgresMemoryStore) -> Memory:
    row = await store.retrieve(memory_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if action == "approve":
        if row.status == "active":
            return row  # idempotent
        if row.status not in ("pending", "rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot approve a {row.status} memory")
        updated = await store.update(memory_id, MemoryUpdate(status="active"))
        await event_bus.emit(
            EventType.MEMORY_APPROVED,
            {"id": str(memory_id), "tenant_id": get_current_tenant_id()},
            source="memories",
        )
        return updated
    # reject
    if row.status == "rejected":
        return row  # idempotent
    if row.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Cannot reject a {row.status} memory — use /deny for active ones"
        )
    updated = await store.update(memory_id, MemoryUpdate(status="rejected"))
    await event_bus.emit(
        EventType.MEMORY_REJECTED,
        {"id": str(memory_id), "tenant_id": get_current_tenant_id()},
        source="memories",
    )
    return updated


@router.get("/pending/count")
async def pending_count(store: PostgresMemoryStore = Depends(get_store)):
    """Number of memories awaiting approval for this tenant."""
    count = await store.count_memories(filters={"status": "pending"})
    return success_response(data={"count": count})


@router.post("/approvals/bulk")
async def bulk_approvals(body: BulkApprovalBody, store: PostgresMemoryStore = Depends(get_store)):
    """Approve/reject memories in batch (distillation review will lean on this)."""
    approved = rejected = 0
    errors: list[str] = []
    for mid in body.approve:
        try:
            await _transition(mid, "approve", store)
            approved += 1
        except HTTPException:
            errors.append(str(mid))
    for mid in body.reject:
        try:
            await _transition(mid, "reject", store)
            rejected += 1
        except HTTPException:
            errors.append(str(mid))
    return success_response(data={"approved": approved, "rejected": rejected, "errors": errors})


@router.post("/{memory_id}/approve")
async def approve_memory(memory_id: UUID, store: PostgresMemoryStore = Depends(get_store)):
    """Approve a pending (or rejected) memory — it becomes active/usable."""
    row = await _transition(memory_id, "approve", store)
    return success_response(data=MemoryResponse.model_validate(row))


@router.post("/{memory_id}/reject")
async def reject_memory(memory_id: UUID, store: PostgresMemoryStore = Depends(get_store)):
    """Reject a pending memory — hidden everywhere, re-capture allowed."""
    row = await _transition(memory_id, "reject", store)
    return success_response(data=MemoryResponse.model_validate(row))
```

(Match the file's actual imports/DI names — `get_store`, `event_bus`, `EventType`, `MemoryUpdate`, `MemoryResponse`, `BaseModel`, `UUID` — most already imported; add missing ones. Note: `store.update` goes through `MemoryUpdate` which Task 1 blocked at the *API PATCH layer only* — the service-layer call here is exactly why the guard lives in the route, not the store.)

- [ ] **Step 4: Run tests** — approval tests green/skip; full `tests/unit/` green. Verify route ordering: `python -c "from life_graph.main import app; [print(r.path) for r in app.routes if 'memor' in r.path]"` — `/pending/count` and `/approvals/bulk` must print before `/{memory_id}`.

- [ ] **Step 5: Commit**

```bash
git add life_graph/api/memories.py tests/integration/test_memory_approval.py
git commit -m "feat(approval): approve/reject/bulk/count endpoints with events"
```

---

### Task 4: Read paths — dashboard sees pending, automation stays active-only

**Files:**
- Modify: `life_graph/storage/postgres.py` (`_apply_filters` ~347, `hybrid_search` ~162-242)
- Modify: `life_graph/storage/hybrid.py` (`tri_search` ~189, `entity_context` ~332)
- Modify: `life_graph/api/search.py` (~134-156)
- Modify: `life_graph/services/merge_suggestions.py` (~61)
- Test: extend `tests/integration/test_memory_approval.py`

**Interfaces:**
- Consumes: pending rows from Task 1.
- Produces: `_apply_filters` supports `filters["statuses"]: list[str]` (IN-clause; existing single `status` key unchanged); `PostgresMemoryStore.hybrid_search(..., statuses: list[str] = ("active",))`; `HybridQueryEngine.tri_search(..., statuses: list[str] = ("active",))`. `POST /search/` passes `("active", "pending")` (it serves the dashboard). `/graph/hybrid-search` stays active-only (graph explores canon).

- [ ] **Step 1: Failing test** (append):

```python
@skip_on_db_error
@pytest.mark.asyncio
async def test_search_shows_pending_to_dashboard(client: AsyncClient):
    row = await _create(client, "pending searchable iota 6644 unicorn")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post("/api/v1/search/", json={"query": "iota unicorn", "limit": 20})
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        contents = str(resp.json())
        assert "6644" in contents, "dashboard search must include pending memories"
```

- [ ] **Step 2: Run to verify failure** — pending row absent from results (SQL hardcodes `status = 'active'`).

- [ ] **Step 3: Implement**

`_apply_filters` — after the existing single-status branch:

```python
        if "statuses" in filters:
            stmt = stmt.where(model.status.in_(tuple(filters["statuses"])))
```

`PostgresMemoryStore.hybrid_search` — add keyword param `statuses: tuple[str, ...] = ("active",)`; in the raw SQL replace both `AND status = 'active'` occurrences with `AND status = ANY(:statuses)` and add `"statuses": list(statuses)` to the bound params dict.

`HybridQueryEngine.tri_search` — add `statuses: tuple[str, ...] = ("active",)` and pass through to `self.memory_store.hybrid_search(..., statuses=statuses)`.

`HybridQueryEngine.entity_context` — both `list_memories` calls gain `"status": "active"` in their filters dict (closes an existing leak where archived/superseded rows already flowed into entity context).

`api/search.py` — the `POST /search/` route: pass `statuses=("active", "pending")` to both the `engine.tri_search(...)` call and the direct `store.hybrid_search(...)` call.

`services/merge_suggestions.py:61` — add `"status": "active"` to the `list_memories` filters (agents must not be asked to merge pending rows).

- [ ] **Step 4: Run tests** — new test green/skip; `python -m pytest tests/unit/ -v` green; grep-verify no automation regression:

```bash
grep -rn "statuses=(\"active\", \"pending\")" life_graph/ | grep -v api/search
```
Expected: no output (only the search route widens visibility).

- [ ] **Step 5: Commit**

```bash
git add life_graph/storage/ life_graph/api/search.py life_graph/services/merge_suggestions.py tests/integration/test_memory_approval.py
git commit -m "feat(approval): search shows pending to the user; automation stays active-only"
```

---

### Task 5: List semantics + daily brief backlog line

**Files:**
- Modify: `life_graph/api/memories.py` (`list_memories` ~166)
- Modify: `life_graph/services/brief.py` (`_capture_summary` ~200-229, `_format_body` ~280-312)
- Test: extend `tests/integration/test_memory_approval.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `GET /memories/` with no `status` param excludes only `rejected` (pending+active+archived+… all visible; each row carries `status`); explicit `?status=rejected` still works. Brief summary dict gains `"pending_approval": int`.

- [ ] **Step 1: Failing test** (append):

```python
@skip_on_db_error
@pytest.mark.asyncio
async def test_default_list_hides_rejected(client: AsyncClient):
    row = await _create(client, "rejected hidden kappa 7755")
    if row is None:
        pytest.skip("DB unavailable")
    await client.post(f"/api/v1/memories/{row['id']}/reject")
    listing = await client.get("/api/v1/memories/", params={"limit": "100"})
    assert listing.status_code == 200
    ids = [r["id"] for r in listing.json()["data"]]
    assert row["id"] not in ids
    explicit = await client.get("/api/v1/memories/", params={"status": "rejected", "limit": "100"})
    assert explicit.status_code == 200
    assert row["id"] in [r["id"] for r in explicit.json()["data"]]
```

- [ ] **Step 2: Run to verify failure** — rejected row appears in the default list today.

- [ ] **Step 3: Implement**

`list_memories` route: when the `status` query param is None, pass `filters["statuses"] = ("active", "pending", "archived", "superseded", "uncertain", "retired")` (everything except `rejected`) — i.e. build the exclusion via the Task 4 `statuses` filter. When `status` is provided, keep the existing single-value behavior.

`brief.py::_capture_summary` — alongside the existing memory count scalar:

```python
        pending = await session.scalar(
            select(func.count())
            .select_from(Memory)
            .where(Memory.tenant_id == tenant_id, Memory.status == "pending")
        )
```

and add `"pending_approval": int(pending or 0)` to the returned summary dict.

`brief.py::_format_body` — after the existing captures line block:

```python
        if capture_summary.get("pending_approval"):
            lines.append(
                f"{capture_summary['pending_approval']} memories are waiting for your approval."
            )
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/integration/test_memory_approval.py tests/unit/ -v` green/skip.

- [ ] **Step 5: Commit**

```bash
git add life_graph/api/memories.py life_graph/services/brief.py tests/integration/test_memory_approval.py
git commit -m "feat(approval): default lists hide rejected; daily brief reports the backlog"
```

---

### Task 6: Dashboard — pending badge, approve/reject actions, tab count, chip copy

**Files:**
- Modify: `dashboard/lib/api.ts` (~71-81, memories block)
- Modify: `dashboard/lib/mobile-api.ts` (hooks, ~132-147 region)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx` (card badge + sheet actions)
- Modify: `dashboard/app/memories/page.tsx` (status column/badge + row actions)
- Modify: `dashboard/components/mobile/mobile-tabbar.tsx` (~22-23, 38, 59-80: Memories tab badge)
- Modify: `dashboard/components/mobile/mobile-capture.tsx` (~267-270, chip copy)
- Test: `npm run build` (+ `npm run lint` on changed files)

**Interfaces:**
- Consumes: Task 3's endpoints exactly: `POST /memories/{id}/approve`, `POST /memories/{id}/reject`, `GET /memories/pending/count`.
- Produces: `api.memories.approve(id)`, `api.memories.reject(id)`, `api.memories.pendingCount()`; mobile hooks `usePendingMemoryCount()`, `useResolveMemory()`.

- [ ] **Step 1: API client** — extend the `memories` block in `lib/api.ts`:

```ts
  approve: (id: string) => POST<any>(`/memories/${id}/approve`, {}),
  reject: (id: string) => POST<any>(`/memories/${id}/reject`, {}),
  pendingCount: () => GET<any>(`/memories/pending/count`),
```

- [ ] **Step 2: Mobile hooks** — in `lib/mobile-api.ts`, mirror `useApprovals`/`useResolveApproval` (lines ~132-147):

```ts
export function usePendingMemoryCount() {
  return useQuery({
    queryKey: ["memories", "pending-count"],
    queryFn: () => api.memories.pendingCount().then((r) => r.data?.count ?? 0),
    refetchInterval: 60_000,
  });
}

export function useResolveMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      action === "approve" ? api.memories.approve(id) : api.memories.reject(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories"] });
    },
  });
}
```

- [ ] **Step 3: Mobile memories page** — on each card where `m.status === "pending"`, render an amber badge + inline ✓/✕ using uzhavu tokens (mirror the chip styling already in the file):

```tsx
{m.status === "pending" && (
  <span style={{ background: "var(--warning-soft, #fef3c7)", color: "var(--warning, #b45309)",
    borderRadius: 999, padding: "1px 8px", fontSize: 11, fontWeight: 600 }}>
    pending
  </span>
)}
```

with two small buttons (✓ → `resolve.mutate({id: m.id, action: "approve"})`, ✕ → reject), disabled while `resolve.isPending`. If the card opens `MemorySheet`, put the buttons in the sheet too.

- [ ] **Step 4: Desktop memories page** — add a status badge cell (Tailwind: `text-amber-600 bg-amber-50 rounded-full px-2 text-xs` for pending; render nothing for active) and ✓/✕ row buttons calling `api.memories.approve/reject` then invalidating `["memories"]` (file already has a query client via its hooks).

- [ ] **Step 5: Tab badge** — `mobile-tabbar.tsx`: add `const pendingMemories = usePendingMemoryCount();` and render the existing red-pill pattern (lines 59-80) on the **Memories** tab when `pendingMemories.data > 0`, using `background: var(--warning, #b45309)` to distinguish from the approvals badge.

- [ ] **Step 6: Capture chip copy** — `mobile-capture.tsx` success toast becomes:

```tsx
    Captured — routed to {result.routedTo} · pending your approval
```

- [ ] **Step 7: Verify** — from `dashboard/`: `npm run build` (must pass; lint has a pre-existing baseline — changed files must add zero new problems).

- [ ] **Step 8: Commit**

```bash
git add dashboard/
git commit -m "feat(approval): pending badges, approve/reject actions, tab count, chip copy"
```

---

### Task 7: Deploy + live E2E + PR

**Files:** none (VM ops + PR)

- [ ] **Step 1: Push & deploy** — push `feat/memory-approval`; on the VM: `git fetch origin && git checkout feat/memory-approval && git pull`, then `docker compose -f docker-compose.production.yml --env-file .env.production build app worker` (**both images**), `up -d --force-recreate --no-deps app worker`, `docker network connect web life_graph_app`, dashboard rebuild + stop/rm/run swap (compose labels gotcha), health + `/m` + `/api/v1/memories/` smoke 200s.

- [ ] **Step 2: E2E via Caddy** (base64-encoded remote bash):
  1. `POST /api/v1/memories/` `{"content": "Approval gate live test — water bill due Friday"}` → response row `status == "pending"`.
  2. `GET /api/v1/memories/pending/count` → count ≥ 1.
  3. Agent exclusion: `POST /search/` shows the row; then check an automation path (e.g. `psql`: the row's status is `pending`, and `GET /api/v1/graph/hybrid-search` for the same text does NOT return it).
  4. `POST /memories/{id}/approve` → `active`; search + graph search now both return it.
  5. Reject flow: create → reject → default list hides it → `?status=rejected` shows it.
  6. Phone: capture → chip says "pending your approval" → Memories tab shows badge + pending card → approve → badge clears.

- [ ] **Step 3: Daily brief spot-check** — trigger `run_daily_brief` via its admin/debug path or inspect `BriefComposer.compose_daily` output in a one-off `docker exec` python snippet: body contains "waiting for your approval" when count > 0.

- [ ] **Step 4: PR**

```bash
gh pr create --repo Raceraja001/life-graph --base master --head feat/memory-approval \
  --title "feat: memory approval gate — every memory waits for the user's yes" \
  --body "Implements docs/superpowers/specs/2026-07-23-memory-approval-gate-design.md ..."
```

User merges via GitHub UI; then sync the VM clone back onto `master`.

---

## Self-review notes

- Spec coverage: gate-all-writes (T1), dedup semantics (T2), transitions + events + bulk + count (T3), visible-but-marked vs automation-exclusion (T4), rejected hidden by default + brief (T5), minimal UI (T6), migration — none needed (spec updated), live verification (T7). ✅
- Type consistency: `statuses: tuple[str, ...]` parameter name identical across `_apply_filters` (dict key), `hybrid_search`, `tri_search`; endpoint paths in T3 = paths consumed in T6. ✅
- Known judgment calls: PATCH guard lives at the route (store.update must stay usable for transitions); `/graph/hybrid-search` stays active-only; capture-spine services (`services/capture.py`) write through `store.store` → gated automatically — implementer of T1 should grep-confirm (`grep -rn "store.store(" life_graph/`) that no writer bypasses `PostgresMemoryStore.store`.
