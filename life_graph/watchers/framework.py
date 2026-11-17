"""Watcher Framework — central registry and orchestrator.

Provides watcher registration, per-tenant execution, and
automatic config provisioning for new tenants.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.watchers.models import WatchConfig

if TYPE_CHECKING:
    from life_graph.watchers.base import BaseWatcher


class WatcherFramework:
    """Central registry and runner for all ambient watchers."""

    def __init__(self, session_factory, settings: dict[str, Any] | None = None):
        self.session_factory = session_factory
        self.settings = settings
        self._registry: dict[str, type[BaseWatcher]] = {}
        self.logger = logging.getLogger("watcher.framework")

    def register(self, watcher_class: type[BaseWatcher]) -> None:
        """Register a watcher class by its name."""
        self._registry[watcher_class.name] = watcher_class
        self.logger.debug("Registered watcher: %s", watcher_class.name)

    def register_defaults(self) -> int:
        """Register every watcher that ships with Life Graph. Returns the count.

        Only ``BaseWatcher`` subclasses are listed: ``run_watcher`` calls
        ``(tenant_id, session_factory, settings)`` and relies on the base
        class owning the run lifecycle, which the older ad-hoc watchers
        (``CodeQualityWatcher``, ``ServerHealthWatcher``) do not. Those are
        reached through ``workers.tasks.run_watchers``, which handles both
        conventions.

        Imported here rather than at module import so constructing a
        framework stays cheap for callers that register their own set.
        """
        from life_graph.watchers.agent_transcripts.watcher import AgentTranscriptWatcher
        from life_graph.watchers.dependency_watcher import DependencyWatcher
        from life_graph.watchers.page_monitor_watcher import PageMonitorWatcher
        from life_graph.watchers.tech_radar_watcher import TechRadarWatcher

        for watcher_class in (
            AgentTranscriptWatcher,
            DependencyWatcher,
            TechRadarWatcher,
            PageMonitorWatcher,
        ):
            self.register(watcher_class)
        return len(self._registry)

    def get_registered(self) -> dict[str, type[BaseWatcher]]:
        """Return a copy of the registered watcher classes."""
        return dict(self._registry)

    async def run_watcher(
        self,
        tenant_id: str,
        watcher_name: str,
    ) -> dict[str, Any]:
        """Instantiate and run a single watcher by name."""
        watcher_cls = self._registry.get(watcher_name)
        if not watcher_cls:
            return {"status": "error", "error": f"Unknown watcher: {watcher_name}"}

        watcher = watcher_cls(
            tenant_id=tenant_id,
            session_factory=self.session_factory,
            settings=self.settings,
        )
        return await watcher.run()

    async def run_all_for_tenant(
        self,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Run all enabled watchers for a tenant."""
        results: list[dict[str, Any]] = []

        async with self.session_factory() as session:
            stmt = select(WatchConfig).where(
                WatchConfig.tenant_id == tenant_id,
                WatchConfig.enabled == True,  # noqa: E712
            )
            result = await session.execute(stmt)
            configs = result.scalars().all()

        for config in configs:
            if config.watcher_name in self._registry:
                res = await self.run_watcher(tenant_id, config.watcher_name)
                results.append(res)
            else:
                self.logger.warning(
                    "Config exists for unregistered watcher: %s",
                    config.watcher_name,
                )

        return results

    async def ensure_configs(self, tenant_id: str) -> int:
        """Create default watch_configs for any registered watcher missing a config.

        Returns the number of configs created.
        """
        created = 0
        async with self.session_factory() as session:
            for name, cls in self._registry.items():
                stmt = select(WatchConfig).where(
                    WatchConfig.tenant_id == tenant_id,
                    WatchConfig.watcher_name == name,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is None:
                    config = WatchConfig(
                        tenant_id=tenant_id,
                        watcher_name=name,
                        display_name=cls.display_name,
                        schedule=cls.default_schedule,
                        enabled=True,
                    )
                    session.add(config)
                    created += 1

            if created:
                await session.commit()
                self.logger.info(
                    "Created %d default watcher configs for tenant %s",
                    created,
                    tenant_id,
                )

        return created
