"""Persona service — manages database-driven agent configurations.

Personas define agent behavior (system prompts, tools, model settings)
without code changes. The service handles CRUD operations, seeds
6 built-in personas for new tenants, and enforces tenant-based
tool permission filtering.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import AgentPersona

logger = logging.getLogger(__name__)


# ── Built-in Persona Definitions ──────────────────────────────

_BUILTIN_PERSONAS: list[dict[str, Any]] = [
    {
        "name": "chief",
        "display_name": "Command Router",
        "icon": "🧠",
        "description": (
            "Classifies user intent and routes to the best"
            " specialist agent."
        ),
        "system_prompt": (
            "You are the Chief Router for Life Graph. Your job"
            " is to classify the user's intent and route their"
            " request to the best specialist agent. Analyze the"
            " message carefully, determine the primary intent"
            " (code, research, deploy, data, docs, or general),"
            " and respond with the agent name to route to."
        ),
        "intent_tags": ["general"],
        "temperature": 0.3,
        "allowed_tools": None,
    },
    {
        "name": "cody",
        "display_name": "Code Specialist",
        "icon": "🧑‍💻",
        "description": (
            "Writes, reviews, debugs, and refactors code."
        ),
        "system_prompt": (
            "You are Cody, a senior software engineer. You"
            " write clean, tested, production-ready code. You"
            " explain your reasoning and suggest improvements."
            " Always consider edge cases and error handling."
        ),
        "intent_tags": ["code", "debug", "refactor"],
        "temperature": 0.4,
        "allowed_tools": [
            "file_read",
            "file_write",
            "terminal",
            "git",
        ],
    },
    {
        "name": "rex",
        "display_name": "Research Analyst",
        "icon": "🔬",
        "description": (
            "Researches topics, answers questions, and"
            " synthesizes information."
        ),
        "system_prompt": (
            "You are Rex, a research analyst. You search for"
            " information, synthesize findings, and provide"
            " well-sourced answers. You cite your sources and"
            " distinguish facts from opinions."
        ),
        "intent_tags": ["research", "question"],
        "temperature": 0.7,
        "allowed_tools": ["web_search", "memory_search"],
    },
    {
        "name": "ops",
        "display_name": "DevOps Engineer",
        "icon": "⚙️",
        "description": (
            "Manages deployments, infrastructure, and"
            " monitoring."
        ),
        "system_prompt": (
            "You are Ops, a DevOps engineer. You manage"
            " deployments, containers, servers, and monitoring."
            " You prioritize reliability, security, and"
            " automation. Always explain risks before executing"
            " destructive operations."
        ),
        "intent_tags": ["deploy", "monitor", "infrastructure"],
        "temperature": 0.3,
        "allowed_tools": ["terminal", "docker", "ssh"],
    },
    {
        "name": "penny",
        "display_name": "Data Analyst",
        "icon": "📊",
        "description": (
            "Analyzes data, queries databases, and builds"
            " analytics."
        ),
        "system_prompt": (
            "You are Penny, a data analyst. You query"
            " databases, analyze datasets, build"
            " visualizations, and extract insights. You explain"
            " your methodology and highlight key findings."
        ),
        "intent_tags": ["data", "database", "analytics"],
        "temperature": 0.5,
        "allowed_tools": [
            "terminal",
            "file_read",
            "file_write",
        ],
    },
    {
        "name": "scribe",
        "display_name": "Documentation Writer",
        "icon": "📝",
        "description": (
            "Writes and maintains documentation, READMEs, and"
            " guides."
        ),
        "system_prompt": (
            "You are Scribe, a technical writer. You create"
            " clear, well-structured documentation. You write"
            " READMEs, API docs, guides, and changelogs. You"
            " follow the project's existing style and tone."
        ),
        "intent_tags": ["docs", "documentation"],
        "temperature": 0.6,
        "allowed_tools": [
            "file_read",
            "file_write",
            "memory_search",
        ],
    },
]


class PersonaService:
    """Manages agent persona CRUD and built-in seeding.

    Uses the injected async session factory to open its own
    sessions, safe to call from any async context.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def get_by_name(
        self, tenant_id: str, name: str
    ) -> dict[str, Any] | None:
        """Look up a persona by tenant and unique name.

        Args:
            tenant_id: The tenant scope.
            name: The persona's unique name (e.g. 'cody').

        Returns:
            Dict representation of the persona, or None.
        """
        async with self._session_factory() as session:
            stmt = select(AgentPersona).where(
                AgentPersona.tenant_id == tenant_id,
                AgentPersona.name == name,
                AgentPersona.is_active.is_(True),
            )
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()
            if persona is None:
                return None
            return self._persona_to_dict(persona)

    async def get_by_intent(
        self, tenant_id: str, intent: str
    ) -> dict[str, Any] | None:
        """Find the first active persona matching *intent*.

        Queries personas whose intent_tags array contains the
        given intent string.

        Args:
            tenant_id: The tenant scope.
            intent: The classified intent string.

        Returns:
            Dict representation of the matching persona, or None.
        """
        async with self._session_factory() as session:
            stmt = select(AgentPersona).where(
                AgentPersona.tenant_id == tenant_id,
                AgentPersona.is_active.is_(True),
                AgentPersona.intent_tags.any(intent),
            )
            result = await session.execute(stmt)
            persona = result.scalars().first()
            if persona is None:
                return None
            return self._persona_to_dict(persona)

    async def seed_builtins(self, tenant_id: str) -> int:
        """Insert built-in personas if none exist for this tenant.

        Uses INSERT with conflict handling to be idempotent — safe to
        call on every startup without crashing on duplicates.

        Args:
            tenant_id: The tenant to seed personas for.

        Returns:
            Number of personas inserted (0 if already seeded).
        """
        async with self._session_factory() as session:
            # Check if tenant already has personas
            check = (
                select(AgentPersona.id)
                .where(AgentPersona.tenant_id == tenant_id)
                .limit(1)
            )
            existing = await session.execute(check)
            if existing.scalar_one_or_none() is not None:
                logger.debug(
                    "Tenant %s already has personas — skip seed",
                    tenant_id,
                )
                return 0

            count = 0
            for defn in _BUILTIN_PERSONAS:
                try:
                    persona = AgentPersona(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        name=defn["name"],
                        display_name=defn["display_name"],
                        icon=defn["icon"],
                        description=defn["description"],
                        system_prompt=defn["system_prompt"],
                        model="gemini/gemini-2.5-flash",
                        temperature=defn["temperature"],
                        max_tokens=4096,
                        allowed_tools=defn["allowed_tools"],
                        intent_tags=defn["intent_tags"],
                        is_builtin=True,
                        is_active=True,
                    )
                    session.add(persona)
                    await session.flush()
                    count += 1
                except Exception:
                    # Duplicate — already exists, skip
                    await session.rollback()
                    logger.debug(
                        "Persona %s already exists for tenant %s — skip",
                        defn["name"],
                        tenant_id,
                    )
                    return 0

            await session.commit()
            logger.info(
                "Seeded %d built-in personas for tenant %s",
                count,
                tenant_id,
            )
            return count

    # ── CRUD Operations ──────────────────────────────────

    async def create(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new custom persona.

        Args:
            tenant_id: Tenant scope.
            data: Persona fields (name, system_prompt, etc.).

        Returns:
            Dict representation of the created persona.

        Raises:
            ValueError: If name already exists for tenant.
        """
        name = data["name"]

        async with self._session_factory() as session:
            # Check uniqueness
            existing = await session.execute(
                select(AgentPersona.id).where(
                    AgentPersona.tenant_id == tenant_id,
                    AgentPersona.name == name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(
                    f"Persona '{name}' already exists"
                )

            persona = AgentPersona(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                display_name=data.get("display_name"),
                description=data.get("description"),
                system_prompt=data["system_prompt"],
                model=data.get(
                    "model", "gemini/gemini-2.5-flash"
                ),
                temperature=data.get("temperature", 0.7),
                max_tokens=data.get("max_tokens", 4096),
                allowed_tools=data.get("allowed_tools"),
                intent_tags=data.get("intent_tags"),
                icon=data.get("icon"),
                is_builtin=False,
                is_active=True,
                properties=data.get("properties", {}),
            )
            session.add(persona)
            await session.commit()
            await session.refresh(persona)

            logger.info(
                "Created persona '%s' for tenant %s",
                name, tenant_id,
            )
            return self._persona_to_dict(persona)

    async def list_all(
        self,
        tenant_id: str,
        *,
        include_inactive: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """List all personas for a tenant.

        Args:
            tenant_id: Tenant scope.
            include_inactive: If True, include soft-deleted.

        Returns:
            Tuple of (persona dicts, total count).
        """
        async with self._session_factory() as session:
            base = select(AgentPersona).where(
                AgentPersona.tenant_id == tenant_id,
            )
            count_base = (
                select(func.count())
                .select_from(AgentPersona)
                .where(AgentPersona.tenant_id == tenant_id)
            )

            if not include_inactive:
                base = base.where(
                    AgentPersona.is_active.is_(True),
                )
                count_base = count_base.where(
                    AgentPersona.is_active.is_(True),
                )

            count_result = await session.execute(count_base)
            total = count_result.scalar() or 0

            stmt = base.order_by(
                AgentPersona.is_builtin.desc(),
                AgentPersona.name.asc(),
            )
            result = await session.execute(stmt)
            personas = [
                self._persona_to_dict(p)
                for p in result.scalars().all()
            ]
            return personas, total

    async def get_by_id(
        self, tenant_id: str, persona_id: str,
    ) -> dict[str, Any] | None:
        """Get a persona by UUID.

        Args:
            tenant_id: Tenant scope.
            persona_id: Persona UUID string.

        Returns:
            Dict representation, or None if not found.
        """
        async with self._session_factory() as session:
            stmt = select(AgentPersona).where(
                AgentPersona.id == uuid.UUID(persona_id),
                AgentPersona.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()
            if persona is None:
                return None
            return self._persona_to_dict(persona)

    async def update(
        self,
        tenant_id: str,
        persona_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Partially update a persona.

        Args:
            tenant_id: Tenant scope.
            persona_id: Persona UUID string.
            data: Fields to update (partial).

        Returns:
            Updated persona dict, or None if not found.
        """
        # Whitelist of updatable fields
        allowed_fields = {
            "display_name", "description", "system_prompt",
            "model", "temperature", "max_tokens",
            "allowed_tools", "intent_tags", "icon",
            "properties",
        }
        values = {
            k: v for k, v in data.items()
            if k in allowed_fields
        }
        if not values:
            return await self.get_by_id(
                tenant_id, persona_id,
            )

        values["updated_at"] = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            stmt = (
                update(AgentPersona)
                .where(
                    AgentPersona.id == uuid.UUID(persona_id),
                    AgentPersona.tenant_id == tenant_id,
                )
                .values(**values)
                .returning(AgentPersona.id)
            )
            result = await session.execute(stmt)
            updated_id = result.scalar_one_or_none()
            if updated_id is None:
                return None
            await session.commit()

        logger.info(
            "Updated persona %s (fields: %s)",
            persona_id,
            list(values.keys()),
        )
        return await self.get_by_id(tenant_id, persona_id)

    async def delete(
        self, tenant_id: str, persona_id: str,
    ) -> dict[str, Any] | None:
        """Soft-delete a persona (set is_active=False).

        Built-in personas cannot be deleted.

        Args:
            tenant_id: Tenant scope.
            persona_id: Persona UUID string.

        Returns:
            Dict with id/name/message, or None if not found.

        Raises:
            PermissionError: If persona is built-in.
        """
        persona = await self.get_by_id(
            tenant_id, persona_id,
        )
        if persona is None:
            return None

        if persona["is_builtin"]:
            raise PermissionError(
                f"Cannot delete built-in persona "
                f"'{persona['name']}'"
            )

        async with self._session_factory() as session:
            await session.execute(
                update(AgentPersona)
                .where(
                    AgentPersona.id == uuid.UUID(persona_id),
                    AgentPersona.tenant_id == tenant_id,
                )
                .values(
                    is_active=False,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        logger.info(
            "Soft-deleted persona '%s' (%s)",
            persona["name"], persona_id,
        )
        return {
            "id": persona_id,
            "name": persona["name"],
            "message": "Persona deactivated",
        }

    # ── Tool Permission Filtering ────────────────────────

    # Tools restricted to admin/personal tenants only.
    SYSTEM_TOOLS = {
        "terminal", "git", "docker", "ssh", "file_write",
    }
    # Tools available to all tenants.
    SAFE_TOOLS = {
        "memory_search", "knowledge_query", "file_read",
        "web_search", "calculator",
    }

    def resolve_tools(
        self,
        persona: dict[str, Any],
        tenant_id: str,
    ) -> list[str]:
        """Resolve allowed tools based on persona + tenant.

        For admin/personal tenants, the persona's full
        allowed_tools list is returned. For customer tenants,
        system/write tools are filtered out.

        Args:
            persona: Persona dict with allowed_tools.
            tenant_id: Tenant ID to check permissions.

        Returns:
            Filtered list of tool names.
        """
        tools = persona.get("allowed_tools") or []
        if not tools:
            return []

        # Admin/personal/legacy tenants get full access
        if self._is_admin_tenant(tenant_id):
            return list(tools)

        # Customer tenants: strip system tools
        return [
            t for t in tools
            if t not in self.SYSTEM_TOOLS
        ]

    @staticmethod
    def _is_admin_tenant(tenant_id: str) -> bool:
        """Check if a tenant has admin-level tool access."""
        admin_prefixes = (
            "default", "legacy", "personal", "admin",
        )
        return any(
            tenant_id.startswith(p) for p in admin_prefixes
        )

    @staticmethod
    def _persona_to_dict(
        persona: AgentPersona,
    ) -> dict[str, Any]:
        """Convert an AgentPersona ORM instance to a plain dict."""
        return {
            "id": str(persona.id),
            "tenant_id": persona.tenant_id,
            "name": persona.name,
            "display_name": persona.display_name,
            "description": persona.description,
            "system_prompt": persona.system_prompt,
            "model": persona.model,
            "temperature": persona.temperature,
            "max_tokens": persona.max_tokens,
            "allowed_tools": persona.allowed_tools,
            "intent_tags": persona.intent_tags,
            "icon": persona.icon,
            "is_builtin": persona.is_builtin,
            "is_active": persona.is_active,
            "properties": persona.properties,
            "use_count": persona.use_count,
            "last_used_at": (
                persona.last_used_at.isoformat()
                if persona.last_used_at
                else None
            ),
            "created_at": persona.created_at.isoformat(),
            "updated_at": persona.updated_at.isoformat(),
        }
