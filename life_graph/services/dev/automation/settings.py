"""The automation settings document: intake, schedules, digest, breaker, timezone.

The shape mirrors race-app's ``AutomationSettings`` (packages/shared-types
``automation.ts``) so its cockpit can be re-pointed with few changes: the same
camelCase field names (``maxConcurrent``, ``projectId``, ``pollMinutes``,
``commentOnIssue``, ``after``…), accepted in snake_case too. Differences:
a source/job names a life-graph **persona** (which pins the driver) instead
of a race-app agent (``agentId`` is accepted as an alias), there is no
``budget`` section (the Governor and the subscription share are the budget),
and unknown sections (``runHealth``, ``prFeedback``, ``budget``) are ignored
rather than refused, so the cockpit may send its whole document.

Every feature is **off by default** except the circuit breaker, which only
ever stops automatic starts.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from life_graph.config import settings

SourceKind = Literal["github_issues", "failing_ci", "life_graph_intentions", "todo_comments"]
Mode = Literal["plan", "ask", "auto"]

MAX_SOURCES = 20
MAX_SCHEDULES = 50
_HHMM = re.compile(r"^\d{2}:\d{2}$")


class _Model(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="ignore", from_attributes=True
    )


def parse_hhmm(value: str) -> int | None:
    """``"HH:MM"`` → minutes since midnight; None when malformed or out of range."""
    if not isinstance(value, str) or not _HHMM.match(value):
        return None
    h, m = int(value[:2]), int(value[3:])
    return h * 60 + m if h < 24 and m < 60 else None


def _check_time(value: str) -> str:
    if parse_hhmm(value) is None:
        raise ValueError("time must be HH:MM (00:00-23:59)")
    return value


class IntakeSource(_Model):
    """Where backlog items come from and how their tasks run."""

    id: str | None = None
    kind: SourceKind
    name: str | None = Field(None, max_length=80)
    enabled: bool = False
    project_id: str
    # github_issues: label (default "life-graph"); todo_comments: marker (default
    # "TODO(race)"); life_graph_intentions: tag (default "dev").
    filter: str | None = Field(None, max_length=100)
    persona: str | None = Field(
        None, max_length=100, validation_alias=AliasChoices("persona", "agentId", "agent_id")
    )
    mode: Mode = "ask"
    comment_on_issue: bool = False
    poll_minutes: int = Field(30, ge=5, le=1440)
    # Read-only (set by the poller; ignored on save).
    last_polled_at: str | None = None
    last_error: str | None = None


class IntakeSettings(_Model):
    sources: list[IntakeSource] = Field(default_factory=list, max_length=MAX_SOURCES)
    # Intake tasks queued/running at once (0 = intake starts nothing).
    max_concurrent: int = Field(1, ge=0, le=10)
    # Intake tasks started per tenant-local day.
    max_per_day: int = Field(5, ge=0, le=100)


class ScheduledDevJob(_Model):
    """A dev-task job: on days at a local time, or after another job (``after``)."""

    id: str | None = None
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = False
    project_id: str
    instruction: str = Field(..., min_length=5, max_length=8000)
    persona: str | None = Field(
        None, max_length=100, validation_alias=AliasChoices("persona", "agentId", "agent_id")
    )
    mode: Mode = "ask"
    # 0-6 = Sunday-Saturday; ignored while ``after`` is set.
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], max_length=7)
    time: str = "02:00"
    after: str | None = None
    # Read-only.
    last_run_at: str | None = None
    last_task_id: str | None = None

    @field_validator("days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        if any(not isinstance(d, int) or d < 0 or d > 6 for d in value):
            raise ValueError("days are 0-6 (Sunday-Saturday)")
        return sorted(set(value))

    @field_validator("time")
    @classmethod
    def _time(cls, value: str) -> str:
        return _check_time(value)


class DigestSettings(_Model):
    enabled: bool = False
    time: str = "08:00"

    @field_validator("time")
    @classmethod
    def _time(cls, value: str) -> str:
        return _check_time(value)


class BreakerSettings(_Model):
    enabled: bool = True
    threshold: int = Field(3, ge=2, le=10)


class AutomationSettings(_Model):
    intake: IntakeSettings = Field(default_factory=IntakeSettings)
    schedules: list[ScheduledDevJob] = Field(default_factory=list, max_length=MAX_SCHEDULES)
    digest: DigestSettings = Field(default_factory=DigestSettings)
    breaker: BreakerSettings = Field(default_factory=BreakerSettings)
    # IANA zone for days/times and the daily limit; None = settings.user_timezone.
    timezone: str | None = Field(None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value

    def dump(self) -> dict:
        """The API shape (camelCase)."""
        return self.model_dump(by_alias=True, mode="json")


def tenant_zone(value: str | None) -> ZoneInfo:
    """The zone for *value*, else ``settings.user_timezone``, else UTC."""
    for name in (value, settings.user_timezone, "UTC"):
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def _is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def assign_ids(doc: AutomationSettings) -> AutomationSettings:
    """Give every source/job a UUID; a non-UUID id (a draft's temp id) is replaced
    and ``after`` references to it are translated."""
    for source in doc.intake.sources:
        if not _is_uuid(source.id):
            source.id = str(uuid.uuid4())
    mapping: dict[str, str] = {}
    for job in doc.schedules:
        if not _is_uuid(job.id):
            new = str(uuid.uuid4())
            if job.id:
                mapping[job.id] = new
            job.id = new
    for job in doc.schedules:
        if job.after and job.after in mapping:
            job.after = mapping[job.after]
    return doc


def settings_problem(doc: AutomationSettings) -> str | None:
    """Plain message for the first problem a save must refuse, or None."""
    ids = [s.id for s in doc.intake.sources if s.id] + [j.id for j in doc.schedules if j.id]
    if len(ids) != len(set(ids)):
        return "Two sources or jobs share an id."
    for job in doc.schedules:
        if not job.after and not job.days:
            return f'"{job.name}" needs at least one day (or a job to run after).'
    return chain_problem(doc.schedules)


def chain_problem(jobs: list[ScheduledDevJob]) -> str | None:
    """The first ``after`` problem (unknown job, itself, a loop), or None."""
    by_id = {j.id: j for j in jobs}
    for job in jobs:
        if not job.after:
            continue
        if job.after == job.id:
            return f'"{job.name}" can\'t run after itself.'
        if job.after not in by_id:
            return f'"{job.name}" is set to run after a job that doesn\'t exist ({job.after}).'
    for job in jobs:
        seen = {job.id}
        nxt = by_id.get(job.after) if job.after else None
        while nxt is not None:
            if nxt.id in seen:
                return f'"{job.name}" is part of a loop of jobs that run after each other.'
            seen.add(nxt.id)
            nxt = by_id.get(nxt.after) if nxt.after else None
    return None
