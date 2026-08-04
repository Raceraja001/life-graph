# External-AI Transcript Distillation (v1: Claude Code) — Design

**Goal:** Distill the user's local AI coding-agent transcripts into Life Graph — harvesting durable facts/preferences/decisions into (pending, deduped) memories and archiving the raw thread to MinIO — starting with Claude Code, with a full one-time backfill of existing sessions plus ongoing go-forward sync.

**Status:** Approved design (Approach A — thin local uploader, server-side brains). Ready for implementation plan.

## Architecture

A **thin local uploader** on the Windows machine ships raw transcript deltas to the VM; **all parsing, redaction, extraction, and archiving happen server-side**, reusing the existing `MemoryManager.ingest` (extract + dedup) and `MinIOStorage` (archive). A pluggable `TranscriptParser` interface means ChatGPT Codex and Antigravity slot in later without touching the uploader or the distiller.

The core insight: the transcripts live on the user's laptop, but the distillation intelligence lives on the remote backend. The only thing that must run locally is a dumb, resumable file-tailer that POSTs new bytes upstream. Everything else reuses machinery that already exists for the internal chat distiller (`ConversationDistiller`).

**Data flow:**
```
Windows Task Scheduler
  └─ transcript_uploader.py  (glob *.jsonl, ship bytes past last offset)
       └─ POST /api/v1/ingest/transcript  {tool, session_id, source_path, lines[]}
            ├─ upsert ExternalSession, append raw lines to staging
            └─ enqueue (debounced) distill_transcript(session_id, tenant_id)
                 └─ ARQ worker:
                      parse (Claude Code JSONL → Turn[])
                       → redact (secrets scrubbed)
                       → MemoryManager.ingest(user-turn text)  [pending, deduped]
                       → MinIOStorage.upload(redacted raw thread)  [best-effort]
                       → advance ExternalSession.last_distilled_at / offset marker
```

Backfill and go-forward are the **same code path**; the only difference is whether the uploader's per-file offset starts at 0 (backfill) or at a prior committed position (go-forward).

**Tech stack:** Python 3.11 (backend + local script share the language), FastAPI, SQLAlchemy 2.0 async, Alembic, ARQ (Redis) for the throttled job, MinIO for archive, LiteLLM/ResilientLLM under `MemoryManager` for the (rare) tier-3 extraction. Local script uses only the Python stdlib (`urllib`, `json`, `pathlib`) so it needs no venv on the laptop beyond a system Python.

## Global Constraints

- **Tenant scoping:** every DB query filters by `tenant_id`; the uploader sends `X-Tenant-ID: personal`; the worker sets tenant context via `set_tenant_context(tenant_id, "system")` (mirrors `distill_conversation`).
- **Secrets:** no secret (API key, CF service-token secret) is committed to git or printed to chat. The uploader reads its config (backend URL, API key, CF service-token pair) from a local file (`%USERPROFILE%\.life_graph_uploader.json`, gitignored) or environment; `.env.example` names variables only.
- **Redaction before both extraction and archive** — credentials never reach MinIO or become memories.
- **Commit trailer** exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **New memories flow through the dedup pipeline** (SHA-256 exact + pgvector cosine ≥ threshold) via `MemoryManager.ingest` — no bespoke insert path.
- **Test pattern:** `httpx.AsyncClient` + `ASGITransport` with tenant headers; unit tests must not need Postgres (conftest mocks pgvector); accept `500` when DB is unreachable but never `422` for valid input.

## Components

### 1. Local uploader — `scripts/transcript_uploader.py` (+ `scripts/run_transcript_uploader.bat`)

Reuses the established local-helper pattern (`scripts/keep_awake.py` + `run_keep_awake.bat` + Task Scheduler).

**Responsibility:** ship new transcript bytes; own nothing else.

**Config** (from `%USERPROFILE%\.life_graph_uploader.json`):
```json
{
  "backend_url": "https://brain.raceraja001.in",
  "api_key": "<LIFE_GRAPH_API_KEY>",
  "cf_access_client_id": "<token>.access",
  "cf_access_client_secret": "<secret>",
  "tenant_id": "personal",
  "roots": [{"tool": "claude-code", "dir": "~/.claude/projects", "glob": "**/*.jsonl"}],
  "batch_lines": 500
}
```

**State file** `%USERPROFILE%\.life_graph_uploader_state.json`:
```json
{ "<abs-file-path>": {"offset": 12345, "session_id": "<uuid>"} }
```

**Algorithm (each run):**
1. For each configured root, glob files.
2. For each file: `size = os.path.getsize(f)`. If `size <= state.offset`, skip (nothing new; also handles truncation/rotation defensively — if `size < offset`, reset offset to 0 and re-ship, since Claude Code files are append-only so this is rare).
3. Open the file, `seek(offset)`, read to EOF. **Trim to the last `\n`** — never ship a partial trailing line (a live session may be mid-append). `new_bytes_end = offset + len(text_up_to_last_newline)`.
4. Split into lines; batch into groups of `batch_lines`. POST each batch to `/api/v1/ingest/transcript` with `{tool, session_id, source_path, lines}`. `session_id` = the file's stem (Claude Code names files `<session-uuid>.jsonl`).
5. On HTTP `202`/`200` for all batches of a file, commit `state.offset = new_bytes_end`. On any non-2xx or network error, **do not advance** that file's offset (retry next run); log and continue with other files.
6. Sleep briefly between files during backfill to avoid hammering (config-free, e.g. 200 ms).

**Auth headers on every request:** `Authorization: Bearer <api_key>`, `X-Tenant-ID: <tenant_id>`, `CF-Access-Client-Id`, `CF-Access-Client-Secret`.

**Idempotency/resumability:** offset only advances on success; the server also dedups by `(session_id, line-hash/offset)` so a resend is a no-op. A crash mid-run resumes from the last committed offset.

### 2. Ingest endpoint — `POST /api/v1/ingest/transcript` (`life_graph/api/ingest_transcript.py`, or extend existing `api/ingest.py`)

**Request body** (`models/schemas.py: TranscriptIngest`):
```python
class TranscriptIngest(BaseModel):
    tool: str                 # "claude-code"
    session_id: str           # external session identifier (uuid string)
    source_path: str          # original local path, for provenance only
    lines: list[str]          # raw JSONL lines (each a JSON object string)
```

**Handler:**
1. Validate `tool` is a registered parser key (else `422`).
2. Upsert `ExternalSession` on `(tenant_id, tool, external_id=session_id)`; set/refresh `source_path`.
3. Append the raw `lines` to the session's **staging object** (see Data model): a single MinIO object per session, updated read-append-write — `existing = minio.download(bucket, raw_key)` (empty if absent) → `minio.upload(bucket, raw_key, existing + b"".join(l+"\n" for l in lines))`. This needs a small **`MinIOStorage.download(bucket, key) -> bytes`** addition (wraps the minio client's `get_object`; generally useful). Safe without locking in the single-user case because the uploader ships a session's batches sequentially in one run; a Redis per-session guard can be added later if ever multi-writer. Update `line_count`.
4. Enqueue **debounced** `distill_transcript(session_id, tenant_id)` — debounce by only enqueuing if no undrained job exists for this session (a Redis `SET NX` guard keyed `distill:transcript:<tenant>:<session>` with a short TTL), so a burst of batches during backfill collapses to few jobs.
5. Return `202 {"accepted": len(lines), "session_id": ...}`.

Tenant from `X-Tenant-ID`; auth from the standard Bearer middleware (already enforced globally).

### 3. Parser interface — `life_graph/extraction/transcript_parsers/`

```python
# base.py
class Turn(TypedDict):
    role: str            # "user" | "assistant"
    text: str            # plain text content
    ts: str | None       # ISO8601 timestamp if available

class TranscriptParser(Protocol):
    tool: str
    def parse(self, lines: Iterable[str]) -> list[Turn]: ...

PARSERS: dict[str, TranscriptParser]   # {"claude-code": ClaudeCodeParser()}
```

**`claude_code.py`** — grounded in the real on-disk schema (verified against live files). Each JSONL line is an object with a top-level `type`:

| `type` | Keep? | Notes |
|---|---|---|
| `user` | **yes, conditionally** | `message.role=="user"`. `message.content` is `str` (real typed prompt) OR `list` (tool_result / image blocks). |
| `assistant` | no (v1) | `message.content` is a list of text/tool_use/thinking blocks. User-turns-only, matching the internal distiller. |
| `attachment`, `queue-operation`, `last-prompt`, `summary`, `system` | no | harness/meta bookkeeping. |

Rules for a `user` line to yield a `Turn`:
- `isSidechain` is falsy (skip sub-agent side threads) and `userType == "external"` (real user, not synthetic tool feedback).
- If `message.content` is a `str`, use it. If it's a `list`, concatenate only the `type=="text"` blocks whose text is genuinely user-authored; **drop `tool_result` blocks** and any block that is entirely a `<system-reminder>`/`<local-command-*>` wrapper (harness-injected). If nothing real remains, yield no turn.
- Strip leading/trailing whitespace; skip empty results.
- `ts` from the line's `timestamp`.

The parser is pure (lines → turns), so it is unit-testable against a committed fixture and carries no I/O.

### 4. Redactor — `life_graph/services/redaction.py`

```python
def redact(text: str) -> str: ...
```

Regex-based scrub applied to **each turn's text before extraction** and to the **raw thread before archive**. Patterns (case-insensitive where sensible), each replaced with `«REDACTED:<kind>»`:
- Bearer/authorization headers: `(?i)bearer\s+[A-Za-z0-9._\-]{16,}`
- OpenAI/Anthropic/OpenRouter-style keys: `sk-[A-Za-z0-9\-]{20,}`, `sk-or-[A-Za-z0-9\-]{20,}`
- AWS access keys: `AKIA[0-9A-Z]{16}`
- Google API keys: `AIza[0-9A-Za-z\-_]{35}`
- PEM private keys: `-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----`
- Env-style secret assignments: `(?im)^\s*[A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API[_-]?KEY|PRIVATE[_-]?KEY)[A-Z0-9_]*\s*[=:]\s*\S+`
- Generic long hex/base64 secrets guarded by a nearby secret-ish keyword (avoid over-redacting normal code).

Redaction is deliberately conservative-but-present: it will not catch every secret shape, but it removes the common high-risk ones before anything durable is written. Documented as best-effort in the module docstring.

### 5. Distiller — `life_graph/services/transcript_distiller.py`

Parallel to `ConversationDistiller`; **reuses its primitives** (`MemoryManager.ingest`, `MinIOStorage.upload`) rather than the `Conversation` table.

```python
ARCHIVE_BUCKET = "transcripts"

class TranscriptDistiller:
    def __init__(self, session_factory, memory_manager, minio, store, parsers): ...
    async def distill(self, session_id: str) -> dict:
        # returns {"new_facts": int, "archived": bool, "skipped": bool}
```

**`distill` logic:**
1. Resolve tenant via `get_current_tenant_id()`. Load `ExternalSession` by `(tenant_id, external_id=session_id)`; raise `ExternalSessionNotFound` if missing/foreign-tenant.
2. Load the session's raw NDJSON from staging (all lines seen so far).
3. `turns = PARSERS[session.tool].parse(lines)`.
4. **New user turns since marker:** the parser preserves order; the distiller tracks progress by **turn count** (`session.last_turn_index`) — new user-turns are those with index `> last_turn_index`. (Turn-count marker is robust to missing timestamps; Claude timestamps exist but Codex/Antigravity may differ.)
5. If no new user turns: advance markers, `return {"skipped": True, "new_facts": 0, "archived": False}` (mirrors the internal distiller's no-op-still-advances behavior so a debounce race can't loop forever).
6. **Tier 1 (facts):** `text = "\n".join(redact(t["text"]) for t in new_user_turns)`; `memories = await manager.ingest(text, context={"source_session": session_id, "tool": session.tool}, source="transcript")`. Tag each memory with the tool name (`"claude-code"`) and `"transcript"` via `store.update`, matching the internal distiller's tag-append pattern.
7. **Tier 2 (archive, best-effort):** build a redacted snapshot (all turns, redacted) → `minio.upload("transcripts", f"{tenant_id}/{tool}/{session_id}.json", data, content_type="application/json")`. Never let an archive failure lose facts (try/except, log).
8. Advance `session.last_turn_index = len(turns)`, `session.last_distilled_at = _utcnow()`; commit.
9. Best-effort emit a `TRANSCRIPT_DISTILLED` event (new `EventType`) for WebSocket/analytics; suppress all exceptions.

### 6. Data model — `ExternalSession` (`models/db.py` + Alembic migration `030_external_sessions.py`)

```python
class ExternalSession(Base):
    __tablename__ = "external_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(index=True)
    tool: Mapped[str]                              # "claude-code"
    external_id: Mapped[str]                        # session uuid string
    source_path: Mapped[str | None]
    raw_key: Mapped[str | None]                     # MinIO key of appended raw NDJSON staging object
    line_count: Mapped[int] = mapped_column(default=0)     # raw lines ingested so far
    last_turn_index: Mapped[int] = mapped_column(default=0) # distill progress marker (turns)
    last_distilled_at: Mapped[datetime | None]
    created_at / updated_at
    __table_args__ = (UniqueConstraint("tenant_id", "tool", "external_id"),)
```

Migration includes `tenant_id` and the unique constraint. Raw staging lives in one MinIO object per session (`raw_key = staging/<tenant>/<tool>/<session>.ndjson`), updated read-append-write (§Component 2.3), and *is* the source the distiller parses + the basis for the redacted archive. Sessions are bounded in size, so read-append-write is cheap.

### 7. ARQ job + throttling — `life_graph/workers/distill_transcript.py`

```python
DISTILL_TRANSCRIPT_JOB = "life_graph.workers.distill_transcript.distill_transcript"
async def distill_transcript(ctx, session_id: str, tenant_id: str) -> dict:
    set_tenant_context(tenant_id, "system")
    from life_graph.api.dependencies import get_transcript_distiller
    return await get_transcript_distiller().distill(session_id)
```

Registered in `workers/settings.py` `functions`. **Throttling for the 808-session backfill** is emergent, not bespoke: worker concurrency is bounded, the debounce guard collapses batch bursts per session, and tier-3 extraction routes through `ResilientLLM` (free-model cooldowns pace LLM calls). No dedicated rate limiter in v1 — if backfill needs to be gentler, lower worker `max_jobs`. A cron sweep is **not** needed (unlike the internal idle-distiller) because ingest enqueues directly; go-forward is driven by the uploader.

DI provider `get_transcript_distiller()` in `dependencies.py` mirrors `get_distillation_service()`:
```python
return TranscriptDistiller(async_session, get_memory_manager(), MinIOStorage(), get_store(), PARSERS)
```

## Deploy Prerequisite — Cloudflare Access service token

The API sits behind Cloudflare Access (browsers get a login redirect) and the origin firewall admits only Cloudflare IPs, so a headless uploader cannot authenticate as-is. One-time setup during deploy:
1. Create a **Cloudflare Access service token** (Zero Trust → Access → Service Auth).
2. Add an Access policy on `brain.raceraja001.in` (or scoped to `/api/v1/ingest/*`) with an **Include → Service Token** rule for that token.
3. The uploader sends `CF-Access-Client-Id` + `CF-Access-Client-Secret`; Access admits it at the edge; Caddy forwards; the backend still enforces the Bearer `LIFE_GRAPH_API_KEY`. Two independent gates preserved.

Secrets live only in the uploader's local config file and Cloudflare — never in git or chat.

## Error Handling

- **Uploader:** offset advances only on full success; partial trailing lines never shipped; per-file failures isolated; truncation defensively resets offset.
- **Endpoint:** unknown `tool` → `422`; valid input with DB down → `500` (never `422`); returns `202` before heavy work.
- **Distiller:** archive is best-effort and never blocks facts; markers advance only after a committed run; no-op runs still advance markers to prevent debounce loops; foreign-tenant/missing session → typed error.
- **Redaction:** pure function; failure is not possible on valid `str` (guarded), but extraction proceeds on redacted text only.
- **Idempotency:** at-least-once ingest + memory dedup + turn-index marker ⇒ effectively-once fact creation.

## Testing

- **Parser** (`tests/unit/test_claude_code_parser.py`): committed fixture `.jsonl` covering `user` str content, `user` list content with a `tool_result` block (dropped), a `<system-reminder>`-only user line (dropped), an `isSidechain` line (dropped), and `assistant`/`attachment` lines (dropped). Assert exact `Turn[]`.
- **Redactor** (`tests/unit/test_redaction.py`): each pattern (bearer, sk-, AKIA, AIza, PEM, env-assignment) is scrubbed; ordinary code/prose is left intact (no over-redaction).
- **Distiller** (`tests/unit/test_transcript_distiller.py`): fixture session → asserts N pending memories via a stubbed `MemoryManager.ingest`, tool tag applied, MinIO `upload` called with the redacted snapshot (MinIO mocked); no-op second run returns `skipped`.
- **Endpoint** (`tests/integration/test_ingest_transcript.py`): `httpx.AsyncClient`+`ASGITransport`, tenant header, valid body → `202` and a `distill_transcript` enqueue (ARQ pool mocked); unknown `tool` → `422`.
- **Uploader** (`tests/unit/test_transcript_uploader.py`): pure-Python offset math — partial trailing line held back, offset advances only on mocked-2xx, truncation resets, glob batching. No network.

## Scope (v1) and YAGNI boundaries

**In:** Claude Code parser; full backfill + go-forward via the uploader; server-side redaction; facts→pending-memories + MinIO archive; `ExternalSession` model; ingest endpoint; ARQ job; local uploader + `.bat` + Task Scheduler; CF Access service-token setup.

**Out (interface-ready, not built):**
- ChatGPT Codex parser (`~/.codex/sessions/**/rollout-*.jsonl`) and Antigravity parser (`state.vscdb` SQLite blobs) — add a `PARSERS` entry + fixtures later; the uploader gains a config `roots` entry with no code change.
- Assistant-turn fact harvesting (user-turns-only in v1).
- A dashboard "Sources" card / status endpoint (a `GET /api/v1/ingest/transcript/status` summary can follow).
- Any dedicated rate limiter (emergent throttling suffices for 808 sessions).
