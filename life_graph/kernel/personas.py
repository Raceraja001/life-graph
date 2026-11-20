"""Persona service — manages database-driven agent configurations.

Personas define agent behavior (system prompts, tools, model settings)
without code changes; the built-in ones are data files in
kernel/builtin_personas/, loaded by kernel/persona_files.py. The service
handles CRUD operations, seeds built-in personas for new tenants, and
enforces tenant-based tool permission filtering. The roster (docs/design/11_persona_roster_plan.md):
jarvis is the lead the user talks to; scout, admin, tutor, cody and ops are
its workers; support-desk answers customers; the code-fixer engines and
dependency-updater run dev tasks. RETIRED_PERSONAS are kept but switched off.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from life_graph.config import settings
from life_graph.kernel.persona_files import load_builtin_personas, load_fragments
from life_graph.models.db import AgentPersona

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


# ── Built-in Persona Definitions ──────────────────────────────

# One Markdown file per persona in kernel/builtin_personas/ (header: fields;
# body: the system prompt), read once at import. Editing a file changes the
# seeded persona on the next start: seed_builtins reconciles existing rows.
_BUILTIN_PERSONAS: list[dict[str, Any]] = load_builtin_personas()

# The shared passages the code-fixer prompts put in, as they appear there
# (with the leading space); tests check the prompts carry them.
_FRAGMENTS = load_fragments()
_UNDERSTANDING_ASK = " " + _FRAGMENTS["understanding_ask"]
_TEST_FIRST_CODE_EDIT = " " + _FRAGMENTS["test_first_code_edit"]

# Retired by the roster plan (docs/design/11_persona_roster_plan.md): Jarvis
# took over their work. Deactivated, never deleted, so their conversations
# stay readable; seeding keeps them off (seed_builtins, _reconcile_builtin).
RETIRED_PERSONAS: frozenset[str] = frozenset(
    {"assistant", "chief", "penny", "swe-lead", "rex", "scribe", "uzhavu-ops"}
)

# Tools that read or change files, run commands or inspect the host. Jarvis
# holds none of them (see its allowed_tools); the workers it delegates to do.
HOST_TOOLS: frozenset[str] = frozenset(
    {
        "file_read",
        "file_write",
        "code_read",
        "code_search",
        "code_list",
        "code_edit",
        "run_command",
        "run_tests",
        "git_status",
        "git_log",
        "git_diff",
        "git_branch",
        "inspect_system",
    }
)


def _seed_model(defn: dict[str, Any]) -> str:
    """The model a built-in persona is first seeded with: the configured agent
    model, except a cloud-driver persona, which must start on a free cloud
    model (drivers/cloud.py refuses anything else)."""
    if defn.get("driver") == "cloud" and settings.dev_cloud_models_list:
        return settings.dev_cloud_models_list[0]
    return settings.agent_llm_model


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
            stmt = (
                select(AgentPersona)
                .where(
                    AgentPersona.tenant_id == tenant_id,
                    AgentPersona.is_active.is_(True),
                    AgentPersona.intent_tags.any(intent),
                )
                # Several personas share an intent ("code": cody and every
                # code-fixer). Without an order Postgres returned whichever
                # row it read first, and adding code-fixer-cloud flipped chat
                # routing to code-fixer (CI, 2026-10-19). A chat message goes
                # to a conversational persona first; driver-pinned personas
                # are for dev tasks.
                .order_by(
                    AgentPersona.driver.is_not(None),
                    AgentPersona.created_at,
                    AgentPersona.name,
                )
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
        ``system_prompt`` /
        ``driver`` /
        ``verifier_chain`` /
        ``task_types`` forever. Every ``is_builtin=True`` row is
        therefore reconciled against its definition on each call —
        but ONLY those five fields, and only when they actually
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
                # Reconciled too — a tenant seeded before migration 021 has
                # these NULL/empty and nothing else ever fills them in.
                AgentPersona.driver,
                AgentPersona.verifier_chain,
                AgentPersona.task_types,
                AgentPersona.is_active,
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
                            # Never hardcode a model id here: gemini-2.5-flash was
                            # seeded long after it started 404ing for new API keys,
                            # so every freshly seeded tenant arrived broken. The
                            # configured default is what the orchestrator itself
                            # falls back to (orchestrator.py), so they agree.
                            model=_seed_model(defn),
                            temperature=defn["temperature"],
                            max_tokens=4096,
                            allowed_tools=defn["allowed_tools"],
                            intent_tags=defn["intent_tags"],
                            driver=defn.get("driver"),
                            verifier_chain=defn.get("verifier_chain", []),
                            context_profile=defn.get("context_profile", {}),
                            task_types=defn.get("task_types", []),
                            is_builtin=True,
                            is_active=defn["name"] not in RETIRED_PERSONAS,
                        )
                        session.add(persona)
                        await session.flush()
                    count += 1
                except IntegrityError:
                    # Duplicate — a concurrent seed call beat us to
                    # this one name. Skip it, keep seeding the rest.
                    logger.debug(
                        "Persona %s already exists for tenant %s — skip",
                        defn["name"],
                        tenant_id,
                    )
                    continue
                except Exception:
                    # Anything else is a real failure, not a duplicate:
                    # still skip this one persona, but say so.
                    logger.warning(
                        "Persona %s could not be seeded for tenant %s",
                        defn["name"],
                        tenant_id,
                        exc_info=True,
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

        Reconciles ``allowed_tools``, ``system_prompt``, and the three
        driver-loop columns added in migration 021 — ``driver``,
        ``verifier_chain``, ``task_types``. A row whose ``is_builtin`` is
        False is a user-owned persona that merely shares the name; it is
        left alone.

        The driver-loop columns were previously excluded, which meant a
        tenant seeded before 021 kept ``driver = NULL`` forever: the pins on
        uzhavu-ops and dependency-updater — the whole reason those personas
        exist — never arrived, and no amount of restarting fixed it. They are
        safe to overwrite because :meth:`update` does not list them as
        updatable fields, so unlike ``allowed_tools`` (which can carry
        hand-granted MCP tools) there is no user edit to clobber.

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

        # Driver-loop columns. Normalised through list() because these are
        # JSONB and come back as plain lists, while the definitions are
        # literals — a bare != would compare fine but be fragile if either
        # side ever became a tuple.
        if row.driver != defn.get("driver"):
            values["driver"] = defn.get("driver")
        target_chain = list(defn.get("verifier_chain", []))
        if list(row.verifier_chain or []) != target_chain:
            values["verifier_chain"] = target_chain
        target_types = list(defn.get("task_types", []))
        if list(row.task_types or []) != target_types:
            values["task_types"] = target_types
        # One way only: a retired built-in is switched off; one the user
        # switched off themselves is never switched back on.
        if defn["name"] in RETIRED_PERSONAS and getattr(row, "is_active", False):
            values["is_active"] = False

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
                model=data.get("model") or settings.agent_llm_model,
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

        values["updated_at"] = datetime.now(UTC)

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
                    updated_at=datetime.now(UTC),
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
