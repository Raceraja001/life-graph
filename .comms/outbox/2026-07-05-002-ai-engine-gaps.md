# AI Engine Gap Analysis — 05 Jul 2026

> **Spec**: `.comms/specs/ai-engine-improvements.md` (15 items)
> **Audited**: 13 source files, ~2,486 lines of Python
> **Result**: 11 of 15 items DONE, 1 BUG found, 3 gaps to fix

---

## Verdict Per Item

| # | Item | Spec Status | Codebase Status | Verdict |
|:--|:-----|:------------|:----------------|:--------|
| P0-1 | Conversation History | Build | `storage/conversations.py` (263 lines) — full CRUD, tables auto-created | ✅ **DONE** |
| P0-2 | Auto-Title Generation | Build | `api/chat.py` `_auto_title()` — LLM-based + fallback | ✅ **DONE** |
| P0-3 | Token Usage Tracking | Build | `storage/usage.py` (196 lines) — 7 models, cost estimation, stats API | ✅ **DONE** |
| P1-1 | Streaming Error Recovery | Build | `orchestrator.py` — 2 retries, exponential backoff, fallback model | ✅ **DONE** |
| P1-2 | Context Window Mgmt | Build | `llm/context.py` (151 lines) — heuristic token counting, message trimming | ✅ **DONE** (heuristic, not tiktoken) |
| P1-3 | Tool Result Size | Build | `tools/registry.py` — 4000 char truncation, JSON-aware, 15s timeout | ✅ **DONE** |
| P1-4 | Gmail Structured Output | Build | `tools/gmail.py` (426 lines) — structured JSON, MIME handling, body truncation | ✅ **DONE** |
| P1-5 | Knowledge File Upload | Build | `knowledge/ingestion.py` — text-only splitting | ❌ **GAP: No PDF/DOCX parsers** |
| P2-1 | DB Personas | Build | `storage/personas.py` (9KB) — DB-backed, 6 built-in, org-scoped CRUD | ✅ **DONE** |
| P2-2 | Voice Chat | Build | `voice/chat.py` — Deepgram STT + ElevenLabs TTS pipeline | ✅ **DONE** |
| P2-3 | Batch Embedding | Build | `memory/embeddings.py` — `embed_batch()` exists, thread pool executor | ✅ **DONE** |
| P2-4 | Health Diagnostics | Build | `api/health.py` (106 lines) — 6 service checks, latency tracking | ⚠️ **SHALLOW** (config checks, not connectivity) |
| P2-5 | System Prompt Versioning | Build | `conversations.py` stores `system_prompt_hash` column | ✅ **DONE** (column exists) |
| P3-1 | Request ID Tracing | Build | `main.py` `RequestIdMiddleware` — X-Request-ID header | ✅ **DONE** |
| P3-2 | Tool Timeout | Build | `tools/registry.py` — 15s `asyncio.wait_for` | ✅ **DONE** |
| P3-3 | Conversation Export | Build | Not found | ❌ **GAP: No export endpoint** |

---

## 🐛 Bug Found

**File**: `app/api/chat.py` line ~131
**Issue**: `system_prompt` variable used in `trim_messages()` call BEFORE it's constructed on line ~136.
**Impact**: Potential `NameError` at runtime or stale `None` value passed to context trimming.
**Fix**: Move `trim_messages()` call to after system prompt assembly.

---

## Genuine Gaps (3 items)

### GAP 1: Knowledge File Upload (P1-5)
- **Current**: `ingestion.py` only accepts raw text strings
- **Missing**: PDF parser (pymupdf/PyPDF2), DOCX parser (python-docx), CSV parser
- **Missing**: `POST /v1/knowledge/upload` multipart file endpoint
- **Fix**: Add `knowledge/parsers.py` with file type detection + parsing, add upload endpoint to `api/knowledge.py`

### GAP 2: Conversation Export (P3-3)
- **Current**: `api/conversations.py` has list/get/delete/rename but no export
- **Missing**: `GET /v1/conversations/{id}/export?format=markdown|json`
- **Fix**: Add export endpoint to conversations router, add `export()` method to ConversationStore

### GAP 3: Health Check Depth (P2-4)
- **Current**: Checks only verify API keys exist, not connectivity
- **Missing**: Actual LLM API test call, DB pool check, embedding model load check
- **Fix**: Add real connectivity tests (tiny LLM call, DB `SELECT 1`, embedding of test string)

---

## Quality Issues Found (not in spec, but worth fixing)

| Issue | File | Severity | Notes |
|:------|:-----|:---------|:------|
| CORS `*` in production | `main.py` L47 | 🟡 Medium | Code has TODO comment, not yet restricted |
| Gmail API sync-blocking | `tools/gmail.py` | 🟡 Medium | Google API calls run synchronously on event loop |
| Sync tool handlers block | `tools/registry.py` | 🟡 Medium | Sync handlers not wrapped in `run_in_executor` |
| Token count approximate | `orchestrator.py` L138 | 🟢 Low | Increments by 1 per chunk, not actual API token count |
| Rate limit in-memory | `middleware/rate_limit.py` | 🟢 Low | No Redis, resets on restart |
| Request ID 8 chars | `main.py` | 🟢 Low | UUID[:8] has collision risk |
| No ingestion dedup | `knowledge/ingestion.py` | 🟢 Low | Re-ingesting same doc creates duplicate chunks |

---

## Recommended Fix Priority

1. **🐛 Fix chat.py bug** (5 min) — move `trim_messages()` after system prompt assembly
2. **GAP 2: Conversation export** (30 min) — smallest gap, most useful
3. **GAP 3: Health check depth** (30 min) — adds real connectivity tests
4. **GAP 1: File upload parsers** (2-3 hours) — needs external deps (pymupdf, python-docx)
5. **Quality: CORS restriction** (5 min) — use env var for allowed origins
6. **Quality: Gmail async** (30 min) — wrap API calls in `run_in_executor`

---

*Generated: 05 Jul 2026*
*Audited by: uzhavu-dev-chat (3cfaf498)*
*Source: Full codebase scan of apps/ai-engine/app/ (13 files, ~2,486 lines)*
