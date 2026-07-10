"""Scheduler — persistent cron job management for Life Graph.

Manages scheduled jobs that fire on cron expressions and spawn
agent tasks via the ProcessManager. Tracks run history,
consecutive failures, and auto-disables after configurable
failure threshold.

Uses a built-in cron parser (no external dependencies) to
compute next_run_at timestamps from standard 5-field cron
expressions.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.models.db import ScheduledJob

logger = logging.getLogger(__name__)


# ── Lightweight Cron Parser ────────────────────────────────


class CronExpression:
    """Parse and evaluate standard 5-field cron expressions.

    Fields: minute hour day-of-month month day-of-week
    Supports: *, specific values, ranges (1-5), steps (*/5),
    lists (1,3,5), and combinations (1-5/2).

    Examples:
        '0 3 * * *'   → 3:00 AM daily
        '*/15 * * * *' → every 15 minutes
        '0 0 * * 1'   → midnight every Monday
    """

    _FIELD_RANGES = [
        (0, 59),   # minute
        (0, 23),   # hour
        (1, 31),   # day of month
        (1, 12),   # month
        (0, 6),    # day of week (0=Sunday)
    ]

    def __init__(self, expression: str) -> None:
        self.expression = expression.strip()
        parts = self.expression.split()
        if len(parts) != 5:
            raise ValueError(
                f"Cron expression must have 5 fields,"
                f" got {len(parts)}: {expression!r}"
            )
        self._fields = [
            self._parse_field(parts[i], *self._FIELD_RANGES[i])
            for i in range(5)
        ]

    @staticmethod
    def _parse_field(
        field: str, lo: int, hi: int,
    ) -> set[int]:
        """Parse a single cron field into a set of values."""
        values: set[int] = set()
        for part in field.split(","):
            # Handle step: */5 or 1-10/2
            step = 1
            if "/" in part:
                part, step_str = part.split("/", 1)
                step = int(step_str)

            if part == "*":
                values.update(range(lo, hi + 1, step))
            elif "-" in part:
                start, end = part.split("-", 1)
                values.update(
                    range(int(start), int(end) + 1, step)
                )
            else:
                values.add(int(part))

        return values

    def next_fire_time(
        self,
        after: datetime | None = None,
    ) -> datetime:
        """Compute the next fire time after a given datetime.

        Args:
            after: Base time (defaults to now UTC).

        Returns:
            The next datetime matching the cron expression.
        """
        if after is None:
            after = datetime.now(timezone.utc)

        # Start from the next minute
        dt = after.replace(second=0, microsecond=0)
        from datetime import timedelta
        dt += timedelta(minutes=1)

        minutes, hours, days, months, dows = self._fields

        # Search up to 366 days ahead
        for _ in range(525960):  # ~365 days in minutes
            if (
                dt.month in months
                and dt.day in days
                and dt.weekday() in self._py_weekdays(dows)
                and dt.hour in hours
                and dt.minute in minutes
            ):
                return dt
            dt += timedelta(minutes=1)

        raise ValueError(
            f"No matching time found for {self.expression}"
        )

    @staticmethod
    def _py_weekdays(cron_dows: set[int]) -> set[int]:
        """Convert cron day-of-week (0=Sun) to Python (0=Mon).

        Cron: 0=Sunday, 1=Monday, ..., 6=Saturday
        Python: 0=Monday, 1=Tuesday, ..., 6=Sunday
        """
        mapping = {
            0: 6, 1: 0, 2: 1, 3: 2,
            4: 3, 5: 4, 6: 5,
        }
        return {mapping[d] for d in cron_dows}

    @staticmethod
    def validate(expression: str) -> bool:
        """Check if a cron expression is syntactically valid."""
        try:
            CronExpression(expression)
            return True
        except (ValueError, KeyError):
            return False


# ── Scheduler Service ──────────────────────────────────────


class SchedulerService:
    """Manages scheduled job CRUD and execution tracking.

    Does NOT run a background loop — instead, computes
    next_run_at and relies on an external trigger (e.g.,
    APScheduler, or a periodic health check) to fire jobs.
    This keeps the service testable and dependency-free.

    Args:
        session_factory: Async session factory for DB access.
        process_manager: ProcessManager for task spawning.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        process_manager: Any,
    ) -> None:
        self._session_factory = session_factory
        self._process_manager = process_manager
        self._max_failures = (
            settings.kernel_max_consecutive_failures
        )

    # ── CRUD ──────────────────────────────────────────────

    async def create(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new scheduled job.

        Args:
            tenant_id: Tenant scope.
            data: Job fields (name, cron_expression, etc.).

        Returns:
            Dict representation of the created job.

        Raises:
            ValueError: If name already exists or cron invalid.
        """
        name = data["name"]
        cron_expr = data["cron_expression"]

        # Validate cron expression
        if not CronExpression.validate(cron_expr):
            raise ValueError(
                f"Invalid cron expression: {cron_expr!r}"
            )

        # Compute next_run_at
        cron = CronExpression(cron_expr)
        next_run = cron.next_fire_time()

        async with self._session_factory() as session:
            # Check uniqueness
            existing = await session.execute(
                select(ScheduledJob.id).where(
                    ScheduledJob.tenant_id == tenant_id,
                    ScheduledJob.name == name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(
                    f"Schedule '{name}' already exists"
                )

            job = ScheduledJob(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                description=data.get("description"),
                cron_expression=cron_expr,
                agent_name=data["agent_name"],
                input=data.get("input", {}),
                is_active=True,
                timeout_seconds=data.get(
                    "timeout_seconds", 600,
                ),
                max_retries=data.get("max_retries", 3),
                next_run_at=next_run,
                properties=data.get("properties", {}),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)

            logger.info(
                "Created schedule '%s' (cron=%s, next=%s)",
                name, cron_expr, next_run,
            )
            return self._job_to_dict(job)

    async def list_all(
        self,
        tenant_id: str,
        *,
        include_inactive: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """List all scheduled jobs for a tenant.

        Args:
            tenant_id: Tenant scope.
            include_inactive: Include disabled jobs.

        Returns:
            Tuple of (job dicts, total count).
        """
        async with self._session_factory() as session:
            base = select(ScheduledJob).where(
                ScheduledJob.tenant_id == tenant_id,
            )
            count_base = (
                select(func.count())
                .select_from(ScheduledJob)
                .where(ScheduledJob.tenant_id == tenant_id)
            )

            if not include_inactive:
                base = base.where(
                    ScheduledJob.is_active.is_(True),
                )
                count_base = count_base.where(
                    ScheduledJob.is_active.is_(True),
                )

            count_result = await session.execute(count_base)
            total = count_result.scalar() or 0

            stmt = base.order_by(
                ScheduledJob.next_run_at.asc(),
            )
            result = await session.execute(stmt)
            jobs = [
                self._job_to_dict(j)
                for j in result.scalars().all()
            ]
            return jobs, total

    async def get_by_id(
        self, tenant_id: str, job_id: str,
    ) -> dict[str, Any] | None:
        """Get a scheduled job by UUID.

        Args:
            tenant_id: Tenant scope.
            job_id: Job UUID string.

        Returns:
            Job dict, or None if not found.
        """
        async with self._session_factory() as session:
            stmt = select(ScheduledJob).where(
                ScheduledJob.id == uuid.UUID(job_id),
                ScheduledJob.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                return None
            return self._job_to_dict(job)

    async def update(
        self,
        tenant_id: str,
        job_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a scheduled job.

        Recomputes next_run_at if cron_expression changes.

        Args:
            tenant_id: Tenant scope.
            job_id: Job UUID string.
            data: Fields to update (partial).

        Returns:
            Updated job dict, or None if not found.
        """
        allowed = {
            "description", "cron_expression",
            "agent_name", "input", "is_active",
            "timeout_seconds", "max_retries",
            "properties",
        }
        values = {
            k: v for k, v in data.items()
            if k in allowed
        }
        if not values:
            return await self.get_by_id(
                tenant_id, job_id,
            )

        # Validate and recompute if cron changed
        new_cron = values.get("cron_expression")
        if new_cron:
            if not CronExpression.validate(new_cron):
                raise ValueError(
                    f"Invalid cron: {new_cron!r}"
                )
            cron = CronExpression(new_cron)
            values["next_run_at"] = cron.next_fire_time()

        # If re-activating, reset failure count
        if values.get("is_active") is True:
            values["consecutive_failures"] = 0

        values["updated_at"] = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            stmt = (
                update(ScheduledJob)
                .where(
                    ScheduledJob.id == uuid.UUID(job_id),
                    ScheduledJob.tenant_id == tenant_id,
                )
                .values(**values)
                .returning(ScheduledJob.id)
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is None:
                return None
            await session.commit()

        logger.info(
            "Updated schedule %s (fields: %s)",
            job_id, list(values.keys()),
        )
        return await self.get_by_id(tenant_id, job_id)

    async def delete(
        self, tenant_id: str, job_id: str,
    ) -> dict[str, Any] | None:
        """Soft-delete a scheduled job.

        Args:
            tenant_id: Tenant scope.
            job_id: Job UUID string.

        Returns:
            Dict with id/message, or None if not found.
        """
        job = await self.get_by_id(tenant_id, job_id)
        if job is None:
            return None

        async with self._session_factory() as session:
            await session.execute(
                update(ScheduledJob)
                .where(
                    ScheduledJob.id == uuid.UUID(job_id),
                    ScheduledJob.tenant_id == tenant_id,
                )
                .values(
                    is_active=False,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        logger.info(
            "Deleted schedule '%s' (%s)",
            job["name"], job_id,
        )
        return {
            "id": job_id,
            "name": job["name"],
            "message": "Schedule removed",
        }

    # ── Job Execution ─────────────────────────────────────

    async def fire_job(
        self, tenant_id: str, job_id: str,
    ) -> dict[str, Any] | None:
        """Fire a scheduled job — spawn a task.

        Called when a cron trigger fires. Spawns a task via
        ProcessManager and updates run tracking.

        Args:
            tenant_id: Tenant scope.
            job_id: Job UUID string.

        Returns:
            Spawn result dict, or None if job not found.
        """
        job = await self.get_by_id(tenant_id, job_id)
        if job is None or not job["is_active"]:
            return None

        await event_bus.emit(
            EventType.SCHEDULE_FIRED,
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "job_name": job["name"],
                "agent_name": job["agent_name"],
            },
            source="scheduler",
        )

        try:
            result = await self._process_manager.spawn(
                tenant_id=tenant_id,
                agent_name=job["agent_name"],
                input_data=job.get("input", {}),
                task_name=f"schedule:{job['name']}",
                timeout_seconds=job.get(
                    "timeout_seconds", 600,
                ),
                max_retries=job.get("max_retries", 3),
            )

            task_id = (
                result.get("task_id")
                if isinstance(result, dict)
                else str(result)
            )

            await self._record_run(
                job_id, "completed", task_id,
            )
            return result

        except Exception as exc:
            logger.error(
                "Schedule %s fire failed: %s",
                job_id, exc,
            )
            await self._record_run(
                job_id, "failed", None,
            )
            return None

    async def _record_run(
        self,
        job_id: str,
        status: str,
        task_id: str | None,
    ) -> None:
        """Record a job run and check failure threshold.

        Updates last_run_at, last_run_status, run_count,
        and consecutive_failures. If failures exceed
        threshold, auto-disables the job.
        """
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            # Read current state
            stmt = select(ScheduledJob).where(
                ScheduledJob.id == uuid.UUID(job_id),
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                return

            new_failures = (
                0 if status == "completed"
                else job.consecutive_failures + 1
            )

            # Compute next run
            try:
                cron = CronExpression(job.cron_expression)
                next_run = cron.next_fire_time(now)
            except ValueError:
                next_run = None

            values: dict[str, Any] = {
                "last_run_at": now,
                "last_run_status": status,
                "run_count": job.run_count + 1,
                "consecutive_failures": new_failures,
                "next_run_at": next_run,
                "updated_at": now,
            }
            if task_id:
                values["last_run_task_id"] = (
                    uuid.UUID(task_id)
                )

            # Auto-disable on threshold
            if new_failures >= self._max_failures:
                values["is_active"] = False
                logger.warning(
                    "Auto-disabled schedule %s after"
                    " %d consecutive failures",
                    job_id, new_failures,
                )

        # Apply update in fresh session
        async with self._session_factory() as session:
            await session.execute(
                update(ScheduledJob)
                .where(
                    ScheduledJob.id == uuid.UUID(job_id),
                )
                .values(**values)
            )
            await session.commit()

        if new_failures >= self._max_failures:
            await event_bus.emit(
                EventType.SCHEDULE_DISABLED,
                {
                    "job_id": job_id,
                    "job_name": job.name,
                    "consecutive_failures": new_failures,
                },
                source="scheduler",
            )

    # ── Due Job Finder ────────────────────────────────────

    async def get_due_jobs(
        self, tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find all active jobs whose next_run_at is past.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            List of due job dicts.
        """
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            stmt = select(ScheduledJob).where(
                ScheduledJob.is_active.is_(True),
                ScheduledJob.next_run_at <= now,
            )
            if tenant_id:
                stmt = stmt.where(
                    ScheduledJob.tenant_id == tenant_id,
                )

            result = await session.execute(stmt)
            return [
                self._job_to_dict(j)
                for j in result.scalars().all()
            ]

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _job_to_dict(
        job: ScheduledJob,
    ) -> dict[str, Any]:
        """Convert a ScheduledJob ORM instance to dict."""
        return {
            "id": str(job.id),
            "tenant_id": job.tenant_id,
            "name": job.name,
            "description": job.description,
            "cron_expression": job.cron_expression,
            "agent_name": job.agent_name,
            "input": job.input or {},
            "is_active": job.is_active,
            "run_count": job.run_count,
            "consecutive_failures": (
                job.consecutive_failures
            ),
            "last_run_at": (
                job.last_run_at.isoformat()
                if job.last_run_at else None
            ),
            "last_run_status": job.last_run_status,
            "last_run_task_id": (
                str(job.last_run_task_id)
                if job.last_run_task_id else None
            ),
            "next_run_at": (
                job.next_run_at.isoformat()
                if job.next_run_at else None
            ),
            "max_retries": job.max_retries,
            "timeout_seconds": job.timeout_seconds,
            "properties": job.properties or {},
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
