"""Context Packet Builder — assembles what an agent needs to know.

Builds context packets from the Life Graph substrate:
- Project info from kernel project registry
- Relevant procedures
- User preferences
- Related memories (semantic search)
- Calibration profile (bias info)

Token budget: 6k default, truncate in reverse priority order.
Privacy: external drivers don't get memories/preferences on private tasks.
Scope: memories are project-scoped, fail-closed (:func:`memory_in_scope`).
A packet for a project carries only memories attributed to that project; a
packet with no project carries no memory attributed to any project.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, any_, func, or_, select

from life_graph.core.trust import fence_untrusted, is_excluded_from_agents, is_untrusted
from life_graph.drivers.base import ContextPacket

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

logger = logging.getLogger(__name__)

# ── Project scoping of packet memories ─────────────────────────────────
#
# A memory row has no project column; producers record the project in
# ``properties`` (and older skills only as a tag, services/skill_distiller.py
# ``skill_project``). These are every key a producer uses for it today.
#: ``properties`` keys holding the registry id of a project.
_PROJECT_ID_KEYS = ("project_id",)
#: ``properties`` keys holding a project's name (Claude Code hook: ``project``).
_PROJECT_NAME_KEYS = ("project", "project_name")
#: ``properties`` keys holding a filesystem path inside a project.
_PROJECT_PATH_KEYS = ("cwd", "repo_path", "project_path")
#: ``properties`` keys holding a repository as ``owner/name`` (or a bare name).
_PROJECT_REPO_KEYS = ("repo",)
_ATTRIBUTION_KEYS = _PROJECT_ID_KEYS + _PROJECT_NAME_KEYS + _PROJECT_PATH_KEYS + _PROJECT_REPO_KEYS
_TAG_PREFIX = "project:"
# "unknown" is what a producer writes when it could not tell (skill_project).
_NO_PROJECT = frozenset({"", "unknown", "none", "null"})


def _norm_name(value: object) -> str:
    return str(value or "").strip().lower()


def _norm_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/")


@dataclass(frozen=True, slots=True)
class ProjectScope:
    """The project a packet is built for, as the registry knows it."""

    project_id: str
    names: frozenset[str]
    path: str

    @classmethod
    def from_project(cls, project_id: uuid.UUID, project_context: dict) -> ProjectScope:
        """Build from the registry row ``_load_project`` returned."""
        path = _norm_path(project_context.get("path"))
        names = {_norm_name(project_context.get("name"))}
        if path:
            names.add(_norm_name(path.rsplit("/", 1)[-1]))
        return cls(str(project_id), frozenset(names - _NO_PROJECT), path)

    def path_matches(self, value: str) -> bool:
        return bool(self.path) and (value == self.path or value.startswith(self.path + "/"))

    def repo_matches(self, value: str) -> bool:
        return _norm_name(value.rsplit("/", 1)[-1]) in self.names


def _claims(props: dict[str, Any]) -> list[tuple[str, str]]:
    """The project attributions a memory's ``properties`` make, as (kind, value)."""
    out: list[tuple[str, str]] = []
    for kind, keys in (
        ("id", _PROJECT_ID_KEYS),
        ("name", _PROJECT_NAME_KEYS),
        ("path", _PROJECT_PATH_KEYS),
        ("repo", _PROJECT_REPO_KEYS),
    ):
        for key in keys:
            raw = props.get(key)
            if raw is None or _norm_name(raw) in _NO_PROJECT:
                continue
            out.append((kind, _norm_path(raw) if kind == "path" else str(raw).strip()))
    return out


def _claim_matches(scope: ProjectScope, kind: str, value: str) -> bool:
    if kind == "id":
        return value.lower() == scope.project_id.lower()
    if kind == "name":
        return _norm_name(value) in scope.names
    if kind == "path":
        return scope.path_matches(value)
    return scope.repo_matches(value)


def memory_in_scope(
    properties: dict[str, Any] | None,
    tags: list[str] | None,
    scope: ProjectScope | None,
) -> bool:
    """Whether a memory may enter a driver packet built for *scope*. Fail-closed.

    With a project (a dev task): the memory must be attributed to that same
    project, by registry id, name, path or repo in ``properties`` or by a
    project tag, and no attribution may name a different project. A memory
    with no project attribution is left out: it is not context for this
    repository (incident 2026-11-28: a race-app task was handed apptx-v2's git
    conflict alerts, because every tenant memory competed on importance alone).

    Without a project: only memories that name no project at all go in.
    """
    props = properties if isinstance(properties, dict) else {}
    claims = _claims(props)
    tag_list = [str(t) for t in (tags or [])]
    prefixed = [t[len(_TAG_PREFIX) :] for t in tag_list if t.lower().startswith(_TAG_PREFIX)]
    if scope is None:
        return not claims and not prefixed
    if any(not _claim_matches(scope, kind, value) for kind, value in claims):
        return False
    if any(_norm_name(name) not in scope.names for name in prefixed):
        return False
    if claims or prefixed:
        return True
    # Older skill rows carry their project only as a bare tag.
    return any(_norm_name(t) in scope.names for t in tag_list)


def _scope_clause(memory: Any, scope: ProjectScope | None) -> ColumnElement[bool]:
    """SQL pre-filter mirroring :func:`memory_in_scope`, so the top-k is drawn
    from in-scope rows. :func:`memory_in_scope` re-checks every row."""
    props = memory.properties
    if scope is None:
        blank = sorted(_NO_PROJECT)
        return and_(
            *(
                or_(
                    props[key].astext.is_(None),
                    func.lower(func.trim(props[key].astext)).in_(blank),
                )
                for key in _ATTRIBUTION_KEYS
            )
        )
    names = sorted(scope.names)
    conds: list[ColumnElement[bool]] = [
        func.lower(props[key].astext) == scope.project_id.lower() for key in _PROJECT_ID_KEYS
    ]
    if names:
        conds += [func.lower(props[key].astext).in_(names) for key in _PROJECT_NAME_KEYS]
        conds += [func.lower(props[key].astext).in_(names) for key in _PROJECT_REPO_KEYS]
        conds += [
            func.lower(props[key].astext).like(f"%/{name}")
            for key in _PROJECT_REPO_KEYS
            for name in names
        ]
        conds += [any_(memory.tags) == name for name in names]
        conds += [any_(memory.tags) == f"{_TAG_PREFIX}{name}" for name in names]
    if scope.path:
        for key in _PROJECT_PATH_KEYS:
            conds.append(props[key].astext == scope.path)
            conds.append(props[key].astext.startswith(scope.path + "/", autoescape=True))
    return or_(*conds)


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
        preferences = await self._load_preferences(tenant_id, session, project_id)
        scope = ProjectScope.from_project(project_id, project_context) if project_id else None
        if project_id and not project_context:
            # The project is not in this tenant's registry: nothing can be
            # matched to it, so no memory is (fail-closed).
            memories: list[dict] = []
        else:
            memories = await self._load_memories(tenant_id, instruction, session, scope=scope)
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
                # Verifier sandbox dependency setup. Read from the registry,
                # never the worktree, which the agent controls.
                **{
                    key: (project.scan_metadata or {}).get(key)
                    for key in (
                        "sandbox_setup",
                        "sandbox_setup_allow",
                        "sandbox_test_command",
                        "sandbox_test_timeout",
                        "sandbox_toolchain",
                        "sandbox_js_test_runner",
                        "sandbox_start_command",
                        "sandbox_app_port",
                        "sandbox_e2e_command",
                        "sandbox_e2e_timeout",
                        "required_checks",
                        "auto_open_pr",
                        "auto_merge",
                        "base_branch",
                        "auto_approve_plans",
                        # The unattended-landing gate (services/dev/change_policy.py).
                        "protected_paths",
                        "auto_merge_max_lines",
                        "auto_merge_max_files",
                        "diff_coverage_min",
                        "mutation_min_kill",
                    )
                },
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
                select(Procedure)
                .where(
                    Procedure.tenant_id == tenant_id,
                    Procedure.status == "active",
                )
                .order_by(Procedure.confidence.desc())
                .limit(5)
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
        project_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Load top user preferences by confidence.

        Preferences learned from a project (``properties.project_id``) apply
        only to dispatches for that project; one repo's conventions are
        wrong advice in another. Preferences without a project always apply.

        Returns:
            List of preference dicts with topic, choice, confidence.
        """
        try:
            from life_graph.models.db import Preference

            result = await session.execute(
                select(Preference)
                .where(
                    Preference.tenant_id == tenant_id,
                    Preference.status == "active",
                    or_(
                        Preference.properties["project_id"].astext.is_(None),
                        Preference.properties["project_id"].astext == str(project_id),
                    ),
                )
                .order_by(Preference.confidence.desc())
                .limit(10)
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
        *,
        scope: ProjectScope | None = None,
    ) -> list[dict]:
        """Load recent relevant memories, scoped to the packet's project.

        For now, loads the most recent high-importance memories among those
        :func:`memory_in_scope` admits for *scope*.
        Future: semantic search using instruction embedding.

        Returns:
            List of memory dicts with content, importance, tags.
        """
        try:
            from life_graph.models.db import Memory

            result = await session.execute(
                select(Memory)
                .where(
                    Memory.tenant_id == tenant_id,
                    Memory.status == "active",
                    _scope_clause(Memory, scope),
                )
                .order_by(
                    Memory.importance.desc(),
                    Memory.created_at.desc(),
                )
                .limit(10)
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
                and memory_in_scope(m.properties, m.tags, scope)
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
            Dict with brier_score and bias_findings. The estimate multiplier
            is left out: it is meant for time estimates (actual/predicted
            duration), which are not recorded, so the value computed from
            yes/no outcomes would mislead an agent planning work.
        """
        try:
            from life_graph.services.calibration import latest_snapshot

            snapshot = await latest_snapshot(session, tenant_id)
            if not snapshot:
                return {}

            return {
                "brier_score": snapshot.brier_score,
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
                    attr_name,
                    max_tokens,
                    total,
                )
            else:
                total += section_tokens
