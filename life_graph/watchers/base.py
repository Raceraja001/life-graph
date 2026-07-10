"""Abstract base watcher with full lifecycle management.

The BaseWatcher handles: config loading, enabled checks, auto-disable
on 5 consecutive failures, run record creation, event persistence,
and failure tracking.
"""

from __future__ import annotations

import abc
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class Severity(str, Enum):
    """Event severity levels."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    INFO = "info"


@dataclass
class WatchEventData:
    """In-memory event data collected during watcher execution."""

    severity: Severity
    title: str
    details: dict = field(default_factory=dict)
    summary: str | None = None


class BaseWatcher(abc.ABC):
    """Abstract base class for all ambient watchers.

    Subclasses must set `name`, `display_name`, `default_schedule`
    class attributes and implement the `execute()` method.
    """

    name: str = "base"
    display_name: str = "Base Watcher"
    default_schedule: str = "0 6 * * *"

    def __init__(
        self,
        tenant_id: str,
        session_factory,
        settings: dict[str, Any] | None = None,
    ):
        self.tenant_id = tenant_id
        self.session_factory = session_factory
        self.settings = settings or {}
        self._events: list[WatchEventData] = []
        self.logger = logging.getLogger(f"watcher.{self.name}")

    def emit_event(
        self,
        severity: Severity,
        title: str,
        details: dict | None = None,
        summary: str | None = None,
    ) -> None:
        """Queue an event to be persisted after successful execution."""
        self._events.append(
            WatchEventData(
                severity=severity,
                title=title,
                details=details or {},
                summary=summary,
            )
        )

    @abc.abstractmethod
    async def execute(self) -> None:
        """Subclass implements the actual watcher logic here.

        Call self.emit_event() to record findings.
        """
        ...

    async def run(self) -> dict[str, Any]:
        """Full lifecycle: load config → check enabled → create run → execute → persist events."""
        from life_graph.watchers.models import WatchConfig, WatchEvent, WatcherRun

        run_id = uuid.uuid4()
        start_time = time.monotonic()
        self._events.clear()

        # ── Phase 1: Load config and check preconditions ──────
        async with self.session_factory() as session:
            stmt = select(WatchConfig).where(
                WatchConfig.tenant_id == self.tenant_id,
                WatchConfig.watcher_name == self.name,
            )
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()

            if config is None:
                self.logger.warning(
                    "No config found for watcher %s, tenant %s",
                    self.name, self.tenant_id,
                )
                return {"status": "skipped", "reason": "no_config"}

            if not config.enabled:
                self.logger.info(
                    "Watcher %s disabled for tenant %s",
                    self.name, self.tenant_id,
                )
                return {"status": "skipped", "reason": "disabled"}

            # Auto-disable after 5 consecutive failures
            if config.consecutive_failures >= 5:
                self.logger.warning(
                    "Watcher %s auto-disabled after %d consecutive failures",
                    self.name, config.consecutive_failures,
                )
                await session.execute(
                    update(WatchConfig)
                    .where(WatchConfig.id == config.id)
                    .values(enabled=False)
                )
                await session.commit()
                return {"status": "skipped", "reason": "auto_disabled"}

            # ── Phase 2: Create run record ────────────────────
            watcher_run = WatcherRun(
                id=run_id,
                tenant_id=self.tenant_id,
                watcher_name=self.name,
                status="running",
            )
            session.add(watcher_run)
            await session.commit()

        # ── Phase 3: Execute watcher logic ────────────────────
        try:
            await self.execute()
            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # ── Phase 4: Persist events and mark success ──────
            async with self.session_factory() as session:
                for evt_data in self._events:
                    event = WatchEvent(
                        tenant_id=self.tenant_id,
                        watcher_name=self.name,
                        run_id=run_id,
                        severity=evt_data.severity.value,
                        title=evt_data.title,
                        details=evt_data.details,
                        summary=evt_data.summary,
                    )
                    session.add(event)

                now = datetime.now(timezone.utc)
                await session.execute(
                    update(WatcherRun)
                    .where(WatcherRun.id == run_id)
                    .values(
                        status="success",
                        completed_at=now,
                        duration_ms=elapsed_ms,
                        events_generated=len(self._events),
                    )
                )

                # Reset consecutive failures and update last_run_at
                await session.execute(
                    update(WatchConfig)
                    .where(
                        WatchConfig.tenant_id == self.tenant_id,
                        WatchConfig.watcher_name == self.name,
                    )
                    .values(
                        consecutive_failures=0,
                        last_run_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

            self.logger.info(
                "Watcher %s completed: %d events in %dms",
                self.name, len(self._events), elapsed_ms,
            )
            return {
                "status": "success",
                "run_id": str(run_id),
                "events": len(self._events),
                "duration_ms": elapsed_ms,
            }

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            self.logger.exception("Watcher %s failed: %s", self.name, exc)

            # ── Phase 5: Record failure ───────────────────────
            async with self.session_factory() as session:
                now = datetime.now(timezone.utc)
                await session.execute(
                    update(WatcherRun)
                    .where(WatcherRun.id == run_id)
                    .values(
                        status="failed",
                        completed_at=now,
                        duration_ms=elapsed_ms,
                        error=str(exc),
                    )
                )

                # Increment consecutive_failures
                stmt = select(WatchConfig).where(
                    WatchConfig.tenant_id == self.tenant_id,
                    WatchConfig.watcher_name == self.name,
                )
                result = await session.execute(stmt)
                config = result.scalar_one_or_none()
                if config:
                    await session.execute(
                        update(WatchConfig)
                        .where(WatchConfig.id == config.id)
                        .values(
                            consecutive_failures=config.consecutive_failures + 1,
                            last_run_at=now,
                            updated_at=now,
                        )
                    )
                await session.commit()

            return {
                "status": "failed",
                "run_id": str(run_id),
                "error": str(exc),
                "duration_ms": elapsed_ms,
            }
