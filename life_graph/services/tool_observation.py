"""Tool-exhaust observation hook (Capture Spine).

Registered on the tool registry; after every tool execution it records an
observation capture event (``surface="tool_exhaust"``) so the substrate can
later cite what agents actually did. Applies two storage disciplines from the
capture-spine spec:

* **Redaction** — args are already summarized + secret-redacted by the
  registry (:func:`life_graph.core.redaction.summarize_args`).
* **Daily cap sampling** — once a tenant exceeds ``daily_cap`` observations in
  a day, further *low-signal* observations (successful, no project) are kept
  at only ``sample_rate`` to avoid drowning the spine in noise.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime

from sqlalchemy import func, select

from life_graph.core.events import event_bus
from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
from life_graph.models.db import CaptureEvent
from life_graph.services.capture import CaptureService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

DAILY_CAP = 500
LOW_SIGNAL_SAMPLE_RATE = 0.10
TOOL_EXHAUST_SURFACE = "tool_exhaust"


class ToolObservationHook:
    """Async post-exec hook that ingests tool observations into the spine."""

    def __init__(
        self,
        *,
        session_factory=None,
        bus=None,
        daily_cap: int = DAILY_CAP,
        sample_rate: float = LOW_SIGNAL_SAMPLE_RATE,
        rng=random.random,
    ) -> None:
        self._session_factory = session_factory or async_session
        self._bus = bus or event_bus
        self._daily_cap = daily_cap
        self._sample_rate = sample_rate
        self._rng = rng

    @staticmethod
    def is_low_signal(observation: dict) -> bool:
        """Low-signal = succeeded and not tied to a project (routine noise)."""
        return (
            observation.get("exit_status") == "ok"
            and not observation.get("project_id")
        )

    def should_store(self, count_today: int, low_signal: bool) -> bool:
        """Decide whether to persist, applying the daily cap to noise only.

        High-signal observations (errors, timeouts, project-scoped) always
        store. Low-signal ones store until the cap, then at ``sample_rate``.
        """
        if not low_signal:
            return True
        if count_today < self._daily_cap:
            return True
        return self._rng() < self._sample_rate

    async def __call__(self, observation: dict) -> None:
        """Post-exec hook entry point. No-op without tenant context."""
        if not has_tenant_context():
            return
        tenant_id = get_current_tenant_id()

        low_signal = self.is_low_signal(observation)
        count_today = await self._today_count(tenant_id) if low_signal else 0
        if not self.should_store(count_today, low_signal):
            return

        content = (
            f"tool:{observation.get('tool')} "
            f"status:{observation.get('exit_status')} "
            f"{observation.get('duration_ms')}ms "
            f"args:{observation.get('args_summary', '')}"
        )
        async with self._session_factory() as session:
            svc = CaptureService(session, self._bus)
            await svc.ingest(
                tenant_id=tenant_id,
                surface=TOOL_EXHAUST_SURFACE,
                content=content,
                modality="structured",
                properties=observation,
            )
            await session.commit()

    async def _today_count(self, tenant_id: str) -> int:
        """Count today's tool-exhaust observations for the tenant (UTC day)."""
        start_of_day = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(CaptureEvent)
                .where(
                    CaptureEvent.tenant_id == tenant_id,
                    CaptureEvent.surface == TOOL_EXHAUST_SURFACE,
                    CaptureEvent.occurred_at >= start_of_day,
                )
            )
            return int(result.scalar() or 0)
