"""Persona service — manages database-driven agent configurations.

Personas define agent behavior (system prompts, tools, model settings)
without code changes. The service handles CRUD operations, seeds
built-in personas for new tenants (6 conversational + 2 operational
agents that carry a pinned driver and verifier chain), and enforces
tenant-based tool permission filtering.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.kernel.propose_contract import (
    AGENT_TASK_PROPOSE_CONTRACT,
    COMMAND_PROPOSE_CONTRACT,
)
from life_graph.models.db import AgentPersona

logger = logging.getLogger(__name__)


# ── Built-in Persona Definitions ──────────────────────────────

_BUILTIN_PERSONAS: list[dict[str, Any]] = [
    {
        "name": "chief",
        "display_name": "Command Router",
        "icon": "🧠",
        "description": ("Classifies user intent and routes to the best specialist agent."),
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
        "description": ("Writes, reviews, debugs, and refactors code."),
        "system_prompt": (
            "You are Cody, a senior software engineer. You"
            " write clean, tested, production-ready code. You"
            " explain your reasoning and suggest improvements."
            " Always consider edge cases and error handling."
            + AGENT_TASK_PROPOSE_CONTRACT
        ),
        "intent_tags": ["code", "debug", "refactor"],
        "temperature": 0.4,
        "allowed_tools": [
            "file_read",
            "file_write",
            "run_command",
            "git_status",
            "git_log",
            "git_diff",
            "git_branch",
        ],
    },
    {
        "name": "rex",
        "display_name": "Research Analyst",
        "icon": "🔬",
        "description": ("Researches topics, answers questions, and synthesizes information."),
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
        "description": ("Manages deployments, infrastructure, and monitoring."),
        "system_prompt": (
            "You are Ops, a DevOps engineer. You manage"
            " deployments, containers, servers, and monitoring."
            " You prioritize reliability, security, and"
            " automation. Always explain risks before executing"
            " destructive operations."
            + COMMAND_PROPOSE_CONTRACT
        ),
        "intent_tags": ["deploy", "monitor", "infrastructure"],
        "temperature": 0.3,
        "allowed_tools": ["run_command"],
    },
    {
        "name": "penny",
        "display_name": "Data Analyst",
        "icon": "📊",
        "description": ("Analyzes data, queries databases, and builds analytics."),
        "system_prompt": (
            "You are Penny, a data analyst. You query"
            " databases, analyze datasets, build"
            " visualizations, and extract insights. You explain"
            " your methodology and highlight key findings."
        ),
        "intent_tags": ["data", "database", "analytics"],
        "temperature": 0.5,
        "allowed_tools": [
            "run_command",
            "file_read",
            "file_write",
        ],
    },
    {
        "name": "scribe",
        "display_name": "Documentation Writer",
        "icon": "📝",
        "description": ("Writes and maintains documentation, READMEs, and guides."),
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
    # ── Operational personas (Agent Drivers spec) ─────────────
    # These carry a pinned driver, task_types, and a verifier
    # chain so the dispatcher can run them unattended.
    {
        "name": "uzhavu-ops",
        "display_name": "Uzhavu Operations",
        "icon": "🚜",
        "description": (
            "Operates the Uzhavu platform — deploy checks, incident diagnosis, and fixes."
        ),
        "system_prompt": (
            "You are Uzhavu-Ops, the operator for the Uzhavu"
            " SaaS platform. You run deploy checks, diagnose"
            " incidents, and apply fixes. You prioritize"
            " reliability and safety: always explain the risk"
            " and blast radius before any destructive or"
            " production-affecting operation, and prefer the"
            " smallest reversible change that resolves the"
            " incident."
        ),
        "intent_tags": ["deploy", "incident", "uzhavu"],
        "temperature": 0.2,
        "allowed_tools": [
            "run_command",
            "git_status",
            "git_log",
            "git_diff",
            "git_branch",
            "web_search",
        ],
        "driver": "claude_code",
        "task_types": ["deploy_check", "incident_fix"],
        "verifier_chain": ["build_ok", "tests_pass"],
        "context_profile": {"domains": ["uzhavu", "infra"]},
    },
    {
        "name": "dependency-updater",
        "display_name": "Dependency Updater",
        "icon": "📦",
        "description": (
            "Turns dependency-watcher findings into safe upgrade"
            " PRs, running project tests before landing."
        ),
        "system_prompt": (
            "You are the Dependency Updater. You take dependency"
            " watcher findings and prepare minimal, safe version"
            " bumps. Prefer patch and minor upgrades; flag major"
            " version jumps for human review with a short"
            " migration note. Always run the project's tests and"
            " keep each change scoped to dependency manifests and"
            " lockfiles."
        ),
        "intent_tags": ["dependencies", "maintenance"],
        "temperature": 0.2,
        "allowed_tools": [
            "run_command",
            "git_status",
            "git_log",
            "git_diff",
            "git_branch",
            "file_read",
            "file_write",
        ],
        "driver": "claude_code",
        "task_types": ["dependency_update"],
        "verifier_chain": ["tests_pass", "diff_within_scope"],
        "context_profile": {"domains": ["dependencies", "infra"]},
    },
    # ── Personal-life personas (docs/specs/personal-roles.md) ──
    {
        "name": "tutor",
        "display_name": "Tech Tutor",
        "icon": "🎓",
        "description": "Tracks what you're learning, guides you, and checks understanding.",
        "system_prompt": (
            "You are Tutor. You help the user learn new technologies at their pace."
            " You check understanding before moving on, suggest small hands-on"
            " exercises, and track what they've already learned so you don't repeat"
            " yourself. Prefer teaching through building over lecturing."
            " End your reply with ONLY a JSON array of findings, each object "
            "{\"title\": str, \"detail\": str, \"urgency\": \"now\"|\"brief\"}. Use \"now\" "
            "only for genuinely time-sensitive items; use \"brief\" otherwise. If you have "
            "nothing new to report, return []."
        ),
        "intent_tags": ["learn", "tutorial", "study"],
        "temperature": 0.6,
        "allowed_tools": ["web_search", "memory_search"],
    },
    {
        "name": "scout",
        "display_name": "Knowledge Scout",
        "icon": "🧭",
        "description": "Ambiently researches topics useful to the user and surfaces findings.",
        "system_prompt": (
            "You are Scout. You research topics the user cares about and surface"
            " genuinely new, useful findings — not restatements of what you already"
            " reported. You never take action, only report."
            " End your reply with ONLY a JSON array of findings, each object "
            "{\"title\": str, \"detail\": str, \"urgency\": \"now\"|\"brief\"}. Use \"now\" "
            "only for genuinely time-sensitive items; use \"brief\" otherwise. If you have "
            "nothing new to report, return []."
        ),
        "intent_tags": ["research", "scout", "digest"],
        "temperature": 0.5,
        "allowed_tools": ["web_search", "browse_web", "memory_search"],
    },
    {
        "name": "admin",
        "display_name": "Work & Life Admin",
        "icon": "🗂️",
        "description": "Surfaces work/life admin items (bills, follow-ups, meeting prep) for review.",
        "system_prompt": (
            "You are Admin. You review the user's tracked commitments and surface"
            " anything that needs attention — nothing more. You never send, pay, or"
            " write anything on the user's behalf; you only report what you find."
            " End your reply with ONLY a JSON array of findings, each object "
            "{\"title\": str, \"detail\": str, \"urgency\": \"now\"|\"brief\"}. Use \"now\" "
            "only for genuinely time-sensitive items; use \"brief\" otherwise. If you have "
            "nothing new to report, return []."
        ),
        "intent_tags": ["admin", "reminder", "work"],
        "temperature": 0.4,
        "allowed_tools": ["memory_search", "get_current_datetime"],
    },
    {
        "name": "swe-lead",
        "display_name": "SWE Team Lead",
        "icon": "🧑‍💼",
        "description": "Coordinates cody/ops/rex on engineering work that needs more than one specialist.",
        "system_prompt": (
            "You are the SWE Team Lead. For work that needs more than one"
            " specialist, delegate sub-tasks to cody (code), ops (deploy/infra), or"
            " rex (research) using delegate_to_persona, then synthesize their"
            " results. For simple single-step work, just do it yourself — don't"
            " delegate needlessly."
        ),
        "intent_tags": ["team", "build", "project"],
        "temperature": 0.4,
        "allowed_tools": ["delegate_to_persona", "run_command", "git_status", "git_log", "git_diff", "git_branch"],
        "verifier_chain": ["tests_pass", "diff_within_scope"],
    },
    {
        "name": "jarvis",
        "display_name": "Jarvis",
        "icon": "🤖",
        "description": "Explicitly-invoked orchestrator for requests that span multiple roles.",
        "system_prompt": (
            "You are Jarvis, the orchestrator. The user selected you explicitly"
            " because their request spans more than one role, or because they"
            " want you personally to handle something. You may have your own"
            " tools beyond delegate_to_persona (e.g. web browsing) — if a task"
            " is simple and self-contained (looking something up, checking a"
            " page), use your own tool directly instead of delegating for it."
            " Never answer from memory what a tool could check for you live —"
            " if you have a browsing tool and the answer depends on current or"
            " verifiable page content, call it; do not guess or fabricate a"
            " plausible-looking answer. The moment ONE tool call returns"
            " usable, readable data that answers the question, STOP and report"
            " it — you have a hard cap on tool calls per turn, so do not spend"
            " it re-confirming an answer you already have against a second or"
            " third source. Only try another source if the first attempt"
            " genuinely failed (error, timeout, no relevant data) or its"
            " result was ambiguous. Reserve delegate_to_persona for"
            " subtasks that genuinely need a specific persona's specialized"
            " role. When delegating: first decide the MINIMUM set of personas"
            " needed. Always include any role the user named. Delegate to each"
            " chosen persona AT MOST ONCE via delegate_to_persona with a clear,"
            " self-contained subtask — do not delegate to the same persona"
            " repeatedly. Wait for their results, then synthesize a single"
            " coherent answer. If the request needs only one role, delegate"
            " once; never fan out redundantly."
        ),
        "intent_tags": [],
        "temperature": 0.4,
        "allowed_tools": ["delegate_to_persona"],
    },
]


class PersonaService:
    """Manages agent persona CRUD and built-in seeding.

    Uses the injected async session factory to open its own
    sessions, safe to call from any async context.
    """

    # get_by_name() is on the hot path for every chat turn (once directly,
    # once again inside ProcessManager.spawn()) — personas change rarely, so
    # a short-TTL in-process cache turns the second lookup into a cache hit.
    # This is a single-process cache: correct for a single uvicorn worker
    # (this deployment); a multi-worker deployment would need a shared cache
    # (e.g. Redis) instead for cross-worker invalidation.
    _CACHE_TTL_SECONDS = 30.0

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._name_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    def _invalidate_tenant_cache(self, tenant_id: str) -> None:
        """Drop all cached personas for *tenant_id* (called after any write)."""
        stale = [key for key in self._name_cache if key[0] == tenant_id]
        for key in stale:
            del self._name_cache[key]

    async def get_by_name(self, tenant_id: str, name: str) -> dict[str, Any] | None:
        """Look up a persona by tenant and unique name.

        Args:
            tenant_id: The tenant scope.
            name: The persona's unique name (e.g. 'cody').

        Returns:
            Dict representation of the persona, or None.
        """
        cache_key = (tenant_id, name)
        cached = self._name_cache.get(cache_key)
        if cached is not None:
            expires_at, persona = cached
            if expires_at > time.monotonic():
                return dict(persona)
            del self._name_cache[cache_key]

        async with self._session_factory() as session:
            stmt = select(AgentPersona).where(
                AgentPersona.tenant_id == tenant_id,
                AgentPersona.name == name,
                AgentPersona.is_active.is_(True),
            )
            result = await session.execute(stmt)
            persona_row = result.scalar_one_or_none()
            if persona_row is None:
                return None
            persona = self._persona_to_dict(persona_row)
            self._name_cache[cache_key] = (
                time.monotonic() + self._CACHE_TTL_SECONDS,
                persona,
            )
            return dict(persona)

    async def get_by_intent(self, tenant_id: str, intent: str) -> dict[str, Any] | None:
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
        """Insert missing built-in personas AND reconcile existing ones.

        Checks existing persona names (not just "does the tenant
        have any persona at all") so that newly-added built-ins
        reach tenants that were already seeded under an older
        version of _BUILTIN_PERSONAS — safe to call on every
        startup.

        The same reasoning applies to built-ins that *changed*, not
        only ones that were added: consumers (``TaskDispatcher.
        _load_persona``, ``kernel/process_manager._run_agent``) read
        the DB row, never ``_BUILTIN_PERSONAS``, so a tenant seeded
        under an older version would keep stale ``allowed_tools`` /
        ``system_prompt`` forever. Every ``is_builtin=True`` row is
        therefore reconciled against its definition on each call —
        but ONLY those two fields, and only when they actually
        differ (no no-op write on every startup). Rows a user
        created themselves (``is_builtin=False``) are never touched,
        and neither are the built-ins' other fields (display_name,
        icon, temperature, …), which the update API lets a user
        deliberately tweak.

        Args:
            tenant_id: The tenant to seed personas for.

        Returns:
            Total number of persona rows CHANGED — inserted **plus**
            reconciled — so ``0`` still means "this tenant was already
            fully up to date". The breakdown is not squeezed into the
            return value (it stays a plain ``int`` for the existing
            callers) but is logged: a summary line carrying both counts,
            plus one ``info`` line naming each reconciled persona and
            which fields drifted.
        """
        async with self._session_factory() as session:
            existing_stmt = select(
                AgentPersona.name,
                AgentPersona.is_builtin,
                AgentPersona.allowed_tools,
                AgentPersona.system_prompt,
            ).where(
                AgentPersona.tenant_id == tenant_id,
            )
            existing_result = await session.execute(existing_stmt)
            existing_rows = {row[0]: row for row in existing_result.all()}
            existing_names = set(existing_rows)

            count = 0
            reconciled = 0
            for defn in _BUILTIN_PERSONAS:
                if defn["name"] in existing_names:
                    reconciled += await self._reconcile_builtin(
                        session, tenant_id, defn, existing_rows[defn["name"]]
                    )
                    continue
                try:
                    # A SAVEPOINT scoped to this one persona: if the
                    # insert fails (e.g. a concurrent seed call for the
                    # same tenant beat us to this name), only this
                    # SAVEPOINT rolls back — not the whole transaction,
                    # which would otherwise discard every persona
                    # already flushed earlier in this loop.
                    async with session.begin_nested():
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
                            driver=defn.get("driver"),
                            verifier_chain=defn.get("verifier_chain", []),
                            context_profile=defn.get("context_profile", {}),
                            task_types=defn.get("task_types", []),
                            is_builtin=True,
                            is_active=True,
                        )
                        session.add(persona)
                        await session.flush()
                    count += 1
                except Exception:
                    # Duplicate — a concurrent seed call beat us to
                    # this one name. Skip it, keep seeding the rest.
                    logger.debug(
                        "Persona %s already exists for tenant %s — skip",
                        defn["name"],
                        tenant_id,
                    )
                    continue

            await session.commit()
            if count or reconciled:
                self._invalidate_tenant_cache(tenant_id)
            logger.info(
                "Seeded %d built-in personas for tenant %s (%d reconciled)",
                count,
                tenant_id,
                reconciled,
            )
            return count + reconciled

    @staticmethod
    async def _reconcile_builtin(
        session: AsyncSession,
        tenant_id: str,
        defn: dict[str, Any],
        row: Any,
    ) -> int:
        """Bring one already-seeded built-in row back in line with its
        definition. Returns 1 if an UPDATE was issued, else 0.

        Only ``allowed_tools`` and ``system_prompt`` are reconciled — see
        :meth:`seed_builtins`. A row whose ``is_builtin`` is False is a
        user-owned persona that merely shares the name; it is left alone.

        Bridged MCP tool names (``mcp_<server>_<tool>``, see
        ``services/mcp_bridge.py``) are excluded from the ``allowed_tools``
        comparison: they're never part of a builtin's static definition,
        only granted by hand via ``PATCH /personas/{id}`` once a server is
        configured. Comparing the full list would silently wipe that grant
        back out on every restart — comparing only the static subset lets
        it survive.
        """
        if not row.is_builtin:
            return 0

        values: dict[str, Any] = {}
        current_tools = list(row.allowed_tools) if row.allowed_tools is not None else None
        target_tools = defn["allowed_tools"]
        if target_tools is None:
            if current_tools is not None:
                values["allowed_tools"] = None
        else:
            static_current = (
                [t for t in current_tools if not t.startswith("mcp_")]
                if current_tools is not None
                else None
            )
            if static_current != target_tools:
                values["allowed_tools"] = target_tools
        if row.system_prompt != defn["system_prompt"]:
            values["system_prompt"] = defn["system_prompt"]
        if not values:
            return 0

        # updated_at is stamped by the column's own onupdate=_utcnow.
        await session.execute(
            update(AgentPersona)
            .where(
                AgentPersona.tenant_id == tenant_id,
                AgentPersona.name == defn["name"],
                AgentPersona.is_builtin.is_(True),
            )
            .values(**values)
        )
        logger.info(
            "Reconciled built-in persona %s for tenant %s (fields: %s)",
            defn["name"],
            tenant_id,
            sorted(values),
        )
        return 1

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
                raise ValueError(f"Persona '{name}' already exists")

            persona = AgentPersona(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                display_name=data.get("display_name"),
                description=data.get("description"),
                system_prompt=data["system_prompt"],
                model=data.get("model", "gemini/gemini-2.5-flash"),
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

            self._invalidate_tenant_cache(tenant_id)
            logger.info(
                "Created persona '%s' for tenant %s",
                name,
                tenant_id,
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

            if not include_inactive:
                base = base.where(
                    AgentPersona.is_active.is_(True),
                )

            # No limit/offset on this query -- every matching row is always
            # returned, so a separate COUNT(*) can never differ from
            # len(personas). Dropped it rather than running a second,
            # always-redundant query.
            stmt = base.order_by(
                AgentPersona.is_builtin.desc(),
                AgentPersona.name.asc(),
            )
            result = await session.execute(stmt)
            personas = [self._persona_to_dict(p) for p in result.scalars().all()]
            return personas, len(personas)

    async def get_by_id(
        self,
        tenant_id: str,
        persona_id: str,
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
            "display_name",
            "description",
            "system_prompt",
            "model",
            "temperature",
            "max_tokens",
            "allowed_tools",
            "intent_tags",
            "icon",
            "properties",
        }
        values = {k: v for k, v in data.items() if k in allowed_fields}
        if not values:
            return await self.get_by_id(
                tenant_id,
                persona_id,
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

        self._invalidate_tenant_cache(tenant_id)
        logger.info(
            "Updated persona %s (fields: %s)",
            persona_id,
            list(values.keys()),
        )
        return await self.get_by_id(tenant_id, persona_id)

    async def delete(
        self,
        tenant_id: str,
        persona_id: str,
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
            tenant_id,
            persona_id,
        )
        if persona is None:
            return None

        if persona["is_builtin"]:
            raise PermissionError(f"Cannot delete built-in persona '{persona['name']}'")

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

        self._invalidate_tenant_cache(tenant_id)
        logger.info(
            "Soft-deleted persona '%s' (%s)",
            persona["name"],
            persona_id,
        )
        return {
            "id": persona_id,
            "name": persona["name"],
            "message": "Persona deactivated",
        }

    # ── Tool Permission Filtering ────────────────────────

    # Tools restricted to admin/personal tenants only.
    SYSTEM_TOOLS = {
        "terminal",
        "git",
        "docker",
        "ssh",
        "file_write",
    }
    # Tools available to all tenants.
    SAFE_TOOLS = {
        "memory_search",
        "knowledge_query",
        "file_read",
        "web_search",
        "calculator",
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
        return [t for t in tools if t not in self.SYSTEM_TOOLS]

    @staticmethod
    def _is_admin_tenant(tenant_id: str) -> bool:
        """Check if a tenant has admin-level tool access."""
        admin_prefixes = (
            "default",
            "legacy",
            "personal",
            "admin",
        )
        return any(tenant_id.startswith(p) for p in admin_prefixes)

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
            "driver": persona.driver,
            "verifier_chain": persona.verifier_chain,
            "context_profile": persona.context_profile,
            "task_types": persona.task_types,
            "icon": persona.icon,
            "is_builtin": persona.is_builtin,
            "is_active": persona.is_active,
            "properties": persona.properties,
            "use_count": persona.use_count,
            "last_used_at": (persona.last_used_at.isoformat() if persona.last_used_at else None),
            "created_at": persona.created_at.isoformat(),
            "updated_at": persona.updated_at.isoformat(),
        }
