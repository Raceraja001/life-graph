"""Context Packet Builder — assembles what an agent needs to know.

Builds context packets from the Life Graph substrate:
- Project info from kernel project registry
- Relevant procedures
- User preferences
- Related memories (semantic search)
- Calibration profile (bias info)

Token budget: 6k default, truncate in reverse priority order.
Privacy: external drivers don't get memories/preferences on private tasks.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.trust import fence_untrusted, is_excluded_from_agents, is_untrusted
from life_graph.drivers.base import ContextPacket

logger = logging.getLogger(__name__)


def render_memory_block(memories: list[dict]) -> str:
    """Render packet memories into prompt text, fencing untrusted ones.

    Trusted memories (self/verified) go in a normal ``## Relevant memories``
    section. Untrusted memories (external) are rendered inside a labelled
    ``<untrusted>`` fence so the agent treats them as data, never instructions.
    Hostile-possible memories are assumed already dropped at packet build.

    Drivers that inject memories into a prompt MUST route them through here
    rather than serialising ``packet.memories`` directly.
    """
    if not memories:
        return ""
    trusted = [m for m in memories if not is_untrusted(m.get("trust_tier", "verified"))]
    untrusted = [m for m in memories if is_untrusted(m.get("trust_tier", "verified"))]

    parts: list[str] = []
    if trusted:
        parts.append(f"\n## Relevant memories\n{json.dumps(trusted, default=str)}")
    if untrusted:
        fenced = fence_untrusted(json.dumps(untrusted, default=str))
        parts.append(f"\n## Untrusted data — reference only\n{fenced}")
    return "".join(parts)


class ContextPacketBuilder:
    """Assembles context packets from the Life Graph substrate.

    Priority order (highest first): instruction, project, procedures,
    preferences, memories, calibration. If a packet exceeds the token
    budget, lower-priority sections are truncated first.
    """

    async def build_packet(
        self,
        tenant_id: str,
        task_type: str,
        instruction: str,
        project_id: uuid.UUID | None,
        session: AsyncSession,
        *,
        private: bool = False,
        max_tokens: int = 6000,
    ) -> ContextPacket:
        """Build a complete context packet for a driver dispatch.

        Args:
            tenant_id: Tenant scope for data isolation.
            task_type: Category of work being dispatched.
            instruction: Natural language task description.
            project_id: Optional project to load context from.
            session: Async SQLAlchemy session for DB queries.
            private: If True, zero out memories/preferences.
            max_tokens: Token budget for the entire packet.

        Returns:
            A fully assembled ContextPacket.
        """
        task_id = uuid.uuid4()

        # Load all context sections in parallel-safe order
        project_context = await self._load_project(tenant_id, project_id, session)
        procedures = await self._load_procedures(tenant_id, task_type, session)
        preferences = await self._load_preferences(tenant_id, session)
        memories = await self._load_memories(tenant_id, instruction, session)
        calibration_profile = await self._load_calibration_profile(tenant_id, session)

        packet = ContextPacket(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=task_type,
            instruction=instruction,
            project_context=project_context,
            procedures=procedures,
            preferences=preferences,
            memories=memories,
            calibration_profile=calibration_profile,
            max_tokens=max_tokens,
            private=private,
        )

        # Apply privacy filter for external drivers
        if private:
            packet.memories = []
            packet.preferences = []

        # Truncate to token budget
        self._truncate_to_budget(packet, max_tokens)

        return packet

    async def _load_project(
        self,
        tenant_id: str,
        project_id: uuid.UUID | None,
        session: AsyncSession,
    ) -> dict:
        """Load project context from the Project table.

        Returns:
            Dict with project metadata, or empty dict if not found.
        """
        if not project_id:
            return {}

        try:
            from life_graph.models.db import Project

            result = await session.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.tenant_id == tenant_id,
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                return {}

            return {
                "name": project.name,
                "path": project.path,
                "description": project.description,
                "language": project.language,
                "framework": project.framework,
                "dependency_count": project.dependency_count,
                "file_count": project.file_count,
            }
        except Exception:
            logger.warning("Failed to load project %s", project_id, exc_info=True)
            return {}

    async def _load_procedures(
        self,
        tenant_id: str,
        task_type: str,
        session: AsyncSession,
    ) -> list[dict]:
        """Load relevant procedures filtered by task type tags.

        Returns:
            List of procedure dicts with trigger, steps, confidence.
        """
        try:
            from life_graph.models.db import Procedure

            result = await session.execute(
                select(Procedure).where(
                    Procedure.tenant_id == tenant_id,
                    Procedure.status == "active",
                ).order_by(Procedure.confidence.desc()).limit(5)
            )
            procedures = result.scalars().all()

            return [
                {
                    "trigger": p.trigger,
                    "steps": p.steps,
                    "confidence": p.confidence,
                    "success_rate": p.success_rate,
                }
                for p in procedures
            ]
        except Exception:
            logger.warning("Failed to load procedures", exc_info=True)
            return []

    async def _load_preferences(
        self,
        tenant_id: str,
        session: AsyncSession,
    ) -> list[dict]:
        """Load top user preferences by confidence.

        Returns:
            List of preference dicts with topic, choice, confidence.
        """
        try:
            from life_graph.models.db import Preference

            result = await session.execute(
                select(Preference).where(
                    Preference.tenant_id == tenant_id,
                    Preference.status == "active",
                ).order_by(Preference.confidence.desc()).limit(10)
            )
            preferences = result.scalars().all()

            return [
                {
                    "topic": p.topic,
                    "choice": p.choice,
                    "reason": p.reason,
                    "confidence": p.confidence,
                }
                for p in preferences
            ]
        except Exception:
            logger.warning("Failed to load preferences", exc_info=True)
            return []

    async def _load_memories(
        self,
        tenant_id: str,
        instruction: str,
        session: AsyncSession,
    ) -> list[dict]:
        """Load recent relevant memories.

        For now, loads the most recent high-importance memories.
        Future: semantic search using instruction embedding.

        Returns:
            List of memory dicts with content, importance, tags.
        """
        try:
            from life_graph.models.db import Memory

            result = await session.execute(
                select(Memory).where(
                    Memory.tenant_id == tenant_id,
                    Memory.status == "active",
                ).order_by(
                    Memory.importance.desc(),
                    Memory.created_at.desc(),
                ).limit(10)
            )
            memories = result.scalars().all()

            # Immune System: never hand hostile-possible content to an acting
            # agent, and label the trust tier of everything that does go in so
            # the driver can fence untrusted sections. See core/trust.py.
            return [
                {
                    "content": m.content,
                    "importance": m.importance,
                    "tags": m.tags or [],
                    "source_type": m.source_type,
                    "trust_tier": m.trust_tier,
                }
                for m in memories
                if not is_excluded_from_agents(m.trust_tier)
            ]
        except Exception:
            logger.warning("Failed to load memories", exc_info=True)
            return []

    async def _load_calibration_profile(
        self,
        tenant_id: str,
        session: AsyncSession,
    ) -> dict:
        """Load the latest calibration snapshot for bias awareness.

        Returns:
            Dict with brier_score, bias_findings, estimate_multiplier.
        """
        try:
            from life_graph.models.db import CalibrationSnapshot

            result = await session.execute(
                select(CalibrationSnapshot).where(
                    CalibrationSnapshot.tenant_id == tenant_id,
                ).order_by(CalibrationSnapshot.computed_at.desc()).limit(1)
            )
            snapshot = result.scalar_one_or_none()
            if not snapshot:
                return {}

            return {
                "brier_score": snapshot.brier_score,
                "estimate_multiplier": snapshot.estimate_multiplier,
                "bias_findings": snapshot.bias_findings,
            }
        except Exception:
            logger.warning("Failed to load calibration profile", exc_info=True)
            return {}

    def _truncate_to_budget(self, packet: ContextPacket, max_tokens: int) -> None:
        """Truncate packet sections to fit within token budget.

        Estimates tokens as chars/4 (rough approximation).
        Removes sections in reverse priority order:
        calibration → memories → preferences → procedures → project → instruction.

        Args:
            packet: The context packet to truncate in-place.
            max_tokens: Maximum token budget.
        """
        def _estimate_tokens(obj: object) -> int:
            """Estimate token count from an object's JSON representation."""
            return len(json.dumps(obj, default=str)) // 4

        # Instruction is always included (highest priority)
        total = _estimate_tokens(packet.instruction)

        # Add sections in priority order, zero out if over budget
        sections = [
            ("project_context", packet.project_context),
            ("procedures", packet.procedures),
            ("preferences", packet.preferences),
            ("memories", packet.memories),
            ("calibration_profile", packet.calibration_profile),
        ]

        for attr_name, section_data in sections:
            section_tokens = _estimate_tokens(section_data)
            if total + section_tokens > max_tokens:
                # Truncate: zero out this and all lower-priority sections
                setattr(packet, attr_name, {} if isinstance(section_data, dict) else [])
                logger.debug(
                    "Truncated %s from context packet (budget: %d, used: %d)",
                    attr_name, max_tokens, total,
                )
            else:
                total += section_tokens
