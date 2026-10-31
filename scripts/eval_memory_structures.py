"""Memory-structure bake-off: which way of storing memories answers best?

Feeds the synthetic test life (evals/memory_structures/test_life.json, a
fictional person, no owner data) into each memory method, asks all its
questions through the same answer model and prompt, and scores the answers by
rule. Owner decisions (2026-10-30): synthetic data only; free cloud models;
Claude writes the right answers.

    python scripts/eval_memory_structures.py run --methods Z,A [--limit 20]
    python scripts/eval_memory_structures.py report <run_dir>

Methods:
  Z    everything: all messages in the prompt (the reference, no retrieval)
  A    notes: facts extracted per message as sentences, hybrid search (meaning +
       keywords, RRF), dated lines, newest first. What Life Graph does today.
  B    fixed form: profile topics with fields, a new value replaces the old
  C    connections, growing list: typed things + aliases, ~46 starter relation
       types (one-value ones replace), new types allowed (stand-in for approval)
  D    free connections: the model names relations itself, nothing replaces
  E    summary pages per thing, written from C's connections
  AB, AC, ACE  mixes: the parts' contexts together

Every model call and embedding is cached under evals/local/bakeoff/cache, so a
re-run or a new method costs only its own new calls.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals" / "memory_structures" / "test_life.json"
OUT = ROOT / "evals" / "local" / "bakeoff"
CACHE = OUT / "cache"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_CHAT = os.environ.get("BAKEOFF_OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_EMBED = os.environ.get("BAKEOFF_EMBED_URL", "http://localhost:11434/api/embed")
EMBED_MODEL = "bge-m3"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
FALLBACK_MODELS = ["nvidia/nemotron-3.5-lightning:free"]
#: Hidden reasoning used up the token budget and returned no content (2026-10-30).
REASONING_OFF = {"enabled": False}
#: Free models allow ~20 requests a minute: one call every 3.2 s, never parallel.
MIN_INTERVAL_S = 3.2


def _api_key() -> str:
    key = os.environ.get("LIFE_GRAPH_OPENROUTER_API_KEY", "")
    if key:
        return key
    for env in (ROOT / ".env", ROOT.parent.parent / "life-graph" / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("LIFE_GRAPH_OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip()
    sys.exit("No LIFE_GRAPH_OPENROUTER_API_KEY in the environment or .env")


# ── model calls, cached ─────────────────────────────────────────────


class LLM:
    """One free cloud model, called one at a time, every answer cached by its prompt."""

    def __init__(self, model: str, parallel: int = 1) -> None:
        self.model = model
        self.local = model.startswith("ollama:")
        self.key = "" if self.local else _api_key()
        # Free cloud models: one call at a time. A local model takes a few at once.
        self.sem = asyncio.Semaphore(parallel if self.local else 1)
        self.client = httpx.AsyncClient(timeout=120.0)
        self._last = 0.0
        self.calls = 0
        self.cached = 0
        CACHE.mkdir(parents=True, exist_ok=True)
        self._path = CACHE / "llm.jsonl"
        self._cache: dict[str, str] = {}
        if self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self._cache[row["k"]] = row["v"]

    def _key(self, model: str, messages: list[dict], json_mode: bool) -> str:
        blob = json.dumps([model, messages, json_mode], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    async def chat(
        self, messages: list[dict], *, json_mode: bool = False, max_tokens: int = 700
    ) -> str:
        for model in [self.model] if self.local else [self.model, *FALLBACK_MODELS]:
            k = self._key(model, messages, json_mode)
            if k in self._cache:
                self.cached += 1
                return self._cache[k]
            async with self.sem:
                out = await (
                    self._local(model, messages, json_mode, max_tokens)
                    if self.local
                    else self._call(model, messages, json_mode, max_tokens)
                )
            if out is not None:
                self._cache[k] = out
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(
                        json.dumps({"k": k, "model": model, "v": out}, ensure_ascii=False) + "\n"
                    )
                return out
        raise RuntimeError("every model failed")

    async def _local(self, model, messages, json_mode, max_tokens) -> str | None:
        body: dict[str, Any] = {
            "model": model.removeprefix("ollama:"),
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": max_tokens},
        }
        if json_mode:
            body["format"] = "json"
        for attempt in range(4):
            try:
                r = await self.client.post(OLLAMA_CHAT, json=body, timeout=600.0)
                if r.status_code == 200:
                    text = (r.json().get("message") or {}).get("content") or ""
                    self.calls += 1
                    if text.strip():
                        return text
                else:
                    print(f"  {model}: HTTP {r.status_code} {r.text[:120]}", file=sys.stderr)
            except httpx.HTTPError as exc:
                print(f"  {model}: {exc.__class__.__name__}, retry {attempt + 1}", file=sys.stderr)
            await asyncio.sleep(5 * (attempt + 1))
        return None

    async def _call(self, model, messages, json_mode, max_tokens) -> str | None:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "reasoning": REASONING_OFF,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(6):
            wait = self._last + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            try:
                r = await self.client.post(
                    OPENROUTER, json=body, headers={"Authorization": f"Bearer {self.key}"}
                )
            except httpx.HTTPError as exc:
                print(f"  network error ({exc.__class__.__name__}), retrying", file=sys.stderr)
                await asyncio.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 200:
                data = r.json()
                try:
                    text = data["choices"][0]["message"]["content"] or ""
                except (KeyError, IndexError):
                    text = ""
                self.calls += 1
                if text.strip():
                    return text
            elif r.status_code in (429, 500, 502, 503, 504):
                print(f"  {model}: HTTP {r.status_code}, retry {attempt + 1}", file=sys.stderr)
                await asyncio.sleep(min(60, 8 * (attempt + 1)))
                continue
            else:
                print(f"  {model}: HTTP {r.status_code} {r.text[:160]}", file=sys.stderr)
                return None
        print(f"  {model}: gave up after retries", file=sys.stderr)
        return None


class Embedder:
    """bge-m3 on the local Ollama (synthetic text only), cached by text."""

    def __init__(self) -> None:
        self._path = CACHE / "emb.json"
        self._cache: dict[str, list[float]] = (
            json.loads(self._path.read_text(encoding="utf-8")) if self._path.exists() else {}
        )
        self.client = httpx.AsyncClient(timeout=120.0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        todo = [t for t in dict.fromkeys(texts) if t not in self._cache]
        for i in range(0, len(todo), 32):
            batch = todo[i : i + 32]
            r = await self.client.post(OLLAMA_EMBED, json={"model": EMBED_MODEL, "input": batch})
            r.raise_for_status()
            for t, v in zip(batch, r.json()["embeddings"], strict=True):
                self._cache[t] = v
        if todo:
            self._path.write_text(json.dumps(self._cache), encoding="utf-8")
        return [self._cache[t] for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _json(text: str) -> Any:
    """The first JSON object in a model's reply (some wrap it in prose or fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


# ── scoring ─────────────────────────────────────────────────────────

ABSTAIN = re.compile(
    r"don'?t know|do not know|don’t know|not sure|no information|not mentioned|"
    r"haven'?t (?:told|mentioned|shared)|have not (?:told|mentioned|shared)|no record|"
    r"isn'?t in|is not in|not in (?:my|the) (?:memory|notes|context)|can'?t find|cannot find|"
    r"not (?:explicitly |specifically )?(?:mentioned|provided|specified|stated|given|available|recorded)|do(?:es)? not (?:specify|say|mention|state)|"
    r"தெரியாது|தகவல் இல்லை",
    re.I,
)


def _has(alt: str, text: str) -> bool:
    alt = alt.lower()
    if len(alt) <= 3 and re.fullmatch(r"[\w+ ]+", alt):
        return re.search(rf"(?<![\w]){re.escape(alt)}(?![\w])", text) is not None
    return alt in text


def score(q: dict, answer: str) -> tuple[bool, list[str]]:
    """(passed, why not). Rules from test_life.json's "about"."""
    text = " ".join(answer.lower().split())
    bad = [t for t in q.get("must_not", []) if t.lower() in text]
    if q.get("abstain"):
        ok = bool(ABSTAIN.search(text)) and not bad
        return ok, ([] if ok else ["did not say it doesn't know"] + [f"said: {b}" for b in bad])
    missing = [" / ".join(g) for g in q.get("must", []) if not any(_has(a, text) for a in g)]
    why = [f"missing: {m}" for m in missing] + [f"said: {b}" for b in bad]
    return not why, why


# ── the shared answer step ──────────────────────────────────────────

ANSWER_SYSTEM = (
    "You answer the user's questions about their own life, using ONLY the memory notes given. "
    "Today is {today}. When a fact changed over time, give the latest unless the question asks "
    "about the past. If the notes do not contain the answer, reply exactly: I don't know. "
    "Never guess or invent. Answer in one or two short sentences, in the language of the question."
)


async def answer(llm: LLM, today: str, context: str, question: str) -> str:
    return await llm.chat(
        [
            {"role": "system", "content": ANSWER_SYSTEM.format(today=today)},
            {"role": "user", "content": f"Memory notes:\n{context}\n\nQuestion: {question}"},
        ],
        max_tokens=300,
    )


# ── methods ─────────────────────────────────────────────────────────


class Method:
    key = "?"
    name = "?"

    async def build(self, data: dict, llm: LLM, emb: Embedder) -> None:  # noqa: B027
        pass

    async def context(self, q: str, llm: LLM, emb: Embedder) -> str:
        raise NotImplementedError

    def stats(self) -> dict[str, Any]:
        return {}


class Everything(Method):
    key, name = "Z", "Everything in the prompt (reference)"

    async def build(self, data, llm, emb):
        self.text = "\n".join(f"({m['date']}) {m['text']}" for m in data["messages"])

    async def context(self, q, llm, emb):
        return self.text

    def stats(self):
        return {"context_chars": len(self.text)}


EXTRACT_NOTES = (
    "Extract lasting facts about the user from their message, as short third-person sentences "
    "('The user's wife is Priya.'). Keep names, numbers, dates and places exactly. Include "
    "decisions and plans. Skip greetings, questions to the assistant and anything the user is "
    "only unsure about ('maybe', 'thinking about'). Reply as JSON: "
    '{"facts": ["...", "..."]} (empty list if none). Message date: {date}.'
)


class Notes(Method):
    """A: Life Graph today, in miniature: extracted sentences, hybrid search, dated lines."""

    key, name = "A", "Notes + hybrid search (today)"
    TOP = 8

    async def build(self, data, llm, emb):
        self.notes: list[dict] = []

        async def one(m):
            return await llm.chat(
                [
                    {"role": "system", "content": EXTRACT_NOTES.replace("{date}", m["date"])},
                    {"role": "user", "content": m["text"]},
                ],
                json_mode=True,
                max_tokens=400,
            )

        replies = await asyncio.gather(*(one(m) for m in data["messages"]))
        for m, reply in zip(data["messages"], replies, strict=True):
            facts = (_json(reply) or {}).get("facts") or []
            for f in facts:
                if isinstance(f, str) and f.strip():
                    self.notes.append({"text": f.strip(), "date": m["date"], "src": m["id"]})
        self.vecs = await emb.embed([n["text"] for n in self.notes])
        self.df = Counter(w for n in self.notes for w in set(_words(n["text"])))

    def _keyword_rank(self, q: str) -> list[int]:
        qw = set(_words(q))
        n = len(self.notes)
        scores = []
        for i, note in enumerate(self.notes):
            tf = Counter(_words(note["text"]))
            s = sum(tf[w] * math.log(1 + n / (1 + self.df[w])) for w in qw if w in tf)
            scores.append((s, i))
        return [i for s, i in sorted(scores, reverse=True) if s > 0]

    async def context(self, q, llm, emb):
        (qv,) = await emb.embed([q])
        by_meaning = sorted(range(len(self.notes)), key=lambda i: -cosine(qv, self.vecs[i]))
        fused: dict[int, float] = defaultdict(float)
        for rank, i in enumerate(by_meaning[:40]):
            fused[i] += 1.0 / (60 + rank)
        for rank, i in enumerate(self._keyword_rank(q)[:40]):
            fused[i] += 0.5 / (60 + rank)
        top = sorted(fused, key=lambda i: -fused[i])[: self.TOP]
        top.sort(key=lambda i: self.notes[i]["date"], reverse=True)
        return "\n".join(f"({self.notes[i]['date']}) {self.notes[i]['text']}" for i in top)

    def stats(self):
        return {"notes": len(self.notes)}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w']+", text.lower()) if len(w) > 2]


# ── L: Life Graph's own pipeline (notes + owner form, 2026-10-31 plan) ──────


class LifeGraph(Method):
    """L: Life Graph's real extractor and slot rules (PYTHONPATH must point at a
    life-graph checkout): every fact is a note; slotted facts form the owner's
    form, a new value replacing the old (kept as history); Jarvis gets the form
    plus the best notes, as services/memory_context.py does."""

    key, name = "L", "Life Graph: notes + form (real code)"

    async def build(self, data, llm, emb):
        from life_graph.api.dependencies import get_extraction_pipeline

        pipeline = get_extraction_pipeline()
        # Production extracts a message the day it is said and tells the model
        # "Today is …"; here old messages are replayed, so each is told its own
        # date (else "dinner for her birthday" in February became "her birthday
        # is today", 2026-10-31).
        said_on = _dated_extraction()

        self.notes_m = Notes()
        self.notes_m.notes = []
        self.form: dict[str, dict[str, Any]] = {}
        self.slot_count = 0

        async def one(m):
            said_on.set(m["date"])
            return m, list((await pipeline.extract(m["text"], capture=True)).facts)

        # In date order, one at a time, as messages reach production.
        for msg in sorted(data["messages"], key=lambda d: (d["date"], d["id"])):
            m, facts = await one(msg)
            for f in facts:
                text = f.content.strip()
                if not text:
                    continue
                self.notes_m.notes.append({"text": text, "date": m["date"], "src": m["id"]})
                if f.slot:
                    self.slot_count += 1
                    old = self.form.get(f.slot)
                    history = list(old["history"]) if old else []
                    if old and old["text"] != text:
                        history.append(f"{old['text']} (until {m['date']})")
                    self.form[f.slot] = {"text": text, "since": m["date"], "history": history}
        self.notes_m.vecs = await emb.embed([n["text"] for n in self.notes_m.notes])
        self.notes_m.df = Counter(w for n in self.notes_m.notes for w in set(_words(n["text"])))

    async def context(self, q, llm, emb):
        form = "\n".join(
            f"[{k}] {v['text']} (since {v['since']})"
            + (f" [before: {'; '.join(v['history'])}]" if v["history"] else "")
            for k, v in sorted(self.form.items())
        )
        notes = await self.notes_m.context(q, llm, emb)
        return f"## Your form\n{form}\n\n## Notes\n{notes}"

    def stats(self):
        return {
            "notes": len(self.notes_m.notes),
            "slots": len(self.form),
            "slotted_facts": self.slot_count,
            "with_history": sum(1 for v in self.form.values() if v["history"]),
        }


# ── R: Life Graph end to end — the real store, search, judge and form ──


class _RealStore:
    """The test life stored once through Life Graph's own MemoryManager in a
    throwaway tenant (database: LIFE_GRAPH_DATABASE_URL, use the test database),
    shared by every R variant of a run. Facts come from the real extractor and
    are cached in evals/local/bakeoff/facts_<data>.json, so variants and re-runs
    store the same facts. Each memory is dated to its message; the owner is
    taken to keep every unreviewed fact that is not hedged."""

    def __init__(self) -> None:
        self.tenant = f"bakeoff_{datetime.now(UTC):%Y%m%d%H%M%S}"
        self.built = False
        self.decayed = False
        self.counts: dict[str, int] = {}

    async def build(self, data: dict) -> None:
        if self.built:
            return
        from dataclasses import asdict

        from sqlalchemy import text

        from life_graph.api.dependencies import get_extraction_pipeline, get_memory_manager
        from life_graph.core.tenant import tenant_scope
        from life_graph.extraction.rules import ExtractedFact
        from life_graph.storage.database import async_session

        cache = OUT / f"facts_{Path(data.get('_path', 'test_life')).stem}.json"
        facts: dict[str, list[dict]] = (
            json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
        )
        msgs = sorted(data["messages"], key=lambda d: (d["date"], d["id"]))
        said_on = _dated_extraction()
        pipeline = get_extraction_pipeline()
        for n, m in enumerate(msgs, 1):
            if m["id"] not in facts:
                said_on.set(m["date"])
                got = (await pipeline.extract(m["text"], capture=True)).facts
                facts[m["id"]] = [asdict(f) for f in got]
                if n % 50 == 0:
                    cache.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
        cache.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")

        from life_graph.config import settings

        # Stored as production stores (facts said together are linked); the
        # variants differ only in how Jarvis reads.
        settings.memory_links = True
        manager = get_memory_manager()
        known = set(ExtractedFact.__dataclass_fields__)
        with tenant_scope(self.tenant):
            for m in msgs:
                batch = [
                    ExtractedFact(**{k: v for k, v in f.items() if k in known})
                    for f in facts[m["id"]]
                    if (f.get("content") or "").strip()
                ]
                if not batch:
                    continue
                async with async_session() as s:
                    wall = (await s.execute(text("SELECT clock_timestamp()"))).scalar_one()
                await manager.store_facts(batch, source="capture", trust_tier="self")
                async with async_session() as s:
                    # Said on the message's day: written now, dated then.
                    await s.execute(
                        text(
                            "UPDATE memories SET updated_at = CAST(:d AS timestamptz),"
                            " created_at = CASE WHEN created_at >= :w"
                            " THEN CAST(:d AS timestamptz) ELSE created_at END,"
                            " last_accessed = CASE WHEN last_accessed >= :w"
                            " THEN CAST(:d AS timestamptz) ELSE last_accessed END"
                            " WHERE tenant_id = :t AND updated_at >= :w"
                        ),
                        {
                            "d": datetime.fromisoformat(f"{m['date']}T12:00:00+05:30"),
                            "t": self.tenant,
                            "w": wall,
                        },
                    )
                    await s.commit()
        async with async_session() as s:
            # The owner keeps what is not hedged (a stand-in for reviewing it).
            await s.execute(
                text(
                    "UPDATE memories SET status = 'active' WHERE tenant_id = :t"
                    " AND status = 'pending'"
                    " AND COALESCE(properties->>'certainty', '') <> 'hedged'"
                ),
                {"t": self.tenant},
            )
            await s.commit()
            rows = await s.execute(
                text("SELECT status, count(*) FROM memories WHERE tenant_id = :t GROUP BY 1"),
                {"t": self.tenant},
            )
            self.counts = {r[0]: r[1] for r in rows}
            links = await s.execute(
                text("SELECT count(*) FROM memory_links WHERE tenant_id = :t"), {"t": self.tenant}
            )
            self.counts["links"] = links.scalar_one()
        self.built = True

    async def decay(self, today: str) -> None:
        """The owner approves every archive the decay job would propose on *today*
        (workers/decay.py's formula, without its per-night cap)."""
        if self.decayed:
            return
        from sqlalchemy import text

        from life_graph.config import settings
        from life_graph.storage.database import async_session

        async with async_session() as s:
            res = await s.execute(
                text(
                    "UPDATE memories SET status = 'archived' WHERE tenant_id = :t"
                    " AND status = 'active' AND importance_tier <> 'critical'"
                    " AND COALESCE(properties->>'kind', '') <> 'episode'"
                    " AND importance * exp(-decay_rate * EXTRACT(EPOCH FROM ("
                    "CAST(:today AS timestamptz) - COALESCE(last_accessed, created_at)))"
                    " / 86400.0) < :th"
                ),
                {
                    "t": self.tenant,
                    "today": datetime.fromisoformat(f"{today}T12:00:00+05:30"),
                    "th": settings.decay_archive_threshold,
                },
            )
            await s.commit()
        self.counts["decay_archived"] = res.rowcount or 0
        self.decayed = True


_REAL: _RealStore | None = None
#: One question at a time through the real path: its judge calls go through
#: Life Graph's own client, outside the LLM class's limit, and 140 at once
#: locked up the shared Ollama (2026-10-31).
_REAL_GATE = asyncio.Semaphore(1)
#: Judge outcomes per variant, so a run whose judge failed cannot pass as a result.
_JUDGE: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "failed": 0})
_CURRENT = {"key": ""}


def _count_judge() -> None:
    from life_graph.services import memory_retrieval

    if getattr(memory_retrieval, "_bakeoff_counted", False):
        return
    original = memory_retrieval.judge

    async def counted(question, contents):
        out = await original(question, contents)
        tally = _JUDGE[_CURRENT["key"]]
        tally["calls"] += 1
        tally["failed"] += out is None
        return out

    memory_retrieval.judge = counted
    memory_retrieval._bakeoff_counted = True


def _dated_extraction():
    """Tell the extractor each replayed message's own date (see LifeGraph.build)."""
    import contextvars
    from datetime import date as _date

    from life_graph.extraction import llm as lg_llm

    if getattr(lg_llm, "_bakeoff_said_on", None) is not None:
        return lg_llm._bakeoff_said_on
    said_on = contextvars.ContextVar("said_on", default=None)
    original = lg_llm._user_message

    def dated(text, *, schema_in_prompt):
        msg = original(text, schema_in_prompt=schema_in_prompt)
        d = said_on.get()
        if d:
            day = _date.fromisoformat(d)
            msg = re.sub(
                r"Today is \w+ \d{4}-\d{2}-\d{2}", f"Today is {day:%A %Y-%m-%d}", msg, count=1
            )
        return msg

    lg_llm._user_message = dated
    lg_llm._bakeoff_said_on = said_on
    return said_on


class RealLifeGraph(Method):
    """R*: what Jarvis gets in production (services/memory_context.py: the form,
    then search + links + cold tier, filtered by the local relevance judge),
    with the 2026-10-31 brain steps switched on or off. Asking changes nothing:
    usage counts, used-together links and reawakening are off here, so variants
    do not leak into each other (that learning needs real use over time)."""

    def __init__(self, key, name, *, cold=False, links=False, strength=False, decay=False):
        self.key, self.name = key, name
        self.flags = {
            "memory_cold_tier": cold,
            "memory_links": links,
            "memory_strength_rank": strength,
        }
        self.decay_first = decay

    def _apply(self) -> None:
        from life_graph.config import settings

        for k, v in self.flags.items():
            setattr(settings, k, v)

    async def build(self, data, llm, emb):
        global _REAL
        if _REAL is None:
            _REAL = _RealStore()
        if _REAL.decayed and not self.decay_first:
            sys.exit("R variants without decay must run before the ones with it")
        await _REAL.build(data)
        self._apply()
        if self.decay_first:
            await _REAL.decay(data["today"])
        from life_graph.api.dependencies import get_store
        from life_graph.services import memory_context

        async def nothing(*a, **k):
            return 0

        memory_context._strengthen = nothing
        get_store().touch_many = nothing
        _count_judge()

    async def context(self, q, llm, emb):
        from life_graph.core.tenant import tenant_scope
        from life_graph.services import memory_context

        async with _REAL_GATE:
            self._apply()
            _CURRENT["key"] = self.key
            with tenant_scope(_REAL.tenant):
                return await memory_context.memory_block(_REAL.tenant, q) or ""

    def stats(self):
        return {
            "tenant": _REAL.tenant if _REAL else None,
            **(_REAL.counts if _REAL else {}),
            "judge": dict(_JUDGE[self.key]),
        }


# ── B: a fixed profile form (Memobase-style topics, free sub-fields) ──

FORM_TOPICS = [
    "basics",
    "family",
    "work",
    "projects",
    "hobbies",
    "places",
    "devices",
    "money",
    "health",
    "preferences",
    "learning",
    "plans",
    "decisions",
]
EXTRACT_FORM = (
    "You keep a profile of the user, organised by topic. Topics (use only these): "
    + ", ".join(FORM_TOPICS)
    + ". Each topic holds short fields, e.g. family.wife, family.daughter_school, work.employer, "
    "devices.phone, hobbies.cricket. Given the current profile and the user's new message (dated "
    '{date}), return the changes as JSON: {"set": [{"topic": t, "field": f, "value": v}]}. '
    "Use an existing field name when the message updates it (a new value replaces the old one). "
    "Keep names, numbers, dates exactly. Skip greetings, questions and things the user is unsure "
    "about. Empty list if nothing to change."
)


class Form(Method):
    key, name = "B", "Fixed form (profile slots)"

    async def build(self, data, llm, emb):
        self.profile: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in FORM_TOPICS}
        for m in data["messages"]:
            current = {
                t: {f: v["value"] for f, v in fs.items()} for t, fs in self.profile.items() if fs
            }
            reply = await llm.chat(
                [
                    {"role": "system", "content": EXTRACT_FORM.replace("{date}", m["date"])},
                    {
                        "role": "user",
                        "content": f"Current profile: {json.dumps(current, ensure_ascii=False)}\n\nMessage: {m['text']}",
                    },
                ],
                json_mode=True,
                max_tokens=500,
            )
            for ch in (_json(reply) or {}).get("set") or []:
                t, f, v = (
                    str(ch.get("topic", "")).lower(),
                    str(ch.get("field", "")).strip(),
                    ch.get("value"),
                )
                if t not in self.profile or not f or v in (None, ""):
                    continue
                v = str(v)
                old = self.profile[t].get(f)
                history = list(old["history"]) if old else []
                if old and old["value"] != v:
                    history.append(f"{old['value']} (until {m['date']})")
                self.profile[t][f] = {"value": v, "since": m["date"], "history": history}

    def render(self) -> str:
        lines = []
        for t, fs in self.profile.items():
            for f, v in fs.items():
                past = f" [before: {'; '.join(v['history'])}]" if v["history"] else ""
                lines.append(f"{t}.{f}: {v['value']} (since {v['since']}){past}")
        return "\n".join(lines)

    async def context(self, q, llm, emb):
        return self.render()

    def stats(self):
        return {"fields": sum(len(fs) for fs in self.profile.values())}


# ── C / D: connections between things ──────────────────────────────

#: Starter list for C: (name, one value per subject?)
RELATIONS = [
    ("name", True),
    ("nickname", False),
    ("spouse", True),
    ("child", False),
    ("parent", False),
    ("sibling", False),
    ("relative", False),
    ("friend", False),
    ("lives_in", True),
    ("hometown", True),
    ("works_at", True),
    ("job_title", True),
    ("manager", True),
    ("colleague", False),
    ("works_on", False),
    ("leads", False),
    ("role_in", True),
    ("client", False),
    ("member_of", False),
    ("studies_at", True),
    ("grade", True),
    ("teaches", True),
    ("uses", False),
    ("built_with", False),
    ("runs_on", True),
    ("owns", False),
    ("phone", True),
    ("laptop", True),
    ("camera", True),
    ("hobby", False),
    ("learning", False),
    ("visited", False),
    ("plans", False),
    ("prefers", False),
    ("avoids", False),
    ("allergic_to", False),
    ("blood_group", True),
    ("health_condition", False),
    ("birthday", True),
    ("age", True),
    ("anniversary", True),
    ("amount", True),
    ("decided", False),
    ("schedule", True),
    ("located_at", True),
    ("provider", True),
]
ENTITY_TYPES = [
    "person",
    "place",
    "organisation",
    "project",
    "thing",
    "activity",
    "event",
    "money",
    "topic",
]
EXTRACT_GRAPH = (
    "Turn the user's message (dated {date}) into connections between things. The user is the "
    'entity "self". Entity types: ' + ", ".join(ENTITY_TYPES) + ". {vocab} Reply as JSON: "
    '{"entities": [{"name": n, "type": t, "aliases": [..]}], "relations": [{"subject": '
    'entity name or self, "relation": r, "object": entity name or null, "value": text or null, '
    '"ended": true if the message says it stopped/ended}]{extra}}. Use the known entity names '
    "below when the message refers to them (including by nickname or role, e.g. 'my wife'). Keep "
    "names, numbers and dates exactly. Skip greetings, questions and things the user is unsure "
    "about."
)
VOCAB_C = (
    "Use ONLY these relations: " + ", ".join(r for r, _ in RELATIONS) + ". If none fits, add a "
    'new one to "new_relations" as {"name": n, "one_value": true|false} and use it.'
)
VOCAB_D = "Name each relation freely with a short verb phrase."


class Graph(Method):
    """C (fixed, growing relation list, one-value relations replace) or D (free relations)."""

    key, name = "C", "Connections, growing list"
    free = False

    async def build(self, data, llm, emb):
        self.vocab = {r: one for r, one in RELATIONS}
        self.new_relations: list[str] = []
        self.entities: dict[str, dict[str, Any]] = {
            "self": {"name": "self", "type": "person", "aliases": []}
        }
        self.rels: list[dict[str, Any]] = []
        for m in data["messages"]:
            known = "; ".join(
                f"{e['name']} ({e['type']}{', aka ' + ', '.join(e['aliases']) if e['aliases'] else ''})"
                for e in self.entities.values()
            )
            system = (
                EXTRACT_GRAPH.replace("{date}", m["date"])
                .replace("{vocab}", VOCAB_D if self.free else VOCAB_C)
                .replace("{extra}", "" if self.free else ', "new_relations": [..]')
            )
            reply = await llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Known entities: {known}\n\nMessage: {m['text']}"},
                ],
                json_mode=True,
                max_tokens=700,
            )
            out = _json(reply) or {}
            for nr in out.get("new_relations") or []:
                n = str(nr.get("name", "")).strip().lower().replace(" ", "_")
                if n and n not in self.vocab:
                    # Stands in for the owner's one-time approval of a new relation type.
                    self.vocab[n] = bool(nr.get("one_value"))
                    self.new_relations.append(n)
            for e in out.get("entities") or []:
                self._add_entity(e)
            for r in out.get("relations") or []:
                self._add_relation(r, m["date"])
        self.lines = [self._line(r) for r in self.rels]
        self.vecs = await emb.embed(self.lines) if self.lines else []

    def _canon(self, name: str | None) -> str | None:
        if not name:
            return None
        key = str(name).strip().lower()
        if key in ("self", "user", "me", "the user", "i"):
            return "self"
        for k, e in self.entities.items():
            if key == k or key in (a.lower() for a in e["aliases"]):
                return k
        return key

    def _add_entity(self, e: dict) -> None:
        name = str(e.get("name") or "").strip()
        if not name:
            return
        key = self._canon(name) or name.lower()
        ent = self.entities.setdefault(
            key, {"name": name, "type": str(e.get("type") or "thing"), "aliases": []}
        )
        for a in e.get("aliases") or []:
            if (
                isinstance(a, str)
                and a.strip()
                and a.lower() not in (x.lower() for x in ent["aliases"])
            ):
                ent["aliases"].append(a.strip())

    def _add_relation(self, r: dict, date: str) -> None:
        rel = str(r.get("relation") or "").strip().lower().replace(" ", "_")
        subj = self._canon(r.get("subject"))
        obj = self._canon(r.get("object"))
        value = r.get("value")
        if not rel or not subj or (obj is None and value in (None, "")):
            return
        for k in (subj, obj):
            if k and k not in self.entities:
                self.entities[k] = {"name": k, "type": "thing", "aliases": []}
        target = obj or str(value).strip().lower()
        if r.get("ended"):
            for old in self.rels:
                if (
                    old["s"] == subj
                    and old["r"] == rel
                    and old["until"] is None
                    and (old["o"] or str(old["v"]).lower()) == target
                ):
                    old["until"] = date
            return
        one_value = (not self.free) and self.vocab.get(rel, False)
        for old in self.rels:
            if old["s"] == subj and old["r"] == rel and old["until"] is None:
                same = (old["o"] or str(old["v"]).lower()) == target
                if same:
                    return  # already known
                if one_value:
                    old["until"] = date  # a one-value relation: the new value replaces it
        self.rels.append(
            {
                "s": subj,
                "r": rel,
                "o": obj,
                "v": None if obj else str(value),
                "since": date,
                "until": None,
            }
        )

    def _name(self, key: str | None) -> str:
        if key == "self":
            return "the user"
        e = self.entities.get(key or "")
        if not e:
            return str(key)
        return e["name"] + (f" (aka {', '.join(e['aliases'])})" if e["aliases"] else "")

    def _line(self, r: dict) -> str:
        obj = self._name(r["o"]) if r["o"] else r["v"]
        when = f"since {r['since']}" + (f", ENDED {r['until']}" if r["until"] else "")
        return f"{self._name(r['s'])} —{r['r']}→ {obj} ({when})"

    def _mentioned(self, q: str) -> set[str]:
        ql = q.lower()
        hits = {"self"}
        for k, e in self.entities.items():
            names = [e["name"], *e["aliases"]]
            if any(len(n) > 2 and n.lower() in ql for n in names):
                hits.add(k)
        return hits

    async def context(self, q, llm, emb):
        if not self.rels:
            return ""
        hits = self._mentioned(q)
        # 1 hop from what the question names, plus everything about the user.
        near = {i for i, r in enumerate(self.rels) if r["s"] in hits or r["o"] in hits}
        reach = {self.rels[i]["o"] for i in near if self.rels[i]["o"]} | hits
        # 2nd hop, through what the user is connected to ("my wife's school").
        hop2 = {i for i, r in enumerate(self.rels) if r["s"] in reach}
        (qv,) = await emb.embed([q])
        by_meaning = sorted(range(len(self.rels)), key=lambda i: -cosine(qv, self.vecs[i]))[:25]
        chosen = (near | hop2) if len(near | hop2) <= 80 else set(by_meaning) | near
        chosen |= set(by_meaning[:15])
        return "\n".join(self.lines[i] for i in sorted(chosen, key=lambda i: self.rels[i]["since"]))

    def stats(self):
        return {
            "entities": len(self.entities),
            "relations": len(self.rels),
            "relation_types": len({r["r"] for r in self.rels}),
            "new_relation_types": len(getattr(self, "new_relations", [])),
            "ended": sum(1 for r in self.rels if r["until"]),
        }


class FreeGraph(Graph):
    key, name = "D", "Free connections"
    free = True


# ── E: a summary page per thing, written from C's connections ───────

SUMMARY = (
    "Write a short profile (2-5 sentences) of {who} from these facts about the user's life. Say "
    "what is current and what has changed (with dates). Use only the facts given."
)


class Summaries(Method):
    key, name = "E", "Summary pages (from connections)"

    def __init__(self, graph: Graph | None = None) -> None:
        self.graph = graph or Graph()

    async def build(self, data, llm, emb):
        if not getattr(self.graph, "rels", None):
            await self.graph.build(data, llm, emb)
        g = self.graph
        self.pages: dict[str, str] = {}
        for k in g.entities:
            lines = [g._line(r) for r in g.rels if r["s"] == k or r["o"] == k]
            if not lines:
                continue
            who = "the user" if k == "self" else g._name(k)
            self.pages[k] = await llm.chat(
                [
                    {"role": "system", "content": SUMMARY.replace("{who}", who)},
                    {"role": "user", "content": "\n".join(lines)},
                ],
                max_tokens=300,
            )

    async def context(self, q, llm, emb):
        keys = self.graph._mentioned(q)
        # The user's own connections reach the people/things a role word means ("my wife").
        reach = {
            r["o"] for r in self.graph.rels if r["s"] == "self" and r["o"] and r["until"] is None
        }
        ql = q.lower()
        keys |= {k for k in reach if any(w in ql for w in _role_words(self.graph, k))}
        return "\n\n".join(
            f"[{self.graph._name(k)}] {self.pages[k]}" for k in keys if k in self.pages
        )

    def stats(self):
        return {"pages": len(self.pages)}


ROLE_WORDS = {
    "spouse": ["wife", "husband", "spouse", "மனைவி", "கணவர்"],
    "child": ["daughter", "son", "kid", "child", "மகள்", "மகன்"],
    "parent": ["father", "mother", "dad", "mom", "appa", "amma", "parents", "அப்பா", "அம்மா"],
    "sibling": ["sister", "brother", "சகோதரி", "சகோதரன்"],
    "manager": ["manager", "boss"],
    "works_at": ["company", "office", "employer"],
    "works_on": ["project", "side project"],
    "leads": ["project i lead", "team"],
}


def _role_words(g: Graph, key: str) -> list[str]:
    rels = {r["r"] for r in g.rels if r["s"] == "self" and r["o"] == key and r["until"] is None}
    return [w for r in rels for w in ROLE_WORDS.get(r, [])]


# ── mixes ───────────────────────────────────────────────────────────


class Mix(Method):
    """Several methods' contexts, one after another, built once and shared."""

    def __init__(self, key: str, parts: list[Method]) -> None:
        self.key = key
        self.parts = parts
        self.name = " + ".join(p.name.split(" (")[0] for p in parts)

    async def build(self, data, llm, emb):
        for p in self.parts:
            await p.build(data, llm, emb)

    async def context(self, q, llm, emb):
        out = []
        for p in self.parts:
            c = await p.context(q, llm, emb)
            if c:
                out.append(f"## {p.name}\n{c}")
        return "\n\n".join(out)

    def stats(self):
        return {k: v for p in self.parts for k, v in p.stats().items()}


def _graph_once() -> Graph:
    """One C build shared by C, E and the mixes in a run (its calls are cached anyway)."""
    global _SHARED_GRAPH
    if _SHARED_GRAPH is None:
        _SHARED_GRAPH = Graph()
    return _SHARED_GRAPH


_SHARED_GRAPH: Graph | None = None

METHODS: dict[str, Any] = {
    "Z": Everything,
    "L": LifeGraph,
    "R0": lambda: RealLifeGraph("R0", "Real: as of 30 Oct (no brain steps)"),
    "R1": lambda: RealLifeGraph("R1", "Real: + cold tier", cold=True),
    "R2": lambda: RealLifeGraph("R2", "Real: + cold + links", cold=True, links=True),
    "R3": lambda: RealLifeGraph(
        "R3", "Real: + cold + links + strength", cold=True, links=True, strength=True
    ),
    "RD0": lambda: RealLifeGraph("RD0", "Real, after decay: no brain steps", decay=True),
    "RD1": lambda: RealLifeGraph("RD1", "Real, after decay: + cold", cold=True, decay=True),
    "RD2": lambda: RealLifeGraph(
        "RD2", "Real, after decay: + cold + links", cold=True, links=True, decay=True
    ),
    "RD3": lambda: RealLifeGraph(
        "RD3",
        "Real, after decay: + cold + links + strength",
        cold=True,
        links=True,
        strength=True,
        decay=True,
    ),
    "A": Notes,
    "B": Form,
    "C": _graph_once,
    "D": FreeGraph,
    "E": lambda: Summaries(_graph_once()),
    "AB": lambda: Mix("AB", [Notes(), Form()]),
    "AC": lambda: Mix("AC", [Notes(), _graph_once()]),
    "ACE": lambda: Mix("ACE", [Notes(), _graph_once(), Summaries(_graph_once())]),
}


# ── run and report ──────────────────────────────────────────────────


async def run(
    method_keys: list[str],
    model: str,
    limit: int | None,
    kinds: set[str] | None,
    data_path: Path = DATA,
    parallel: int = 1,
) -> Path:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    data["_path"] = str(data_path)
    questions = [q for q in data["questions"] if not kinds or q["kind"] in kinds][: limit or None]
    llm, emb = LLM(model, parallel), Embedder()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    tag = data_path.stem.replace("test_life", "") or "_small"
    safe_model = re.sub(r"[^\w.-]+", "_", model)[:40]
    run_dir = OUT / "runs" / f"{stamp}{tag}_{safe_model}_{'-'.join(method_keys)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "model": model,
        "data": data_path.name,
        "messages": len(data["messages"]),
        "questions": len(questions),
        "methods": {},
    }
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as out:
        for key in method_keys:
            method = METHODS[key]()
            t0 = time.monotonic()
            if not getattr(method, "_built", False):
                await method.build(data, llm, emb)
                method._built = True
            build_s = round(time.monotonic() - t0, 1)
            print(f"[{key}] built in {build_s}s {method.stats()}", flush=True)
            per_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
            ctx_chars = []

            async def ask(q, method=method):
                ctx = await method.context(q["q"], llm, emb)
                return ctx, await answer(llm, data["today"], ctx, q["q"])

            done = await asyncio.gather(*(ask(q) for q in questions))
            for n, (q, (ctx, ans)) in enumerate(zip(questions, done, strict=True), 1):
                ctx_chars.append(len(ctx))
                ok, why = score(q, ans)
                per_kind[q["kind"]][0] += ok
                per_kind[q["kind"]][1] += 1
                out.write(
                    json.dumps(
                        {
                            "method": key,
                            "id": q["id"],
                            "kind": q["kind"],
                            "q": q["q"],
                            "ok": ok,
                            "why": why,
                            "answer": ans,
                            "context_chars": len(ctx),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                out.flush()
                if n % 20 == 0:
                    print(f"[{key}] {n}/{len(questions)}", flush=True)
            passed = sum(v[0] for v in per_kind.values())
            summary["methods"][key] = {
                "name": method.name,
                "passed": passed,
                "score": round(100 * passed / max(1, len(questions)), 1),
                "by_kind": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per_kind.items())},
                "avg_context_chars": round(sum(ctx_chars) / max(1, len(ctx_chars))),
                "build_s": build_s,
                **method.stats(),
            }
            print(
                f"[{key}] {passed}/{len(questions)} = {summary['methods'][key]['score']}%",
                flush=True,
            )
    summary["llm_calls"], summary["llm_cached"] = llm.calls, llm.cached
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    report(run_dir)
    return run_dir


def rescore(run_dir: Path) -> None:
    """Score a run's answers again with the current test set: no model calls."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in data["questions"]}
    rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    per: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        r["ok"], r["why"] = score(qs[r["id"]], r["answer"])
        per[r["method"]][r["kind"]][0] += r["ok"]
        per[r["method"]][r["kind"]][1] += 1
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    for key, kinds in per.items():
        passed, total = sum(v[0] for v in kinds.values()), sum(v[1] for v in kinds.values())
        s["methods"][key].update(
            passed=passed,
            score=round(100 * passed / max(1, total), 1),
            by_kind={k: f"{v[0]}/{v[1]}" for k, v in sorted(kinds.items())},
        )
    (run_dir / "summary.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    report(run_dir)


def report(run_dir: Path) -> None:
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    kinds = sorted({k for m in s["methods"].values() for k in m["by_kind"]})
    print(
        f"\n{s.get('data', 'test_life.json')} ({s.get('messages', '?')} messages) · model {s['model']} · {s['questions']} questions · {s['llm_calls']} calls ({s['llm_cached']} cached)"
    )
    print(f"{'method':<34}{'score':>7}  " + "  ".join(f"{k[:9]:>9}" for k in kinds))
    for key, m in s["methods"].items():
        cells = "  ".join(f"{m['by_kind'].get(k, '-'):>9}" for k in kinds)
        print(f"{key + ' ' + m['name']:<34}{m['score']:>6}%  {cells}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--methods", default="Z,A")
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--limit", type=int)
    r.add_argument("--kinds", help="comma-separated question kinds")
    r.add_argument(
        "--data", type=Path, default=DATA, help="test life JSON (default: the small one)"
    )
    r.add_argument("--parallel", type=int, default=1, help="local model: calls at once")
    rp = sub.add_parser("report")
    rp.add_argument("run_dir", type=Path)
    rs = sub.add_parser("rescore")
    rs.add_argument("run_dir", type=Path)
    a = ap.parse_args()
    if a.cmd == "run":
        keys = [k.strip().upper() for k in a.methods.split(",") if k.strip()]
        unknown = [k for k in keys if k not in METHODS]
        if unknown:
            sys.exit(f"unknown methods {unknown}; have {sorted(METHODS)}")
        asyncio.run(
            run(
                keys,
                a.model,
                a.limit,
                set(a.kinds.split(",")) if a.kinds else None,
                a.data,
                a.parallel,
            )
        )
    elif a.cmd == "rescore":
        rescore(a.run_dir)
    else:
        report(a.run_dir)


if __name__ == "__main__":
    main()
