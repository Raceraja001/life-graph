"""Memory yield — how much of what was captured became memory.

The one number a memory system has to watch: after the 2026-10-23 fresh
start, 935 captures in 30 hours produced 2 active memories, and nothing said
so. Captures are counted per surface, split into the ones extraction reads
(``settings.capture_no_extract_surfaces`` names the trail-only ones) and the
ones that yielded anything; memories created in the window are counted by
status and traced back to the surface they came from. Counts only, no
content: the brief line leaves the machine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from life_graph.config import settings
from life_graph.models.db import CaptureEvent, Memory

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

KEPT = ("active", "pending")
# Below this many extractable captures a zero is a quiet day, not a fault.
_WARN_MIN_EXTRACTABLE = 10
_MAX_SURFACE_LINES = 4


async def report(session: AsyncSession, tenant_id: str, since: datetime) -> dict[str, Any]:
    """Captures and memories since *since* for one tenant, per surface and in total."""
    trail_only = set(settings.capture_no_extract_surfaces_list)

    capture_rows = (
        await session.execute(
            select(
                CaptureEvent.surface,
                func.count(),
                func.count().filter(CaptureEvent.yield_count > 0),
            )
            .where(CaptureEvent.tenant_id == tenant_id, CaptureEvent.occurred_at >= since)
            .group_by(CaptureEvent.surface)
        )
    ).all()
    memory_rows = (
        await session.execute(
            select(CaptureEvent.surface, Memory.status, func.count())
            .select_from(Memory)
            .outerjoin(CaptureEvent, Memory.capture_event_id == CaptureEvent.id)
            .where(Memory.tenant_id == tenant_id, Memory.created_at >= since)
            .group_by(CaptureEvent.surface, Memory.status)
        )
    ).all()

    surfaces: dict[str, dict[str, Any]] = {}

    def entry(surface: str | None) -> dict[str, Any]:
        name = surface or "unknown"
        return surfaces.setdefault(
            name,
            {"captures": 0, "extracted": name not in trail_only, "yielded": 0, "memories": {}},
        )

    for surface, captures, yielded in capture_rows:
        e = entry(surface)
        e["captures"] += int(captures or 0)
        e["yielded"] += int(yielded or 0)
    for surface, status, count in memory_rows:
        mem = entry(surface)["memories"]
        mem[status] = mem.get(status, 0) + int(count or 0)

    totals = {
        "captures": 0,
        "extractable": 0,
        "yielded": 0,
        "kept": 0,
        "rejected": 0,
        "archived": 0,
    }
    for e in surfaces.values():
        totals["captures"] += e["captures"]
        if e["extracted"]:
            totals["extractable"] += e["captures"]
            totals["yielded"] += e["yielded"]
        for status, n in e["memories"].items():
            if status in KEPT:
                totals["kept"] += n
            elif status in ("rejected", "archived"):
                totals[status] += n
    totals["kept_rate"] = (
        round(totals["kept"] / totals["extractable"], 3) if totals["extractable"] else None
    )
    return {"since": since.isoformat(), "surfaces": surfaces, "totals": totals}


def lines(rep: dict[str, Any]) -> list[str]:
    """The brief's lines: a total, the busiest surfaces, and a warning when a
    day's worth of extractable captures kept nothing."""
    t = rep["totals"]
    if not t["captures"]:
        return []
    rate = f" ({round(t['kept_rate'] * 100)}%)" if t["kept_rate"] is not None else ""
    out = [
        f"Yield: {t['captures']} captures, {t['extractable']} read by extraction → "
        f"{t['kept']} kept{rate}, {t['rejected']} rejected, {t['archived']} archived."
    ]
    busiest = sorted(
        ((name, e) for name, e in rep["surfaces"].items() if e["extracted"] and e["captures"]),
        key=lambda item: item[1]["captures"],
        reverse=True,
    )[:_MAX_SURFACE_LINES]
    for name, e in busiest:
        kept = sum(n for s, n in e["memories"].items() if s in KEPT)
        out.append(f"  {name}: {e['captures']} captures → {kept} kept")
    if t["extractable"] >= _WARN_MIN_EXTRACTABLE and t["kept"] == 0:
        out.append(
            f"⚠ Nothing was kept from {t['extractable']} extractable captures. "
            "Check the extractor: scripts/eval_extraction.py run."
        )
    return out
