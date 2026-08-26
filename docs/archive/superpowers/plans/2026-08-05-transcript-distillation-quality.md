# Transcript Distillation Quality Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the note-tuned extraction for Claude Code transcripts with a conversation-aware LLM extractor, so distillation produces clean decisions/preferences/project-facts/open-tasks instead of harness-text leakage and `X → Y` fragments.

**Architecture:** Harden the Claude Code parser to strip injected harness/skill/tool content and emit assistant turns as short context gists; add a conversation-aware extractor that chunks the cleaned dialogue and makes one free-model LLM call per chunk to emit categorized facts; rewire `TranscriptDistiller` to feed those facts (scoped to new turns + a small lookback) through a new `MemoryManager.store_facts` wrapper that reuses the existing embed/dedup/score/pending path.

**Tech Stack:** Python 3.11, SQLAlchemy async, `ResilientLLM` (LiteLLM over free OpenRouter), pytest (LLM mocked).

## Global Constraints

- Branch `feat/transcript-quality`, worktree `scratchpad/transcript-wt`, off `origin/master` @ `e4012b2`.
- Distilled transcript memories stay `status="pending"` (unchanged — the store-side path already sets this).
- Extractor uses the free model via `ResilientLLM` cheap tier — no new model config.
- Redaction still runs before both extraction and archive.
- Ruff line-length 100, double quotes; type-only imports under `TYPE_CHECKING` (repo enforces UP035/TC003). Run `ruff check` on modified files; do NOT bare `ruff format` large existing files (memory_manager.py, dependencies.py) — hand-match style for added lines.
- Commit trailer exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Tests from the worktree root: `cd /c/Users/admin/AppData/Local/Temp/claude/d--DevTools-Projects-life-graph/50a1450a-757b-4355-854f-3591f2d0f5be/scratchpad/transcript-wt && /c/Python314/python.exe -m pytest <path> -v`.
- Reused types/interfaces (exist — do not reimplement):
  - `life_graph.extraction.rules.ExtractedFact(content: str, fact_type: str, confidence: float, entities: list[str] = [], source_text: str = "")` — a dataclass.
  - `life_graph.core.memory_manager.MemoryManager._process_fact(fact, context, source, skip_dedup=False, trust_tier=None) -> Memory | None` (embeds, dedups, scores, sets pending).
  - `life_graph.services.resilient_llm.ResilientLLM.chat(messages, *, model=None, tier="cheap", temperature=0.3, max_tokens=1024, response_format=None, **kwargs) -> str`; provider `get_resilient_llm()`.
  - `life_graph.extraction.transcript_parsers.base.Turn` = `TypedDict("Turn", {"role": str, "text": str, "ts": str | None})`.

---

## File Structure

**Modified:**
- `life_graph/extraction/transcript_parsers/claude_code.py` — harden parser (strip injected blocks, drop injection turns, emit assistant gists).
- `life_graph/core/memory_manager.py` — add `store_facts`.
- `life_graph/services/transcript_distiller.py` — rewire to use the extractor + `store_facts`; add `resilient_llm` dependency + `CONTEXT_LOOKBACK`.
- `life_graph/api/dependencies.py` — pass `get_resilient_llm()` into `get_transcript_distiller()`.
- `tests/unit/test_claude_code_parser.py` — extend.
- `tests/unit/test_transcript_distiller.py` — update for the rewire.

**Created:**
- `life_graph/extraction/transcript_extract.py` — conversation-aware extractor.
- `tests/unit/test_transcript_extract.py` — extractor tests.

---

## Task 1: Harden the Claude Code parser

**Files:**
- Modify: `life_graph/extraction/transcript_parsers/claude_code.py`
- Test: `tests/unit/test_claude_code_parser.py` (extend)

**Interfaces:**
- Produces: `ClaudeCodeParser.parse(lines) -> list[Turn]` now (a) strips injected blocks from within user turns, (b) drops turns that are harness/skill/command injections, (c) emits `assistant` turns truncated to a ~400-char gist. `Turn.role` is `"user"` or `"assistant"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/test_claude_code_parser.py`)

```python
def test_strips_appended_system_reminder_but_keeps_prompt():
    line = (
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"Use OpenRouter free models.'
        '\\n<system-reminder>ambient context here</system-reminder>"}}'
    )
    turns = ClaudeCodeParser().parse([line])
    assert len(turns) == 1
    assert "OpenRouter free models" in turns[0]["text"]
    assert "ambient context" not in turns[0]["text"]


def test_drops_skill_body_turn():
    line = (
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"Base directory for this skill: '
        '/x/y\\n# Some Skill\\ninstructions..."}}'
    )
    assert ClaudeCodeParser().parse([line]) == []


def test_drops_system_notification_turn():
    line = (
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"[SYSTEM NOTIFICATION - NOT USER INPUT]\\n..."}}'
    )
    assert ClaudeCodeParser().parse([line]) == []


def test_emits_assistant_gist_text_only_truncated():
    long_text = "x" * 800
    line = (
        '{"type":"assistant","isSidechain":false,"message":{"role":"assistant",'
        '"content":[{"type":"thinking","thinking":"secret"},'
        '{"type":"text","text":"' + long_text + '"},'
        '{"type":"tool_use","name":"Bash","input":{}}]}}'
    )
    turns = ClaudeCodeParser().parse([line])
    assert len(turns) == 1
    assert turns[0]["role"] == "assistant"
    assert "secret" not in turns[0]["text"]
    assert len(turns[0]["text"]) <= 410  # 400 + " …"
    assert turns[0]["text"].endswith("…")
```

- [ ] **Step 2: Run to verify they fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_claude_code_parser.py -v`
Expected: the 4 new tests FAIL (reminder not stripped; skill/notification turns not dropped; assistant turns not emitted).

- [ ] **Step 3: Rewrite `claude_code.py`**

```python
# life_graph/extraction/transcript_parsers/claude_code.py
"""Parser for Claude Code session transcripts (``~/.claude/projects/**/*.jsonl``).

Each line is a JSON object with a top-level ``type``. Genuine external user
turns become ``user`` Turns with harness-injected spans stripped; assistant
turns become short context gists; tool results, sidechains, and harness/skill/
command injections are dropped.
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from life_graph.extraction.transcript_parsers.base import Turn

if TYPE_CHECKING:
    from collections.abc import Iterable

_GIST_MAX = 400

# Harness-injected spans removed from WITHIN a user turn (the real prose stays).
_INJECTED_BLOCK = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<command-name>.*?</command-name>"
    r"|<command-message>.*?</command-message>"
    r"|<command-args>.*?</command-args>"
    r"|<local-command-[a-z0-9-]+>.*?</local-command-[a-z0-9-]+>"
    r"|<ide_selection>.*?</ide_selection>"
    r"|<ide_opened_file>.*?</ide_opened_file>",
    re.DOTALL,
)

# A turn whose leading content is one of these is not the user talking.
_INJECTION_MARKERS = (
    "Base directory for this skill:",
    "(Re-invocation of",
    "Launching skill:",
    "Caveat: The messages below were generated by the user while running local commands",
    "This session is being continued from a previous conversation",
)


class ClaudeCodeParser:
    tool = "claude-code"

    def parse(self, lines: Iterable[str]) -> list[Turn]:
        turns: list[Turn] = []
        for raw in lines:
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(obj, dict) or obj.get("isSidechain"):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            typ = obj.get("type")
            if typ == "user" and msg.get("role") == "user":
                if obj.get("userType") not in (None, "external"):
                    continue
                text = self._strip_injected(self._text(msg.get("content"))).strip()
                if not text or self._is_injected(text):
                    continue
                turns.append(Turn(role="user", text=text, ts=obj.get("timestamp")))
            elif typ == "assistant" and msg.get("role") == "assistant":
                gist = self._text(msg.get("content")).strip()
                if not gist:
                    continue
                if len(gist) > _GIST_MAX:
                    gist = gist[:_GIST_MAX].rstrip() + " …"
                turns.append(Turn(role="assistant", text=gist, ts=obj.get("timestamp")))
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
    def _strip_injected(text: str) -> str:
        return _INJECTED_BLOCK.sub("", text)

    @staticmethod
    def _is_injected(text: str) -> bool:
        """True when the turn is harness/skill/command output, not user prose."""
        t = text.lstrip()
        if (
            t.startswith("<local-command-")
            or t.startswith("[SYSTEM NOTIFICATION")
            or "<task-notification>" in t[:200]
        ):
            return True
        head = t[:200]
        return any(marker in head for marker in _INJECTION_MARKERS)
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_claude_code_parser.py -v`
Expected: all tests PASS (the 4 new + the original 4 — original drops of tool_result/sidechain/attachment still hold; the original "one genuine user prompt" fixture still yields 1 user turn).

- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/extraction/transcript_parsers/claude_code.py tests/unit/test_claude_code_parser.py
ruff format life_graph/extraction/transcript_parsers/claude_code.py tests/unit/test_claude_code_parser.py
git add life_graph/extraction/transcript_parsers/claude_code.py tests/unit/test_claude_code_parser.py
git commit -m "feat(parser): strip harness/skill injections, emit assistant context gists

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Conversation-aware extractor

**Files:**
- Create: `life_graph/extraction/transcript_extract.py`
- Test: `tests/unit/test_transcript_extract.py`

**Interfaces:**
- Consumes: `Turn` (Task 1 shape), `ResilientLLM.chat` (kwargs above).
- Produces:
  - `async extract_transcript_facts(turns: list[Turn], *, resilient_llm) -> list[ExtractedFact]`
  - `_chunk(turns, max_chars=10_000, overlap=2) -> list[list[Turn]]` (module-private, tested directly)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_transcript_extract.py
"""Unit tests for the conversation-aware transcript extractor (LLM mocked)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.extraction.transcript_extract import _chunk, extract_transcript_facts


def _t(role, text):
    return {"role": role, "text": text, "ts": None}


@pytest.mark.asyncio
async def test_extracts_categorized_facts():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=json.dumps({"facts": [
        {"content": "User prefers OpenRouter free models.", "category": "preference"},
        {"content": "Client wants TPV in Cashfree and Razorpay.", "category": "fact"},
    ]}))
    turns = [_t("assistant", "which models?"), _t("user", "use openrouter free models")]
    facts = await extract_transcript_facts(turns, resilient_llm=llm)
    assert [f.content for f in facts] == [
        "User prefers OpenRouter free models.",
        "Client wants TPV in Cashfree and Razorpay.",
    ]
    assert facts[0].fact_type == "preference"
    assert facts[1].fact_type == "fact"


@pytest.mark.asyncio
async def test_all_assistant_chunk_makes_no_llm_call():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=json.dumps({"facts": []}))
    facts = await extract_transcript_facts([_t("assistant", "context only")], resilient_llm=llm)
    assert facts == []
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_chunk_failure_is_swallowed(monkeypatch):
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("all models exhausted"))
    facts = await extract_transcript_facts([_t("user", "hi")], resilient_llm=llm)
    assert facts == []  # no crash


@pytest.mark.asyncio
async def test_malformed_json_yields_no_facts():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value="not json at all")
    facts = await extract_transcript_facts([_t("user", "hi")], resilient_llm=llm)
    assert facts == []


def test_chunk_packs_to_budget_with_overlap():
    turns = [_t("user", "x" * 40) for _ in range(10)]
    chunks = _chunk(turns, max_chars=100, overlap=1)
    assert len(chunks) > 1
    # consecutive chunks share the 1-turn overlap (last of chunk N == first of N+1)
    assert chunks[0][-1] == chunks[1][0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.extraction.transcript_extract`.

- [ ] **Step 3: Write `transcript_extract.py`**

```python
# life_graph/extraction/transcript_extract.py
"""Conversation-aware fact extraction for external AI-tool transcripts.

Replaces the note-tuned rules/spaCy tiers for transcripts: chunks the cleaned
dialogue and makes one free-model LLM call per chunk to emit categorized,
standalone facts in the user's voice — decisions, preferences, project/domain
facts, and open tasks — while excluding code and AI-process meta.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from life_graph.extraction.rules import ExtractedFact

if TYPE_CHECKING:
    from life_graph.extraction.transcript_parsers.base import Turn

logger = logging.getLogger(__name__)

_MAX_CHARS = 10_000
_OVERLAP = 2

# LLM "category" -> existing ExtractedFact.fact_type value.
_CATEGORY_TO_FACT_TYPE = {
    "decision": "decision",
    "preference": "preference",
    "fact": "fact",
    "task": "intention",
}

_SYSTEM_PROMPT = """You extract durable personal-knowledge facts from a developer's \
conversation with an AI coding assistant.
The user's turns are labelled `USER:`; assistant turns (`ASSISTANT:`) are context \
only — never extract facts from them.
Emit ONLY things worth remembering long-term, in the user's voice:
1. decisions the user made
2. preferences they expressed
3. concrete project or domain facts
4. open tasks / TODOs they raised
Do NOT emit: code, commands, file paths, shell output, error text, or anything about \
the AI-assistant process itself (skills, plans, reviews, tool mechanics).
Each fact is one standalone sentence understandable without the conversation.
Respond with JSON: {"facts": [{"content": "...", "category": "decision|preference|fact|task"}]}.
If there is nothing durable, return {"facts": []}."""


def _line(turn: Turn) -> str:
    return f"{turn['role'].upper()}: {turn['text']}"


def _chunk(turns: list[Turn], max_chars: int = _MAX_CHARS, overlap: int = _OVERLAP) -> list[list[Turn]]:
    """Greedily pack turns into ~max_chars windows, carrying `overlap` trailing turns forward."""
    chunks: list[list[Turn]] = []
    cur: list[Turn] = []
    size = 0
    for t in turns:
        length = len(_line(t))
        if cur and size + length > max_chars:
            chunks.append(cur)
            cur = cur[-overlap:] if overlap else []
            size = sum(len(_line(x)) for x in cur)
        cur.append(t)
        size += length
    if cur:
        chunks.append(cur)
    return chunks


def _parse_facts(raw: str) -> list[ExtractedFact]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    out: list[ExtractedFact] = []
    for item in data.get("facts", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        category = str(item.get("category", "fact")).lower()
        out.append(
            ExtractedFact(
                content=content,
                fact_type=_CATEGORY_TO_FACT_TYPE.get(category, "fact"),
                confidence=0.7,
                entities=[],
                source_text=content,
            )
        )
    return out


async def extract_transcript_facts(turns: list[Turn], *, resilient_llm) -> list[ExtractedFact]:
    """Extract categorized facts from a cleaned dialogue via the free-model LLM."""
    facts: list[ExtractedFact] = []
    for chunk in _chunk(turns):
        if not any(t["role"] == "user" for t in chunk):
            continue  # context-only window — nothing to extract, skip the call
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(_line(t) for t in chunk)},
        ]
        try:
            raw = await resilient_llm.chat(
                messages,
                tier="cheap",
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
        except Exception:  # noqa: BLE001 - a failed chunk must not sink the session
            logger.warning("Transcript extraction chunk failed", exc_info=True)
            continue
        facts.extend(_parse_facts(raw))
    return facts
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_extract.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/extraction/transcript_extract.py tests/unit/test_transcript_extract.py
ruff format life_graph/extraction/transcript_extract.py tests/unit/test_transcript_extract.py
git add life_graph/extraction/transcript_extract.py tests/unit/test_transcript_extract.py
git commit -m "feat(extraction): conversation-aware transcript extractor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `store_facts` + rewire `TranscriptDistiller`

**Files:**
- Modify: `life_graph/core/memory_manager.py` (add `store_facts`)
- Modify: `life_graph/services/transcript_distiller.py` (rewire extraction; add `resilient_llm` dep + `CONTEXT_LOOKBACK`)
- Modify: `life_graph/api/dependencies.py` (`get_transcript_distiller` passes `get_resilient_llm()`)
- Test: `tests/unit/test_transcript_distiller.py` (update)

**Interfaces:**
- Consumes: `extract_transcript_facts` (Task 2), `ExtractedFact` (Task 1 store path).
- Produces:
  - `MemoryManager.store_facts(facts: list[ExtractedFact], context=None, source=None) -> list[Memory]`
  - `TranscriptDistiller(session_factory, memory_manager, minio, store, parsers, resilient_llm)` — new final positional param.
  - `CONTEXT_LOOKBACK = 4` (module constant in `transcript_distiller.py`).

- [ ] **Step 1: Add `store_facts` to `MemoryManager`** (after `ingest`, before `supersede` — near line ~120 in `life_graph/core/memory_manager.py`)

```python
    async def store_facts(
        self,
        facts: list[ExtractedFact],
        context: dict[str, Any] | None = None,
        source: str | None = None,
    ) -> list[Memory]:
        """Persist already-extracted facts through the store-side path (embed,
        dedup, score, pending) — bypassing the note-tuned extraction tiers.

        Used by transcript distillation, which extracts facts itself.
        """
        stored: list[Memory] = []
        for fact in facts:
            memory = await self._process_fact(fact, context, source, skip_dedup=False, trust_tier=None)
            if memory:
                stored.append(memory)
        return stored
```

Ensure `ExtractedFact` is imported in `memory_manager.py` (it already imports from `life_graph.extraction`; if `ExtractedFact` isn't imported, add `from life_graph.extraction.rules import ExtractedFact` — verify first with `grep -n "ExtractedFact" life_graph/core/memory_manager.py`).

- [ ] **Step 2: Write the failing `store_facts` test** (new file `tests/unit/test_store_facts.py`)

```python
# tests/unit/test_store_facts.py
"""Unit test for MemoryManager.store_facts (store-side path, _process_fact mocked)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction.rules import ExtractedFact


@pytest.mark.asyncio
async def test_store_facts_processes_each_fact(monkeypatch):
    mgr = MemoryManager.__new__(MemoryManager)  # bypass __init__/DI
    m1, m2 = SimpleNamespace(id=1), SimpleNamespace(id=2)
    calls = []

    async def fake_process(fact, context, source, skip_dedup=False, trust_tier=None):
        calls.append((fact.content, source))
        return {"a": m1, "b": m2, "c": None}[fact.content]

    monkeypatch.setattr(mgr, "_process_fact", fake_process)
    facts = [
        ExtractedFact(content="a", fact_type="fact", confidence=0.7),
        ExtractedFact(content="b", fact_type="decision", confidence=0.7),
        ExtractedFact(content="c", fact_type="fact", confidence=0.7),  # duplicate -> None
    ]
    stored = await mgr.store_facts(facts, context={"tool": "claude-code"}, source="transcript")
    assert stored == [m1, m2]  # None (dup) filtered out
    assert calls == [("a", "transcript"), ("b", "transcript"), ("c", "transcript")]
```

- [ ] **Step 3: Run — verify store_facts test fails then passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_store_facts.py -v`
Expected: initially FAIL (`AttributeError: store_facts`) if run before Step 1; after Step 1 it PASSES. (If you did Step 1 first, confirm it passes now.)

- [ ] **Step 4: Rewire `TranscriptDistiller`** (`life_graph/services/transcript_distiller.py`)

Add near the top (after imports):

```python
from life_graph.extraction.transcript_extract import extract_transcript_facts

CONTEXT_LOOKBACK = 4
```

Change `__init__` to accept `resilient_llm`:

```python
    def __init__(self, session_factory, memory_manager, minio, store, parsers, resilient_llm) -> None:
        self._session_factory = session_factory
        self._manager = memory_manager
        self._minio = minio
        self._store = store
        self._parsers = parsers
        self._llm = resilient_llm
```

First add `Turn` to the top-level imports of `transcript_distiller.py`:

```python
from life_graph.extraction.transcript_parsers.base import Turn
```

Then replace the Tier-1 extraction block — the two lines that build `text` and call `self._manager.ingest(...)` — with:

```python
            # Extraction window: new turns + a small lookback for context, redacted.
            start = max(0, es.last_turn_index - CONTEXT_LOOKBACK)
            window = [
                Turn(role=t["role"], text=redact(t["text"]), ts=t.get("ts"))
                for t in turns[start:]
            ]
            facts = await extract_transcript_facts(window, resilient_llm=self._llm)
            memories = await self._manager.store_facts(
                facts,
                context={"source_session": session_id, "tool": es.tool},
                source="transcript",
            )
```

Keep the existing tag-append loop over `memories`, the archive block, and the `es.last_turn_index = len(turns)` advance exactly as they are. `redact` is already imported at the top of the file — do not re-import it.

- [ ] **Step 5: Wire `resilient_llm` in `get_transcript_distiller`** (`life_graph/api/dependencies.py`)

```python
    return TranscriptDistiller(
        async_session, get_memory_manager(), MinIOStorage(), get_store(), PARSERS, get_resilient_llm()
    )
```

- [ ] **Step 6: Update the distiller tests** (`tests/unit/test_transcript_distiller.py`)

The existing tests construct `TranscriptDistiller(...)` without `resilient_llm` and mock `_manager.ingest`. Update:
- Add a `resilient_llm=MagicMock()` argument to every `TranscriptDistiller(...)` construction (the `_distiller` helper).
- Replace the `manager.ingest`-based assertions with the new path: monkeypatch the module-level `extract_transcript_facts` to return a fixed `[ExtractedFact(...)]`, and set `manager.store_facts = AsyncMock(return_value=[mem])`.

Rewrite the two tests' bodies accordingly. Example for the happy-path test:

```python
import life_graph.services.transcript_distiller as td_mod
from life_graph.extraction.rules import ExtractedFact

@pytest.mark.asyncio
async def test_distill_extracts_new_turns_and_archives(monkeypatch):
    from life_graph.services import transcript_distiller as td
    monkeypatch.setattr(td, "get_current_tenant_id", lambda: TENANT)

    sess = _session_obj()
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, manager, minio, store, session = _distiller(sess, [mem])  # _distiller now passes resilient_llm
    monkeypatch.setattr(d, "_load_session", AsyncMock(return_value=sess))

    async def fake_extract(turns, *, resilient_llm):
        # assert the raw secret was redacted before extraction
        joined = " ".join(t["text"] for t in turns)
        assert "sk-abcDEF1234567890abcdef" not in joined
        return [ExtractedFact(content="User prefers OpenRouter.", fact_type="preference", confidence=0.7)]
    monkeypatch.setattr(td_mod, "extract_transcript_facts", fake_extract)
    manager.store_facts = AsyncMock(return_value=[mem])

    result = await d.distill("sess-1")
    assert result["new_facts"] == 1
    assert result["archived"] is True
    assert minio.upload.call_args.args[0] == "transcripts"
    assert sess.last_turn_index == 2
    manager.store_facts.assert_awaited_once()
```

Update `_distiller(...)` to build `TranscriptDistiller(factory, manager, minio, store, PARSERS, MagicMock())` and to provide `manager.store_facts`. Keep `test_download_failure_does_not_regress_marker` and `test_missing_session_raises` (adjust their `_distiller` construction for the new arg). Ensure the RAW fixture the parser sees still yields 2 user turns so `last_turn_index == 2` holds; if the archive-redaction assertion depended on `store_facts`, keep it checking `minio.upload` bytes.

- [ ] **Step 7: Run the affected tests**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_transcript_distiller.py tests/unit/test_store_facts.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full unit suite (no regressions)**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -q`
Expected: all pass (the new/updated tests + no regressions elsewhere).

- [ ] **Step 9: Lint + commit**

```bash
ruff check life_graph/core/memory_manager.py life_graph/services/transcript_distiller.py life_graph/api/dependencies.py tests/unit/test_store_facts.py tests/unit/test_transcript_distiller.py
git add life_graph/core/memory_manager.py life_graph/services/transcript_distiller.py life_graph/api/dependencies.py tests/unit/test_store_facts.py tests/unit/test_transcript_distiller.py
git commit -m "feat(distiller): use conversation-aware extractor + store_facts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] **Full unit suite green:** `/c/Python314/python.exe -m pytest tests/unit/ -q`.
- [ ] **Lint clean** on all created/modified files: `ruff check life_graph/ tests/unit/test_transcript_extract.py`.
- [ ] **The real gate (manual, controller-run — NOT a subagent step):** deploy the branch to the VM (rebuild app+worker), then re-ship the *same 3 real sessions* from the earlier sanity check and inspect the resulting `pending` memories. Only if they read as clean decisions/preferences/facts/tasks — no harness/skill text, no code, no `X → Y` fragments — merge and run the 808-session backfill. If still noisy, iterate on the extractor prompt (Task 2) before backfilling.

---

## Self-Review notes (author)

- **Spec coverage:** parser hardening (T1), conversation extractor + chunking (T2), `store_facts` + distiller rewire + scoped window + `resilient_llm` wiring (T3), manual re-test gate (final). All spec sections map to a task.
- **Type consistency:** `Turn` dict keys (`role`/`text`/`ts`), `ExtractedFact(content, fact_type, confidence, entities, source_text)`, `extract_transcript_facts(turns, *, resilient_llm)`, `store_facts(facts, context, source)`, `TranscriptDistiller(..., resilient_llm)`, `CONTEXT_LOOKBACK=4` used identically across tasks.
- **Category→fact_type mapping** (`task→intention`, others identity) is defined once in T2 and not re-derived elsewhere.
- **No re-extraction of whole session:** T3 scopes the window to `turns[last_turn_index - 4:]`; dedup collapses the small overlap.
