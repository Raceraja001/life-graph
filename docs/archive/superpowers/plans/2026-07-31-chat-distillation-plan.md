# Chat Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn ask-your-memories conversations into durable memories — extract new facts from the user's chat turns into pending (approval-gated) memories, and archive the whole thread to a MinIO snapshot file — triggered manually or by an idle cron.

**Architecture:** A new `ConversationDistiller` service reuses the existing `MemoryManager.ingest` pipeline (3-tier extract + dedup, `status="pending"` by default) over the user's turns created since a new `Conversation.last_distilled_at` marker, tags the results, and writes a JSON snapshot to a `conversations` MinIO bucket. A background ARQ job runs the distiller; a manual endpoint enqueues it (with an inline fallback); a 15-minute cron enqueues idle conversations. The mobile chat thread gets a "Distill" button that surfaces the new-fact count via a WebSocket completion event.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async, `mapped_column`), Alembic, ARQ, MinIO (`life_graph.storage.minio_client.MinIOStorage`), pytest (`httpx.AsyncClient` + `ASGITransport`), Next.js 16 / React 19 dashboard, `@tanstack/react-query` v5.

## Global Constraints

- **Branch:** `feat/chat-distillation`, already checked out (worktree at `scratchpad/hotfix-wt`), off `origin/master` (`d829b61`, which has the chat feature #13 + approval gate #12). Commit after each task with trailer exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Every DB query filters by `tenant_id`.** Use `get_current_tenant_id()` (request path) or `set_tenant_context(tenant_id, "system")` (worker path). Distilled memories are tenant-scoped like all memories.
- **Distilled facts are approval-gated:** they flow through `MemoryManager.ingest` → the store's default `status="pending"`. Never set them active.
- **The archive file is NOT gated** — it is a backup, written directly to MinIO. A MinIO failure must never discard the facts already created.
- **ARQ enqueue uses the FULL dotted job name** matching `WorkerSettings.functions` (e.g. `life_graph.workers.distill.distill_conversation`) — a bare name silently never runs. There is a regression test (`tests/unit/test_arq_enqueue_names.py`) that scans `enqueue_job` literals; keep it passing.
- **Marker semantics (supersedes the spec's "unchanged on no-op"):** `distill()` **always advances** `last_distilled_at` to now at the end of a run — even a no-op — so the idle cron cannot re-enqueue the same conversation forever. Fact extraction selects user turns created **after the previous marker value** (captured before overwriting). A new chat message bumps `Conversation.updated_at` (existing behaviour in `conversation.py`), which re-makes the conversation eligible.
- **Ruff:** line-length 100, double quotes. Type hints + docstrings on public APIs. Run `ruff check life_graph/` and `ruff format life_graph/` before committing backend tasks.
- **Backend test gate:** `pytest tests/unit/ -v` (no DB — `conftest.py` mocks pgvector) for unit tasks; `pytest tests/integration/ -v` for the endpoint. Tests are defensive: accept 500 when DB is unreachable, but never accept 422 for valid input.
- **Frontend:** no JS test runner in `dashboard/`. Gate = `npm run build` clean + `npm run lint` zero NEW problems, from `dashboard/`. No new npm dependency. No `@typescript-eslint/no-explicit-any` (repo treats it as ERROR) — use `unknown`/typed casts. Design tokens only.
- **No new secrets.** MinIO is already configured on the VM (`LIFE_GRAPH_MINIO_*`); `MinIOStorage()` reads them from config.

## File Structure

**Task 1 — Schema + event** (foundation)
- Modify: `life_graph/models/db.py` (add `Conversation.last_distilled_at`)
- Create: `alembic/versions/<rev>_add_conversation_last_distilled_at.py` (migration)
- Modify: `life_graph/core/events.py` (add `CONVERSATION_DISTILLED`)

**Task 2 — Distiller service + archive** (+ unit tests)
- Create: `life_graph/services/distillation.py` (`ConversationDistiller`, `build_snapshot`)
- Create: `tests/unit/test_distillation.py`

**Task 3 — Worker job + cron + DI**
- Create: `life_graph/workers/distill.py` (`distill_conversation`, `distill_idle_conversations`)
- Modify: `life_graph/workers/settings.py` (register functions + cron)
- Modify: `life_graph/api/dependencies.py` (`get_distillation_service`)

**Task 4 — Manual endpoint** (+ integration test)
- Modify: `life_graph/api/conversations.py` (`POST /conversations/{id}/distill`)
- Create/Modify: `tests/integration/test_conversation_distill.py`

**Task 5 — Dashboard trigger + live count**
- Create: `dashboard/lib/distill-events.ts`
- Modify: `dashboard/lib/api.ts` (`conversations.distill`)
- Modify: `dashboard/lib/mobile-api.ts` (`useDistillConversation`)
- Modify: `dashboard/lib/use-websocket.ts` (EVENT_MAP + emit distill count)
- Modify: `dashboard/app/(mobile)/m/chat/page.tsx` (Distill button + toast)

---

### Task 1: Schema + event type

Add the `last_distilled_at` marker column, its migration, and the `CONVERSATION_DISTILLED` event.

**Files:**
- Modify: `life_graph/models/db.py` (the `Conversation` model)
- Create: `alembic/versions/<rev>_add_conversation_last_distilled_at.py`
- Modify: `life_graph/core/events.py`

**Interfaces:**
- Produces: `Conversation.last_distilled_at: datetime | None`; `EventType.CONVERSATION_DISTILLED = "conversation:distilled"`.

- [ ] **Step 1: Add the column to the model**

In `life_graph/models/db.py`, find the `Conversation` class (it has `title`, `created_at`, `updated_at`). Add, after `updated_at`, matching the file's `mapped_column` style and imports (`datetime` is already imported):

```python
    last_distilled_at: Mapped[datetime | None] = mapped_column(default=None)
```

- [ ] **Step 2: Find the current Alembic head**

Run: `python -m alembic heads`
Expected: prints one revision id (the current head). Note it — it becomes `down_revision`.

- [ ] **Step 3: Autogenerate the migration**

Run: `python -m alembic revision --autogenerate -m "add conversation last_distilled_at"`
Then open the generated file in `alembic/versions/`. Verify `upgrade()` contains exactly an add-column for the nullable `last_distilled_at` on the `conversations` table, and `downgrade()` drops it. Remove any unrelated autogen noise (e.g. incidental type/index changes to other tables the autogen may have picked up) so the migration is single-purpose:

```python
def upgrade() -> None:
    op.add_column("conversations", sa.Column("last_distilled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "last_distilled_at")
```

Confirm `down_revision` equals the head from Step 2.

- [ ] **Step 4: Apply and verify the migration**

Run: `python -m alembic upgrade head`
Expected: applies cleanly. Then `python -m alembic current` shows the new revision. (If no DB is available in the dev env, skip the apply — note it — the migration correctness is verified by reading; the batched deploy applies it.)

- [ ] **Step 5: Add the event type**

In `life_graph/core/events.py`, in the `EventType` enum, add after `CONVERSATION_MESSAGE = "conversation:message"`:

```python
    CONVERSATION_DISTILLED = "conversation:distilled"
```

- [ ] **Step 6: Lint + commit**

```bash
ruff check life_graph/ && ruff format life_graph/
git add life_graph/models/db.py life_graph/core/events.py alembic/versions/
git commit -m "feat(distill): conversation last_distilled_at marker + CONVERSATION_DISTILLED event

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `ConversationDistiller` service + archive snapshot

The core logic: select the user's turns since the previous marker, run them through `manager.ingest` (extract + dedup + pending), tag/provenance the results, write the whole-thread JSON archive to MinIO, advance the marker, emit the event. Unit-tested with mocked manager + MinIO (no DB — the service takes a session_factory the test can stub, and the tests exercise the pure selection/tagging/snapshot logic).

**Files:**
- Create: `life_graph/services/distillation.py`
- Create: `tests/unit/test_distillation.py`

**Interfaces:**
- Consumes: `MemoryManager.ingest(text, context=..., source=...) -> list[Memory]` (Task-independent, exists); `MinIOStorage.upload(bucket, key, data: bytes, content_type=...) -> str` and `.ensure_bucket(bucket)`; `PostgresMemoryStore.update(memory_id, MemoryUpdate)` for tagging; `Conversation`, `ConversationMessage`, `_utcnow` from `models/db.py`; `ConversationNotFound` from `services/conversation.py`; `EventType.CONVERSATION_DISTILLED`, `event_bus`.
- Produces:
  - `class ConversationDistiller.__init__(self, session_factory, memory_manager, minio, store)`
  - `async def distill(self, conversation_id: uuid.UUID) -> dict` returning `{"new_facts": int, "archived": bool, "skipped": bool}`
  - `def build_snapshot(conv, messages, distilled_memory_ids) -> bytes`
  - Module constants `ARCHIVE_BUCKET = "conversations"`.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_distillation.py`:

```python
"""Unit tests for ConversationDistiller — selection, tagging, archive, resilience."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.services.distillation import (
    ARCHIVE_BUCKET,
    ConversationDistiller,
    build_snapshot,
)


def _msg(role, content, minutes):
    base = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(), role=role, content=content,
        cited_memory_ids=[], created_at=base + timedelta(minutes=minutes),
    )


def _conv(last_distilled_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(), tenant_id="t1", title="Chat",
        created_at=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 31, 12, 30, tzinfo=timezone.utc),
        last_distilled_at=last_distilled_at,
    )


class _FakeSession:
    """Minimal async session: returns a preset conversation + messages."""

    def __init__(self, conv, messages):
        self._conv = conv
        self._messages = messages
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, _model, _id):
        return self._conv if _id == self._conv.id else None

    async def execute(self, _query):
        result = MagicMock()
        result.scalars.return_value.all.return_value = self._messages
        return result

    async def commit(self):
        self.committed = True


def _distiller(conv, messages, ingest_return=None, upload=None):
    session = _FakeSession(conv, messages)
    manager = SimpleNamespace(ingest=AsyncMock(return_value=ingest_return or []))
    minio = SimpleNamespace(upload=upload or MagicMock(return_value="ok"))
    store = SimpleNamespace(update=AsyncMock())
    d = ConversationDistiller(lambda: session, manager, minio, store)
    return d, session, manager, minio, store


@pytest.mark.asyncio
async def test_first_run_extracts_all_user_turns():
    conv = _conv(last_distilled_at=None)
    messages = [_msg("user", "insurance due Aug 20", 0), _msg("assistant", "Noted", 1),
                _msg("user", "and car service in Sept", 2)]
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, session, manager, _minio, store = _distiller(conv, messages, ingest_return=[mem])

    result = await d.distill(conv.id)

    # Only the two USER turns feed extraction, joined by newline.
    text = manager.ingest.call_args.args[0] if manager.ingest.call_args.args else manager.ingest.call_args.kwargs["text"]
    assert "insurance due Aug 20" in text and "car service in Sept" in text
    assert "Noted" not in text  # assistant turn excluded
    assert result["new_facts"] == 1
    assert conv.last_distilled_at is not None  # marker advanced


@pytest.mark.asyncio
async def test_incremental_only_new_turns():
    marker = datetime(2026, 7, 31, 12, 1, tzinfo=timezone.utc)
    conv = _conv(last_distilled_at=marker)
    messages = [_msg("user", "old fact", 0), _msg("user", "new fact", 5)]  # 12:00, 12:05
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, *_rest = _distiller(conv, messages, ingest_return=[mem])
    manager = _rest[1]

    await d.distill(conv.id)
    text = manager.ingest.call_args.args[0] if manager.ingest.call_args.args else manager.ingest.call_args.kwargs["text"]
    assert "new fact" in text and "old fact" not in text  # only turns after the marker


@pytest.mark.asyncio
async def test_no_new_user_turns_is_noop_but_advances_marker():
    marker = datetime(2026, 7, 31, 13, 0, tzinfo=timezone.utc)
    conv = _conv(last_distilled_at=marker)
    messages = [_msg("user", "already distilled", 0)]  # 12:00 < marker
    d, session, manager, minio, _store = _distiller(conv, messages)

    result = await d.distill(conv.id)

    manager.ingest.assert_not_called()
    assert result == {"new_facts": 0, "archived": False, "skipped": True}
    assert conv.last_distilled_at > marker  # advanced to prevent re-enqueue
    assert not (isinstance(minio.upload, MagicMock) and minio.upload.called)


@pytest.mark.asyncio
async def test_distilled_memories_tagged_and_provenanced():
    conv = _conv()
    messages = [_msg("user", "buy milk", 0)]
    mem = SimpleNamespace(id=uuid.uuid4(), tags=["shopping"])
    d, _session, manager, _minio, store = _distiller(conv, messages, ingest_return=[mem])

    await d.distill(conv.id)

    # provenance passed to ingest as context/source
    kwargs = manager.ingest.call_args.kwargs
    assert kwargs.get("source") == "chat"
    assert kwargs.get("context", {}).get("conversation_id") == str(conv.id)
    # "chat" tag appended via store.update
    store.update.assert_awaited()
    update_arg = store.update.call_args.args[1]
    assert "chat" in update_arg.tags


@pytest.mark.asyncio
async def test_minio_failure_preserves_facts():
    conv = _conv()
    messages = [_msg("user", "fact", 0)]
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    boom = MagicMock(side_effect=RuntimeError("minio down"))
    d, _session, _manager, _minio, _store = _distiller(conv, messages, ingest_return=[mem], upload=boom)

    result = await d.distill(conv.id)

    assert result["new_facts"] == 1
    assert result["archived"] is False  # archive failed, facts kept, no raise


@pytest.mark.asyncio
async def test_unknown_conversation_raises():
    from life_graph.services.conversation import ConversationNotFound

    conv = _conv()
    d, *_ = _distiller(conv, [])
    with pytest.raises(ConversationNotFound):
        await d.distill(uuid.uuid4())  # different id → session.get returns None


def test_build_snapshot_shape():
    conv = _conv()
    messages = [_msg("user", "q", 0), _msg("assistant", "a", 1)]
    mids = [uuid.uuid4()]
    raw = build_snapshot(conv, messages, mids)
    doc = json.loads(raw.decode("utf-8"))
    assert doc["conversation_id"] == str(conv.id)
    assert doc["tenant_id"] == "t1"
    assert len(doc["messages"]) == 2
    assert doc["messages"][0]["role"] == "user"
    assert doc["distilled_memory_ids"] == [str(mids[0])]
    assert ARCHIVE_BUCKET == "conversations"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_distillation.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: life_graph.services.distillation`.

- [ ] **Step 3: Implement the service**

Create `life_graph/services/distillation.py`:

```python
"""ConversationDistiller — promote a chat's new user-facts into pending memories
and archive the whole thread to MinIO.

Tier 1: the user's turns created since ``Conversation.last_distilled_at`` run
through ``MemoryManager.ingest`` (3-tier extract + dedup), landing as
``status="pending"`` memories tagged ``"chat"`` with ``conversation_id``
provenance — the approval gate then applies.

Tier 2: the complete thread is written to the ``conversations`` MinIO bucket as
a JSON snapshot (overwritten each run) — a durable, reprocessable backup.

The marker is advanced on every run (even a no-op) so the idle cron cannot
re-enqueue the same conversation forever; a new chat message bumps
``updated_at`` and re-makes it eligible.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Conversation, ConversationMessage, _utcnow
from life_graph.models.schemas import MemoryUpdate
from life_graph.services.conversation import ConversationNotFound

logger = logging.getLogger(__name__)

ARCHIVE_BUCKET = "conversations"


def build_snapshot(
    conv: Any, messages: list[Any], distilled_memory_ids: list[uuid.UUID]
) -> bytes:
    """Serialize the whole thread to a UTF-8 JSON snapshot (bytes)."""
    doc = {
        "conversation_id": str(conv.id),
        "tenant_id": conv.tenant_id,
        "title": conv.title,
        "distilled_at": _utcnow().isoformat(),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "cited_memory_ids": [str(c) for c in (m.cited_memory_ids or [])],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "distilled_memory_ids": [str(m) for m in distilled_memory_ids],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")


class ConversationDistiller:
    """Distill new facts from a conversation and archive the thread."""

    def __init__(self, session_factory, memory_manager, minio, store) -> None:
        self._session_factory = session_factory
        self._manager = memory_manager
        self._minio = minio
        self._store = store

    async def distill(self, conversation_id: uuid.UUID) -> dict:
        """Extract new user-facts → pending memories; archive the thread.

        Returns ``{"new_facts": int, "archived": bool, "skipped": bool}``.
        Raises ``ConversationNotFound`` if the conversation is missing or owned
        by another tenant.
        """
        tenant_id = get_current_tenant_id()

        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                raise ConversationNotFound("Conversation not found")

            rows = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
            )
            messages = list(rows.scalars().all())

            prev_marker = conv.last_distilled_at
            new_user_turns = [
                m
                for m in messages
                if m.role == "user"
                and (prev_marker is None or m.created_at > prev_marker)
            ]

            if not new_user_turns:
                conv.last_distilled_at = _utcnow()  # advance to avoid re-enqueue
                await session.commit()
                return {"new_facts": 0, "archived": False, "skipped": True}

            # Tier 1: extract new facts (pending, deduped) with provenance.
            text = "\n".join(t.content for t in new_user_turns)
            memories = await self._manager.ingest(
                text,
                context={"conversation_id": str(conversation_id)},
                source="chat",
            )
            # Append the "chat" tag to each distilled memory for identification.
            for mem in memories:
                tags = list(mem.tags or [])
                if "chat" not in tags:
                    tags.append("chat")
                    await self._store.update(mem.id, MemoryUpdate(tags=tags))

            # Tier 2: archive the whole current thread (best-effort).
            archived = False
            try:
                data = build_snapshot(conv, messages, [m.id for m in memories])
                key = f"{tenant_id}/{conversation_id}.json"
                self._minio.upload(
                    ARCHIVE_BUCKET, key, data, content_type="application/json"
                )
                archived = True
            except Exception:  # pragma: no cover - archive must never lose facts
                logger.exception("Archive upload failed for conversation %s", conversation_id)

            conv.last_distilled_at = _utcnow()
            await session.commit()

        try:
            await event_bus.emit(
                EventType.CONVERSATION_DISTILLED,
                {
                    "conversation_id": str(conversation_id),
                    "tenant_id": tenant_id,
                    "new_facts": len(memories),
                },
                source="distillation",
            )
        except Exception:  # pragma: no cover - events must never break the job
            pass

        return {"new_facts": len(memories), "archived": archived, "skipped": False}
```

Note on the test doubles: the tests set the tenant via the real `get_current_tenant_id()` contextvar. Add at the top of `test_distillation.py` a fixture/auto-setup that sets it — insert this near the imports:

```python
from life_graph.core.tenant import set_tenant_context

@pytest.fixture(autouse=True)
def _tenant():
    set_tenant_context("t1", "test")
    yield
```

Also confirm `MinIOStorage.upload` accepts a `content_type` keyword; if its signature differs (e.g. positional `content_type` or a different name), adapt the call in `distill()` and the test's `upload` mock accordingly — read `life_graph/storage/minio_client.py` first. Likewise confirm `MemoryUpdate` exists in `life_graph/models/schemas.py` and accepts `tags`; if the store's update contract differs, match it (the goal is: append the `"chat"` tag to each distilled memory).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_distillation.py -v`
Expected: all pass. If a signature mismatch surfaces (`upload`/`MemoryUpdate`/`store.update`), fix the implementation to match the real API and re-run — do not change a test to hide a real contract error.

- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/ && ruff format life_graph/
git add life_graph/services/distillation.py tests/unit/test_distillation.py
git commit -m "feat(distill): ConversationDistiller service + thread archive

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Worker job + cron + DI factory

Wire the distiller into ARQ: a per-conversation job, an idle-sweep cron, and a DI factory to build the service.

**Files:**
- Create: `life_graph/workers/distill.py`
- Modify: `life_graph/workers/settings.py`
- Modify: `life_graph/api/dependencies.py`

**Interfaces:**
- Consumes: `set_tenant_context` (`core/tenant.py`); `get_memory_manager`, `get_store` (`api/dependencies.py`); `MinIOStorage`; `async_session` (`storage/database.py`); `ConversationDistiller`; `Conversation`, `_utcnow`.
- Produces:
  - `get_distillation_service() -> ConversationDistiller` in `dependencies.py`
  - `async def distill_conversation(ctx, conversation_id: str, tenant_id: str) -> dict`
  - `async def distill_idle_conversations(ctx) -> dict`
  - registration of both in `WorkerSettings.functions` + a 15-min cron for the sweep.
- Constant: `IDLE_MINUTES = 30`, `MAX_ENQUEUE_PER_SWEEP = 200`.

- [ ] **Step 1: Add the DI factory**

In `life_graph/api/dependencies.py`, near `get_conversation_service` (the Conversation section ~line 481), add:

```python
@lru_cache(maxsize=1)
def get_distillation_service():
    """Return the singleton conversation distiller."""
    from life_graph.services.distillation import ConversationDistiller
    from life_graph.storage.minio_client import MinIOStorage

    return ConversationDistiller(
        async_session, get_memory_manager(), MinIOStorage(), get_store()
    )
```

Confirm `lru_cache`, `async_session`, `get_memory_manager`, `get_store` are already imported/defined in this file (they are used elsewhere in it). If `get_store` is not present, use the same store the app uses for memories (read the file to confirm the exact provider name).

- [ ] **Step 2: Write the worker module**

Create `life_graph/workers/distill.py`:

```python
"""ARQ jobs for chat distillation.

``distill_conversation`` distills one conversation (mirrors the worker pattern
in ``ingest_capture``: set tenant context, build the service from DI, run it).
``distill_idle_conversations`` is the 15-minute cron sweep that enqueues every
conversation idle > IDLE_MINUTES with new activity since its last distill.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import or_, select

from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Conversation, _utcnow
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

IDLE_MINUTES = 30
MAX_ENQUEUE_PER_SWEEP = 200
DISTILL_JOB_NAME = "life_graph.workers.distill.distill_conversation"


async def distill_conversation(ctx: dict, conversation_id: str, tenant_id: str) -> dict:
    """Distill a single conversation for one tenant."""
    set_tenant_context(tenant_id, "system")
    from life_graph.api.dependencies import get_distillation_service

    distiller = get_distillation_service()
    result = await distiller.distill(uuid.UUID(conversation_id))
    logger.info("Distilled conversation %s: %s", conversation_id, result)
    return result


async def distill_idle_conversations(ctx: dict) -> dict:
    """Cron: enqueue distillation for idle conversations with new activity."""
    cutoff = _utcnow() - timedelta(minutes=IDLE_MINUTES)
    async with async_session() as session:
        rows = await session.execute(
            select(Conversation.id, Conversation.tenant_id)
            .where(
                Conversation.updated_at < cutoff,
                or_(
                    Conversation.last_distilled_at.is_(None),
                    Conversation.last_distilled_at < Conversation.updated_at,
                ),
            )
            .limit(MAX_ENQUEUE_PER_SWEEP)
        )
        targets = list(rows.all())

    if not targets:
        return {"enqueued": 0}

    redis = ctx.get("redis")
    if redis:
        from arq import create_pool

        from life_graph.workers.settings import parse_redis_settings

        pool = await create_pool(parse_redis_settings())
        for conv_id, tenant_id in targets:
            await pool.enqueue_job(DISTILL_JOB_NAME, str(conv_id), tenant_id)
        await pool.close()
    else:  # fallback: run inline (mirrors run_all_consolidations' degraded path)
        for conv_id, tenant_id in targets:
            await distill_conversation(ctx, str(conv_id), tenant_id)

    logger.info("Enqueued distillation for %d idle conversations", len(targets))
    return {"enqueued": len(targets)}
```

- [ ] **Step 3: Register the jobs + cron**

In `life_graph/workers/settings.py`:
- Add to the `functions` list (near `ingest_capture_text`):

```python
        "life_graph.workers.distill.distill_conversation",
        "life_graph.workers.distill.distill_idle_conversations",
```

- Add to `cron_jobs` (the `cron` import already exists at the top of the file):

```python
        # ── Chat distillation: idle sweep every 15 min ──
        cron(
            "life_graph.workers.distill.distill_idle_conversations",
            minute={0, 15, 30, 45},
            run_at_startup=False,
        ),
```

- [ ] **Step 4: Sanity-check imports compile**

Run: `python -c "import life_graph.workers.distill; import life_graph.workers.settings; import life_graph.api.dependencies"`
Expected: no ImportError. (Confirms the DI factory, worker, and settings wiring resolve.)

- [ ] **Step 5: Verify the ARQ enqueue-name regression test still passes**

Run: `pytest tests/unit/test_arq_enqueue_names.py -v`
Expected: PASS — `distill_idle_conversations` enqueues via the FULL dotted `DISTILL_JOB_NAME`. If the test doesn't yet know this module, and it scans a fixed file list, extend its scan to include `life_graph/workers/distill.py`; the assertion (enqueue literal ∈ `functions`) must hold.

- [ ] **Step 6: Lint + commit**

```bash
ruff check life_graph/ && ruff format life_graph/
git add life_graph/workers/distill.py life_graph/workers/settings.py life_graph/api/dependencies.py
git commit -m "feat(distill): ARQ per-conversation job + 15-min idle sweep cron

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Manual distill endpoint

Add `POST /api/v1/conversations/{id}/distill`: ownership check, enqueue the background job (full dotted name), inline fallback if the pool is down, return the standard envelope.

**Files:**
- Modify: `life_graph/api/conversations.py`
- Create: `tests/integration/test_conversation_distill.py`

**Interfaces:**
- Consumes: `get_conversation_service` (for the ownership check via `get_thread`), the ARQ pool (from app state), `get_distillation_service` (inline fallback), `success_response`.
- Produces: `POST /conversations/{id}/distill` → `success_response({"status": "distilling"})`; 404 on foreign/missing id.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_conversation_distill.py` (follow the existing conversation integration test's fixtures — `httpx.AsyncClient` + `ASGITransport`, tenant headers). Minimum cases:

```python
import pytest


@pytest.mark.asyncio
async def test_distill_unknown_conversation_returns_404(client, tenant_headers):
    import uuid

    resp = await client.post(f"/api/v1/conversations/{uuid.uuid4()}/distill", headers=tenant_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_distill_own_conversation_acks(client, tenant_headers):
    created = await client.post("/api/v1/conversations", headers=tenant_headers)
    if created.status_code >= 500:
        pytest.skip("DB unavailable")
    conv_id = created.json()["data"]["id"]

    resp = await client.post(f"/api/v1/conversations/{conv_id}/distill", headers=tenant_headers)
    # Valid input must never 422; accept 200 (queued/inline) or 500 (DB/redis down), never 422.
    assert resp.status_code != 422
    if resp.status_code == 200:
        assert resp.json()["data"]["status"] == "distilling"
```

Match the actual `client`/`tenant_headers` fixture names used by the existing `tests/integration/test_conversation*.py`; reuse them.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/integration/test_conversation_distill.py -v`
Expected: FAIL (404 route not found → 404 is coincidentally right for the unknown case, but the own-conversation case fails because the route doesn't exist / returns 405). Confirm the route is genuinely absent before implementing.

- [ ] **Step 3: Implement the endpoint**

In `life_graph/api/conversations.py`, add a new route. Use the existing ownership path (`svc.get_thread` returns `None` for a foreign/missing id) for the 404, then enqueue:

```python
@router.post("/{conversation_id}/distill")
async def distill_conversation_endpoint(
    conversation_id: UUID,
    request: Request,
    svc: ConversationService = Depends(get_conversation_service),
):
    """Distill this conversation's new facts into pending memories + archive.

    Enqueues a background job (results arrive via the CONVERSATION_DISTILLED
    event); falls back to running inline if the ARQ pool is unavailable so a
    manual tap still works.
    """
    from life_graph.core.tenant import get_current_tenant_id

    thread = await svc.get_thread(conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    tenant_id = get_current_tenant_id()
    job_name = "life_graph.workers.distill.distill_conversation"
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is not None:
        await pool.enqueue_job(job_name, str(conversation_id), tenant_id)
    else:
        from life_graph.api.dependencies import get_distillation_service

        await get_distillation_service().distill(conversation_id)

    return success_response({"status": "distilling"})
```

- Add `Request` to the FastAPI imports at the top (`from fastapi import APIRouter, Depends, HTTPException, Request`).
- Confirm the ARQ pool's app-state attribute name. Read `life_graph/main.py` lifespan / `api/multimodal.py` (which enqueues the capture job) to find how the pool is stored/accessed, and use that exact accessor. If capture uses a helper like `_enqueue_ingest_job`/`get_arq_pool`, reuse it here instead of `request.app.state.arq_pool`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/integration/test_conversation_distill.py -v`
Expected: PASS (or skip if DB unavailable). The unknown-id case returns 404; the own-id case returns 200 `{"status": "distilling"}` (or 500 if redis/DB is down — never 422).

- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/ && ruff format life_graph/
git add life_graph/api/conversations.py tests/integration/test_conversation_distill.py
git commit -m "feat(distill): POST /conversations/{id}/distill (enqueue + inline fallback)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Dashboard — Distill button + live fact count

Add a "Distill" action to the mobile chat thread. On tap it POSTs, shows "Distilling…", and — when the `conversation:distilled` WebSocket event arrives — shows "→ N new facts pending your approval" and live-refreshes the approvals/memories lists.

**Files:**
- Create: `dashboard/lib/distill-events.ts`
- Modify: `dashboard/lib/api.ts`
- Modify: `dashboard/lib/mobile-api.ts`
- Modify: `dashboard/lib/use-websocket.ts`
- Modify: `dashboard/app/(mobile)/m/chat/page.tsx`

**Interfaces:**
- Consumes: WS `data.type === "conversation:distilled"`, `data.payload.{conversation_id,new_facts}`.
- Produces: `api.conversations.distill(id)`; `useDistillConversation()`; `onDistillComplete(cb)` / `emitDistillComplete(detail)`; a Distill button.

- [ ] **Step 1: Create the completion emitter**

Create `dashboard/lib/distill-events.ts`:

```ts
// Module-level pub/sub bridging the conversation:distilled WebSocket event to
// the chat surface, so it can show an honest "→ N new facts" toast when the
// background distill job finishes. Keeps useWebSocket otherwise invalidation-only.

export interface DistillDetail {
  conversationId: string;
  newFacts: number;
}

const listeners = new Set<(d: DistillDetail) => void>();

export function emitDistillComplete(detail: DistillDetail): void {
  listeners.forEach((fn) => fn(detail));
}

/** Subscribe to distill-completion events. Returns an unsubscribe function. */
export function onDistillComplete(cb: (d: DistillDetail) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
```

- [ ] **Step 2: Add the API client method**

In `dashboard/lib/api.ts`, inside the `conversations: { … }` object (after `ask`), add:

```ts
    distill: (id: string) => POST<any>(`/conversations/${id}/distill`, {}),
```

- [ ] **Step 3: Add the mutation hook**

In `dashboard/lib/mobile-api.ts`, near the other conversation hooks, add:

```ts
export function useDistillConversation() {
  return useMutation({
    mutationFn: (id: string) => api.conversations.distill(id),
  });
}
```

(`useMutation` and `api` are already imported in this file.)

- [ ] **Step 4: Wire the event into `use-websocket.ts`**

In `dashboard/lib/use-websocket.ts`:
- Add the emitter import after the existing imports:

```ts
import { emitDistillComplete } from "./distill-events";
```

- Add to `EVENT_MAP` (precise key so only the distilled event refreshes the gate lists — chat messages are unaffected):

```ts
  "conversation:distilled": ["approvals", "memories"],
```

- In the `ws.onmessage` handler, right after `const type: string = data.type || "";` and before the EVENT_MAP loop, add:

```ts
        if (type === "conversation:distilled") {
          emitDistillComplete({
            conversationId: String(data?.payload?.conversation_id ?? ""),
            newFacts: Number(data?.payload?.new_facts ?? 0),
          });
        }
```

- [ ] **Step 5: Add the Distill button + toast to the chat thread**

In `dashboard/app/(mobile)/m/chat/page.tsx`:
- Add imports: extend the `react` import to include what's needed (it already imports `useEffect, useRef, useState`); add `Sparkles` to the `lucide-react` import; and:

```ts
import { onDistillComplete } from "@/lib/distill-events";
import { useDistillConversation } from "@/lib/mobile-api";
```

- Inside `MobileChat`, after `const resolveMemory = useResolveMemory();`, add. The subscription runs once (empty deps), so it reads the current conversation id through a ref (`currentConvRef`) to avoid a stale closure — a toast only shows for the conversation you're looking at:

```tsx
  const distill = useDistillConversation();
  const [distillMsg, setDistillMsg] = useState<string | null>(null);

  // Live pointer to the open conversation, for the once-mounted WS subscription.
  const currentConvRef = useRef<string | null>(conversationId);
  currentConvRef.current = conversationId;

  useEffect(() => {
    return onDistillComplete(({ conversationId: eventConvId, newFacts }) => {
      if (!eventConvId || eventConvId !== currentConvRef.current) return;
      setDistillMsg(
        newFacts > 0
          ? `→ ${newFacts} new ${newFacts === 1 ? "fact" : "facts"} pending your approval`
          : "Nothing new to distill",
      );
    });
  }, []);

  const onDistill = async () => {
    if (!conversationId || distill.isPending || !online) return;
    setDistillMsg("Distilling…");
    try {
      await distill.mutateAsync(conversationId);
    } catch {
      setDistillMsg("Couldn’t distill — try again");
    }
  };
```

(`useRef` is already imported in this file.)

- In the thread header row (the `<div>` at ~line 240 containing the back button + title `<span>`), add a Distill button **after** the title span, before the closing `</div>`:

```tsx
        <button
          onClick={() => void onDistill()}
          disabled={distill.isPending || !online}
          aria-label="Distill this chat into memories"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            flexShrink: 0,
            height: "30px",
            paddingInline: "11px",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-pill)",
            background: "var(--surface-2)",
            color: "var(--text-muted)",
            fontFamily: "inherit",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--fw-semibold)",
            cursor: distill.isPending || !online ? "default" : "pointer",
            opacity: distill.isPending || !online ? 0.5 : 1,
          }}
        >
          <Sparkles width={13} height={13} /> {distill.isPending ? "Distilling…" : "Distill"}
        </button>
```

- Render the toast: just below the thread header `<div>` (before the messages scroll container at ~line 275), add:

```tsx
      {distillMsg && (
        <div
          role="status"
          onClick={() => setDistillMsg(null)}
          style={{
            flexShrink: 0,
            margin: "2px 0 4px",
            padding: "8px 11px",
            borderRadius: "var(--radius-md)",
            background: "var(--success-soft)",
            color: "var(--success)",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--fw-semibold)",
          }}
        >
          {distillMsg}
        </div>
      )}
```

- [ ] **Step 6: Build + lint**

Run (from `dashboard/`):
```bash
npm run build
npm run lint
```
Expected: build clean; lint zero NEW problems vs baseline. Fix any real type/import error (no `any`, no unused imports).

- [ ] **Step 7: Manual verification (self-read + build)**

The full live path (tap → job → event → toast) needs the running worker/WS and is deferred to the batched E2E. Self-verify the wiring: the button calls `distill.mutateAsync`; `use-websocket` emits on `conversation:distilled`; the chat page's `onDistillComplete` subscription sets the toast; `EVENT_MAP` refreshes approvals/memories. Confirm `npm run build` passes.

- [ ] **Step 8: Commit**

```bash
git add dashboard/lib/distill-events.ts dashboard/lib/api.ts dashboard/lib/mobile-api.ts dashboard/lib/use-websocket.ts "dashboard/app/(mobile)/m/chat/page.tsx"
git commit -m "feat(distill): mobile chat Distill button + live fact-count toast

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (whole branch)

1. `pytest tests/unit/ -v` and `pytest tests/integration/test_conversation_distill.py -v` green (integration may skip without DB).
2. `ruff check life_graph/` clean; `python -c "import life_graph.main"` imports (wiring resolves).
3. `npm run build` + `npm run lint` clean from `dashboard/`.
4. Trace one end-to-end path by reading: Distill tap → `POST /distill` → enqueue `distill_conversation` (full dotted name) → `ConversationDistiller.distill` → `manager.ingest(source="chat")` pending memories + `"chat"` tag + `conversation_id` provenance → MinIO archive → `CONVERSATION_DISTILLED` → `use-websocket` emit → chat toast + approvals refresh. Confirm each hop exists.
5. Idle path: `distill_idle_conversations` cron selects idle-with-new-activity conversations and enqueues them; marker always advances so no infinite re-enqueue.

## Notes for the batch merge

Off `origin/master` (`d829b61`); independent of the open PRs #15/#16/#17/#18. `use-websocket.ts` overlaps PR #18 (which also edits `EVENT_MAP` and adds a `capture-events.ts` emitter) — the additions here (`conversation:distilled` entry + `distill-events.ts`) are additive and mirror #18's pattern; resolve at batch-merge time and re-run `npm run build`. Migration is a single nullable column add — orders cleanly after the notifications migration (028) at deploy.
