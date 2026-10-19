"""When a plan may approve itself (docs/specs/autonomous-app-development.md, item 8).

A plan is reviewed so that a wrong design never fans out into tasks. For a
small, well-specified plan from a driver that has earned trust on the
project, that review costs the person a click and catches little. This
decides when the click can be skipped. All of the following must hold; any
one failing leaves the plan pending for a person:

- the project opted in (``auto_approve_plans`` in its registry settings);
- at most ``auto_plan_max_tasks`` tasks (default 3);
- no spec gaps: every criterion has a test and a task, no check-only task;
- the spec names nothing sensitive (auth, secrets, migrations, sandbox,
  approvals, autonomy, budget, CI). Those always get a human;
- the driver's record on this project is established and its merge rate
  clears the same bar trust-gated PR opening uses.

Deterministic: no LLM decides whether a plan skips review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from life_graph.config import settings

# Areas where a wrong plan does damage a merge gate can't undo, or that
# govern the gates themselves. Matched case-insensitively against the spec.
SENSITIVE = re.compile(
    r"\.env\b|secret|credential|password|\btoken|\bauth|oauth|"
    r"migration|alembic/|\.github/workflows|\bci\b|"
    r"sandbox|approval|autonomy|kill.?switch|governor|budget|billing|payment",
    re.IGNORECASE,
)


@dataclass
class PlanDecision:
    approve: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return "; ".join(self.reasons)


def decide(
    *,
    opted_in: bool,
    spec: str,
    tasks: list[str],
    gaps: list[str],
    record: dict,
    merge_bar: float,
) -> PlanDecision:
    """Whether this plan approves itself, and the reasons either way."""
    blockers: list[str] = []
    if not opted_in:
        blockers.append("project has not opted into auto_approve_plans")
    limit = settings.auto_plan_max_tasks
    if len(tasks) > limit:
        blockers.append(f"{len(tasks)} tasks (auto-approval allows at most {limit})")
    if gaps:
        blockers.append(f"{len(gaps)} spec gap(s)")
    hits = sorted({m.group(0).lower() for m in SENSITIVE.finditer(spec or "")})
    if hits:
        blockers.append(f"touches sensitive areas: {', '.join(hits[:5])}")
    rate = record.get("merge_rate") or 0.0
    if not record.get("established") or rate < merge_bar:
        blockers.append(
            f"driver record {record.get('merged', 0)}/{record.get('total', 0)} merged "
            f"(needs an established record at {merge_bar:.0%})"
        )
    if blockers:
        return PlanDecision(False, blockers)
    return PlanDecision(
        True,
        [
            f"{len(tasks)} task(s), no gaps, nothing sensitive",
            f"driver has {record.get('merged')}/{record.get('total')} merged ({rate:.0%})",
        ],
    )
