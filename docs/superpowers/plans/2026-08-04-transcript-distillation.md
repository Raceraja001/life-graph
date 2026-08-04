# External-AI Transcript Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distill the user's local Claude Code transcripts into Life Graph — server-side parse → redact → extract facts (pending, deduped) + archive raw to MinIO — fed by a thin, resumable local uploader, with full backfill and go-forward on one code path.

**Architecture:** A local `scripts/transcript_uploader.py` tails `~/.claude/projects/**/*.jsonl` and POSTs raw line-deltas to `POST /api/v1/ingest/transcript`. The endpoint upserts an `ExternalSession`, appends the raw lines to a per-session MinIO staging object, and enqueues a debounced ARQ `distill_transcript` job. The job parses the Claude Code JSONL into user `Turn`s, redacts secrets, feeds new-turn text through `MemoryManager.ingest` (pending + deduped), and archives the redacted thread to a `transcripts` MinIO bucket — reusing the exact primitives of the existing `ConversationDistiller`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 async (`mapped_column`), Alembic, ARQ (Redis), MinIO (`minio` SDK), pytest + `httpx.AsyncClient`/`ASGITransport`. The local uploader uses stdlib only (`urllib`, `json`, `pathlib`, `os`).

## Global Constraints

- **Branch/worktree:** all work on `feat/transcript-distillation`, worktree `scratchpad/transcript-wt`, based off `origin/master` @ `430b016`.
- **Tenant scoping:** every DB query filters by `tenant_id`; uploader sends `X-Tenant-ID: personal`; the worker sets tenant via `set_tenant_context(tenant_id, "system")`.
- **Secrets:** never commit or print secrets. Uploader config (backend URL, API key, CF service-token pair) lives in a local gitignored JSON; `.env.example` names variables only.
- **Redaction runs before both extraction and archive** — credentials never reach MinIO or become memories.
- **Commit trailer** exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Memories go through `MemoryManager.ingest`** (SHA-256 + pgvector dedup) — no bespoke insert path.
- **Ruff:** line-length 100, double quotes. Run `ruff check` + `ruff format` before each commit.
- **Test convention:** unit tests need no Postgres (conftest mocks pgvector); integration tests use `ASGITransport(app=app)` + `X-Tenant-ID` header and the `skip_on_db_error` decorator from `tests.integration.conftest`; valid input must never yield `422`; accept `500` when DB/redis is down.
- **Python interpreter for local runs:** `/c/Python314/python.exe` (per house gotcha).
- **Reused interfaces (already exist — do not reimplement):**
  - `life_graph.core.memory_manager.MemoryManager.ingest(text, context=None, source=None, skip_dedup=False, trust_tier=None, capture=False) -> list[Memory]`
  - `life_graph.storage.minio_client.MinIOStorage`: `.upload(bucket, key, data: bytes, content_type=...) -> str`, `.download(bucket, key) -> bytes` (raises `minio.error.S3Error` if the key is absent), `.ensure_bucket(bucket)` (called inside `upload`).
  - `life_graph.api.dependencies`: `get_memory_manager()`, `get_store()`, module-level `async_session` (an async sessionmaker).
  - `life_graph.models.schemas.MemoryUpdate(tags=[...])`; `store.update(memory_id, MemoryUpdate) -> Memory`.
  - `life_graph.core.tenant.get_current_tenant_id()`, `set_tenant_context(tenant_id, actor)`.
  - `life_graph.storage.redis.get_redis() -> aioredis.Redis | None` (None when Redis unconfigured).
  - ARQ enqueue: `from arq import create_pool; from life_graph.workers.settings import parse_redis_settings; pool = await create_pool(parse_redis_settings()); await pool.enqueue_job("<dotted>", *args)`.
  - `life_graph.core.events.event_bus.emit(EventType.X, payload: dict, source: str)`; `EventType` is a `str, Enum`.

---

## File Structure

**Created:**
- `life_graph/services/redaction.py` — `redact(text) -> str` secret scrubber.
- `life_graph/extraction/transcript_parsers/__init__.py` — `PARSERS` registry.
- `life_graph/extraction/transcript_parsers/base.py` — `Turn` TypedDict + `TranscriptParser` Protocol.
- `life_graph/extraction/transcript_parsers/claude_code.py` — `ClaudeCodeParser`.
- `life_graph/services/transcript_distiller.py` — `TranscriptDistiller`, `ExternalSessionNotFound`, `build_transcript_snapshot`.
- `life_graph/api/ingest_transcript.py` — router, `POST /api/v1/ingest/transcript`.
- `life_graph/workers/distill_transcript.py` — ARQ `distill_transcript` job.
- `alembic/versions/030_external_sessions.py` — migration.
- `scripts/transcript_uploader.py` + `scripts/run_transcript_uploader.bat` — local uploader.
- Tests: `tests/unit/test_redaction.py`, `tests/unit/test_claude_code_parser.py`, `tests/unit/test_transcript_distiller.py`, `tests/unit/test_transcript_uploader.py`, `tests/integration/test_ingest_transcript.py`, fixture `tests/fixtures/claude_code_sample.jsonl`.

**Modified:**
- `life_graph/models/db.py` — add `ExternalSession`.
- `life_graph/models/schemas.py` — add `TranscriptIngest`.
- `life_graph/core/events.py` — add `EventType.TRANSCRIPT_DISTILLED`.
- `life_graph/api/dependencies.py` — add `get_transcript_distiller()`.
- `life_graph/main.py` — register the ingest_transcript router.
- `life_graph/workers/settings.py` — register the `distill_transcript` function.
- `.env.example` — document uploader variables (names only).

---

## Task 1: Secret redactor

**Files:**
- Create: `life_graph/services/redaction.py`
- Test: `tests/unit/test_redaction.py`

**Interfaces:**
- Produces: `redact(text: str) -> str` — returns text with common secret shapes replaced by `«REDACTED:<kind>»`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_redaction.py
"""Unit tests for the secret redactor."""
from __future__ import annotations

from life_graph.services.redaction import redact


def test_redacts_bearer_token():
    assert "REDACTED" in redact("Authorization: Bearer sk-abcDEF1234567890abcdef")
    assert "sk-abcDEF1234567890abcdef" not in redact("Bearer sk-abcDEF1234567890abcdef")


def test_redacts_openai_style_key():
    out = redact("my key is sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX please")
    assert "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX" not in out
    assert "please" in out


def test_redacts_aws_access_key():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("AKIAIOSFODNN7EXAMPLE")


def test_redacts_google_api_key():
    key = "AIzaSyA1234567890abcdefghijklmnopqrstuvw"
    assert key not in redact(f"key={key}")


def test_redacts_pem_private_key():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOwIBAAJB\n-----END RSA PRIVATE KEY-----"
    out = redact(pem)
    assert "MIIBOwIBAAJB" not in out


def test_redacts_env_secret_assignment():
    assert "hunter2secretvalue" not in redact("DATABASE_PASSWORD=hunter2secretvalue")
    assert "topsecrettoken123" not in redact("MY_API_KEY: topsecrettoken123")


def test_leaves_ordinary_code_intact():
    code = "def add(a, b):\n    return a + b  # simple helper"
    assert redact(code) == code


def test_non_string_safe():
    assert redact("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_redaction.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_graph.services.redaction'`.

- [ ] **Step 3: Write the implementation**

```python
# life_graph/services/redaction.py
"""Best-effort secret redaction for external transcript content.

Applied to every turn's text before fact extraction and to the raw thread
before archiving, so credentials never become memories or land in MinIO.
This is deliberately conservative-but-present: it removes the common
high-risk secret shapes, not every conceivable one.
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pem", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    )),
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}")),
    ("openrouter_key", re.compile(r"sk-or-[A-Za-z0-9\-]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9\-]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("env_secret", re.compile(
        r"(?im)^(\s*[A-Z0-9_]*"
        r"(?:SECRET|TOKEN|PASSWORD|API[_-]?KEY|PRIVATE[_-]?KEY)[A-Z0-9_]*\s*[=:]\s*)\S+"
    )),
]


def redact(text: str) -> str:
    """Replace common secret shapes with ``«REDACTED:<kind>»``."""
    if not text:
        return text
    out = text
    for kind, pat in _PATTERNS:
        if kind == "env_secret":
            out = pat.sub(rf"\1«REDACTED:{kind}»", out)
        else:
            out = pat.sub(f"«REDACTED:{kind}»", out)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_redaction.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/services/redaction.py && ruff format life_graph/services/redaction.py tests/unit/test_redaction.py
git add life_graph/services/redaction.py tests/unit/test_redaction.py
git commit -m "feat(redaction): best-effort secret scrubber for transcript content

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Claude Code transcript parser

**Files:**
- Create: `life_graph/extraction/transcript_parsers/base.py`
- Create: `life_graph/extraction/transcript_parsers/claude_code.py`
- Create: `life_graph/extraction/transcript_parsers/__init__.py`
- Create: `tests/fixtures/claude_code_sample.jsonl`
- Test: `tests/unit/test_claude_code_parser.py`

**Interfaces:**
- Produces:
  - `Turn` = `TypedDict("Turn", {"role": str, "text": str, "ts": str | None})`
  - `class TranscriptParser(Protocol)` with attribute `tool: str` and method `parse(self, lines: Iterable[str]) -> list[Turn]`.
  - `PARSERS: dict[str, TranscriptParser]` — `{"claude-code": ClaudeCodeParser()}`.

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/claude_code_sample.jsonl` (one JSON object per line — keep it exactly these 6 lines):

```jsonl
{"type":"user","userType":"external","isSidechain":false,"timestamp":"2026-08-01T10:00:00Z","message":{"role":"user","content":"I always deploy with free OpenRouter models to keep costs at zero."}}
{"type":"assistant","timestamp":"2026-08-01T10:00:05Z","message":{"role":"assistant","content":[{"type":"text","text":"Got it."}]}}
{"type":"user","userType":"external","isSidechain":false,"timestamp":"2026-08-01T10:01:00Z","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"x","content":"file contents here"}]}}
{"type":"user","userType":"external","isSidechain":false,"timestamp":"2026-08-01T10:02:00Z","message":{"role":"user","content":[{"type":"text","text":"<system-reminder>ambient context</system-reminder>"}]}}
{"type":"user","userType":"external","isSidechain":true,"timestamp":"2026-08-01T10:03:00Z","message":{"role":"user","content":"subagent side thread prompt"}}
{"type":"attachment","timestamp":"2026-08-01T10:04:00Z","attachment":{"foo":"bar"}}
```

Only the **first** line is a genuine user prompt → exactly one `Turn`.

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_claude_code_parser.py
"""Unit tests for the Claude Code JSONL transcript parser."""
from __future__ import annotations

from pathlib import Path

from life_graph.extraction.transcript_parsers import PARSERS
from life_graph.extraction.transcript_parsers.claude_code import ClaudeCodeParser

FIXTURE = Path(__file__).parent.parent / "fixtures" / "claude_code_sample.jsonl"


def _lines() -> list[str]:
    return FIXTURE.read_text(encoding="utf-8").splitlines()


def test_registered_under_claude_code_key():
    assert isinstance(PARSERS["claude-code"], ClaudeCodeParser)
    assert PARSERS["claude-code"].tool == "claude-code"


def test_extracts_only_genuine_user_prompt():
    turns = ClaudeCodeParser().parse(_lines())
    assert len(turns) == 1
    assert turns[0]["role"] == "user"
    assert "OpenRouter" in turns[0]["text"]
    assert turns[0]["ts"] == "2026-08-01T10:00:00Z"


def test_drops_tool_results_sidechains_reminders_assistant_and_attachments():
    texts = [t["text"] for t in ClaudeCodeParser().parse(_lines())]
    joined = "\n".join(texts)
    assert "file contents here" not in joined   # tool_result dropped
    assert "subagent side thread" not in joined  # isSidechain dropped
    assert "ambient context" not in joined       # system-reminder-only dropped
    assert "Got it" not in joined                # assistant dropped


def test_ignores_malformed_lines():
    turns = ClaudeCodeParser().parse(["not json", "", '{"type":"user"}'])
    assert turns == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_claude_code_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.extraction.transcript_parsers`.

- [ ] **Step 4: Write `base.py`**

```python
# life_graph/extraction/transcript_parsers/base.py
"""Shared types for pluggable transcript parsers.

A parser turns one tool's raw transcript lines into a common ``Turn`` list;
the distiller and endpoint stay tool-agnostic.
"""
from __future__ import annotations

from typing import Iterable, Protocol, TypedDict


class Turn(TypedDict):
    role: str          # "user" | "assistant"
    text: str          # plain text content
    ts: str | None     # ISO8601 timestamp if available


class TranscriptParser(Protocol):
    tool: str

    def parse(self, lines: Iterable[str]) -> list[Turn]: ...
```

- [ ] **Step 5: Write `claude_code.py`**

```python
# life_graph/extraction/transcript_parsers/claude_code.py
"""Parser for Claude Code session transcripts (``~/.claude/projects/**/*.jsonl``).

Each line is a JSON object with a top-level ``type``. Only genuine, external,
non-sidechain ``user`` turns yield a Turn; tool results, harness-injected
system-reminders, assistant turns, and bookkeeping lines are dropped.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from life_graph.extraction.transcript_parsers.base import Turn


class ClaudeCodeParser:
    tool = "claude-code"

    def parse(self, lines: Iterable[str]) -> list[Turn]:
        turns: list[Turn] = []
        for raw in lines:
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(obj, dict) or obj.get("type") != "user":
                continue
            if obj.get("isSidechain"):
                continue
            if obj.get("userType") not in (None, "external"):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            text = self._text(msg.get("content")).strip()
            if not text or self._harness_only(text):
                continue
            turns.append(Turn(role="user", text=text, ts=obj.get("timestamp")))
        return turns

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            return "\n".join(parts)
        return ""

    @staticmethod
    def _harness_only(text: str) -> bool:
        """True when the whole turn is a harness wrapper, not real user text."""
        t = text.strip()
        return (
            (t.startswith("<system-reminder>") and t.endswith("</system-reminder>"))
            or t.startswith("<local-command-")
        )
```

- [ ] **Step 6: Write `__init__.py`**

```python
# life_graph/extraction/transcript_parsers/__init__.py
"""Registry of transcript parsers keyed by tool name."""
from __future__ import annotations

from life_graph.extraction.transcript_parsers.base import TranscriptParser, Turn
from life_graph.extraction.transcript_parsers.claude_code import ClaudeCodeParser

PARSERS: dict[str, TranscriptParser] = {
    "claude-code": ClaudeCodeParser(),
}

__all__ = ["PARSERS", "TranscriptParser", "Turn"]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_claude_code_parser.py -v`
Expected: PASS (4 passed).

- [ ] **Step 8: Lint + commit**

```bash
ruff check life_graph/extraction/transcript_parsers/ && ruff format life_graph/extraction/transcript_parsers/ tests/unit/test_claude_code_parser.py
git add life_graph/extraction/transcript_parsers/ tests/unit/test_claude_code_parser.py tests/fixtures/claude_code_sample.jsonl
git commit -m "feat(parsers): pluggable transcript parser + Claude Code JSONL parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: ExternalSession model + migration

**Files:**
- Modify: `life_graph/models/db.py` (add `ExternalSession` after `ConversationMessage`)
- Create: `alembic/versions/030_external_sessions.py`
- Test: `tests/unit/test_external_session_model.py`

**Interfaces:**
- Produces: `ExternalSession` ORM model with columns `id, tenant_id, tool, external_id, source_path, raw_key, line_count, last_turn_index, last_distilled_at, created_at, updated_at` and unique `(tenant_id, tool, external_id)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_external_session_model.py
"""Unit tests for the ExternalSession model shape."""
from __future__ import annotations

from life_graph.models.db import ExternalSession


def test_columns_present():
    cols = set(ExternalSession.__table__.columns.keys())
    assert {
        "id", "tenant_id", "tool", "external_id", "source_path",
        "raw_key", "line_count", "last_turn_index", "last_distilled_at",
        "created_at", "updated_at",
    } <= cols


def test_unique_constraint_on_tenant_tool_external_id():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in ExternalSession.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("tenant_id", "tool", "external_id") in uniques
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_external_session_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'ExternalSession'`.

- [ ] **Step 3: Add the model to `life_graph/models/db.py`**

Add after the `ConversationMessage` class (imports `UniqueConstraint` — verify it is in the existing `from sqlalchemy import (...)` block near the top; the block already imports `Index`, `String`, `Text`, `Integer`, `DateTime`. Add `UniqueConstraint` to that import list if absent):

```python
class ExternalSession(Base):
    """One external AI-tool session (e.g. a Claude Code transcript file)."""

    __tablename__ = "external_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_distilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "tool", "external_id", name="uq_external_session"),
        Index("ix_external_sessions_tenant_tool", "tenant_id", "tool"),
    )

    def __repr__(self) -> str:
        return f"<ExternalSession(tool={self.tool}, external_id={self.external_id})>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_external_session_model.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Write the Alembic migration**

Create `alembic/versions/030_external_sessions.py` (down_revision is `029`, the current head from the batch deploy):

```python
"""external_sessions table

Revision ID: 030
Revises: 029
Create Date: 2026-08-04

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="legacy"),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("raw_key", sa.Text(), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_turn_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_distilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "tool", "external_id", name="uq_external_session"),
    )
    op.create_index(
        "ix_external_sessions_tenant_tool", "external_sessions", ["tenant_id", "tool"]
    )


def downgrade() -> None:
    op.drop_index("ix_external_sessions_tenant_tool", table_name="external_sessions")
    op.drop_table("external_sessions")
```

- [ ] **Step 6: Verify single alembic head**

Run: `/c/Python314/python.exe -m alembic heads`
Expected: exactly one head, `030 (head)`. (No DB needed — this reads the migration files. If it errors on DB config, instead confirm `down_revision = "029"` matches the output of `/c/Python314/python.exe -m alembic history | head -3`.)

- [ ] **Step 7: Lint + commit**

```bash
ruff check life_graph/models/db.py alembic/versions/030_external_sessions.py && ruff format life_graph/models/db.py alembic/versions/030_external_sessions.py tests/unit/test_external_session_model.py
git add life_graph/models/db.py alembic/versions/030_external_sessions.py tests/unit/test_external_session_model.py
git commit -m "feat(models): ExternalSession model + migration 030

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: TranscriptDistiller service

**Files:**
- Create: `life_graph/services/transcript_distiller.py`
- Modify: `life_graph/core/events.py` (add `TRANSCRIPT_DISTILLED`)
- Test: `tests/unit/test_transcript_distiller.py`

**Interfaces:**
- Consumes: `PARSERS` (Task 2), `redact` (Task 1), `ExternalSession` (Task 3), `MemoryManager.ingest`, `MinIOStorage.upload/.download`, `store.update`, `MemoryUpdate`, `get_current_tenant_id`.
- Produces:
  - `ExternalSessionNotFound(Exception)`
  - `TranscriptDistiller(session_factory, memory_manager, minio, store, parsers)` with `async def distill(session_id: str) -> dict` returning `{"new_facts": int, "archived": bool, "skipped": bool}`.
  - `ARCHIVE_BUCKET = "transcripts"`.

- [ ] **Step 1: Add the event type to `life_graph/core/events.py`**

After the `CONVERSATION_DISTILLED = "conversation:distilled"` line, add:

```python
    TRANSCRIPT_DISTILLED = "transcript:distilled"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_transcript_distiller.py
"""Unit tests for TranscriptDistiller with all I/O mocked."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.extraction.transcript_parsers import PARSERS
from life_graph.services.transcript_distiller import (
    ExternalSessionNotFound,
    TranscriptDistiller,
)

TENANT = "test-transcript"

# Two user turns; second is new relative to last_turn_index=0 after first run.
RAW = (
    '{"type":"user","userType":"external","isSidechain":false,'
    '"timestamp":"2026-08-01T10:00:00Z","message":{"role":"user",'
    '"content":"I prefer OpenRouter free models. My key is sk-abcDEF1234567890abcdef."}}\n'
    '{"type":"user","userType":"external","isSidechain":false,'
    '"timestamp":"2026-08-01T10:05:00Z","message":{"role":"user",'
    '"content":"Deploy target is the GCP VM."}}\n'
)


def _session_obj():
    return SimpleNamespace(
        id=uuid.uuid4(), tenant_id=TENANT, tool="claude-code",
        external_id="sess-1", raw_key="staging/x.ndjson",
        line_count=2, last_turn_index=0, last_distilled_at=None,
    )


def _distiller(sess, ingest_returns):
    session = MagicMock()
    session.get = AsyncMock(return_value=sess)
    session.commit = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    manager = MagicMock()
    manager.ingest = AsyncMock(return_value=ingest_returns)
    minio = MagicMock()
    minio.download = MagicMock(return_value=RAW.encode("utf-8"))
    minio.upload = MagicMock(return_value="http://x")
    store = MagicMock()
    store.update = AsyncMock()
    # Resolve the ExternalSession by (tenant, tool, external_id) via session.get by pk;
    # the distiller looks it up by external_id, so stub the query path too.
    d = TranscriptDistiller(factory, manager, minio, store, PARSERS)
    return d, manager, minio, store, session


@pytest.mark.asyncio
async def test_distill_extracts_new_turns_and_archives(monkeypatch):
    from life_graph.core import tenant as tmod
    monkeypatch.setattr(tmod, "get_current_tenant_id", lambda: TENANT)
    from life_graph.services import transcript_distiller as td
    monkeypatch.setattr(td, "get_current_tenant_id", lambda: TENANT)

    sess = _session_obj()
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, manager, minio, store, session = _distiller(sess, [mem])
    # Make the distiller's session lookup return our session regardless of query.
    monkeypatch.setattr(d, "_load_session", AsyncMock(return_value=sess))

    result = await d.distill("sess-1")

    assert result["new_facts"] == 1
    assert result["archived"] is True
    # Extraction text must be redacted — the sk- key must not be passed to ingest.
    passed_text = manager.ingest.call_args.args[0] if manager.ingest.call_args.args \
        else manager.ingest.call_args.kwargs["text"]
    assert "sk-abcDEF1234567890abcdef" not in passed_text
    # Archive uploaded to the transcripts bucket, redacted.
    assert minio.upload.call_args.args[0] == "transcripts"
    assert sess.last_turn_index == 2


@pytest.mark.asyncio
async def test_missing_session_raises(monkeypatch):
    from life_graph.services import transcript_distiller as td
    monkeypatch.setattr(td, "get_current_tenant_id", lambda: TENANT)
    d, *_ = _distiller(_session_obj(), [])
    monkeypatch.setattr(d, "_load_session", AsyncMock(return_value=None))
    with pytest.raises(ExternalSessionNotFound):
        await d.distill("nope")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_distiller.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.services.transcript_distiller`.

- [ ] **Step 4: Write the implementation**

```python
# life_graph/services/transcript_distiller.py
"""TranscriptDistiller — promote new user-turns from an external AI session into
pending memories and archive the redacted thread to MinIO.

Parallel to ConversationDistiller; reuses MemoryManager.ingest + MinIOStorage.
Progress is tracked by turn index (robust to tools that lack clean timestamps).
"""
from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import ExternalSession, _utcnow
from life_graph.models.schemas import MemoryUpdate
from life_graph.services.redaction import redact

logger = logging.getLogger(__name__)

ARCHIVE_BUCKET = "transcripts"


class ExternalSessionNotFound(Exception):
    """Raised when the session is missing or owned by another tenant."""


def build_transcript_snapshot(session: Any, turns: list[dict], memory_ids: list) -> bytes:
    """Serialize the redacted thread to a UTF-8 JSON snapshot (bytes)."""
    doc = {
        "tool": session.tool,
        "external_id": session.external_id,
        "tenant_id": session.tenant_id,
        "distilled_at": _utcnow().isoformat(),
        "turns": [
            {"role": t["role"], "text": redact(t["text"]), "ts": t.get("ts")}
            for t in turns
        ],
        "distilled_memory_ids": [str(m) for m in memory_ids],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")


class TranscriptDistiller:
    def __init__(self, session_factory, memory_manager, minio, store, parsers) -> None:
        self._session_factory = session_factory
        self._manager = memory_manager
        self._minio = minio
        self._store = store
        self._parsers = parsers

    async def _load_session(self, session, tenant_id: str, external_id: str):
        rows = await session.execute(
            select(ExternalSession).where(
                ExternalSession.tenant_id == tenant_id,
                ExternalSession.external_id == external_id,
            )
        )
        return rows.scalars().first()

    async def distill(self, session_id: str) -> dict:
        tenant_id = get_current_tenant_id()

        async with self._session_factory() as session:
            es = await self._load_session(session, tenant_id, session_id)
            if es is None:
                raise ExternalSessionNotFound("External session not found")

            parser = self._parsers.get(es.tool)
            if parser is None:
                raise ExternalSessionNotFound(f"No parser for tool {es.tool!r}")

            raw = b""
            if es.raw_key:
                with contextlib.suppress(Exception):
                    raw = self._minio.download(ARCHIVE_BUCKET, es.raw_key)
            lines = raw.decode("utf-8", errors="replace").splitlines()
            turns = parser.parse(lines)

            new_turns = turns[es.last_turn_index :]
            new_user_turns = [t for t in new_turns if t["role"] == "user"]

            if not new_user_turns:
                es.last_turn_index = len(turns)
                es.last_distilled_at = _utcnow()
                await session.commit()
                return {"new_facts": 0, "archived": False, "skipped": True}

            text = "\n".join(redact(t["text"]) for t in new_user_turns)
            memories = await self._manager.ingest(
                text,
                context={"source_session": session_id, "tool": es.tool},
                source="transcript",
            )
            for mem in memories:
                tags = list(mem.tags or [])
                changed = False
                for tag in (es.tool, "transcript"):
                    if tag not in tags:
                        tags.append(tag)
                        changed = True
                if changed:
                    await self._store.update(mem.id, MemoryUpdate(tags=tags))

            archived = False
            try:
                data = build_transcript_snapshot(es, turns, [m.id for m in memories])
                key = f"{tenant_id}/{es.tool}/{session_id}.json"
                self._minio.upload(ARCHIVE_BUCKET, key, data, content_type="application/json")
                archived = True
            except Exception:  # pragma: no cover - archive must never lose facts
                logger.exception("Transcript archive failed for %s", session_id)

            es.last_turn_index = len(turns)
            es.last_distilled_at = _utcnow()
            await session.commit()

        with contextlib.suppress(Exception):
            await event_bus.emit(
                EventType.TRANSCRIPT_DISTILLED,
                {"tool": es.tool, "external_id": session_id,
                 "tenant_id": tenant_id, "new_facts": len(memories)},
                source="transcript_distiller",
            )

        return {"new_facts": len(memories), "archived": archived, "skipped": False}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_distiller.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Lint + commit**

```bash
ruff check life_graph/services/transcript_distiller.py life_graph/core/events.py && ruff format life_graph/services/transcript_distiller.py tests/unit/test_transcript_distiller.py
git add life_graph/services/transcript_distiller.py life_graph/core/events.py tests/unit/test_transcript_distiller.py
git commit -m "feat(distiller): TranscriptDistiller — external-session facts + MinIO archive

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Ingest endpoint + DI provider + router registration

**Files:**
- Create: `life_graph/api/ingest_transcript.py`
- Modify: `life_graph/models/schemas.py` (add `TranscriptIngest`)
- Modify: `life_graph/api/dependencies.py` (add `get_transcript_distiller`)
- Modify: `life_graph/main.py` (register router)
- Test: `tests/integration/test_ingest_transcript.py`

**Interfaces:**
- Consumes: `ExternalSession` (Task 3), `PARSERS` (Task 2), `TranscriptDistiller` (Task 4), `MinIOStorage`, `async_session`, `get_redis`, `parse_redis_settings`.
- Produces:
  - `TranscriptIngest` pydantic model: `tool: str, session_id: str, source_path: str, lines: list[str]`.
  - `get_transcript_distiller() -> TranscriptDistiller`.
  - Route `POST /api/v1/ingest/transcript` → `202 {"data": {"accepted": int, "session_id": str}}`; unknown tool → `422`.

- [ ] **Step 1: Add the schema to `life_graph/models/schemas.py`**

```python
class TranscriptIngest(BaseModel):
    """A batch of raw transcript lines from one external AI-tool session."""

    tool: str
    session_id: str
    source_path: str
    lines: list[str]
```

- [ ] **Step 2: Add the DI provider to `life_graph/api/dependencies.py`**

Near `get_distillation_service` (~line 502), add:

```python
@lru_cache(maxsize=1)
def get_transcript_distiller():
    """Return the singleton transcript distiller."""
    from life_graph.extraction.transcript_parsers import PARSERS
    from life_graph.services.transcript_distiller import TranscriptDistiller
    from life_graph.storage.minio_client import MinIOStorage

    return TranscriptDistiller(
        async_session, get_memory_manager(), MinIOStorage(), get_store(), PARSERS
    )
```

- [ ] **Step 3: Write the failing integration test**

```python
# tests/integration/test_ingest_transcript.py
"""Integration tests for POST /api/v1/ingest/transcript."""
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {"X-Tenant-ID": "test-transcript-ingest"}

VALID = {
    "tool": "claude-code",
    "session_id": "sess-abc",
    "source_path": "~/.claude/projects/x/sess-abc.jsonl",
    "lines": ['{"type":"user","userType":"external","isSidechain":false,'
              '"message":{"role":"user","content":"hello world"}}'],
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


class TestIngestTranscript:
    @skip_on_db_error
    async def test_valid_batch_is_accepted(self, client: AsyncClient):
        resp = await client.post("/api/v1/ingest/transcript", json=VALID)
        assert resp.status_code != 422, resp.text
        assert resp.status_code in (200, 202, 500), resp.text
        if resp.status_code in (200, 202):
            assert resp.json()["data"]["session_id"] == "sess-abc"

    async def test_unknown_tool_rejected(self, client: AsyncClient):
        bad = {**VALID, "tool": "not-a-real-tool"}
        resp = await client.post("/api/v1/ingest/transcript", json=bad)
        assert resp.status_code == 422, resp.text

    async def test_missing_fields_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/ingest/transcript", json={"tool": "claude-code"})
        assert resp.status_code == 422, resp.text
```

- [ ] **Step 4: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_ingest_transcript.py -v`
Expected: FAIL — 404 on the route (not registered) so the accepted-status assertion fails / unknown-tool test fails.

- [ ] **Step 5: Write the router `life_graph/api/ingest_transcript.py`**

```python
# life_graph/api/ingest_transcript.py
"""Ingest endpoint for external AI-tool transcript deltas.

Appends raw lines to a per-session MinIO staging object, upserts the
ExternalSession, and enqueues a debounced distill job.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from life_graph.api.dependencies import async_session
from life_graph.core.tenant import get_current_tenant_id
from life_graph.extraction.transcript_parsers import PARSERS
from life_graph.models.db import ExternalSession, _utcnow
from life_graph.models.schemas import TranscriptIngest
from life_graph.services.transcript_distiller import ARCHIVE_BUCKET
from life_graph.storage.minio_client import MinIOStorage
from life_graph.storage.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])

DISTILL_JOB = "life_graph.workers.distill_transcript.distill_transcript"


@router.post("/transcript", status_code=202)
async def ingest_transcript(payload: TranscriptIngest) -> dict:
    if payload.tool not in PARSERS:
        raise HTTPException(status_code=422, detail=f"Unknown tool: {payload.tool}")

    tenant_id = get_current_tenant_id()
    minio = MinIOStorage()

    async with async_session() as session:
        rows = await session.execute(
            select(ExternalSession).where(
                ExternalSession.tenant_id == tenant_id,
                ExternalSession.tool == payload.tool,
                ExternalSession.external_id == payload.session_id,
            )
        )
        es = rows.scalars().first()
        if es is None:
            es = ExternalSession(
                tenant_id=tenant_id, tool=payload.tool,
                external_id=payload.session_id, source_path=payload.source_path,
                raw_key=f"staging/{tenant_id}/{payload.tool}/{payload.session_id}.ndjson",
            )
            session.add(es)
        else:
            es.source_path = payload.source_path
            es.updated_at = _utcnow()

        # Read-append-write the raw staging object (sequential per session).
        existing = b""
        try:
            existing = minio.download(ARCHIVE_BUCKET, es.raw_key)
        except Exception:
            existing = b""
        appended = existing + ("".join(line + "\n" for line in payload.lines)).encode("utf-8")
        minio.upload(ARCHIVE_BUCKET, es.raw_key, appended, content_type="application/x-ndjson")
        es.line_count = (es.line_count or 0) + len(payload.lines)

        await session.commit()

    # Debounced enqueue: one job per session per short window.
    should_enqueue = True
    redis = get_redis()
    if redis is not None:
        try:
            key = f"distill:transcript:{tenant_id}:{payload.session_id}"
            should_enqueue = bool(await redis.set(key, "1", nx=True, ex=60))
        except Exception:  # pragma: no cover - fail open
            should_enqueue = True

    if should_enqueue:
        try:
            from arq import create_pool

            from life_graph.workers.settings import parse_redis_settings

            pool = await create_pool(parse_redis_settings())
            await pool.enqueue_job(DISTILL_JOB, payload.session_id, tenant_id)
        except Exception:  # pragma: no cover - enqueue best-effort
            logger.exception("Failed to enqueue distill_transcript for %s", payload.session_id)

    return {"data": {"accepted": len(payload.lines), "session_id": payload.session_id}}
```

- [ ] **Step 6: Register the router in `life_graph/main.py`**

Find where other routers are included (search `include_router`) and add alongside them:

```python
from life_graph.api import ingest_transcript  # near the other api router imports

app.include_router(ingest_transcript.router)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_ingest_transcript.py -v`
Expected: PASS (3 passed). The unknown-tool and missing-field cases return `422`; the valid case returns `202`/`500` (never `422`).

- [ ] **Step 8: Lint + commit**

```bash
ruff check life_graph/api/ingest_transcript.py life_graph/models/schemas.py life_graph/api/dependencies.py life_graph/main.py && ruff format life_graph/api/ingest_transcript.py tests/integration/test_ingest_transcript.py
git add life_graph/api/ingest_transcript.py life_graph/models/schemas.py life_graph/api/dependencies.py life_graph/main.py tests/integration/test_ingest_transcript.py
git commit -m "feat(api): POST /ingest/transcript — stage raw + debounced distill enqueue

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: ARQ distill_transcript job

**Files:**
- Create: `life_graph/workers/distill_transcript.py`
- Modify: `life_graph/workers/settings.py` (register the function)
- Test: `tests/unit/test_distill_transcript_job.py`

**Interfaces:**
- Consumes: `get_transcript_distiller` (Task 5), `set_tenant_context`.
- Produces: `distill_transcript(ctx, session_id: str, tenant_id: str) -> dict`; constant `DISTILL_TRANSCRIPT_JOB = "life_graph.workers.distill_transcript.distill_transcript"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_distill_transcript_job.py
"""Unit test for the distill_transcript ARQ job wiring."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.workers import distill_transcript as job


@pytest.mark.asyncio
async def test_job_sets_tenant_and_calls_distiller(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        job, "set_tenant_context",
        lambda tid, actor: calls.update(tenant=tid, actor=actor),
    )
    distiller = MagicMock()
    distiller.distill = AsyncMock(return_value={"new_facts": 3})
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_transcript_distiller", lambda: distiller
    )

    result = await job.distill_transcript({}, "sess-1", "personal")

    assert result == {"new_facts": 3}
    assert calls["tenant"] == "personal"
    distiller.distill.assert_awaited_once_with("sess-1")


def test_job_name_constant_matches_dotted_path():
    assert job.DISTILL_TRANSCRIPT_JOB == "life_graph.workers.distill_transcript.distill_transcript"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_distill_transcript_job.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.workers.distill_transcript`.

- [ ] **Step 3: Write the job**

```python
# life_graph/workers/distill_transcript.py
"""ARQ job: distill one external transcript session for one tenant.

Mirrors distill_conversation — set tenant context, build the service from DI,
run it. Backfill throttling is emergent (worker concurrency + ingest debounce
+ ResilientLLM free-model cooldowns), so no dedicated rate limiter here.
"""
from __future__ import annotations

import logging

from life_graph.core.tenant import set_tenant_context

logger = logging.getLogger(__name__)

DISTILL_TRANSCRIPT_JOB = "life_graph.workers.distill_transcript.distill_transcript"


async def distill_transcript(ctx: dict, session_id: str, tenant_id: str) -> dict:
    """Distill a single external session for one tenant."""
    set_tenant_context(tenant_id, "system")

    from life_graph.api.dependencies import get_transcript_distiller

    distiller = get_transcript_distiller()
    result = await distiller.distill(session_id)
    logger.info("Distilled transcript %s: %s", session_id, result)
    return result
```

- [ ] **Step 4: Register the function in `life_graph/workers/settings.py`**

In the `functions = [...]` list, after `"life_graph.workers.distill.distill_idle_conversations",` add:

```python
        "life_graph.workers.distill_transcript.distill_transcript",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_distill_transcript_job.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Verify the enqueue-name guard test still passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_arq_enqueue_names.py -v`
Expected: PASS — the repo-wide scan finds `DISTILL_JOB`/`distill_transcript` registered in `WorkerSettings.functions`.

- [ ] **Step 7: Lint + commit**

```bash
ruff check life_graph/workers/distill_transcript.py life_graph/workers/settings.py && ruff format life_graph/workers/distill_transcript.py tests/unit/test_distill_transcript_job.py
git add life_graph/workers/distill_transcript.py life_graph/workers/settings.py tests/unit/test_distill_transcript_job.py
git commit -m "feat(workers): distill_transcript ARQ job + registration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Local uploader

**Files:**
- Create: `scripts/transcript_uploader.py`
- Create: `scripts/run_transcript_uploader.bat`
- Modify: `.env.example` (document uploader variables, names only)
- Test: `tests/unit/test_transcript_uploader.py`

**Interfaces:**
- Consumes: the endpoint contract from Task 5 (`POST /api/v1/ingest/transcript`, body `{tool, session_id, source_path, lines}`).
- Produces (pure, testable helpers):
  - `new_lines(data: bytes, offset: int) -> tuple[list[str], int]` — returns complete lines past `offset` and the new offset (byte position after the last complete line). If `len(data) < offset` (truncation), treats offset as 0.
  - `batched(seq: list, size: int) -> Iterator[list]`.
  - `session_id_for(path) -> str` — the file stem.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_transcript_uploader.py
"""Unit tests for the local transcript uploader's pure helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "transcript_uploader",
    Path(__file__).parent.parent.parent / "scripts" / "transcript_uploader.py",
)
up = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(up)


def test_new_lines_from_zero():
    data = b'{"a":1}\n{"b":2}\n'
    lines, offset = up.new_lines(data, 0)
    assert lines == ['{"a":1}', '{"b":2}']
    assert offset == len(data)


def test_new_lines_holds_back_partial_trailing_line():
    data = b'{"a":1}\n{"b":2}\n{"partial'
    lines, offset = up.new_lines(data, 0)
    assert lines == ['{"a":1}', '{"b":2}']
    # offset stops after the last complete newline, not at EOF.
    assert offset == len(b'{"a":1}\n{"b":2}\n')


def test_new_lines_resumes_from_offset():
    data = b'{"a":1}\n{"b":2}\n'
    start = len(b'{"a":1}\n')
    lines, offset = up.new_lines(data, start)
    assert lines == ['{"b":2}']
    assert offset == len(data)


def test_new_lines_truncation_resets():
    data = b'{"a":1}\n'
    lines, offset = up.new_lines(data, 9999)  # offset past EOF → treat as reset
    assert lines == ['{"a":1}']
    assert offset == len(data)


def test_batched():
    assert list(up.batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_session_id_for():
    assert up.session_id_for("/x/y/5db24295-1788.jsonl") == "5db24295-1788"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_uploader.py -v`
Expected: FAIL — file `scripts/transcript_uploader.py` does not exist.

- [ ] **Step 3: Write `scripts/transcript_uploader.py`**

```python
# scripts/transcript_uploader.py
"""Ship new Claude Code transcript bytes to Life Graph (thin, resumable).

Run periodically via Task Scheduler (see run_transcript_uploader.bat). Config
from %USERPROFILE%\\.life_graph_uploader.json; per-file byte offsets persisted
in %USERPROFILE%\\.life_graph_uploader_state.json. Stdlib only.
"""
from __future__ import annotations

import glob
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Iterator

CONFIG_PATH = Path(os.path.expanduser("~")) / ".life_graph_uploader.json"
STATE_PATH = Path(os.path.expanduser("~")) / ".life_graph_uploader_state.json"


def new_lines(data: bytes, offset: int) -> tuple[list[str], int]:
    """Return complete lines past ``offset`` and the byte offset after them."""
    if offset > len(data):  # truncation / rotation → re-read from the top
        offset = 0
    chunk = data[offset:]
    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:
        return [], offset  # no complete line yet
    complete = chunk[: last_nl + 1]
    text = complete.decode("utf-8", errors="replace")
    lines = [ln for ln in text.split("\n") if ln != ""]
    return lines, offset + len(complete)


def batched(seq: list, size: int) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def session_id_for(path: str) -> str:
    return Path(path).stem


def _load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _post(cfg: dict, tool: str, session_id: str, source_path: str, lines: list[str]) -> bool:
    body = json.dumps(
        {"tool": tool, "session_id": session_id, "source_path": source_path, "lines": lines}
    ).encode("utf-8")
    req = urllib.request.Request(
        cfg["backend_url"].rstrip("/") + "/api/v1/ingest/transcript",
        data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
            "X-Tenant-ID": cfg.get("tenant_id", "personal"),
            "CF-Access-Client-Id": cfg.get("cf_access_client_id", ""),
            "CF-Access-Client-Secret": cfg.get("cf_access_client_secret", ""),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 - keep going with other files
        print(f"  ! POST failed for {session_id}: {exc}")
        return False


def main() -> None:
    cfg = _load_json(CONFIG_PATH, {})
    if not cfg.get("backend_url"):
        raise SystemExit(f"Missing config at {CONFIG_PATH}")
    state = _load_json(STATE_PATH, {})
    batch_lines = int(cfg.get("batch_lines", 500))

    for root in cfg.get("roots", []):
        tool = root["tool"]
        base = os.path.expanduser(root["dir"])
        pattern = os.path.join(base, root.get("glob", "**/*.jsonl"))
        for path in glob.glob(pattern, recursive=True):
            size = os.path.getsize(path)
            entry = state.get(path, {"offset": 0})
            if size <= entry["offset"]:
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            lines, new_offset = new_lines(data, entry["offset"])
            if not lines:
                continue
            sid = session_id_for(path)
            ok = True
            for batch in batched(lines, batch_lines):
                if not _post(cfg, tool, sid, path, batch):
                    ok = False
                    break
            if ok:
                state[path] = {"offset": new_offset, "session_id": sid}
                STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
                print(f"  ✓ {sid}: shipped {len(lines)} lines")
            time.sleep(0.2)  # gentle during backfill


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `scripts/run_transcript_uploader.bat`**

```bat
@echo off
REM Scheduled runner for the Life Graph transcript uploader.
REM Register with Task Scheduler to run every 15 minutes.
"C:\Python314\python.exe" "%~dp0transcript_uploader.py" >> "%USERPROFILE%\.life_graph_uploader.log" 2>&1
```

- [ ] **Step 5: Document variables in `.env.example`**

Append (names only — the uploader reads a local JSON, but list the CF/API vars so operators know what's needed):

```bash
# --- Local transcript uploader (scripts/transcript_uploader.py) ---
# Configured via %USERPROFILE%\.life_graph_uploader.json, not env, but it needs:
#   backend_url, api_key (LIFE_GRAPH_API_KEY), tenant_id,
#   cf_access_client_id, cf_access_client_secret  (Cloudflare Access service token)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_uploader.py -v`
Expected: PASS (6 passed).

- [ ] **Step 7: Lint + commit**

```bash
ruff check scripts/transcript_uploader.py && ruff format scripts/transcript_uploader.py tests/unit/test_transcript_uploader.py
git add scripts/transcript_uploader.py scripts/run_transcript_uploader.bat .env.example tests/unit/test_transcript_uploader.py
git commit -m "feat(uploader): local Claude Code transcript uploader + Task Scheduler bat

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] **Full unit suite green:** `/c/Python314/python.exe -m pytest tests/unit/ -v` — all pass (new tests + no regressions).
- [ ] **New integration test green** (or skips on no-DB): `/c/Python314/python.exe -m pytest tests/integration/test_ingest_transcript.py -v`.
- [ ] **Single alembic head:** `/c/Python314/python.exe -m alembic heads` → one head `030`.
- [ ] **Lint clean:** `ruff check life_graph/ scripts/` → no new errors in created/modified files.
- [ ] **Deploy prerequisite recorded:** the Cloudflare Access service token (Zero Trust → Access → Service Auth) + an Access policy admitting it on `/api/v1/ingest/*`, plus the `transcripts` MinIO bucket (auto-created by `upload`'s `ensure_bucket`). Populate `%USERPROFILE%\.life_graph_uploader.json` on the Windows box, then run `scripts/transcript_uploader.py` once for the full 808-session backfill.

---

## Self-Review notes (author)

- **Spec coverage:** uploader (T7), ingest endpoint (T5), parser (T2), redactor (T1), distiller+archive (T4), ExternalSession+migration (T3), ARQ job+throttle (T6), CF service-token prereq (final checklist). All spec sections map to a task.
- **Correction vs spec:** `MinIOStorage.download` already exists — no addition needed (used directly in T4/T5).
- **Type consistency:** `Turn` keys (`role`/`text`/`ts`), `ExternalSession` fields (`raw_key`, `last_turn_index`, `external_id`, `tool`), the job name constant, and the `{new_facts, archived, skipped}` return dict are used identically across T2–T7.
- **Marker semantics:** turn-index (`last_turn_index`), not timestamp, so future Codex/Antigravity parsers reuse the distiller unchanged.
