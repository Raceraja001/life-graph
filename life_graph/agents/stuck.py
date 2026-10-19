"""Notice when an agent is going round in circles (docs/specs/agent-condenser.md).

A local model that calls the same tool with the same arguments and gets the
same error will do it until the round cap or the clock runs out. This watches
the tool calls of one run and names the pattern when it appears:

- ``repeat``       the same call, same result, ``REPEAT_LIMIT`` times in a row;
- ``error_repeat`` the same call failing ``REPEAT_LIMIT`` times in a row, even
                   if the error text differs (a timestamp, a counter);
- ``ping_pong``    two calls alternating A, B, A, B, A, B with unchanged results;
- ``no_progress``  ``NO_PROGRESS_LIMIT`` calls in a row that returned nothing
                   new: every result had been seen before in this run.

The orchestrator answers the first detection with a corrective message and
the second by stopping the run. Pure: no I/O, no model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

REPEAT_LIMIT = 3
PING_PONG_STEPS = 6
NO_PROGRESS_LIMIT = 12


def _canonical(arguments: Any) -> str:
    try:
        return json.dumps(arguments, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(arguments)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def is_error_result(result: str) -> bool:
    text = (result or "").lstrip()
    if not text.startswith("{"):
        return False
    try:
        value = json.loads(text)
    except ValueError:
        return text.startswith('{"error"')
    return isinstance(value, dict) and bool(value.get("error"))


@dataclass
class Step:
    tool: str
    args: str
    result: str
    error: bool

    @property
    def call(self) -> tuple[str, str]:
        return self.tool, self.args


@dataclass
class Stuck:
    pattern: str
    tool: str
    count: int
    message: str


@dataclass
class StuckDetector:
    steps: list[Step] = field(default_factory=list)
    seen_results: set[str] = field(default_factory=set)
    unproductive: int = 0
    detections: int = 0

    def record(self, tool: str, arguments: Any, result: str) -> Stuck | None:
        """Add one tool call and its result; returns a detection if one fired."""
        digest = _digest(result or "")
        step = Step(tool, _canonical(arguments), digest, is_error_result(result))
        self.steps.append(step)
        self.unproductive = self.unproductive + 1 if digest in self.seen_results else 0
        self.seen_results.add(digest)
        found = self._check()
        if found is not None:
            self.detections += 1
            # Start counting afresh, so the nudge gets a fair chance to work
            # before the same evidence counts again.
            self.steps.clear()
            self.unproductive = 0
        return found

    def _check(self) -> Stuck | None:
        last = self.steps[-REPEAT_LIMIT:]
        if len(last) == REPEAT_LIMIT and len({s.call for s in last}) == 1:
            tool = last[0].tool
            if len({s.result for s in last}) == 1:
                return Stuck(
                    "repeat",
                    tool,
                    REPEAT_LIMIT,
                    f"You have called {tool} with the same arguments {REPEAT_LIMIT} times and"
                    " got the same result each time. Repeating it will not change the answer.",
                )
            if all(s.error for s in last):
                return Stuck(
                    "error_repeat",
                    tool,
                    REPEAT_LIMIT,
                    f"{tool} has failed {REPEAT_LIMIT} times in a row with the same arguments."
                    " Read the error and change the arguments or the approach.",
                )
        window = self.steps[-PING_PONG_STEPS:]
        if len(window) == PING_PONG_STEPS:
            a, b = window[0], window[1]
            if a.call != b.call and all(
                (s.call, s.result)
                == ((a if i % 2 == 0 else b).call, (a if i % 2 == 0 else b).result)
                for i, s in enumerate(window)
            ):
                return Stuck(
                    "ping_pong",
                    f"{a.tool}/{b.tool}",
                    PING_PONG_STEPS,
                    f"You are alternating between {a.tool} and {b.tool} with the same results."
                    " Neither call is telling you anything new.",
                )
        if self.unproductive >= NO_PROGRESS_LIMIT:
            return Stuck(
                "no_progress",
                self.steps[-1].tool,
                self.unproductive,
                f"Your last {self.unproductive} tool calls returned only results you had"
                " already seen. You are not learning anything new.",
            )
        return None


def nudge_text(stuck: Stuck) -> str:
    """The corrective message added to the conversation after a first detection."""
    return (
        f"[Loop detected: {stuck.pattern}] {stuck.message} Do something different: "
        "use another tool or other arguments, re-read the task, or, if you are blocked,"
        " stop now and explain clearly what is blocking you and what you tried."
    )
