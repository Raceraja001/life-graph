#!/usr/bin/env python3
"""Move one tenant's data into another tenant.

Why this exists
---------------
A client that sends no ``X-Tenant-ID`` header lands in the server's default
tenant ``dev`` (``api/middleware.py``). On the owner's instance that put
hundreds of memories, written by self-evolution, the developer assistant,
Jarvis and chat, into ``dev`` instead of the owner's own tenant ``raja``. This
script moves them, and everything that hangs off them, across.

What it moves, and what it leaves
---------------------------------
Every table with a ``tenant_id`` column (in whichever schema the search
path finds it) is listed in exactly one of
:data:`MOVE`, :data:`LEAVE_CONFIG` or :data:`LEAVE_OPERATIONAL`, each with the
reason. The script reads the live schema first and refuses to run if it finds
a tenant table that is not listed, so a new table cannot be silently skipped
(or silently moved).

- **Moved:** the owner's knowledge — memories, their links, entities and
  sessions, the memory review items in ``approvals``, conversations,
  preferences, decisions, captures and the like.
- **Left:** configuration (tenant settings, devices, owner keys, personas,
  rules, connector accounts, schedules) and operational history (agent tasks,
  job runs, budgets, audit log). Those describe how the server ran *as* that
  tenant; moving them gives the target nothing and could clash with its own.
- **Not moved, only reported:** the Apache AGE graph. It is a best-effort
  mirror of the memory links, rebuilt from the tables.

Collisions (per-tenant UNIQUE keys)
-----------------------------------
- ``memories``: a source memory whose ``content_hash`` matches a target memory
  (both ``active`` or ``pending`` — the same test ``find_exact_duplicate``
  uses) is *folded*: every reference to it is repointed to the target's row,
  then the source copy is deleted. Archived/rejected memories always move.
- ``entities``: same ``key`` in the target → folded the same way, and the
  target row gets the source's ``mentions`` added (and its ``role`` if it had
  none).
- ``capture_events`` (same Telegram message) and ``review_cards`` (same
  ``dedup_key``): folded.
- ``memory_links`` / ``memory_entities`` / ``memory_sessions``: after
  repointing, a row that would duplicate an existing one (or link a memory to
  itself) is dropped.
- ``approvals``: only memory review kinds move; ids inside them are
  repointed; one the target already has (same ``source`` + ``source_ref``) is
  dropped.
- ``money_transactions``: same ``dedup_hash`` in the target is the same
  transaction → the source copy is dropped.
- ``invoices``: same invoice ``number`` in the target is a real conflict →
  the source row is **left in the source tenant** and reported.

Usage
-----
    python scripts/move_tenant_data.py --source dev --target raja           # dry run
    python scripts/move_tenant_data.py --source dev --target raja --apply \\
        --backup-file /backups/before-move.dump

The dry run reads only (a READ ONLY transaction) and prints the plan.
``--apply`` does the whole move in ONE transaction, checks the result, and
rolls back on any mismatch. It needs a non-empty ``--backup-file`` (take a
``pg_dump`` first). See docs/OPERATIONS.md, "Moving a tenant's data".
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from sqlalchemy.engine import Connection

# ── Classification ────────────────────────────────────────────

#: Moved. The value says why and what happens on a collision.
MOVE: dict[str, str] = {
    "memories": "the memories; exact duplicates (content_hash) folded into the target row",
    "memory_links": "links between memories; repointed, duplicates/self-links dropped",
    "memory_entities": "memory mentions entity; repointed, duplicates dropped",
    "entities": "people/things memories mention; same key -> merged into the target row",
    "sessions": "interaction sessions memories were created in",
    "intentions": "reminders/intentions taken from memories",
    "knowledge_gaps": "questions memory could not answer",
    "procedures": "learned procedures",
    "approvals": "memory review items only (kinds: contradiction, merge, entity_alias, "
    "archive); same source+source_ref in target -> dropped",
    "review_cards": "study cards made from memories; same dedup_key -> folded",
    "study_reviews": "study review history (card ids repointed)",
    "conversations": "chat conversations",
    "conversation_messages": "chat turns (cited memory ids repointed)",
    "preferences": "the owner's preferences",
    "evidence": "evidence for preferences",
    "advisor_sessions": "questions asked of the advisor and its answers",
    "documents": "the owner's documents (ids, passports, ...)",
    "money_transactions": "money transactions; same dedup_hash in target -> dropped",
    "invoices": "invoices; same number in target -> LEFT in source and reported",
    "capture_events": "raw captures memories came from; same Telegram message -> folded",
    "corrections": "corrections the owner made",
    "decisions": "decisions",
    "predictions": "predictions",
    "challenges": "challenges to decisions",
    "interview_questions": "questions to ask the owner",
    "calibration_snapshots": "prediction calibration history",
}

#: Left: configuration. Belongs to how the tenant is set up, not what it knows.
LEAVE_CONFIG: dict[str, str] = {
    "tenant_configs": "the tenant's own settings row",
    "agent_personas": "persona definitions",
    "autonomy_policies": "owner auto-approval policy (global + per project)",
    "agent_accounts": "coding-CLI logins (home dirs are per tenant on this machine)",
    "dev_automation_settings": "dev automation settings",
    "dev_intake_sources": "dev intake sources",
    "dev_schedules": "dev-task schedules",
    "devices": "paired devices / owner keys",
    "device_pairing_codes": "pairing codes",
    "telegram_bindings": "which chat belongs to which tenant",
    "telegram_pairing_codes": "pairing codes",
    "push_subscriptions": "browser push endpoints",
    "tenant_webhooks": "webhook settings",
    "notification_channels": "notification settings",
    "vault_secrets": "encrypted secrets",
    "capabilities": "authorization grants",
    "standing_rules": "authorization rules",
    "action_safety_rules": "autonomy safety rules",
    "autonomy_levels": "autonomy level per project",
    "trust_scores": "agent trust scores",
    "watch_configs": "watcher settings",
    "connector_accounts": "connected accounts (credentials, cursors)",
    "connector_items": "items synced by a connected account; stay with the account",
    "money_budgets": "budget settings",
    "money_category_rules": "categorisation rules",
    "page_monitors": "page monitor settings",
    "scheduled_jobs": "schedules",
    "workflows": "workflow definitions",
    "projects": "registered code projects",
    "prompt_versions": "prompt versions",
    "eval_suites": "eval suites",
    "shadow_enrollments": "shadow-mode enrolment",
}

#: Left: operational history of the server running as that tenant.
LEAVE_OPERATIONAL: dict[str, str] = {
    "agent_tasks": "dev-agent tasks",
    "agent_run_steps": "dev-agent run steps",
    "agent_messages": "agent-to-agent messages",
    "agent_sessions": "agent routing sessions",
    "dev_task_events": "dev-task event stream",
    "agent_account_limits": "plan-window snapshots per CLI login",
    "dev_backlog": "intake backlog (tied to agent tasks)",
    "dev_schedule_runs": "dev-task schedule runs",
    "dev_automation_breakers": "automation circuit-breaker state",
    "dev_task_groups": "teams / arena races (tied to agent tasks)",
    "pr_watches": "PR feedback watches (tied to agent tasks)",
    "dev_outcome_log": "per-dispatch routing and review outcomes (tied to agent tasks)",
    "verification_runs": "dev-task verification",
    "driver_stats": "driver statistics",
    "approval_queue": "shell-command approval queue (tied to agent tasks)",
    "auto_actions": "autonomous actions",
    "audit_log": "audit log",
    "budget_spend": "spend against budget caps",
    "tenant_usage": "usage metering",
    "job_runs": "background job runs",
    "nightly_run_log": "nightly run log",
    "optimization_runs": "prompt optimisation runs",
    "cross_system_syncs": "sync history",
    "watch_events": "watcher events",
    "watcher_notifications": "watcher notifications",
    "watcher_runs": "watcher runs",
    "workflow_runs": "workflow runs",
    "shadow_runs": "shadow-mode runs",
    "notifications": "sent notifications",
    "extraction_traces": "extraction debug traces",
    "research_runs": "research job runs",
    "external_sessions": "transcript-upload cursors",
    "shared_context": "agent shared context",
    "topic_findings": "tech-watch job output",
    "llm_offers": "free-LLM-offer job output",
    "tech_radar": "tech-radar job output",
}

#: Tables with no tenant_id that follow a moved table through a foreign key.
FOLLOWERS: dict[str, str] = {
    "memory_sessions": "memory <-> session pairs; follow memories, memory_id repointed",
}

#: Approval kinds that are memory review items and move with the memories.
MEMORY_APPROVAL_KINDS = ("contradiction", "merge", "entity_alias", "archive")

#: Extra row filter for MOVE tables that only partly move.
ROW_FILTER: dict[str, str] = {
    "approvals": "kind IN ('contradiction', 'merge', 'entity_alias', 'archive')",
}

#: Folded tables -> every column that points at them. Each is repointed from
#: the folded source row to the target row before the source row is deleted.
#: The schema check refuses to run if a foreign key into one of these tables
#: is missing here. ``[]`` marks a uuid[] column.
REFS: dict[str, tuple[str, ...]] = {
    "memories": (
        "memories.supersedes",
        "memories.superseded_by",
        "memory_links.source_memory_id",
        "memory_links.target_memory_id",
        "memory_entities.memory_id",
        "memory_sessions.memory_id",
        "intentions.source_memory",
        "knowledge_gaps.resolved_by",
        "review_cards.source_memory_id",
        "conversation_messages.cited_memory_ids[]",
    ),
    "entities": (
        "entities.canonical_id",
        "memory_entities.entity_id",
    ),
    "capture_events": (
        "memories.capture_event_id",
        "corrections.capture_event_id",
        "interview_questions.answer_capture_id",
        "decisions.capture_event_id",
        "predictions.capture_event_id",
    ),
    "review_cards": ("study_reviews.card_id",),
}

#: Columns handled by the pair-table code, not by a plain UPDATE.
_PAIR_COLUMNS = {
    "memory_links.source_memory_id",
    "memory_links.target_memory_id",
    "memory_entities.memory_id",
    "memory_entities.entity_id",
    "memory_sessions.memory_id",
}

#: Unique indexes on MOVE tables that include tenant_id, and are handled.
HANDLED_UNIQUES = {
    "entities": "uq_entities_tenant_key",
    "approvals": "uq_approvals_source_ref",
    "review_cards": "uq_review_cards_dedup",
    "money_transactions": "uq_money_transactions_dedup",
    "invoices": "uq_invoices_number",
    "capture_events": "uq_ce_telegram_message",
}

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class RefusedError(Exception):
    """The script will not run; the message says why."""


class VerifyError(Exception):
    """The move did not produce the planned counts; the transaction rolls back."""


def _q(table: str) -> str:
    """*table* as a quoted identifier. Only ever our own constants.

    Names are bare on purpose: which schema a table lives in depends on the
    database role (the ``"$user"`` entry of ``search_path``; on the owner's
    instance some tables sit in the ``life_graph`` schema, in CI all are in
    ``public``). The app's ORM uses bare names too, so this resolves to
    exactly the tables the app reads and writes. :func:`discover` only sees
    tables visible on the search path, and refuses shadowed ones.
    """
    return f'"{table}"'


# ── Schema discovery and checks ───────────────────────────────


@dataclass
class Schema:
    #: tables (bare names, as the search path resolves them) with tenant_id
    tenant_tables: set[str]
    #: (child_table, child_column, parent_table)
    fks: list[tuple[str, str, str]]
    #: table -> names of unique indexes whose columns include tenant_id
    tenant_uniques: dict[str, set[str]]
    #: schema.table with tenant_id that bare names do not reach (shadowed or
    #: off the search path); refused, since rows there would be missed
    hidden: set[str] = field(default_factory=set)


_SYSTEM = "('pg_catalog', 'information_schema', 'ag_catalog', 'pg_toast')"


def discover(conn: Connection) -> Schema:
    """Read which tables have tenant_id, every FK, and per-tenant unique indexes."""
    tenant_tables: set[str] = set()
    hidden: set[str] = set()
    for schema_name, name, visible in conn.execute(
        text(
            f"""
            SELECT n.nspname, c.relname, pg_table_is_visible(c.oid)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
                               AND NOT a.attisdropped
            WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN {_SYSTEM}
            """
        )
    ):
        if visible:
            tenant_tables.add(name)
        else:
            hidden.add(f"{schema_name}.{name}")
    fks = [
        (r[0], r[1], r[2])
        for r in conn.execute(
            text(
                f"""
                SELECT cc.relname, a.attname, pc.relname
                FROM pg_constraint con
                JOIN pg_class cc ON cc.oid = con.conrelid
                JOIN pg_namespace cn ON cn.oid = cc.relnamespace
                JOIN pg_class pc ON pc.oid = con.confrelid
                JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
                WHERE con.contype = 'f' AND cn.nspname NOT IN {_SYSTEM}
                  AND pg_table_is_visible(cc.oid) AND pg_table_is_visible(pc.oid)
                """
            )
        )
    ]
    tenant_uniques: dict[str, set[str]] = {}
    for table, index in conn.execute(
        text(
            f"""
            SELECT c.relname, ic.relname
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_class ic ON ic.oid = i.indexrelid
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
            WHERE i.indisunique AND NOT i.indisprimary AND a.attname = 'tenant_id'
              AND n.nspname NOT IN {_SYSTEM} AND pg_table_is_visible(c.oid)
            """
        )
    ):
        tenant_uniques.setdefault(table, set()).add(index)
    return Schema(tenant_tables, fks, tenant_uniques, hidden)


def check_schema(schema: Schema) -> list[str]:
    """Problems that make the move unsafe. Empty means the lists match the schema."""
    problems: list[str] = []
    listed = set(MOVE) | set(LEAVE_CONFIG) | set(LEAVE_OPERATIONAL)
    overlap = (set(MOVE) & (set(LEAVE_CONFIG) | set(LEAVE_OPERATIONAL))) | (
        set(LEAVE_CONFIG) & set(LEAVE_OPERATIONAL)
    )
    problems += [f"{t}: listed twice (move and leave)" for t in sorted(overlap)]
    problems += [
        f"{t}: has tenant_id but bare names do not reach it (shadowed or off search_path)"
        for t in sorted(schema.hidden)
    ]
    problems += [
        f"{t}: has tenant_id but is not classified (add it to MOVE or LEAVE_*)"
        for t in sorted(schema.tenant_tables - listed)
    ]
    problems += [
        f"{t}: classified but has no tenant_id column (or no longer exists)"
        for t in sorted(listed - schema.tenant_tables)
    ]
    for table in MOVE:
        for index in sorted(schema.tenant_uniques.get(table, set())):
            if HANDLED_UNIQUES.get(table) != index:
                problems.append(f"{table}: per-tenant unique index {index} has no collision rule")
    registered = {ref.removesuffix("[]") for refs in REFS.values() for ref in refs}
    for child, column, parent in schema.fks:
        if parent in REFS and f"{child}.{column}" not in registered:
            problems.append(f"{child}.{column} references folded table {parent} but is not in REFS")
        if parent in MOVE and child not in schema.tenant_tables and child not in FOLLOWERS:
            problems.append(f"{child} (no tenant_id) references moved {parent}; add to FOLLOWERS")
    return problems


def cross_refs(conn: Connection, schema: Schema, source: str) -> dict[str, int]:
    """Source-tenant rows that would point across tenants after the move.

    A foreign key from a table that stays (LEAVE_*) into one that moves, or
    the other way round, links rows that end up in different tenants.
    """
    out: dict[str, int] = {}
    for child, column, parent in schema.fks:
        child_moves, parent_moves = child in MOVE, parent in MOVE
        if child_moves == parent_moves or child not in schema.tenant_tables:
            continue
        if parent not in schema.tenant_tables:
            continue
        n = conn.execute(
            text(
                f"SELECT count(*) FROM {_q(child)} c JOIN {_q(parent)} p ON p.id = c.{column} "
                "WHERE c.tenant_id = :src AND p.tenant_id = :src"
            ),
            {"src": source},
        ).scalar_one()
        if n:
            out[f"{child}.{column} -> {parent}"] = int(n)
    return out


# ── Planning (read only) ──────────────────────────────────────


@dataclass
class TablePlan:
    table: str
    source_before: int
    target_before: int
    #: Source rows folded into / dropped as duplicates of target rows (deleted).
    merged: int = 0
    #: Source rows left in the source because of a conflict.
    skipped: int = 0
    #: Source rows the row filter keeps in the source (approvals of other kinds).
    kept: int = 0

    @property
    def moving(self) -> int:
        return self.source_before - self.merged - self.skipped - self.kept


@dataclass
class PairChange:
    """A row of a pair table (memory_links etc.) whose ids get repointed."""

    key: tuple[str, ...]  # identifies the current row
    new: tuple[str, ...] | None  # new id pair, None = drop the row


@dataclass
class Plan:
    source: str
    target: str
    tables: dict[str, TablePlan] = field(default_factory=dict)
    #: folded table -> {source id: target id}
    maps: dict[str, dict[str, str]] = field(default_factory=dict)
    links: list[PairChange] = field(default_factory=list)
    mentions: list[PairChange] = field(default_factory=list)
    memory_sessions: list[PairChange] = field(default_factory=list)
    #: approval id -> (new source_ref, new payload json); only changed ones
    approval_rewrites: dict[str, tuple[str | None, str]] = field(default_factory=dict)
    approvals_dropped: list[str] = field(default_factory=list)
    money_dropped: list[str] = field(default_factory=list)
    invoices_skipped: list[str] = field(default_factory=list)
    cross_refs: dict[str, int] = field(default_factory=dict)
    graph_vertices: int | None = None


def _count(conn: Connection, table: str, tenant: str, where: str = "") -> int:
    clause = f" AND ({where})" if where else ""
    return int(
        conn.execute(
            text(f"SELECT count(*) FROM {_q(table)} WHERE tenant_id = :t{clause}"), {"t": tenant}
        ).scalar_one()
    )


def _pairs(conn: Connection, sql: str, params: dict[str, Any]) -> dict[str, str]:
    return {str(a): str(b) for a, b in conn.execute(text(sql), params) if b is not None}


def _build_maps(conn: Connection, src: str, tgt: str) -> dict[str, dict[str, str]]:
    p = {"src": src, "tgt": tgt}
    live = "('active', 'pending')"
    return {
        "memories": _pairs(
            conn,
            f"""
            SELECT s.id, (
                SELECT t.id FROM memories t
                WHERE t.tenant_id = :tgt AND t.content_hash = s.content_hash
                  AND t.status IN {live}
                ORDER BY t.created_at, t.id LIMIT 1)
            FROM memories s
            WHERE s.tenant_id = :src AND s.content_hash IS NOT NULL AND s.status IN {live}
            """,
            p,
        ),
        "entities": _pairs(
            conn,
            "SELECT s.id, t.id FROM entities s JOIN entities t "
            "ON t.key = s.key AND t.tenant_id = :tgt WHERE s.tenant_id = :src",
            p,
        ),
        "capture_events": _pairs(
            conn,
            """
            SELECT s.id, (
                SELECT t.id FROM capture_events t
                WHERE t.tenant_id = :tgt AND t.surface = 'telegram'
                  AND t.properties->>'chat_id' = s.properties->>'chat_id'
                  AND t.properties->>'message_id' = s.properties->>'message_id' LIMIT 1)
            FROM capture_events s
            WHERE s.tenant_id = :src AND s.surface = 'telegram'
              AND s.properties->>'chat_id' IS NOT NULL AND s.properties->>'message_id' IS NOT NULL
            """,
            p,
        ),
        "review_cards": _pairs(
            conn,
            "SELECT s.id, t.id FROM review_cards s JOIN review_cards t "
            "ON t.dedup_key = s.dedup_key AND t.tenant_id = :tgt WHERE s.tenant_id = :src",
            p,
        ),
    }


def _plan_pairs(
    rows: Iterable[tuple[Any, ...]],
    remap: Callable[[tuple[str, ...]], tuple[str, ...]],
    exists: Callable[[tuple[str, ...]], bool],
    *,
    self_loop: bool = False,
) -> list[PairChange]:
    """Decide, for rows whose ids change, the new ids or drop.

    A row is dropped when its new ids equal another row's — one that is not
    changing (``exists``) or one already kept in this batch — or, with
    *self_loop*, when both ends become the same memory.
    """
    changes: list[PairChange] = []
    taken: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(str(v) for v in row)
        new = remap(key)
        if (self_loop and new[0] == new[1]) or new in taken or exists(new):
            changes.append(PairChange(key, None))
        else:
            taken.add(new)
            changes.append(PairChange(key, new))
    return changes


def _plan_links(conn: Connection, plan: Plan) -> None:
    mm = plan.maps["memories"]
    if not mm:
        return
    olds = list(mm)
    rows = conn.execute(
        text(
            "SELECT id, source_memory_id, target_memory_id, link_type FROM memory_links "
            "WHERE tenant_id = :src AND (source_memory_id::text = ANY(:olds) "
            "OR target_memory_id::text = ANY(:olds)) ORDER BY created_at, id"
        ),
        {"src": plan.source, "olds": olds},
    ).all()
    changing = [str(r[0]) for r in rows]

    def remap(key: tuple[str, ...]) -> tuple[str, ...]:
        return (mm.get(key[1], key[1]), mm.get(key[2], key[2]), key[3])

    def exists(new: tuple[str, ...]) -> bool:
        return bool(
            conn.execute(
                text(
                    "SELECT 1 FROM memory_links WHERE source_memory_id = CAST(:s AS uuid) "
                    "AND target_memory_id = CAST(:t AS uuid) AND link_type = :lt "
                    "AND NOT (id::text = ANY(:changing))"
                ),
                {"s": new[0], "t": new[1], "lt": new[2], "changing": changing},
            ).first()
        )

    plan.links = _plan_pairs(rows, remap, exists, self_loop=True)


def _plan_mentions(conn: Connection, plan: Plan) -> None:
    mm, em = plan.maps["memories"], plan.maps["entities"]
    if not mm and not em:
        return
    rows = conn.execute(
        text(
            "SELECT memory_id, entity_id FROM memory_entities WHERE tenant_id = :src "
            "AND (memory_id::text = ANY(:m) OR entity_id::text = ANY(:e)) "
            "ORDER BY memory_id, entity_id"
        ),
        {"src": plan.source, "m": list(mm), "e": list(em)},
    ).all()
    changing = {(str(a), str(b)) for a, b in rows}

    def exists(new: tuple[str, ...]) -> bool:
        if new in changing:
            return False
        return bool(
            conn.execute(
                text(
                    "SELECT 1 FROM memory_entities WHERE memory_id = CAST(:m AS uuid) "
                    "AND entity_id = CAST(:e AS uuid)"
                ),
                {"m": new[0], "e": new[1]},
            ).first()
        )

    plan.mentions = _plan_pairs(rows, lambda k: (mm.get(k[0], k[0]), em.get(k[1], k[1])), exists)


def _plan_memory_sessions(conn: Connection, plan: Plan) -> None:
    mm = plan.maps["memories"]
    if not mm:
        return
    rows = conn.execute(
        text(
            "SELECT memory_id, session_id FROM memory_sessions WHERE memory_id::text = ANY(:m) "
            "ORDER BY memory_id, session_id"
        ),
        {"m": list(mm)},
    ).all()
    changing = {(str(a), str(b)) for a, b in rows}

    def exists(new: tuple[str, ...]) -> bool:
        if new in changing:
            return False
        return bool(
            conn.execute(
                text(
                    "SELECT 1 FROM memory_sessions WHERE memory_id = CAST(:m AS uuid) "
                    "AND session_id = CAST(:s AS uuid)"
                ),
                {"m": new[0], "s": new[1]},
            ).first()
        )

    plan.memory_sessions = _plan_pairs(rows, lambda k: (mm.get(k[0], k[0]), k[1]), exists)


def _rewrite_ids(value: str, mapping: dict[str, str]) -> str:
    return _UUID_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), value)


def _plan_approvals(conn: Connection, plan: Plan) -> None:
    """Repoint ids inside moving approvals; drop ones the target already has."""
    mapping = {**plan.maps["memories"], **plan.maps["entities"]}
    rows = conn.execute(
        text(
            f"SELECT id, source, source_ref, payload::text FROM approvals "
            f"WHERE tenant_id = :src AND {ROW_FILTER['approvals']} ORDER BY created_at, id"
        ),
        {"src": plan.source},
    ).all()
    target_keys = {
        (s, r)
        for s, r in conn.execute(
            text("SELECT source, source_ref FROM approvals WHERE tenant_id = :tgt"),
            {"tgt": plan.target},
        )
        if r is not None
    }
    seen: set[tuple[str, str]] = set()
    for aid, source, ref, payload in rows:
        new_ref = _rewrite_ids(ref, mapping) if ref is not None else None
        new_payload = _rewrite_ids(payload, mapping)
        if new_ref is not None:
            if (source, new_ref) in target_keys or (source, new_ref) in seen:
                plan.approvals_dropped.append(str(aid))
                continue
            seen.add((source, new_ref))
        if new_ref != ref or new_payload != payload:
            plan.approval_rewrites[str(aid)] = (new_ref, new_payload)


def build_plan(conn: Connection, schema: Schema, source: str, target: str) -> Plan:
    """Work out exactly what the move would do. Reads only."""
    plan = Plan(source, target)
    plan.maps = _build_maps(conn, source, target)
    _plan_links(conn, plan)
    _plan_mentions(conn, plan)
    _plan_memory_sessions(conn, plan)
    _plan_approvals(conn, plan)
    plan.money_dropped = [
        str(r[0])
        for r in conn.execute(
            text(
                "SELECT s.id FROM money_transactions s JOIN money_transactions t "
                "ON t.dedup_hash = s.dedup_hash AND t.tenant_id = :tgt WHERE s.tenant_id = :src"
            ),
            {"src": source, "tgt": target},
        )
    ]
    plan.invoices_skipped = [
        str(r[0])
        for r in conn.execute(
            text(
                "SELECT s.id FROM invoices s JOIN invoices t "
                "ON t.number = s.number AND t.tenant_id = :tgt WHERE s.tenant_id = :src"
            ),
            {"src": source, "tgt": target},
        )
    ]
    merged = {t: len(m) for t, m in plan.maps.items()}
    merged["memory_links"] = sum(c.new is None for c in plan.links)
    merged["memory_entities"] = sum(c.new is None for c in plan.mentions)
    merged["approvals"] = len(plan.approvals_dropped)
    merged["money_transactions"] = len(plan.money_dropped)
    for table in MOVE:
        tp = TablePlan(table, _count(conn, table, source), _count(conn, table, target))
        tp.merged = merged.get(table, 0)
        if table in ROW_FILTER:
            tp.kept = tp.source_before - _count(conn, table, source, ROW_FILTER[table])
        if table == "invoices":
            tp.skipped = len(plan.invoices_skipped)
        plan.tables[table] = tp
    plan.cross_refs = cross_refs(conn, schema, source)
    plan.graph_vertices = _graph_vertices(conn, source)
    return plan


def _graph_vertices(conn: Connection, tenant: str) -> int | None:
    """AGE vertices tagged with *tenant*; None when the graph is not there.

    ``agtype`` has no cast to text for maps, so the properties go through
    ``agtype_out`` (the type's own output function) first.
    """
    try:
        with conn.begin_nested():
            return int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM life_graph._ag_label_vertex "
                        "WHERE ag_catalog.agtype_out(properties)::text LIKE :pat"
                    ),
                    {"pat": f'%"tenant_id": "{tenant}"%'},
                ).scalar_one()
            )
    except Exception:
        return None


# ── Apply ─────────────────────────────────────────────────────


def _exec(conn: Connection, sql: str, params: dict[str, Any] | None = None) -> int:
    return int(conn.execute(text(sql), params or {}).rowcount)


def _repoint_column(conn: Connection, ref: str, mapping: dict[str, str]) -> None:
    """Point *ref* (``table.column``) from folded ids to their targets, any tenant."""
    is_array = ref.endswith("[]")
    table, column = ref.removesuffix("[]").split(".")
    params = {"olds": list(mapping), "news": list(mapping.values())}
    m = "(SELECT unnest(CAST(:olds AS uuid[])) AS old, unnest(CAST(:news AS uuid[])) AS new) m"
    if is_array:
        _exec(
            conn,
            f"""
            UPDATE {_q(table)} c SET {column} = (
                SELECT array_agg(coalesce(m.new, u.x) ORDER BY u.ord)
                FROM unnest(c.{column}) WITH ORDINALITY u(x, ord) LEFT JOIN {m} ON m.old = u.x)
            WHERE c.{column} && CAST(:olds AS uuid[])
            """,
            params,
        )
    else:
        _exec(
            conn,
            f"UPDATE {_q(table)} c SET {column} = m.new FROM {m} WHERE c.{column} = m.old",
            params,
        )


def _apply_pairs(conn: Connection, plan: Plan) -> None:
    for c in plan.links:
        if c.new is None:
            _exec(conn, "DELETE FROM memory_links WHERE id = CAST(:id AS uuid)", {"id": c.key[0]})
        else:
            _exec(
                conn,
                "UPDATE memory_links SET source_memory_id = CAST(:s AS uuid), "
                "target_memory_id = CAST(:t AS uuid) WHERE id = CAST(:id AS uuid)",
                {"s": c.new[0], "t": c.new[1], "id": c.key[0]},
            )
    for table, col in (("memory_entities", "entity_id"), ("memory_sessions", "session_id")):
        changes = plan.mentions if table == "memory_entities" else plan.memory_sessions
        where = f"memory_id = CAST(:m AS uuid) AND {col} = CAST(:o AS uuid)"
        for c in changes:
            p = {"m": c.key[0], "o": c.key[1]}
            if c.new is None:
                _exec(conn, f"DELETE FROM {table} WHERE {where}", p)
            else:
                _exec(
                    conn,
                    f"UPDATE {table} SET memory_id = CAST(:nm AS uuid), {col} = CAST(:no AS uuid) "
                    f"WHERE {where}",
                    {**p, "nm": c.new[0], "no": c.new[1]},
                )


def _fold(conn: Connection, plan: Plan) -> None:
    """Repoint every reference to folded rows, then delete the folded source rows.

    Approvals and money rows dropped as duplicates go first, so rewriting the
    remaining approvals cannot trip their unique key on a row about to go.
    """
    em = plan.maps["entities"]
    if em:
        _exec(
            conn,
            """
            UPDATE entities t SET mentions = t.mentions + s.mentions,
                                  role = coalesce(t.role, s.role), updated_at = now()
            FROM entities s, (SELECT unnest(CAST(:olds AS uuid[])) AS old,
                                     unnest(CAST(:news AS uuid[])) AS new) m
            WHERE s.id = m.old AND t.id = m.new
            """,
            {"olds": list(em), "news": list(em.values())},
        )
    _apply_pairs(conn, plan)
    for table, mapping in plan.maps.items():
        if not mapping:
            continue
        for ref in REFS[table]:
            if ref.removesuffix("[]") not in _PAIR_COLUMNS:
                _repoint_column(conn, ref, mapping)
    _delete_ids(conn, plan, "approvals", plan.approvals_dropped)
    _delete_ids(conn, plan, "money_transactions", plan.money_dropped)
    for aid, (ref, payload) in plan.approval_rewrites.items():
        _exec(
            conn,
            "UPDATE approvals SET source_ref = :r, payload = CAST(:p AS jsonb) "
            "WHERE id = CAST(:id AS uuid)",
            {"r": ref, "p": payload, "id": aid},
        )
    for table, mapping in plan.maps.items():
        _delete_ids(conn, plan, table, list(mapping))


def _delete_ids(conn: Connection, plan: Plan, table: str, ids: list[str]) -> None:
    """Delete source-tenant rows of *table* by id; exactly ``len(ids)`` or raise."""
    if not ids:
        return
    n = _exec(
        conn,
        f"DELETE FROM {_q(table)} WHERE tenant_id = :src AND id = ANY(CAST(:ids AS uuid[]))",
        {"src": plan.source, "ids": ids},
    )
    if n != len(ids):
        raise VerifyError(f"{table}: deleted {n} rows, planned {len(ids)}")


def _move_rows(conn: Connection, plan: Plan) -> None:
    for table, tp in plan.tables.items():
        clauses = ["tenant_id = :src"]
        if table in ROW_FILTER:
            clauses.append(f"({ROW_FILTER[table]})")
        params: dict[str, Any] = {"src": plan.source, "tgt": plan.target}
        if table == "invoices" and plan.invoices_skipped:
            clauses.append("NOT (id = ANY(CAST(:skip AS uuid[])))")
            params["skip"] = plan.invoices_skipped
        n = _exec(
            conn, f"UPDATE {_q(table)} SET tenant_id = :tgt WHERE {' AND '.join(clauses)}", params
        )
        if n != tp.moving:
            raise VerifyError(f"{table}: moved {n} rows, planned {tp.moving}")


def _cross_tenant_pointers(conn: Connection, tenant: str) -> int:
    """Rows of *tenant* in the memory pair tables whose other end is in another tenant."""
    return int(
        conn.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM memory_links l
                     JOIN memories a ON a.id = l.source_memory_id
                     JOIN memories b ON b.id = l.target_memory_id
                    WHERE l.tenant_id = :t AND (a.tenant_id <> :t OR b.tenant_id <> :t))
                + (SELECT count(*) FROM memory_entities me
                     JOIN memories m ON m.id = me.memory_id
                     JOIN entities e ON e.id = me.entity_id
                    WHERE me.tenant_id = :t AND (m.tenant_id <> :t OR e.tenant_id <> :t))
                """
            ),
            {"t": tenant},
        ).scalar_one()
    )


def verify(conn: Connection, plan: Plan, pointers_before: int) -> list[str]:
    """Mismatches between the planned and the actual result. Empty = good."""
    errors: list[str] = []
    for table, tp in plan.tables.items():
        src_after = _count(conn, table, plan.source)
        tgt_after = _count(conn, table, plan.target)
        if src_after != tp.skipped + tp.kept:
            errors.append(f"{table}: source has {src_after}, expected {tp.skipped + tp.kept}")
        if tgt_after != tp.target_before + tp.moving:
            errors.append(
                f"{table}: target has {tgt_after}, expected {tp.target_before} + {tp.moving}"
            )
    after = _cross_tenant_pointers(conn, plan.target)
    if after > pointers_before:
        errors.append(f"cross-tenant links/mentions in target: {after}, before {pointers_before}")
    return errors


def apply_move(
    conn: Connection,
    plan: Plan,
    *,
    before_verify: Callable[[Connection], None] | None = None,
) -> None:
    """Do the move on *conn*, inside the caller's transaction. Raises on mismatch.

    *before_verify* is a test seam: it runs after the writes and before the
    checks, so a test can make the result disagree with the plan.
    """
    pointers_before = _cross_tenant_pointers(conn, plan.source) + _cross_tenant_pointers(
        conn, plan.target
    )
    _fold(conn, plan)
    _move_rows(conn, plan)
    if before_verify is not None:
        before_verify(conn)
    errors = verify(conn, plan, pointers_before)
    if errors:
        raise VerifyError("; ".join(errors))


# ── Entry points ──────────────────────────────────────────────


def tenant_present(conn: Connection, tenant: str) -> bool:
    """A tenant is present if it has a tenant_configs row or any memory."""
    return bool(
        conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM tenant_configs WHERE tenant_id = :t) "
                "OR EXISTS (SELECT 1 FROM memories WHERE tenant_id = :t)"
            ),
            {"t": tenant},
        ).scalar_one()
    )


def check_args(source: str, target: str, apply: bool, backup_file: str | None) -> None:
    if not source or not target:
        raise RefusedError("--source and --target are both required")
    if source == target:
        raise RefusedError("source and target are the same tenant")
    if apply:
        if not backup_file:
            raise RefusedError("--apply needs --backup-file (take a pg_dump first)")
        path = Path(backup_file)
        if not path.is_file() or path.stat().st_size == 0:
            raise RefusedError(f"backup file {backup_file} does not exist or is empty")


def _prepare(conn: Connection, source: str, target: str) -> Plan:
    """Checks that hold for both modes, then the plan."""
    for t in (source, target):
        if not tenant_present(conn, t):
            raise RefusedError(f"tenant {t!r} is not present (no tenant_configs row, no memories)")
    schema = discover(conn)
    problems = check_schema(schema)
    if problems:
        raise RefusedError("schema does not match the table lists:\n  " + "\n  ".join(problems))
    return build_plan(conn, schema, source, target)


def run(
    engine: Any,
    *,
    source: str,
    target: str,
    apply: bool = False,
    backup_file: str | None = None,
    allow_cross_refs: bool = False,
    out: Callable[[str], None] = print,
    before_verify: Callable[[Connection], None] | None = None,
) -> Plan:
    """Dry run (default) or apply. Raises :class:`RefusedError` / :class:`VerifyError`."""
    check_args(source, target, apply, backup_file)
    if not apply:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            try:
                plan = _prepare(conn, source, target)
                report(plan, out)
                out("\nDry run: nothing was written. Re-run with --apply --backup-file <dump>.")
                return plan
            finally:
                conn.rollback()
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        plan = _prepare(conn, source, target)
        report(plan, out)
        if plan.cross_refs and not allow_cross_refs:
            raise RefusedError(
                "rows would point across tenants (see above); re-run with --allow-cross-refs "
                "to accept that"
            )
        apply_move(conn, plan, before_verify=before_verify)
    out("\nApplied and verified: every table has the planned counts. Committed.")
    return plan


def report(plan: Plan, out: Callable[[str], None] = print) -> None:
    out(f"Move tenant {plan.source!r} -> {plan.target!r}\n")
    out(f"{'table':38} {'source':>7} {'target':>7} {'move':>6} {'folded':>7} {'left':>5}")
    for table, tp in plan.tables.items():
        out(
            f"{table:38} {tp.source_before:7} {tp.target_before:7} {tp.moving:6} "
            f"{tp.merged:7} {tp.skipped + tp.kept:5}"
        )
    out("\nfolded = deleted after repointing to an equal target row; left = stays in source.")
    for table, mapping in plan.maps.items():
        if mapping:
            out(f"  {table}: {len(mapping)} source rows equal a target row -> folded")
    dropped = sum(c.new is None for c in plan.memory_sessions)
    if plan.memory_sessions:
        out(
            f"  public.memory_sessions (no tenant_id): {len(plan.memory_sessions)} repointed, "
            f"{dropped} dropped as duplicates"
        )
    out(f"  approvals rewritten (ids inside repointed): {len(plan.approval_rewrites)}")
    if plan.invoices_skipped:
        out(f"  invoices left in source (number clash): {', '.join(plan.invoices_skipped)}")
    kept = plan.tables["approvals"].kept
    out(f"  approvals of other kinds left in source: {kept}")
    if plan.cross_refs:
        out("\nRows that would point across tenants after the move:")
        for ref, n in plan.cross_refs.items():
            out(f"  {ref}: {n}")
    if plan.graph_vertices is not None:
        out(
            f"\nAGE graph: {plan.graph_vertices} vertices tagged {plan.source!r} are NOT moved "
            "(the graph is a best-effort mirror of the tables)."
        )
    out("\nNot moved (configuration): " + ", ".join(sorted(LEAVE_CONFIG)))
    out("Not moved (operational history): " + ", ".join(sorted(LEAVE_OPERATIONAL)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", required=True, help="tenant to move data out of")
    parser.add_argument("--target", required=True, help="tenant to move data into")
    parser.add_argument("--apply", action="store_true", help="do it (default: dry run)")
    parser.add_argument("--backup-file", help="existing, non-empty pg_dump; required by --apply")
    parser.add_argument(
        "--allow-cross-refs",
        action="store_true",
        help="apply even if some rows that stay would point at rows that move",
    )
    args = parser.parse_args(argv)

    from life_graph.config import settings, sqlalchemy_sync_url

    engine = create_engine(sqlalchemy_sync_url(settings.database_url_sync))
    try:
        run(
            engine,
            source=args.source,
            target=args.target,
            apply=args.apply,
            backup_file=args.backup_file,
            allow_cross_refs=args.allow_cross_refs,
        )
    except RefusedError as exc:
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 2
    except VerifyError as exc:
        print(f"\nROLLED BACK: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
