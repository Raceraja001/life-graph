"""Prompt version service — manages prompt versioning with atomic activation.

Supports create, activate (atomic swap), rollback, and version listing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.self_improving.models import PromptVersion
from life_graph.self_improving.schemas import (
    PromptVersionCreate,
    PromptVersionResponse,
)

logger = logging.getLogger(__name__)


class PromptVersionService:
    """Service layer for prompt version management."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._sf = session_factory

    async def create(
        self, tenant_id: str, data: PromptVersionCreate,
    ) -> PromptVersionResponse:
        """Create a new prompt version with auto-incremented version_number."""
        async with self._sf() as session:
            # Get next version number
            stmt = select(func.coalesce(
                func.max(PromptVersion.version_number), 0,
            )).where(
                PromptVersion.tenant_id == tenant_id,
                PromptVersion.task_type == data.task_type,
            )
            result = await session.execute(stmt)
            max_version = result.scalar_one()
            next_version = max_version + 1

            version = PromptVersion(
                tenant_id=tenant_id,
                task_type=data.task_type,
                version_number=next_version,
                prompt_text=data.prompt_text,
                few_shot_examples=data.few_shot_examples,
                created_by=data.created_by,
                change_note=data.change_note,
                is_active=False,
            )
            session.add(version)
            await session.commit()
            await session.refresh(version)
            return PromptVersionResponse.model_validate(version)

    async def get_active(
        self, tenant_id: str, task_type: str,
    ) -> PromptVersionResponse | None:
        """Get the currently active prompt version for a task type."""
        async with self._sf() as session:
            stmt = select(PromptVersion).where(
                PromptVersion.tenant_id == tenant_id,
                PromptVersion.task_type == task_type,
                PromptVersion.is_active.is_(True),
            )
            result = await session.execute(stmt)
            version = result.scalar_one_or_none()
            if not version:
                return None
            return PromptVersionResponse.model_validate(version)

    async def list_versions(
        self, tenant_id: str, task_type: str,
    ) -> list[PromptVersionResponse]:
        """List all versions for a task type, sorted by version_number DESC."""
        async with self._sf() as session:
            stmt = (
                select(PromptVersion)
                .where(
                    PromptVersion.tenant_id == tenant_id,
                    PromptVersion.task_type == task_type,
                )
                .order_by(PromptVersion.version_number.desc())
            )
            result = await session.execute(stmt)
            versions = result.scalars().all()
            return [PromptVersionResponse.model_validate(v) for v in versions]

    async def activate(
        self, tenant_id: str, version_id: uuid.UUID,
        reason: str | None = None,
    ) -> PromptVersionResponse:
        """Atomically swap the active version: deactivate current, activate new.

        Uses a single transaction for consistency.
        """
        now = datetime.now(timezone.utc)

        async with self._sf() as session:
            async with session.begin():
                # Get the version to activate
                stmt = select(PromptVersion).where(
                    PromptVersion.id == version_id,
                    PromptVersion.tenant_id == tenant_id,
                )
                result = await session.execute(stmt)
                version = result.scalar_one_or_none()
                if not version:
                    raise ValueError(
                        f"Version {version_id} not found for tenant {tenant_id}"
                    )

                # Deactivate current active version for this task_type
                await session.execute(
                    update(PromptVersion)
                    .where(
                        PromptVersion.tenant_id == tenant_id,
                        PromptVersion.task_type == version.task_type,
                        PromptVersion.is_active.is_(True),
                    )
                    .values(
                        is_active=False,
                        deactivated_at=now,
                    )
                )

                # Activate the new version
                version.is_active = True
                version.activated_at = now
                version.deactivated_at = None
                if reason:
                    version.change_note = reason

            # session.begin() auto-commits on exit
            await session.refresh(version)
            return PromptVersionResponse.model_validate(version)

    async def rollback(
        self, tenant_id: str, version_id: uuid.UUID,
        reason: str = "manual_rollback",
    ) -> PromptVersionResponse:
        """Deactivate the current active version and reactivate a previous one."""
        return await self.activate(tenant_id, version_id, reason=reason)

    async def get_version(
        self, version_id: uuid.UUID,
    ) -> PromptVersionResponse:
        """Get a single prompt version by ID."""
        async with self._sf() as session:
            stmt = select(PromptVersion).where(
                PromptVersion.id == version_id,
            )
            result = await session.execute(stmt)
            version = result.scalar_one_or_none()
            if not version:
                raise ValueError(f"Version {version_id} not found")
            return PromptVersionResponse.model_validate(version)
