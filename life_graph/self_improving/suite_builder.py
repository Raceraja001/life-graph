"""Turn reviewed extractions into labelled examples and an eval suite.

The label for an extraction call is how the user resolved the memories it
produced — there is no separate labelling step (Charter non-goal: no
maintenance tax):

* approved memory  -> the fact is expected, with its *current* text, so an
  edit before approval becomes the target;
* rejected memory  -> the fact is not expected.

The rules are conservative on purpose, because a noisy label teaches the
wrong thing. A trace is used only when every fact it produced (at or above
``extraction_min_confidence``, the same floor production applies) is linked to
a memory that has been resolved. A fact with no linked memory — deduplicated
into an existing one, dropped, or deleted by the user — cannot be told apart
from a rejection after the fact, so its whole trace is left out. Traces that
produced no facts are left out too: nothing says what the model missed.

A stable 80/20 split by trace id sends 20% to the held-out eval suite and keeps
the rest as the optimizer's pool of few-shot examples. The split never moves,
so a candidate built from training examples is never scored on them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)

TASK_TYPE = "capture_extraction"
SUITE_NAME = "Capture extraction (from your reviews)"
_HOLDOUT_MODULUS = 5  # 1 in 5 traces is held out (20%)


@dataclass
class LabelledTrace:
    """One reviewed extraction: its input and the facts the user kept."""

    trace_id: str
    input_text: str
    expected: list[dict[str, Any]] = field(default_factory=list)

    @property
    def split(self) -> str:
        return split_for(self.trace_id)

    def expected_output(self) -> str:
        """The eval target: ``{"facts": [...]}`` as JSON."""
        return json.dumps({"facts": self.expected}, ensure_ascii=False)

    def as_few_shot(self) -> dict[str, Any]:
        """A few-shot example in the shape ``build_extraction_messages`` takes."""
        return {"input": self.input_text, "output": {"facts": self.expected}}


def split_for(trace_id: str) -> str:
    """Stable 80/20 train/holdout assignment by trace id."""
    digest = int(hashlib.sha256(str(trace_id).encode()).hexdigest(), 16)
    return "holdout" if digest % _HOLDOUT_MODULUS == 0 else "train"


def derive_expected(
    trace_facts: list[dict[str, Any]],
    linked: dict[int, dict[str, Any]],
    min_confidence: float,
) -> list[dict[str, Any]] | None:
    """The expected facts for one trace, or None if it cannot be labelled.

    ``linked`` maps fact index -> ``{"status", "content", "fact_type",
    "entities", "confidence"}`` for the memories linked to this trace.
    Pure function; the rules are in the module docstring.
    """
    relevant = [
        i
        for i, fact in enumerate(trace_facts)
        if float(fact.get("confidence", 0.0)) >= min_confidence
    ]
    if not relevant:
        return None
    expected: list[dict[str, Any]] = []
    for i in relevant:
        memory = linked.get(i)
        if memory is None or memory["status"] not in ("active", "rejected"):
            return None  # unlinked (dedup/deleted) or still pending
        if memory["status"] == "active":
            expected.append(
                {
                    "content": memory["content"],
                    "fact_type": memory.get("fact_type") or trace_facts[i].get("fact_type", "fact"),
                    "confidence": float(trace_facts[i].get("confidence", 0.9)),
                    "entities": list(memory.get("entities") or []),
                }
            )
    return expected


async def labelled_traces(
    tenant_id: str, *, task_type: str = TASK_TYPE, limit: int = 2000
) -> list[LabelledTrace]:
    """All usable reviewed traces for a tenant, newest first."""
    from life_graph.config import settings
    from life_graph.models.db import Memory
    from life_graph.self_improving.models import ExtractionTrace
    from life_graph.storage.database import async_session

    async with async_session() as session:
        traces = list(
            (
                await session.execute(
                    select(ExtractionTrace)
                    .where(
                        ExtractionTrace.tenant_id == tenant_id,
                        ExtractionTrace.task_type == task_type,
                    )
                    .order_by(ExtractionTrace.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        if not traces:
            return []
        trace_ids = [str(t.id) for t in traces]
        rows = (
            await session.execute(
                select(
                    Memory.properties["extraction_trace_id"].astext,
                    Memory.properties["extraction_fact_index"].astext,
                    Memory.status,
                    Memory.content,
                    Memory.properties,
                ).where(
                    Memory.tenant_id == tenant_id,
                    Memory.properties["extraction_trace_id"].astext.in_(trace_ids),
                )
            )
        ).all()

    linked: dict[str, dict[int, dict[str, Any]]] = {}
    for trace_id, index, status, content, props in rows:
        try:
            idx = int(index)
        except (TypeError, ValueError):
            continue
        props = props or {}
        linked.setdefault(trace_id, {})[idx] = {
            "status": status,
            "content": content,
            "fact_type": props.get("fact_type"),
            "entities": props.get("entities") or [],
        }

    out: list[LabelledTrace] = []
    for trace in traces:
        expected = derive_expected(
            list(trace.facts or []),
            linked.get(str(trace.id), {}),
            settings.extraction_min_confidence,
        )
        if expected is not None:
            out.append(LabelledTrace(str(trace.id), trace.input_text, expected))
    return out


async def sync_suite(tenant_id: str) -> dict[str, Any]:
    """Create/refresh the tenant's extraction suite from its held-out traces.

    Returns counts plus the training pool for the optimizer. Idempotent: cases
    are keyed by trace id; traces that stop qualifying are deactivated.
    """
    from life_graph.config import settings
    from life_graph.self_improving.models import EvalCase, EvalSuite
    from life_graph.storage.database import async_session

    traces = await labelled_traces(tenant_id)  # newest first
    # Newest held-out traces only: eval cost grows with the suite, and recent
    # captures reflect how the user writes now.
    holdout = [t for t in traces if t.split == "holdout"][: settings.eval_max_holdout_cases]
    train = [t for t in traces if t.split == "train"]

    async with async_session() as session:
        suite = (
            await session.execute(
                select(EvalSuite).where(
                    EvalSuite.tenant_id == tenant_id, EvalSuite.task_type == TASK_TYPE
                )
            )
        ).scalar_one_or_none()
        if suite is None:
            suite = EvalSuite(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                task_type=TASK_TYPE,
                name=SUITE_NAME,
                description=(
                    "Built automatically from reviewed captures: approved facts "
                    "(edited text where edited) are expected, rejected ones are not."
                ),
                auto_optimize_enabled=True,
            )
            session.add(suite)
            await session.flush()

        existing = {
            (case.metadata_ or {}).get("trace_id"): case
            for case in (
                await session.execute(
                    select(EvalCase).where(
                        EvalCase.suite_id == suite.id, EvalCase.source == "trace"
                    )
                )
            )
            .scalars()
            .all()
        }
        wanted = {t.trace_id: t for t in holdout}
        added = updated = deactivated = 0
        for trace_id, trace in wanted.items():
            case = existing.get(trace_id)
            if case is None:
                session.add(
                    EvalCase(
                        suite_id=suite.id,
                        input_text=trace.input_text,
                        expected_output=trace.expected_output(),
                        scoring_type="fact_set_f1",
                        scoring_config={},
                        metadata_={"trace_id": trace_id},
                        source="trace",
                        is_active=True,
                    )
                )
                added += 1
            elif case.expected_output != trace.expected_output() or not case.is_active:
                # A later edit or re-review changes the label.
                case.expected_output = trace.expected_output()
                case.is_active = True
                updated += 1
        for trace_id, case in existing.items():
            if trace_id not in wanted and case.is_active:
                case.is_active = False
                deactivated += 1
        suite.case_count = len(wanted)
        await session.commit()
        suite_id = suite.id

    logger.info(
        "Extraction suite for %s: %d holdout (+%d/~%d/-%d), %d train",
        tenant_id,
        len(holdout),
        added,
        updated,
        deactivated,
        len(train),
    )
    return {
        "suite_id": suite_id,
        "holdout": len(holdout),
        "train_pool": train,
        "added": added,
        "updated": updated,
        "deactivated": deactivated,
    }
