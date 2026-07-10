# AI Engine — Improvement Roadmap

> **Purpose**: Each improvement below is self-contained. Pick any item, read it, and implement it without needing additional context.
>
> **Rules**:
> - Fix one issue per commit. Use conventional commits: `feat:` / `fix:` / `refactor:`
> - Run tests after each change to verify nothing breaks
> - Mark `[x]` when done, add the commit SHA
>
> **Priority**: P0 = critical gaps, P1 = high-value features, P2 = quality improvements, P3 = nice-to-have

---

## P0-1: Conversation Memory — Chat Has No History

- **Status**: `[ ]`
- **Files**: `app/api/chat.py`, `app/agent/orchestrator.py`
- **Risk**: Every chat request is stateless — the AI forgets everything between messages

**Problem**:
The `/v1/generate` endpoint receives `messages` from the frontend but has no server-side conversation storage. If the frontend loses state (page refresh, tab close), the entire conversation is gone. There's no way to:
- Resume a conversation
- Review past conversations
- Let agents reference previous discussions

**Fix**:
1. Create a `conversations` table in PostgreSQL:
   ```sql
   CREATE TABLE ai_conversations (
     id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
     org_id TEXT NOT NULL,
     user_id TEXT,
     title TEXT,
     persona_id TEXT,
     model TEXT,
     message_count INT DEFAULT 0,
     created_at TIMESTAMPTZ DEFAULT NOW(),
     updated_at TIMESTAMPTZ DEFAULT NOW()
   );
   
   CREATE TABLE ai_messages (
     id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
     conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
     role TEXT NOT NULL,  -- 'user', 'assistant', 'system', 'tool'
     content TEXT,
     tool_calls JSONB,
     tool_call_id TEXT,
     tokens_used INT,
     model TEXT,
     created_at TIMESTAMPTZ DEFAULT NOW()
   );
   
   CREATE INDEX idx_conversations_org ON ai_conversations(org_id);
   CREATE INDEX idx_messages_conv ON ai_messages(conversation_id);
   ```

2. Add new file `app/storage/conversations.py`:
   ```python
   class ConversationStore:
       async def create(org_id, user_id, persona_id=None) -> str
       async def get_messages(conversation_id, limit=50) -> list[dict]
       async def add_message(conversation_id, role, content, tool_calls=None) -> str
       async def list_conversations(org_id, user_id=None, limit=20) -> list[dict]
       async def delete(conversation_id, org_id) -> bool
       async def update_title(conversation_id, title) -> None
   ```

3. Modify `/v1/generate` to accept optional `conversation_id`:
   - If provided → load history from DB, append new message
   - If not → create new conversation, return `conversation_id` in first SSE event
   - After assistant response → save assistant message to DB

4. Add new API endpoints:
   - `GET /v1/conversations` — list user's conversations
   - `GET /v1/conversations/{id}` — get conversation with messages
   - `DELETE /v1/conversations/{id}` — delete conversation
   - `PATCH /v1/conversations/{id}` — rename conversation

**Verification**: Start a chat, refresh the page, resume the same conversation by ID. Messages should persist.

---

## P0-2: Auto-Title Generation for Conversations

- **Status**: `[ ]`
- **Files**: `app/api/chat.py` (after P0-1 is done)
- **Depends on**: P0-1

**Problem**:
Once conversations are stored, they need meaningful titles. Users shouldn't have to name them manually.

**Fix**:
After the first assistant response in a new conversation, generate a title:

```python
async def _generate_title(user_message: str, assistant_response: str) -> str:
    response = await litellm.acompletion(
        model="gemini/gemini-2.5-flash",
        messages=[{
            "role": "user",
            "content": f"Generate a short title (max 6 words) for this conversation:\n"
                       f"User: {user_message[:200]}\n"
                       f"Assistant: {assistant_response[:200]}\n"
                       f"Title:"
        }],
        temperature=0.3,
        max_tokens=20,
    )
    return response.choices[0].message.content.strip().strip('"')
```

- Run this as a background task (don't block the response stream)
- Use `asyncio.create_task()` after the first exchange
- Fallback: first 6 words of user's message if LLM call fails

---

## P0-3: Token Usage Tracking & Cost Monitoring

- **Status**: `[ ]`
- **Files**: `app/agent/orchestrator.py`, `app/llm/router.py`
- **Risk**: No visibility into API costs — could run up unexpected bills

**Problem**:
The orchestrator emits `usage` events in SSE but doesn't persist them. There's no way to track total tokens consumed per org/user, monitor daily/monthly API costs, or set usage alerts.

**Fix**:
1. Create a usage tracking table:
   ```sql
   CREATE TABLE ai_usage_logs (
     id SERIAL PRIMARY KEY,
     org_id TEXT NOT NULL,
     user_id TEXT,
     conversation_id TEXT,
     model TEXT NOT NULL,
     prompt_tokens INT DEFAULT 0,
     completion_tokens INT DEFAULT 0,
     total_tokens INT DEFAULT 0,
     estimated_cost_usd NUMERIC(10,6) DEFAULT 0,
     created_at TIMESTAMPTZ DEFAULT NOW()
   );
   CREATE INDEX idx_usage_org_date ON ai_usage_logs(org_id, created_at);
   ```

2. Add `app/storage/usage.py` with model cost map and `log_usage()` / `get_usage_stats()` functions

3. Call `log_usage()` after each LLM call in both `orchestrator.py` and `router.py`

4. Add endpoint: `GET /v1/usage/stats?days=30`

**Verification**: Make 10 chat requests with different models. Check that `/v1/usage/stats` returns accurate token counts and cost estimates.

---

## P1-1: Streaming Error Recovery

- **Status**: `[ ]`
- **Files**: `app/agent/orchestrator.py`
- **Risk**: Mid-stream LLM failures leave users with partial responses and no recovery

**Fix**: Add retry logic (max 2 retries with exponential backoff) and model fallback (switch to gemini-2.5-flash if primary model fails). Emit `partial_error` SSE event so frontend can offer "Retry" button.

---

## P1-2: RAG Context Window Management

- **Status**: `[ ]`
- **Files**: `app/api/chat.py`
- **Risk**: Long conversations + memory injection can exceed model context limits

**Fix**: Add token counting utility (`tiktoken`). Before calling orchestrator, check total tokens. If over limit: trim oldest messages, summarize old context, or reduce memory results from 5 to 2.

---

## P1-3: Tool Result Size Limiting

- **Status**: `[ ]`
- **Files**: `app/agent/tools/registry.py`
- **Risk**: Gmail/web search results can blow the context window

**Fix**: Add `MAX_TOOL_RESULT_CHARS = 4000` truncation in `registry.execute()`. For Gmail specifically, return structured output (subject + first 500 chars) instead of full MIME-parsed body.

---

## P1-4: Structured Tool Output for Gmail

- **Status**: `[ ]`
- **Files**: `app/agent/tools/gmail.py`
- **Risk**: Raw MIME parsing returns encoding artifacts and duplicate content

**Fix**: Prefer text/plain over text/html. Strip HTML tags if only HTML available. Return structured JSON: `{from, to, subject, date, body (truncated), has_attachments}`.

---

## P1-5: Knowledge Base — File Upload Support

- **Status**: `[ ]`
- **Files**: `app/api/knowledge.py`, `app/knowledge/ingestion.py`
- **Risk**: Only accepts raw text — no PDF, DOCX, or CSV

**Fix**: Add `app/knowledge/parsers.py` with PDF (pymupdf), DOCX (python-docx), CSV support. Add `POST /v1/knowledge/upload` multipart endpoint.

---

## P2-1: Persona System — DB-Backed with CRUD

- **Status**: `[ ]`
- **Files**: `app/api/personas.py`

**Fix**: Create `ai_personas` table. Seed 6 built-in personas with `org_id = NULL`. Add CRUD endpoints. Load from DB in `chat.py` instead of hardcoded list. Each org can create custom personas.

---

## P2-2: Voice — Add Voice-to-Chat Pipeline

- **Status**: `[ ]`
- **Files**: `app/voice/stt.py`, `app/api/chat.py`

**Fix**: Create unified WebSocket at `/v1/voice/chat`: User sends audio → Deepgram STT transcribes → AgentOrchestrator generates response → ElevenLabs TTS converts to audio → stream back. Complete voice-to-voice loop in single connection.

---

## P2-3: Batch Embedding for Knowledge Ingestion

- **Status**: `[ ]`
- **Files**: `app/knowledge/ingestion.py`, `app/memory/embeddings.py`

**Fix**: Use existing `embed_batch()` instead of per-chunk `embed()`. Add `store_with_embedding()` to SimpleMemory. Expect 5-10x speedup for document ingestion.

---

## P2-4: Health Check — Add AI-Specific Diagnostics

- **Status**: `[ ]`
- **Files**: `app/api/health.py`

**Fix**: Add checks for LLM API validity, Deepgram, ElevenLabs, embedding model, Life Graph, and Tavily. Each check times out after 3 seconds. Returns `{status, latency_ms}` per service.

---

## P2-5: System Prompt Versioning

- **Status**: `[ ]`
- **Files**: `app/llm/prompts/system.md`, `app/api/chat.py`
- **Depends on**: P0-1

**Fix**: Store system prompt hash in conversation record. New conversations get current prompt. Resumed conversations use their original prompt version. Prevents personality shifts mid-conversation.

---

## P3-1: Add Request ID Tracing

- **Status**: `[ ]`
- **Files**: `app/main.py`

**Fix**: Add middleware generating UUID per request. Include in all log lines and SSE `done`/`error` events. Frontend can include in bug reports.

---

## P3-2: Tool Execution Timeout

- **Status**: `[ ]`
- **Files**: `app/agent/tools/registry.py`

**Fix**: Wrap tool execution in `asyncio.wait_for(timeout=15)`. Return JSON error on timeout instead of hanging.

---

## P3-3: Add Conversation Export

- **Status**: `[ ]`
- **Depends on**: P0-1

**Fix**: `GET /v1/conversations/{id}/export?format=markdown|json` — export conversation as Markdown or JSON.

---

## Summary — Implementation Order

| Phase | Items | Effort | Impact |
|:------|:------|:-------|:-------|
| **Week 1** | P0-1 (Conversation History), P0-2 (Auto-Title) | 2-3 days | 🔥 Core feature |
| **Week 2** | P0-3 (Usage Tracking), P1-1 (Error Recovery) | 2 days | 💰 Cost visibility + reliability |
| **Week 3** | P1-2 (Context Management), P1-3 (Tool Size Limits) | 1-2 days | 🛡️ Prevents crashes |
| **Week 4** | P1-4 (Gmail Cleanup), P1-5 (File Upload) | 2-3 days | 📄 Real document handling |
| **Week 5** | P2-1 (DB Personas), P2-2 (Voice Chat) | 2-3 days | 🎤 Premium features |
| **Week 6+** | P2-3 to P3-3 (Quality & Polish) | Ongoing | ✨ Polish |

---

*Generated: 05 Jul 2026*
*Based on: Full AI engine codebase review (37 files, ~2,745 lines)*
