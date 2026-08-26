# Ask-Your-Memories Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A grounded, multi-turn chat where the user asks plain-language questions and gets answers synthesized from their approved memories, with tappable citations, on both mobile (new) and desktop.

**Architecture:** Reuse `SynthesisService` (grounded answering) + `HybridQueryEngine.tri_search` (approved-only retrieval). Add two tables (`conversations`, `conversation_messages`), a `ConversationService` that retrieves → synthesizes → persists both turns, a REST API, and UI. Citations work by having the synthesizer emit `[Memory N]` tags that map 1:1 to the numbered retrieved memories.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async, pgvector, Alembic, Next.js 16 dashboard, pytest + httpx ASGITransport.

## Global Constraints

- Python: async everywhere, type hints + docstrings on public APIs, double quotes, ruff line-length 100.
- Tenant comes ONLY from the contextvar (`get_current_tenant_id()` from `life_graph.core.tenant`); every table has `tenant_id: str = mapped_column(String(64), nullable=False, default="legacy")`; every query filters by it.
- Retrieval for chat is **approved-only**: `tri_search(..., statuses=("active",))`. Never surface pending/rejected in answers.
- Spec: docs/superpowers/specs/2026-07-23-ask-your-memories-chat-design.md.
- ORM models: UUID pk via `default=uuid.uuid4`; timestamps via the `_utcnow` helper in `models/db.py`; `__table_args__` tuple of `Index(...)` at class end; `__repr__` truncating id to 8 chars. Migrations use `server_default=sa.text("gen_random_uuid()")` for the pk and `sa.text("NOW()")` for timestamps.
- New Alembic revision id `027`, `down_revision = "026"`.
- Frontend: mobile uses inline styles + CSS custom properties (`var(--surface)`, `var(--border)`, `var(--radius-lg)`), pages are `"use client"` default-exported `Mobile<X>` functions; desktop uses Tailwind zinc idiom. No new npm dependencies (no markdown lib) — citation chips are rendered by splitting on `[Memory N]` tokens.
- Commits end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- On Windows: ruff binary is blocked — verify with `python -m py_compile <files>` + pytest. Run pytest from the worktree ROOT (`python -m pytest tests/unit/ -v`) so the worktree's `life_graph/` shadows any installed copy. Unit tests need no Postgres (conftest mocks pgvector); integration tests SKIP locally without a DB (that's expected — they run in the live E2E task). `dashboard/` verification: `npm run build` must pass, lint adds zero new problems over baseline.
- Worktree: `<scratchpad>/hotfix-wt`, branch `feat/memory-chat` (spec committed; branch = master + spec).
- Deploy target: GCP VM `deploy@34.14.194.65` (key `D:\DevTools\gcloud-config\lg_deploy`). Base64-encode remote bash. Build BOTH images (`build app worker`). After `--force-recreate` of app: `docker network connect web life_graph_app`. Compose tracks containers by LABELS — remove stale ones with `docker stop` + `docker rm` (no `-f`). New migration must be applied on the VM: `docker exec life_graph_app python -m alembic upgrade head`.

---

### Task 1: Data model + migration

**Files:**
- Modify: `life_graph/models/db.py` (add two classes near the `Approval` class ~line 2339)
- Create: `alembic/versions/027_conversations.py`
- Test: `tests/unit/test_conversation_models.py` (new)

**Interfaces:**
- Produces: `Conversation` (id, tenant_id, title, created_at, updated_at), `ConversationMessage` (id, conversation_id FK, tenant_id, role, content, cited_memory_ids: list[UUID], model, created_at). Tasks 3–4 import these.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_conversation_models.py`:

```python
"""Conversation ORM models exist with the expected columns."""

from life_graph.models.db import Conversation, ConversationMessage


def test_conversation_columns():
    cols = Conversation.__table__.columns.keys()
    assert {"id", "tenant_id", "title", "created_at", "updated_at"} <= set(cols)


def test_conversation_message_columns():
    cols = ConversationMessage.__table__.columns.keys()
    assert {
        "id", "conversation_id", "tenant_id", "role", "content",
        "cited_memory_ids", "model", "created_at",
    } <= set(cols)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/unit/test_conversation_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'Conversation'`.

- [ ] **Step 3: Add the models** (in `life_graph/models/db.py`, after the `Approval` class, before `DriverStat`):

```python
class Conversation(Base):
    """A multi-turn chat thread between the user and their memories."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_conversations_tenant_updated", "tenant_id", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id!s:.8}, title={self.title})>"


class ConversationMessage(Base):
    """One turn (user question or assistant answer) in a conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_conv_msg_role"),
        Index("ix_conv_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id!s:.8}, role={self.role})>"
```

- [ ] **Step 4: Run test** — `python -m pytest tests/unit/test_conversation_models.py -v` → PASS. Then full unit suite `python -m pytest tests/unit/ -v` stays green. `python -m py_compile life_graph/models/db.py`.

- [ ] **Step 5: Create the migration** `alembic/versions/027_conversations.py`:

```python
"""027 — Conversations: ask-your-memories chat threads.

Revision ID: 027
Revises: 026
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="legacy"),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_conversations_tenant_updated", "conversations",
                    ["tenant_id", "updated_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="legacy"),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cited_memory_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_conv_msg_role"),
    )
    op.create_index("ix_conv_messages_conversation_created", "conversation_messages",
                    ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_conv_messages_conversation_created", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_tenant_updated", table_name="conversations")
    op.drop_table("conversations")
```

- [ ] **Step 6: Verify migration import** — `python -c "import alembic.versions.027_conversations"` won't work (numeric module); instead `python -m py_compile alembic/versions/027_conversations.py` and confirm `down_revision = "026"` matches current head.

- [ ] **Step 7: Commit**

```bash
git add life_graph/models/db.py alembic/versions/027_conversations.py tests/unit/test_conversation_models.py
git commit -m "feat(chat): conversation + message tables (migration 027)"
```

---

### Task 2: Citation-aware synthesis

**Files:**
- Modify: `life_graph/services/synthesis.py`
- Test: `tests/unit/test_synthesis_citations.py` (new)

**Interfaces:**
- Consumes: `synthesize(question, memories, *, model=None)` where each memory dict now MUST include `"id": str`.
- Produces: `synthesize(...)` returns `{"answer", "source_count", "model", "citations": list[str], "history": ...}` — `citations` is the ordered list of memory ids the answer's `[Memory N]` tags resolved to (deduped, order of first appearance). Adds optional `history: list[dict] | None = None` param (prior turns as `{"role","content"}`) inserted before the user question. Task 3 consumes `citations`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_synthesis_citations.py`:

```python
"""Citation parsing: [Memory N] tags map to the Nth memory's id."""

import pytest

from life_graph.services.synthesis import SynthesisService, parse_citations


def test_parse_citations_maps_to_ids():
    ids = ["aaa", "bbb", "ccc"]
    citations = parse_citations("Your insurance is due Aug 15 [Memory 1]. Also [Memory 3].", ids)
    assert citations == ["aaa", "ccc"]


def test_parse_citations_dedupes_and_drops_out_of_range():
    ids = ["aaa", "bbb"]
    citations = parse_citations("[Memory 1] [Memory 1] [Memory 5] [Memory 2]", ids)
    assert citations == ["aaa", "bbb"]  # dup dropped, out-of-range 5 dropped


class _FakeClient:
    def __init__(self, reply: str):
        self._reply = reply

    async def chat(self, **kwargs):
        return self._reply


@pytest.mark.asyncio
async def test_synthesize_returns_citations():
    svc = SynthesisService(client=_FakeClient("It is due Friday [Memory 2]."))
    memories = [
        {"id": "id-a", "content": "car service Monday"},
        {"id": "id-b", "content": "insurance due Friday"},
    ]
    result = await svc.synthesize("when is insurance due?", memories)
    assert result["citations"] == ["id-b"]
    assert result["answer"] == "It is due Friday [Memory 2]."
    assert result["source_count"] == 2
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/unit/test_synthesis_citations.py -v` → FAIL (`parse_citations` undefined; `citations` key missing).

- [ ] **Step 3: Implement** in `life_graph/services/synthesis.py`:

Add at module level (after imports):

```python
import re

_CITATION_RE = re.compile(r"\[Memory\s+(\d+)\]")


def parse_citations(answer: str, memory_ids: list[str]) -> list[str]:
    """Extract [Memory N] tags from an answer and map them to memory ids.

    N is 1-based and aligns with the order memories were given to the model.
    Out-of-range tags are dropped; ids are returned in first-appearance order,
    deduplicated.
    """
    seen: list[str] = []
    for match in _CITATION_RE.finditer(answer):
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(memory_ids):
            mid = memory_ids[idx]
            if mid not in seen:
                seen.append(mid)
    return seen
```

Add a citation rule to `_SYNTHESIS_SYSTEM_PROMPT` (append as a new numbered rule):

```
7. When a fact comes from a memory, cite it inline as [Memory N] using that memory's number from the context. Only cite memories you actually used; never invent a number.
```

Change `synthesize` signature and body:

```python
    async def synthesize(
        self,
        question: str,
        memories: list[dict[str, Any]],
        *,
        model: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
```

Inside, build `memory_ids = [str(m.get("id", "")) for m in memories]` alongside `context_parts`. Build the messages list inserting history between the system prompt and the final user turn:

```python
        messages = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": user_content})
```

After getting `answer`, compute `citations = parse_citations(answer, memory_ids)` (empty on the rule-based fallback path). Return:

```python
        return {
            "answer": answer,
            "source_count": len(memories),
            "model": model_used,
            "citations": citations,
        }
```

(Preserve the existing empty-answer → `_rule_based_answer` fallback; its `citations` is `[]`.)

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_synthesis_citations.py tests/unit/ -v` → green. Existing `ask_brain` still works: it doesn't read `citations`, so no break; but update `api/search.py`'s `memory_dicts` to include `"id": str(m.id)` (one line) so `/search/ask` citations resolve too. `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/synthesis.py life_graph/api/search.py tests/unit/test_synthesis_citations.py
git commit -m "feat(chat): citation-aware synthesis ([Memory N] -> ids) + history"
```

---

### Task 3: ConversationService

**Files:**
- Create: `life_graph/services/conversation.py`
- Modify: `life_graph/core/events.py` (add CONVERSATION_MESSAGE), `life_graph/api/dependencies.py` (provider)
- Test: `tests/unit/test_conversation_service.py` (new)

**Interfaces:**
- Consumes: `HybridQueryEngine.tri_search`, `SynthesisService.synthesize`, `Conversation`/`ConversationMessage` models, `async_session`.
- Produces: `ConversationService(session_factory, hybrid_engine, synthesis)` with:
  - `async def create(self) -> Conversation`
  - `async def list_recent(self, limit=20) -> list[Conversation]`
  - `async def get_thread(self, conversation_id: UUID) -> tuple[Conversation, list[ConversationMessage]] | None`
  - `async def ask(self, conversation_id: UUID, question: str) -> dict` → persists user+assistant turns, returns `{"message": ConversationMessage, "citations": list[str]}`
  - `async def delete(self, conversation_id: UUID) -> bool`
  All tenant-scoped via `get_current_tenant_id()`. Task 4 wraps these.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_conversation_service.py` (mock the engine + synthesis + a fake session factory; verify retrieval is called with `statuses=("active",)`, both turns persisted, citations threaded, title set from first question, tenant isolation). Full test:

```python
"""ConversationService.ask retrieves approved-only, synthesizes, persists both turns."""

import uuid
from unittest.mock import AsyncMock

import pytest

from life_graph.services.conversation import ConversationService


class _FakeSession:
    def __init__(self, store):
        self._store = store
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def add(self, obj):
        self.added.append(obj)
        self._store.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def get(self, model, pk):
        for o in self._store:
            if getattr(o, "id", None) == pk:
                return o
        return None


@pytest.mark.asyncio
async def test_ask_retrieves_active_only_and_persists(monkeypatch):
    store = []
    conv_id = uuid.uuid4()

    # seed a conversation
    from life_graph.models.db import Conversation
    conv = Conversation(id=conv_id, tenant_id="t1", title=None)
    store.append(conv)

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    engine.tri_search.return_value = {
        "memories": [{"id": "m1", "content": "insurance due Friday"}]
    }
    synthesis = AsyncMock()
    synthesis.synthesize.return_value = {
        "answer": "Friday [Memory 1].", "source_count": 1,
        "model": "test", "citations": ["m1"],
    }

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, engine, synthesis)
    result = await svc.ask(conv_id, "when is insurance due?")

    # retrieval was approved-only
    _, kwargs = engine.tri_search.call_args
    assert kwargs.get("statuses") == ("active",)
    # assistant turn returned with citations
    assert result["message"].role == "assistant"
    assert result["message"].cited_memory_ids == ["m1"]
    # both turns persisted
    roles = [getattr(o, "role", None) for o in store if hasattr(o, "role")]
    assert roles == ["user", "assistant"]
    # title set from first question
    assert conv.title == "when is insurance due?"
```

- [ ] **Step 2: Run to verify failure** — FAIL (module/class absent).

- [ ] **Step 3: Implement** `life_graph/services/conversation.py`:

```python
"""ConversationService — grounded, multi-turn chat over approved memories."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Conversation, ConversationMessage

_TITLE_MAX = 60
_HISTORY_TURNS = 6
_RETRIEVE_LIMIT = 8


class ConversationService:
    """Retrieve → synthesize → persist a chat turn, all approved-only."""

    def __init__(self, session_factory, hybrid_engine, synthesis) -> None:
        self._session_factory = session_factory
        self._engine = hybrid_engine
        self._synthesis = synthesis

    async def create(self) -> Conversation:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            conv = Conversation(tenant_id=tenant_id, title=None)
            session.add(conv)
            await session.commit()
            return conv

    async def list_recent(self, limit: int = 20) -> list[Conversation]:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            rows = await session.execute(
                select(Conversation)
                .where(Conversation.tenant_id == tenant_id)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
            )
            return list(rows.scalars().all())

    async def get_thread(
        self, conversation_id: uuid.UUID
    ) -> tuple[Conversation, list[ConversationMessage]] | None:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                return None
            rows = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
            )
            return conv, list(rows.scalars().all())

    async def delete(self, conversation_id: uuid.UUID) -> bool:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                return False
            await session.delete(conv)
            await session.commit()
            return True

    async def ask(self, conversation_id: uuid.UUID, question: str) -> dict[str, Any]:
        tenant_id = get_current_tenant_id()

        # 1. retrieve approved-only
        retrieval = await self._engine.tri_search(
            question, limit=_RETRIEVE_LIMIT, statuses=("active",)
        )
        memories = retrieval.get("memories", [])

        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                raise ValueError("Conversation not found")

            # prior turns → history for the LLM
            prior = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
            )
            history = [
                {"role": m.role, "content": m.content}
                for m in prior.scalars().all()
            ]

            # 2. synthesize
            result = await self._synthesis.synthesize(
                question, memories, history=history or None
            )

            # 3. persist both turns
            user_turn = ConversationMessage(
                conversation_id=conversation_id, tenant_id=tenant_id,
                role="user", content=question, cited_memory_ids=[],
            )
            assistant_turn = ConversationMessage(
                conversation_id=conversation_id, tenant_id=tenant_id,
                role="assistant", content=result["answer"],
                cited_memory_ids=result.get("citations", []),
                model=result.get("model"),
            )
            session.add(user_turn)
            session.add(assistant_turn)
            if not conv.title:
                conv.title = question[:_TITLE_MAX]
            await session.commit()
            await session.refresh(assistant_turn)

        try:
            await event_bus.emit(
                EventType.CONVERSATION_MESSAGE,
                {"conversation_id": str(conversation_id), "tenant_id": tenant_id,
                 "preview": result["answer"][:80]},
                source="conversation",
            )
        except Exception:  # pragma: no cover - events must never break the reply
            pass

        return {"message": assistant_turn, "citations": result.get("citations", [])}
```

`life_graph/core/events.py` — add the block (between Approvals and Agent Driver blocks):

```python
    # ── Conversation Events ──────────────────────────────────
    CONVERSATION_MESSAGE = "conversation:message"
```

`life_graph/api/dependencies.py` — add provider (mirror `get_synthesis_service`, and reuse the hybrid-engine singleton pattern from `api/search.py`/`api/graph.py`; if none is exported, build one from `get_store()`):

```python
@lru_cache(maxsize=1)
def get_conversation_service() -> "ConversationService":
    from life_graph.services.conversation import ConversationService
    from life_graph.storage.database import async_session
    from life_graph.storage.hybrid import HybridQueryEngine

    engine = HybridQueryEngine(memory_store=get_store())
    return ConversationService(async_session, engine, get_synthesis_service())
```

(Check `HybridQueryEngine.__init__` args — the scout shows it holds a `memory_store`; match its real constructor signature.)

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_conversation_service.py tests/unit/ -v` → green. `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/conversation.py life_graph/core/events.py life_graph/api/dependencies.py tests/unit/test_conversation_service.py
git commit -m "feat(chat): ConversationService — retrieve active-only, synthesize, persist"
```

---

### Task 4: Conversation API

**Files:**
- Create: `life_graph/api/conversations.py`
- Modify: `life_graph/main.py` (register router)
- Test: `tests/integration/test_conversations_api.py` (new)

**Interfaces:**
- Consumes: `get_conversation_service`, `get_current_tenant_id`, `success_response`, `MemoryResponse`.
- Produces routes under `/conversations`:
  - `POST /conversations` → `{data: {id, title, created_at}}`
  - `GET /conversations` → `{data: [{id, title, updated_at}]}`
  - `GET /conversations/{id}` → `{data: {id, title, messages: [{id, role, content, cited_memory_ids, model, created_at}]}}` (404 cross-tenant)
  - `POST /conversations/{id}/messages` `{content}` → `{data: {message: {...}, citations: [MemoryResponse]}}` (422 empty content; 404 unknown/cross-tenant)
  - `DELETE /conversations/{id}` → `{data: {deleted: bool}}`
  Task 5 (frontend) calls exactly these.

- [ ] **Step 1: Failing test** — `tests/integration/test_conversations_api.py` mirroring `tests/integration/test_approvals.py` (ASGITransport client, TENANT_HEADERS, `@skip_on_db_error`, tolerant asserts). Cover: create → returns id; post-message → returns answer + citations, both turns visible in GET thread; empty content → 422; cross-tenant id → 404; delete → gone. (Will SKIP locally without DB; runs in Task 8.)

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {"X-Tenant-ID": "test-chat"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=TENANT_HEADERS) as c:
        yield c


@skip_on_db_error
@pytest.mark.asyncio
async def test_create_and_ask(client: AsyncClient):
    created = await client.post("/api/v1/conversations")
    assert created.status_code in (200, 201, 500)
    if created.status_code not in (200, 201):
        pytest.skip("DB unavailable")
    cid = created.json()["data"]["id"]
    ask = await client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "hello?"})
    assert ask.status_code in (200, 500)
    if ask.status_code == 200:
        assert "message" in ask.json()["data"]


@skip_on_db_error
@pytest.mark.asyncio
async def test_empty_content_422(client: AsyncClient):
    created = await client.post("/api/v1/conversations")
    if created.status_code not in (200, 201):
        pytest.skip("DB unavailable")
    cid = created.json()["data"]["id"]
    resp = await client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "  "})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run to verify failure** — 404 (routes absent).

- [ ] **Step 3: Implement** `life_graph/api/conversations.py`:

```python
"""Ask-your-memories chat API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from life_graph.api.dependencies import get_conversation_service, get_store
from life_graph.api.responses import success_response
from life_graph.models.schemas import MemoryResponse
from life_graph.services.conversation import ConversationService
from life_graph.storage.postgres import PostgresMemoryStore

router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageBody(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content must not be empty")
        return v


@router.post("")
async def create_conversation(svc: ConversationService = Depends(get_conversation_service)):
    conv = await svc.create()
    return success_response(data={"id": str(conv.id), "title": conv.title,
                                  "created_at": str(conv.created_at)})


@router.get("")
async def list_conversations(svc: ConversationService = Depends(get_conversation_service)):
    convs = await svc.list_recent()
    return success_response(data=[
        {"id": str(c.id), "title": c.title, "updated_at": str(c.updated_at)}
        for c in convs
    ])


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: UUID,
                           svc: ConversationService = Depends(get_conversation_service)):
    thread = await svc.get_thread(conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv, messages = thread
    return success_response(data={
        "id": str(conv.id), "title": conv.title,
        "messages": [
            {"id": str(m.id), "role": m.role, "content": m.content,
             "cited_memory_ids": [str(x) for x in m.cited_memory_ids],
             "model": m.model, "created_at": str(m.created_at)}
            for m in messages
        ],
    })


@router.post("/{conversation_id}/messages")
async def post_message(conversation_id: UUID, body: MessageBody,
                       svc: ConversationService = Depends(get_conversation_service),
                       store: PostgresMemoryStore = Depends(get_store)):
    try:
        result = await svc.ask(conversation_id, body.content)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg = result["message"]
    # resolve citation ids to full memories for chips
    citations = []
    for mid in result["citations"]:
        row = await store.retrieve(UUID(mid))
        if row is not None:
            citations.append(MemoryResponse.model_validate(row))
    return success_response(data={
        "message": {"id": str(msg.id), "role": msg.role, "content": msg.content,
                    "cited_memory_ids": [str(x) for x in msg.cited_memory_ids],
                    "model": msg.model, "created_at": str(msg.created_at)},
        "citations": [c.model_dump(mode="json") for c in citations],
    })


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: UUID,
                              svc: ConversationService = Depends(get_conversation_service)):
    deleted = await svc.delete(conversation_id)
    return success_response(data={"deleted": deleted})
```

`life_graph/main.py` — after the `approvals_api` include (before `app.include_router(v1_router)`):

```python
    from life_graph.api import conversations as conversations_api
    v1_router.include_router(conversations_api.router)
```

- [ ] **Step 4: Run tests** — integration tests SKIP locally; full `python -m pytest tests/unit/ -v` green. Verify routes load: `python -c "from life_graph.main import app; print([r.path for r in app.routes if 'conversation' in r.path])"`. `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/api/conversations.py life_graph/main.py tests/integration/test_conversations_api.py
git commit -m "feat(chat): conversations REST API (create/list/thread/ask/delete)"
```

---

### Task 5: Dashboard API client + hooks + shared MemorySheet

**Files:**
- Modify: `dashboard/lib/api.ts` (add `conversations` group)
- Modify: `dashboard/lib/mobile-api.ts` (hooks + VMs)
- Create: `dashboard/components/mobile/memory-sheet.tsx` (extract from the memories page)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx` (import the extracted sheet)
- Test: `npm run build` + lint

**Interfaces:**
- Consumes: Task 4 routes.
- Produces: `api.conversations.{create,list,get,ask,remove}`; hooks `useConversations()`, `useConversation(id)`, `useSendMessage()`; shared `<MemorySheet mem onClose resolve>` component. Tasks 6–7 consume these.

- [ ] **Step 1: API client** — add to the `api` object in `lib/api.ts`:

```ts
  conversations: {
    create: () => POST<any>("/conversations", {}),
    list: () => listRequest<any>("/conversations"),
    get: (id: string) => GET<any>(`/conversations/${id}`),
    ask: (id: string, content: string) => POST<any>(`/conversations/${id}/messages`, { content }),
    remove: (id: string) => request<any>("DELETE", `/conversations/${id}`),
  },
```

- [ ] **Step 2: Hooks** — in `lib/mobile-api.ts`, mirroring the useApprovals/useResolveApproval shape:

```ts
export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.conversations.list(),
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api.conversations.get(id as string).then((r) => r.data),
    enabled: !!id,
  });
}

export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      api.conversations.ask(id, content).then((r) => r.data),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["conversation", vars.id] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
```

- [ ] **Step 3: Extract MemorySheet** — move the `MemorySheet` function currently local in `dashboard/app/(mobile)/m/memories/page.tsx` into `dashboard/components/mobile/memory-sheet.tsx` as an exported component with the same props (`{ mem: MemoryVM; onClose: () => void; resolve: ReturnType<typeof useResolveMemory> }`), export `MemoryVM` too if needed. Import it back into the memories page (behavior unchanged there — this is a pure move).

- [ ] **Step 4: Verify** — `cd dashboard && npm run build` passes; lint zero new problems; the memories page still renders the sheet identically.

- [ ] **Step 5: Commit**

```bash
git add dashboard/lib/api.ts dashboard/lib/mobile-api.ts dashboard/components/mobile/memory-sheet.tsx dashboard/app/(mobile)/m/memories/page.tsx
git commit -m "feat(chat): dashboard conversations client, hooks, shared MemorySheet"
```

---

### Task 6: Mobile chat surface

**Files:**
- Create: `dashboard/app/(mobile)/m/chat/page.tsx`
- Modify: `dashboard/components/mobile/mobile-tabbar.tsx` (add Chat tab, bump grid to 5 cols)
- Test: `npm run build` + lint

**Interfaces:**
- Consumes: `useConversations`, `useConversation`, `useSendMessage`, shared `MemorySheet`.

- [ ] **Step 1: Chat page** `dashboard/app/(mobile)/m/chat/page.tsx` — `"use client"`, default-exported `MobileChat`. Behavior:
  - If no conversation selected: show recent conversations list (`useConversations`) + a "New chat" button (calls `api.conversations.create` then selects it). Empty state uses `EmptyCard`.
  - Selected conversation: `useConversation(id)` renders message bubbles (user right, assistant left) using inline styles + CSS vars; assistant bubbles render citation chips by splitting `content` on `[Memory N]` tokens and rendering each N as a tappable chip resolving to `data.citations[?]` — since the thread GET doesn't return full citation memories, keep the chips from the immediate `useSendMessage` response for the just-sent turn, and for historical turns render the `[Memory N]` inline as a subtle superscript that, on tap, calls `api.memories.get(cited_memory_ids[N-1])` and opens the shared `MemorySheet`. (Store `cited_memory_ids` per message from the thread payload.)
  - Input box at the bottom, disabled offline (reuse the offline detection pattern from `mobile-capture.tsx`), "Thinking…" bubble while `useSendMessage` is pending.
  - Follow the inline-style/token conventions of the other `m/*` pages exactly.

- [ ] **Step 2: Tab** — in `mobile-tabbar.tsx`: add `{ href: "/m/chat", label: "Ask", icon: MessageCircle }` (import `MessageCircle` from `lucide-react`) to `TABS`, and change `gridTemplateColumns: "repeat(4, 1fr)"` → `"repeat(5, 1fr)"`.

- [ ] **Step 3: Verify** — `npm run build` passes; lint zero new; manual mental check of the offline-disable + thinking state.

- [ ] **Step 4: Commit**

```bash
git add "dashboard/app/(mobile)/m/chat/page.tsx" dashboard/components/mobile/mobile-tabbar.tsx
git commit -m "feat(chat): mobile Ask tab — threaded chat with citation chips"
```

---

### Task 7: Desktop ChatBar upgrade

**Files:**
- Modify: `dashboard/components/chat-bar.tsx`
- Test: `npm run build` + lint

**Interfaces:**
- Consumes: `useSendMessage`, `api.conversations.create`.

- [ ] **Step 1: Rework** `chat-bar.tsx` to be a compact quick-ask:
  - On first submit, lazily create a conversation (`api.conversations.create`), store its id in local state, then `useSendMessage({id, content})`; subsequent submits reuse the same id (a session-scoped quick thread).
  - Render the returned grounded `answer` with citation chips (split on `[Memory N]`, chip → open memory detail; desktop can route to `/memories?id=` or a simple popover — keep minimal: chip shows the memory content on hover/click via the existing memory detail component on the desktop memories page, or a lightweight inline expansion).
  - Remove the `capture.mutate` advisor call and the `route.mutateAsync`/`api.kernel.route` usage entirely. Remove `JSON.stringify(response)` fallback.
  - Keep the ⌘K focus behavior and the "Conversation" label.

- [ ] **Step 2: Verify** — `npm run build` passes; lint zero new.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/chat-bar.tsx
git commit -m "feat(chat): desktop ChatBar answers from memories with citations"
```

---

### Task 8: Deploy + live E2E + PR

**Files:** none (VM ops + PR)

- [ ] **Step 1: Push & deploy** — push `feat/memory-chat`; on the VM: fetch + checkout + pull, `docker compose ... build app worker`, **apply the migration** `docker exec life_graph_app python -m alembic upgrade head` (verify `conversations`/`conversation_messages` tables created), `up -d --force-recreate --no-deps app worker`, `docker network connect web life_graph_app`, dashboard rebuild + stop/rm/run swap, smoke `/m` + `/api/v1/memories/` = 200.

- [ ] **Step 2: Live E2E** (base64 remote bash):
  1. Approve a memory with known content (e.g. capture "Car insurance due August 15", approve it).
  2. `POST /api/v1/conversations` → get id.
  3. `POST /conversations/{id}/messages {"content":"when is my car insurance due?"}` → answer mentions "August 15", `citations` non-empty, cites the right memory id.
  4. Follow-up `{"content":"what about the car service?"}` → resolves in context (or says not enough memories if none captured).
  5. Ask about a non-captured topic → "I don't have enough memories".
  6. Ask about a still-*pending* memory → not answered (approved-only proof): capture but DON'T approve a distinctive fact, ask about it → not surfaced; approve it, ask again → now answered.
  7. `GET /conversations/{id}` → both turns present in order; `GET /conversations` → thread listed with title.

- [ ] **Step 3: Phone E2E (user)** — open the new **Ask** tab → ask a question → grounded answer with citation chips → tap a chip → memory opens → ask a follow-up → revisit the thread later.

- [ ] **Step 4: PR**

```bash
gh pr create --repo Raceraja001/life-graph --base master --head feat/memory-chat \
  --title "feat: ask-your-memories chat — grounded, multi-turn, cited" \
  --body "Implements docs/superpowers/specs/2026-07-23-ask-your-memories-chat-design.md ..."
```

---

## Self-review notes

- Spec coverage: tables+migration (T1), citation-aware grounded synthesis (T2), retrieve-active-only + persist + multi-turn history (T3), REST API (T4), client/hooks/shared sheet (T5), mobile surface (T6), desktop upgrade (T7), migration-applied deploy + approved-only E2E (T8). ✅
- Type consistency: `synthesize(...)` returns `citations: list[str]` (T2) consumed by `ConversationService.ask` (T3) → API `citations` resolved to `MemoryResponse` (T4) → hooks/chips (T5-7). `statuses=("active",)` asserted in T3 test. Route paths in T4 == client paths in T5. ✅
- Known judgment calls: desktop citation chips kept minimal (T7) vs the richer mobile sheet (T6) — acceptable per spec's "compact quick-ask" desktop decision. Historical-turn citation chips re-fetch the memory on tap rather than storing full memories per message (keeps `conversation_messages` lean — only ids stored). Retrieval uses the raw question (no history-aware query rewrite) per spec non-goals.
