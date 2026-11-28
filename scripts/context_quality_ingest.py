"""The ``ingest`` arm of scripts/eval_context_quality.py: the world built by the save path.

The other arms seed finished rows: valid times, typed links, superseded rows and
decision statuses are written straight from evals/context_quality/dataset.json.
They measure the read side. This arm builds the same person's world the way
Life Graph would have built it, so the same questions show what ingestion
actually writes (ADR docs/design/adr-m8-ingestion-structure.md §6.1):

- every dataset record has an owner's message in
  ``evals/context_quality/ingest_fixtures.json`` (English, Tamil or Tanglish),
  with the day it was said (``said_d``, days relative to the run);
- ``capture`` messages go through the capture spine
  (services/capture_processors.py ``CaptureProcessors``): a CaptureEvent row,
  late, so said_at dates it (core/said_at.py); extraction; ``store_facts``
  (core/memory_manager.py ``_process_fact``); decision detection and the
  DECISION_CANDIDATE listener (services/judgment.py), on a private event bus;
- ``memory_save`` messages call the Jarvis tool (tools/memory_search.py
  ``memory_save``) inside a task whose owner message is the ``said`` text;
  the saved row is then dated when it was said (``MemoryManager._as_said``);
- ``distillation`` messages are facts the system inferred
  (``MemoryManager.store_facts``, source ``distillation``, tier ``verified``);
- ``owner_actions`` are the owner's own moves, made through the owner's
  service calls (services/decision_lifecycle.py ``move`` / ``supersede`` with an
  owner ``by``, what POST /judgment/decisions/{id}/confirm|discard|supersede
  call), and the owner archiving one memory;
- the four M8 flags are on: ``ingest_world_time``, ``ingest_supersession_tiers``,
  ``ingest_typed_links``, ``decision_lifecycle``.

No model is called. The extractor is the real ``LLMExtractor`` with its local
chat replaced by the *recorded* raw output of the local extraction model for
that message (``raw`` in the fixtures; record again with ``--record-fixtures``).
Dates the model wrote (``valid_until``, ``valid_from``) are shifted by the days
between the recording and the run, so "until 20 November" keeps its distance.

Intentions are seeded as rows, as in the other arms: commitments are outside
the ADR. Approvals and typed links are not seeded: only what ingestion writes
is there.

Replay dates: the arm replays months of messages in one go, so a few times the
save path stamps with "now" are put back to when the message was said, as a
live save would have stamped them: a decision's ``created_at``, a memory's
``properties.superseded_at`` (to the newer memory's recorded time) and a
contradiction approval's ``created_at``. Nothing else is touched.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest import mock

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_PATH = ROOT / "evals" / "context_quality" / "ingest_fixtures.json"

PATHS = ("capture", "memory_save", "distillation")
LANGS = ("en", "ta", "tanglish")
OWNER_OPS = ("confirm", "discard", "supersede", "archive")
#: The four M8 ingestion flags, all on for this arm.
FLAGS = (
    "ingest_world_time",
    "ingest_supersession_tiers",
    "ingest_typed_links",
    "decision_lifecycle",
)
#: The surface a capture message comes in on when the fixture names none: the
#: owner's own chat (SELF). Not jarvis_app, whose facts the capture leaves to
#: Jarvis's own memory_save (settings.capture_saved_by_tool_surfaces).
DEFAULT_SURFACE = "chat"
#: Who the owner's moves are made by: an owner label (decision_lifecycle.is_owner_label).
OWNER_BY = "owner"
_DATE_FIELDS = ("valid_until", "valid_from")
_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Fixtures (pure) ───────────────────────────────────────────


def load_fixtures(path: Path = FIXTURES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_facts(msg: dict[str, Any]) -> list[Any]:
    """The facts list of a message's recorded model output ([] when none or unreadable)."""
    try:
        data = json.loads(msg.get("raw") or "")
    except (TypeError, ValueError):
        return []
    facts = data.get("facts") if isinstance(data, dict) else None
    return facts if isinstance(facts, list) else []


def _norm(text_: str) -> str:
    return " ".join((text_ or "").split()).strip().lower()


def fact_keys(msg: dict[str, Any]) -> dict[str, str]:
    """Normalised fact content -> dataset key, for the facts a message's ``keys`` label."""
    if msg.get("path") == "memory_save":
        return {_norm(msg.get("save", "")): msg["expect"][0]} if msg.get("expect") else {}
    out: dict[str, str] = {}
    for item, key in zip(raw_facts(msg), msg.get("keys") or [], strict=False):
        if key and isinstance(item, dict) and item.get("content"):
            out[_norm(item["content"])] = key
    return out


def check_fixtures(fx: dict[str, Any], data: dict[str, Any]) -> list[str]:
    """What is wrong with the fixtures against *data* ([] when they are usable)."""
    problems: list[str] = []
    memory_keys = {m["key"] for m in data["memories"]}
    decision_keys = {d["key"] for d in data["decisions"]}
    seen_ids: set[str] = set()
    seen_keys: dict[str, str] = {}
    for msg in fx.get("messages", []):
        mid = msg.get("id", "?")
        if mid in seen_ids:
            problems.append(f"{mid}: duplicate message id")
        seen_ids.add(mid)
        if msg.get("path") not in PATHS:
            problems.append(f"{mid}: path {msg.get('path')!r} is not one of {PATHS}")
        if msg.get("lang") not in LANGS:
            problems.append(f"{mid}: lang {msg.get('lang')!r} is not one of {LANGS}")
        if not isinstance(msg.get("said_d"), (int, float)) or msg["said_d"] >= 0:
            problems.append(f"{mid}: said_d must be a negative number of days")
        if not (msg.get("said") or "").strip():
            problems.append(f"{mid}: no said text")
        for key in msg.get("expect", []):
            if key not in memory_keys:
                problems.append(f"{mid}: expect key {key!r} is not a dataset memory")
            if key in seen_keys:
                problems.append(f"{mid}: key {key!r} already said in {seen_keys[key]}")
            seen_keys[key] = mid
        if msg.get("decision") is not None and msg["decision"] not in decision_keys:
            problems.append(f"{mid}: decision {msg['decision']!r} is not a dataset decision")
        if msg.get("path") == "memory_save":
            if not (msg.get("save") or "").strip() or len(msg.get("expect", [])) != 1:
                problems.append(f"{mid}: a memory_save needs its save text and one expect key")
            continue
        facts = raw_facts(msg)
        if msg.get("raw") is None:
            problems.append(f"{mid}: no recorded raw output (run --record-fixtures)")
            continue
        keys = msg.get("keys")
        if not isinstance(keys, list) or len(keys) != len(facts):
            problems.append(f"{mid}: keys must label each of the {len(facts)} recorded facts")
            continue
        for key in keys:
            if key is not None and key not in msg.get("expect", []):
                problems.append(f"{mid}: labelled key {key!r} is not in its expect list")
    for act in fx.get("owner_actions", []):
        if act.get("op") not in OWNER_OPS:
            problems.append(f"owner action {act}: op is not one of {OWNER_OPS}")
        refs = [act.get("key"), act.get("by")] if act.get("op") == "supersede" else [act.get("key")]
        pool = memory_keys if act.get("op") == "archive" else decision_keys
        for ref in refs:
            if ref not in pool:
                problems.append(f"owner action {act}: {ref!r} is not a dataset record")
        if not isinstance(act.get("at_d"), (int, float)):
            problems.append(f"owner action {act}: at_d must be a number of days")
    return problems


def coverage(fx: dict[str, Any], data: dict[str, Any]) -> dict[str, list[str]]:
    """Dataset records with no message, and expected keys no recorded fact is labelled with."""
    said = {k for m in fx.get("messages", []) for k in m.get("expect", [])}
    said |= {m["decision"] for m in fx.get("messages", []) if m.get("decision")}
    labelled = {k for m in fx.get("messages", []) for k in fact_keys(m).values()}
    expected = {k for m in fx.get("messages", []) for k in m.get("expect", [])}
    records = [m["key"] for m in data["memories"]] + [d["key"] for d in data["decisions"]]
    return {
        "no_message": sorted(k for k in records if k not in said),
        "not_extracted": sorted(expected - labelled),
    }


def shift_dates(raw: str, days: int) -> str:
    """*raw* model output with its ``valid_until`` / ``valid_from`` days moved by *days*."""
    if not days:
        return raw
    try:
        data = json.loads(raw)
    except ValueError:
        return raw
    for item in data.get("facts", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        for name in _DATE_FIELDS:
            value = item.get(name)
            if isinstance(value, str) and _ISO_DAY.match(value):
                try:
                    item[name] = (date.fromisoformat(value) + timedelta(days=days)).isoformat()
                except ValueError:
                    continue
    return json.dumps(data, ensure_ascii=False)


def message_day(msg: dict[str, Any], spec_days: dict[str, float]) -> float:
    """When *msg* is said, in days from now: its records' (overridden) time, else its own."""
    keys = [*msg.get("expect", []), *([msg["decision"]] if msg.get("decision") else [])]
    days = [spec_days[k] for k in keys if k in spec_days]
    return min(days) if days else float(msg["said_d"])


def plan(fx: dict[str, Any], spec_days: dict[str, float]) -> list[dict[str, Any]]:
    """The messages for the records in *spec_days* (key -> created day), oldest first.

    A message is sent when any of its records is in the spec. Owner actions
    are not planned here: they run once their records exist (owner_actions_due).
    """
    out = []
    for msg in fx.get("messages", []):
        keys = [*msg.get("expect", []), *([msg["decision"]] if msg.get("decision") else [])]
        if any(k in spec_days for k in keys):
            out.append({**msg, "at_d": message_day(msg, spec_days)})
    return sorted(out, key=lambda m: (m["at_d"], m["id"]))


def owner_actions_due(
    fx: dict[str, Any], have: set[str], done: set[int], spec_days: dict[str, float]
) -> list[tuple[int, dict[str, Any], float]]:
    """Owner actions whose records all exist (*have*) and that have not run (*done*).

    Each comes with its time: its own ``at_d``, but never before its records
    were said (a scenario may move a record later).
    """
    out = []
    for i, act in enumerate(fx.get("owner_actions", [])):
        refs = [act["key"], *([act["by"]] if act.get("by") else [])]
        if i in done or not all(r in have for r in refs):
            continue
        at = max([float(act["at_d"])] + [spec_days[r] for r in refs if r in spec_days])
        out.append((i, act, at))
    return sorted(out, key=lambda t: (t[2], t[0]))


def auto_keys(raw: str, expect: list[str], contents: dict[str, str]) -> list[str | None]:
    """Label each recorded fact with the expected record it says, by shared content words.

    Each expected key goes to the one fact that shares the most of its words
    (at least a third of them); the other facts get None. Used when recording;
    the labels are committed and can be corrected by hand.
    """
    from life_graph.services.memory.typed_links import content_words

    facts = raw_facts({"raw": raw})
    labels: list[str | None] = [None] * len(facts)
    for key in expect:
        gold = content_words(contents.get(key, ""))
        best: tuple[float, int] | None = None
        for i, item in enumerate(facts):
            if labels[i] is not None or not isinstance(item, dict):
                continue
            words = content_words(str(item.get("content") or ""))
            score = len(gold & words) / len(gold) if gold else 0.0
            if score >= 1 / 3 and (best is None or score > best[0]):
                best = (score, i)
        if best is not None:
            labels[best[1]] = key
    return labels


@contextlib.contextmanager
def flags_on() -> Iterator[None]:
    """The four M8 ingestion flags on for the block."""
    from life_graph.config import settings

    saved = {name: getattr(settings, name) for name in FLAGS}
    for name in FLAGS:
        setattr(settings, name, True)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(settings, name, value)


# ── The extractor, replayed or recorded ───────────────────────


def _replay_class() -> type:
    from life_graph.extraction.llm import LLMExtractor

    class ReplayExtractor(LLMExtractor):
        """The real local extraction path with the model's answer read from the fixtures.

        ``extract`` always takes the local path; ``_local_chat`` (the one model
        call) returns the recorded raw output for the exact text. A text with no
        recording counts as a miss and gives "nothing to keep".
        """

        def __init__(self, raw_by_text: dict[str, str]) -> None:
            super().__init__(model="replay", lm_client=None)
            self._raw = raw_by_text
            self.misses: list[str] = []
            self.replayed = 0

        async def extract(self, text: str) -> list[Any]:
            return await self._extract_local(text)

        async def _local_chat(self, text: str, **_kw: Any) -> str:
            raw = self._raw.get(text.strip())
            if raw is None:
                self.misses.append(text[:80])
                return '{"facts": []}'
            self.replayed += 1
            return raw

    return ReplayExtractor


def replay_pipeline(fx: dict[str, Any], shift_days: int) -> Any:
    """An ExtractionPipeline whose LLM tier replays the fixtures (no model call)."""
    from life_graph.extraction.pipeline import ExtractionPipeline, not_the_owners_words

    raw_by_text = {
        not_the_owners_words(m["said"]).strip(): shift_dates(m["raw"], shift_days)
        for m in fx.get("messages", [])
        if m.get("path") != "memory_save" and m.get("raw") is not None
    }
    return ExtractionPipeline(llm_extractor=_replay_class()(raw_by_text))


def shift_of(fx: dict[str, Any], now: datetime) -> int:
    """Days between the recording's anchor and *now*."""
    anchor = (fx.get("recorded") or {}).get("anchor")
    if not anchor:
        return 0
    return (now.date() - date.fromisoformat(anchor)).days


async def record_fixtures(
    data: dict[str, Any],
    *,
    url: str,
    model: str,
    path: Path = FIXTURES_PATH,
    where: str = "local Ollama",
) -> dict[str, Any]:
    """Run the local extraction model on every message and write ``raw`` and ``keys``.

    The real ``LLMExtractor._extract_local`` with the four flags on, the said
    day as "Today is", no tenant (so no known-people hint and no trace), on
    the local Ollama at *url* only. Returns a summary.
    """
    from life_graph.config import settings
    from life_graph.core.said_at import said_at
    from life_graph.extraction.llm import LLMExtractor
    from life_graph.extraction.pipeline import not_the_owners_words
    from life_graph.services.llm.client import LMStudioClient

    class Recorder(LLMExtractor):
        last_raw: str = ""

        async def _local_chat(self, text: str, **kw: Any) -> str:
            self.last_raw = await super()._local_chat(text, **kw)
            return self.last_raw

    fx = load_fixtures(path)
    contents = {m["key"]: m["content"] for m in data["memories"]}
    anchor = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    saved = (settings.lm_extraction_model, settings.lm_reasoning_effort)
    settings.lm_extraction_model, settings.lm_reasoning_effort = model, "none"
    recorded = 0
    try:
        with flags_on():
            for msg in fx["messages"]:
                if msg["path"] == "memory_save":
                    continue
                token = said_at.set(anchor + timedelta(days=float(msg["said_d"])))
                try:
                    ext = Recorder(model=model, lm_client=LMStudioClient(base_url=f"{url}/v1"))
                    await ext._extract_local(not_the_owners_words(msg["said"]).strip())
                finally:
                    said_at.reset(token)
                msg["raw"] = ext.last_raw or '{"facts": []}'
                msg["keys"] = auto_keys(msg["raw"], msg.get("expect", []), contents)
                recorded += 1
    finally:
        settings.lm_extraction_model, settings.lm_reasoning_effort = saved
    fx["recorded"] = {
        "model": f"{model} on {where} (think off)",
        "anchor": anchor.date().isoformat(),
        "flags": list(FLAGS),
        "how": "python scripts/eval_context_quality.py --record-fixtures",
    }
    path.write_text(json.dumps(fx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"recorded": recorded, "coverage": coverage(fx, data)}


# ── Building the world through the save path (DB) ─────────────


class IngestState:
    """What one world's ingestion did: owner actions run, misses, mapped records."""

    def __init__(self, fx: dict[str, Any], now: datetime) -> None:
        self.fx = fx
        self.now = now
        self.done: set[int] = set()
        self.said_at: dict[str, datetime] = {}  # key -> when its message was said
        self.unmapped: list[str] = []  # expected records ingestion produced no row for
        self.decisions_detected: dict[str, int] = {}
        self.actions_failed: list[str] = []
        self.extra_memories = 0
        self.replay_misses: list[str] = []


def _manager() -> Any:
    """A MemoryManager over the real store, tagger and detector; hashing embeddings."""
    from life_graph import runtime
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.evals import production_retrieval_arm as arm
    from life_graph.scoring.importance import ImportanceTagger
    from life_graph.services.contradiction import ContradictionDetector

    store = runtime.get_store()
    mgr = MemoryManager(
        store=store,
        extractor=None,  # type: ignore[arg-type] — this arm never calls ingest()
        tagger=ImportanceTagger(),
        contradiction_detector=ContradictionDetector(store=store),
    )

    async def embed(text_: str) -> list[float]:
        return arm._embed(text_)

    mgr._generate_embedding = embed  # type: ignore[method-assign]
    return mgr


@contextlib.contextmanager
def save_path(fx: dict[str, Any], now: datetime) -> Iterator[tuple[Any, Any, Any]]:
    """The flags on, the replayed extractor and the hashing manager in place, and a bus.

    Yields (manager, pipeline, capture processors). The capture processors and
    the decision listener share a private EventBus, so nothing else running in
    the process hears these events.
    """
    from life_graph import runtime
    from life_graph.core.events import EventBus
    from life_graph.services.capture_processors import CaptureProcessors
    from life_graph.services.judgment import _DecisionCandidateListener

    mgr = _manager()
    pipeline = replay_pipeline(fx, shift_of(fx, now))
    bus = EventBus()
    listener = _DecisionCandidateListener(bus)
    listener.subscribe()
    with (
        flags_on(),
        mock.patch.object(runtime, "get_memory_manager", lambda: mgr),
        mock.patch.object(runtime, "get_extraction_pipeline", lambda: pipeline),
    ):
        yield mgr, pipeline, CaptureProcessors(bus)
    listener.unsubscribe()


async def _capture(tenant: str, msg: dict[str, Any], said: datetime, processors: Any) -> Any:
    from life_graph.core.events import Event, EventType
    from life_graph.core.trust import classify_surface
    from life_graph.models.db import CaptureEvent
    from life_graph.storage.database import async_session

    surface = msg.get("surface", DEFAULT_SURFACE)
    tier = msg.get("trust_tier") or classify_surface(surface).value
    evt = CaptureEvent(
        id=uuid.uuid4(),
        tenant_id=tenant,
        surface=surface,
        modality="text",
        content=msg["said"],
        content_hash=hashlib.sha256(f"{msg['said']}{uuid.uuid4()}".encode()).hexdigest(),
        trust_tier=tier,
        status="received",
        yield_count=0,
        occurred_at=said,
        properties={},
    )
    async with async_session() as s:
        s.add(evt)
        await s.commit()
    await processors._on_capture_received(
        Event(
            type=EventType.CAPTURE_RECEIVED,
            payload={"capture_event_id": str(evt.id), "tenant_id": tenant, "modality": "text"},
        )
    )
    return evt.id


async def _memory_save(tenant: str, msg: dict[str, Any], said: datetime, mgr: Any) -> None:
    """Jarvis's memory_save inside a task whose owner message is *msg*'s words."""
    from life_graph import runtime
    from life_graph.core.task_context import set_task_context
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session
    from life_graph.tools.memory_search import memory_save

    task = AgentTask(
        id=uuid.uuid4(),
        tenant_id=tenant,
        agent_name="jarvis",
        status="completed",
        input={"message": msg["said"]},
        result={},
        created_at=said,
    )
    async with async_session() as s:
        s.add(task)
        await s.commit()

    async def run() -> str:
        set_task_context(task.id, tenant)  # this child task's context only
        return await memory_save(content=msg["save"], about=msg.get("about"))

    out = json.loads(await asyncio.create_task(run()))
    if out.get("saved") and out.get("id"):
        row = await runtime.get_store().retrieve(uuid.UUID(out["id"]))
        if row is not None:
            # Dated when it was said, as a live save would be (the late-capture rule).
            await mgr._as_said(row, said, history_of=None)


async def _distil(msg: dict[str, Any], said: datetime, mgr: Any, pipeline: Any) -> None:
    """Facts the system inferred, stored as distillation does (verified tier)."""
    from life_graph.core.said_at import said_at

    token = said_at.set(said)
    try:
        facts = (await pipeline.extract(msg["said"], capture=True)).facts
        if facts:
            await mgr.store_facts(
                facts,
                context={"source": "distillation"},
                source="distillation",
                trust_tier="verified",
            )
    finally:
        said_at.reset(token)


async def _map_message(world: Any, msg: dict[str, Any], state: IngestState, event_id: Any) -> None:
    """Find the rows *msg* produced and file them under their dataset keys."""
    from sqlalchemy import select

    from life_graph.models.db import Decision, Memory
    from life_graph.storage.database import async_session

    # Only this build's records: a message also says records of another
    # phase or scenario (O6 sends the promotion for the job, and its salary
    # fact comes along), and those rows count as extra here.
    wanted = {c: k for c, k in fact_keys(msg).items() if k in world.specs}
    async with async_session() as s:
        rows = (
            (await s.execute(select(Memory).where(Memory.tenant_id == world.tenant)))
            .scalars()
            .all()
        )
        by_content = {}
        for row in rows:
            by_content.setdefault(_norm(row.content), row)
        for content, key in wanted.items():
            row = by_content.get(content)
            if row is None:
                state.unmapped.append(key)
                continue
            world.rows[key] = row
            world.kind[key] = "memory"
        if event_id is not None:
            made = [r for r in rows if r.capture_event_id == event_id]
            state.extra_memories += sum(1 for r in made if _norm(r.content) not in wanted)
        key = msg.get("decision")
        if key and event_id is not None:
            found = (
                (
                    await s.execute(
                        select(Decision)
                        .where(Decision.tenant_id == world.tenant)
                        .where(Decision.capture_event_id == event_id)
                        .order_by(Decision.created_at)
                    )
                )
                .scalars()
                .all()
            )
            state.decisions_detected[key] = len(found)
            if found:
                world.rows[key] = found[0]
                world.kind[key] = "decision"
            else:
                state.unmapped.append(key)


async def _owner_act(world: Any, act: dict[str, Any], at: datetime, state: IngestState) -> None:
    from sqlalchemy import update

    from life_graph.core.errors import DomainError
    from life_graph.models.db import Memory
    from life_graph.services import decision_lifecycle as dl
    from life_graph.storage.database import async_session

    row = world.rows[act["key"]]
    try:
        async with async_session() as s:
            if act["op"] == "archive":
                await s.execute(
                    update(Memory)
                    .where(Memory.id == row.id, Memory.tenant_id == world.tenant)
                    .values(status="archived")
                )
            elif act["op"] == "supersede":
                await dl.supersede(
                    s,
                    world.tenant,
                    row.id,
                    world.rows[act["by"]].id,
                    by=OWNER_BY,
                    owner=True,
                    now=at,
                )
            else:
                to = dl.DECIDED if act["op"] == "confirm" else dl.DISCARDED
                await dl.move(s, world.tenant, row.id, to, by=OWNER_BY, owner=True, now=at)
            await s.commit()
    except DomainError as exc:
        state.actions_failed.append(f"{act['op']} {act['key']}: {exc}")


async def _redate(world: Any, state: IngestState) -> None:
    """Put the replay's "now" stamps back to when things were said (see the module doc)."""
    from sqlalchemy import select

    from life_graph.models.db import Approval, Decision, Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        for key, row in world.rows.items():
            if world.kind.get(key) == "decision" and key in state.said_at:
                d = await s.get(Decision, row.id)
                if d is not None:
                    d.created_at = state.said_at[key]
        mems = {
            m.id: m
            for m in (
                await s.execute(select(Memory).where(Memory.tenant_id == world.tenant))
            ).scalars()
        }
        for m in mems.values():
            newer = mems.get(m.superseded_by) if m.superseded_by else None
            if newer is not None and (m.properties or {}).get("superseded_at"):
                m.properties = {**m.properties, "superseded_at": newer.created_at.isoformat()}
        approvals = (
            await s.execute(
                select(Approval).where(
                    Approval.tenant_id == world.tenant, Approval.kind == "contradiction"
                )
            )
        ).scalars()
        for a in approvals:
            new_id = (a.payload or {}).get("memory_id_new")
            newer = mems.get(uuid.UUID(new_id)) if new_id else None
            if newer is not None:
                a.created_at = newer.created_at
        await s.commit()


async def build(world: Any, spec: dict[str, Any], state: IngestState) -> None:
    """Build *spec*'s memories and decisions in *world* through the save path.

    Every record of the spec is in ``world.specs`` (its gold labels); only
    those ingestion produced a row for are in ``world.rows``. Intentions are
    seeded as rows (eval_context_quality.seed). Owner actions run as soon as
    their records exist, at their own time.
    """
    from life_graph.core.tenant import tenant_scope

    spec_days: dict[str, float] = {}
    for group, kind in (("memories", "memory"), ("decisions", "decision")):
        for rec in spec.get(group, []):
            world.specs[rec["key"]] = rec
            world.kind[rec["key"]] = kind
            spec_days[rec["key"]] = float(rec.get("created_d", -3))
    with tenant_scope(world.tenant), save_path(state.fx, state.now) as (mgr, pipe, procs):
        for msg in plan(state.fx, spec_days):
            said = state.now + timedelta(days=msg["at_d"])
            await _run_due_actions(world, state, spec_days, before=msg["at_d"])
            event_id = None
            if msg["path"] == "capture":
                event_id = await _capture(world.tenant, msg, said, procs)
            elif msg["path"] == "memory_save":
                await _memory_save(world.tenant, msg, said, mgr)
            else:
                await _distil(msg, said, mgr, pipe)
            for key in [
                *msg.get("expect", []),
                *([msg["decision"]] if msg.get("decision") else []),
            ]:
                state.said_at[key] = said
            await _map_message(world, msg, state, event_id)
        await _run_due_actions(world, state, spec_days, before=None)
        await _redate(world, state)
        state.replay_misses += pipe._llm.misses


async def _run_due_actions(
    world: Any, state: IngestState, spec_days: dict[str, float], *, before: float | None
) -> None:
    have = {k for k in world.rows if k in world.specs}
    for i, act, at_d in owner_actions_due(state.fx, have, state.done, spec_days):
        if before is not None and at_d > before:
            continue
        state.done.add(i)
        await _owner_act(world, act, state.now + timedelta(days=at_d), state)


# ── What ingestion wrote versus the gold structure (DB read) ──


async def structure_report(world: Any, data: dict[str, Any], state: IngestState) -> dict[str, Any]:
    """Counts of the structure ingestion wrote, and each gold structure found or missed."""
    from sqlalchemy import select

    from life_graph.models.db import Approval, Decision, Memory, MemoryLink
    from life_graph.services import decision_lifecycle as dl
    from life_graph.services.memory import snapshot
    from life_graph.storage.database import async_session

    async with async_session() as s:
        mems = list(
            (await s.execute(select(Memory).where(Memory.tenant_id == world.tenant))).scalars()
        )
        links = list(
            (
                await s.execute(select(MemoryLink).where(MemoryLink.tenant_id == world.tenant))
            ).scalars()
        )
        approvals = list(
            (
                await s.execute(
                    select(Approval).where(
                        Approval.tenant_id == world.tenant, Approval.kind == "contradiction"
                    )
                )
            ).scalars()
        )
        decisions = list(
            (await s.execute(select(Decision).where(Decision.tenant_id == world.tenant))).scalars()
        )
    key_of = {str(row.id): k for k, row in world.rows.items()}
    by_status: dict[str, int] = {}
    for m in mems:
        by_status[m.status] = by_status.get(m.status, 0) + 1
    typed = [link for link in links if link.link_type != "ASSOCIATED"]
    link_types: dict[str, int] = {}
    for link in typed:
        link_types[link.link_type] = link_types.get(link.link_type, 0) + 1
    app_kinds: dict[str, int] = {}
    for a in approvals:
        p = a.payload or {}
        label = f"{p.get('confidence', 'untiered')}/{'applied' if p.get('applied') else 'waiting'}"
        app_kinds[label] = app_kinds.get(label, 0) + 1
    world_time = sum(1 for m in mems if snapshot.world_time_known(m.valid_from, m.created_at))
    gold = _gold_structure(data, world, key_of, mems, typed, approvals, decisions, dl)
    return {
        "memories": len(mems),
        "memories_by_status": dict(sorted(by_status.items())),
        "extra_memories": state.extra_memories,
        "world_time_set": sum(1 for m in mems if (m.properties or {}).get("world_time")),
        "world_time_known": world_time,
        "valid_until_set": sum(1 for m in mems if m.valid_until is not None),
        "superseded": sum(1 for m in mems if m.superseded_by is not None),
        "links_associated": len(links) - len(typed),
        "links_typed": dict(sorted(link_types.items())),
        "contradiction_approvals": dict(sorted(app_kinds.items())),
        "decisions_by_status": _count(d.status for d in decisions),
        "decisions_owner_confirmed": sum(1 for d in decisions if dl.owner_confirmed(d)),
        "decisions_detected": dict(sorted(state.decisions_detected.items())),
        "replay_misses": state.replay_misses,
        "unmapped_records": sorted(set(state.unmapped)),
        "owner_actions_failed": state.actions_failed,
        "gold": gold,
    }


def _count(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def _gold_structure(
    data: dict[str, Any],
    world: Any,
    key_of: dict[str, str],
    mems: list[Any],
    typed: list[Any],
    approvals: list[Any],
    decisions: list[Any],
    dl: Any,
) -> dict[str, Any]:
    """Each gold structure of the dataset: did ingestion write it?"""
    rows = {str(m.id): m for m in mems}
    out: dict[str, Any] = {}
    # Supersession chains (memories and decisions).
    chains = [
        (r["key"], r["superseded_by"])
        for group in ("memories", "decisions")
        for r in data[group]
        if r.get("superseded_by")
    ]
    found, missed = [], []
    for old, new in chains:
        o, n = world.rows.get(old), world.rows.get(new)
        ok = o is not None and n is not None and getattr(o, "id", None) is not None
        if ok:
            current = (
                rows.get(str(o.id))
                if world.kind.get(old) == "memory"
                else next((d for d in decisions if d.id == o.id), None)
            )
            ok = current is not None and current.superseded_by == n.id
        (found if ok else missed).append(f"{old}->{new}")
    out["supersession"] = {"expected": len(chains), "found": found, "missed": missed}
    # Typed links.
    have_links = {
        frozenset((key_of.get(str(link.source_memory_id)), key_of.get(str(link.target_memory_id))))
        for link in typed
    }
    want = data.get("typed_links", [])
    out["typed_links"] = {
        "expected": len(want),
        "found": [
            f"{x['a']}-{x['type']}-{x['b']}"
            for x in want
            if frozenset((x["a"], x["b"])) in have_links
        ],
        "missed": [
            f"{x['a']}-{x['type']}-{x['b']}"
            for x in want
            if frozenset((x["a"], x["b"])) not in have_links
        ],
        "written": len(typed),
        "written_between_gold_records": sum(1 for p in have_links if None not in p),
    }
    # Pending contradiction approvals.
    have_apps = {
        frozenset(
            (
                key_of.get(str((a.payload or {}).get("memory_id_old"))),
                key_of.get(str((a.payload or {}).get("memory_id_new"))),
            )
        )
        for a in approvals
        if not (a.payload or {}).get("applied") and a.status == "pending"
    }
    want_apps = data.get("approvals", [])
    out["pending_contradictions"] = {
        "expected": len(want_apps),
        "found": [
            f"{x['old']}|{x['new']}"
            for x in want_apps
            if frozenset((x["old"], x["new"])) in have_apps
        ],
        "missed": [
            f"{x['old']}|{x['new']}"
            for x in want_apps
            if frozenset((x["old"], x["new"])) not in have_apps
        ],
    }
    # Memory statuses and ends.
    status_right, status_wrong = 0, []
    for rec in data["memories"]:
        row = world.rows.get(rec["key"])
        temporal = (rec.get("gold") or {}).get("temporal")
        want_status = {
            "superseded": "superseded",
            "pending": "pending",
            "archived": "archived",
        }.get(temporal, "active")
        got = rows[str(row.id)].status if row is not None and str(row.id) in rows else "missing"
        if temporal == "expired":
            m = rows.get(str(row.id)) if row is not None else None
            ok = m is not None and m.valid_until is not None and m.valid_until <= world.now
            got = f"{got}, valid_until {'set' if m is not None and m.valid_until else 'none'}"
        else:
            ok = got == want_status
        if ok:
            status_right += 1
        else:
            status_wrong.append(f"{rec['key']}: {got} (gold {temporal})")
    out["memory_state"] = {
        "right": status_right,
        "of": len(data["memories"]),
        "wrong": status_wrong,
    }
    # Decisions.
    dec_right, dec_wrong = 0, []
    by_id = {d.id: d for d in decisions}
    for rec in data["decisions"]:
        row = world.rows.get(rec["key"])
        d = by_id.get(row.id) if row is not None else None
        got = d.status if d is not None else "missing"
        confirmed = bool(d is not None and dl.owner_confirmed(d))
        want_confirmed = rec.get("status") in dl.CONFIRMED_STATUSES
        if got == rec.get("status", "candidate") and (
            confirmed == want_confirmed or got == "superseded"
        ):
            dec_right += 1
        else:
            dec_wrong.append(
                f"{rec['key']}: {got}{' (owner-confirmed)' if confirmed else ''} (gold {rec.get('status')})"
            )
    out["decisions"] = {"right": dec_right, "of": len(data["decisions"]), "wrong": dec_wrong}
    return out
