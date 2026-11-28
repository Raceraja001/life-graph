"""World time on the save path (ADR m8-ingestion §5.1, build step 3).

The rules live in ``extraction/world_time.py`` (pure, no I/O). This module
wires them into the three places that write a memory:

- ``MemoryManager._process_fact`` (every extracted fact),
- the Jarvis tool ``memory_save`` (tools/memory_search.py),
- the verbatim store of ``POST /memories`` (api/memories.py).

Each asks :func:`for_fact` or :func:`for_text` for a start. ``None`` means
unknown: the caller passes no ``valid_from`` and the row keeps today's
spelling (``valid_from`` = the recorded time, which every reader reads as "no
world time of its own"). We never write a guessed "now". A known start goes to
``store(valid_from=...)`` and is recorded in ``properties.world_time`` by
:func:`record`, so a reader and a rollback can tell a rule-set start from the
default.

The anchor is the moment it was said: ``said_at`` for a late capture
(core/said_at.py), else now. So "yesterday" in a message delivered three days
late is the day before it was said. The time zone is the owner's setting
(``settings.user_timezone`` through ``connectors.tools.user_tz``).

Everything is behind ``settings.ingest_world_time`` (default off). Off, both
functions return ``None`` and nothing about a save changes.

Pure code: no model call and nothing leaves the machine. The model's own
``valid_from`` (one optional field of the extraction call that already runs
locally) is used only when the rules found nothing and a rule agrees with it
(``extraction.world_time.from_model``).
"""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.connectors.tools import user_tz
from life_graph.core.said_at import said_at
from life_graph.extraction import world_time as rules

if TYPE_CHECKING:
    from life_graph.extraction.world_time import WorldTime

#: Fact types that never get a start: a plan has a due time, not a world time.
NO_START_TYPES = frozenset({"intention"})


def enabled() -> bool:
    """True when ``ingest_world_time`` is on."""
    return bool(settings.ingest_world_time)


def anchor() -> datetime:
    """When it was said: ``said_at`` for a late capture, else now (UTC)."""
    return said_at.get() or datetime.now(UTC)


def _skipped(properties: dict[str, Any] | None) -> bool:
    """A day summary keeps its own ``properties.date`` (retrieval.is_valid_at)."""
    return bool(properties) and (properties or {}).get("kind") == "episode"


def _model_start(
    value: object, content: str, source_text: str | None, at: datetime, tz: tzinfo
) -> WorldTime | None:
    """The model's date, checked against the fact's own words.

    The phrase it must agree with is looked for in the content first; the
    owner's words are read only when they hold exactly one time phrase, as
    in :func:`extraction.world_time.world_time_of`.
    """
    if not value or (content and rules.blocked(content)):
        return None
    if rules.phrase_count(content, at, tz):
        return rules.from_model(value, content, at, tz)
    if source_text and rules.phrase_count(source_text, at, tz) == 1:
        return rules.from_model(value, source_text, at, tz)
    return None


def for_text(
    content: str,
    source_text: str | None = None,
    properties: dict[str, Any] | None = None,
    *,
    model_value: object = None,
) -> WorldTime | None:
    """The start of a memory with *content*, said in *source_text*; None for unknown."""
    if not enabled() or not content or _skipped(properties):
        return None
    at, tz = anchor(), user_tz()
    found = rules.world_time_of(content, source_text or None, at, tz)
    if found is None and model_value:
        found = _model_start(model_value, content, source_text, at, tz)
    return found


def for_fact(fact: Any, properties: dict[str, Any] | None = None) -> WorldTime | None:
    """The start of one extracted fact (``extraction.rules.ExtractedFact``), or None.

    An intention, a hedged fact or a negated one gets no start, whatever its
    words say (ADR §5.1 "Never").
    """
    if not enabled():
        return None
    if (
        getattr(fact, "fact_type", None) in NO_START_TYPES
        or getattr(fact, "certainty", "firm") == "hedged"
        or getattr(fact, "polarity", "affirm") == "negate"
    ):
        return None
    return for_text(
        fact.content,
        getattr(fact, "source_text", None),
        properties,
        model_value=getattr(fact, "valid_from", None),
    )


def record(properties: dict[str, Any], found: WorldTime) -> dict[str, Any]:
    """Put *found* in ``properties.world_time`` (start, precision, rule, source)."""
    properties["world_time"] = {
        "start": found.start.isoformat(),
        "precision": found.precision,
        "rule": found.rule,
        "source": found.source,
    }
    return properties


def store_kwargs(found: WorldTime | None) -> dict[str, Any]:
    """``{"valid_from": start}`` for ``store()``, or nothing when unknown."""
    return {"valid_from": found.start} if found is not None else {}
