"""scripts/move_tenant_data.py against the real (test) database.

Every test builds its own pair of synthetic tenants with unique ids, so the
suite can share the test database with other runs. Nothing here touches the
dev or prod databases: tests/conftest.py has already pointed settings at
``<name>_test``.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session as OrmSession

from life_graph.config import settings, sqlalchemy_sync_url
from life_graph.models.assistant import Entity, MemoryEntity, ReviewCard
from life_graph.models.db import (
    AgentSession,
    Approval,
    Conversation,
    ConversationMessage,
    Intention,
    Memory,
    MemoryLink,
    MemorySession,
    Session,
    TenantConfig,
)
from tests.integration.conftest import db_reachable

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "move_tenant_data.py"
_spec = importlib.util.spec_from_file_location("move_tenant_data", _PATH)
mtd = importlib.util.module_from_spec(_spec)
# Registered first: @dataclass looks its module up in sys.modules.
sys.modules["move_tenant_data"] = mtd
_spec.loader.exec_module(mtd)

pytestmark = pytest.mark.skipif(not db_reachable(), reason="needs the test database")


@pytest.fixture(scope="module")
def engine():
    assert settings.database_url_sync.rpartition("/")[2].partition("?")[0].endswith("_test")
    eng = create_engine(sqlalchemy_sync_url(settings.database_url_sync))
    yield eng
    eng.dispose()


@pytest.fixture
def backup(tmp_path: Path) -> str:
    path = tmp_path / "before.dump"
    path.write_bytes(b"PGDMP synthetic")
    return str(path)


@dataclass
class World:
    src: str
    tgt: str
    ids: dict[str, uuid.UUID]


def _hash() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def _build(engine, *, cross_ref: bool = False) -> World:
    """Two tenants: a source with a duplicate of a target memory, and friends.

    source  m1 (active, hash h1)  — exact duplicate of target t1 → folded
            m2 (pending, hash h2) — moves
            m3 (archived, hash h1) — not live, so moves (not folded)
            entity x (same key as target's x) → merged; entity y moves
    """
    tag = uuid.uuid4().hex[:10]
    src, tgt = f"r3bsrc{tag}", f"r3btgt{tag}"
    h1, h2, h3 = _hash(), _hash(), _hash()
    i = {
        k: uuid.uuid4()
        for k in ("t1", "m1", "m2", "m3", "ex_t", "ex_s", "ey", "s1", "conv", "msg", "card")
        + ("ap_c", "ap_d", "ap_m")
    }
    with OrmSession(engine) as s, s.begin():
        s.add_all(
            [
                TenantConfig(tenant_id=src, plan="free", status="active"),
                Memory(id=i["t1"], tenant_id=tgt, content="alpha", content_hash=h1),
                Memory(id=i["m1"], tenant_id=src, content="alpha", content_hash=h1),
                Memory(
                    id=i["m2"], tenant_id=src, content="beta", content_hash=h2, status="pending"
                ),
                Memory(
                    id=i["m3"], tenant_id=src, content="alpha", content_hash=h1, status="archived"
                ),
                Entity(id=i["ex_t"], tenant_id=tgt, key=f"x{tag}", name="X", mentions=2),
                Entity(
                    id=i["ex_s"], tenant_id=src, key=f"x{tag}", name="X", mentions=3, role="pal"
                ),
                Entity(id=i["ey"], tenant_id=src, key=f"y{tag}", name="Y", mentions=1),
                Session(id=i["s1"], tenant_id=src),
            ]
        )
        s.flush()
        s.add_all(
            [
                MemoryEntity(memory_id=i["t1"], entity_id=i["ex_t"], tenant_id=tgt),
                MemoryEntity(memory_id=i["m1"], entity_id=i["ex_s"], tenant_id=src),
                MemoryEntity(memory_id=i["m2"], entity_id=i["ex_s"], tenant_id=src),
                MemoryEntity(memory_id=i["m2"], entity_id=i["ey"], tenant_id=src),
                MemoryLink(
                    source_memory_id=i["m1"],
                    target_memory_id=i["m2"],
                    link_type="RELATED_TO",
                    tenant_id=src,
                ),
                MemoryLink(
                    source_memory_id=i["m3"],
                    target_memory_id=i["m1"],
                    link_type="SUPERSEDES",
                    tenant_id=src,
                ),
                MemorySession(memory_id=i["m1"], session_id=i["s1"]),
                Intention(tenant_id=src, content="remind", source_memory=i["m1"]),
                ReviewCard(
                    id=i["card"],
                    tenant_id=src,
                    front="f",
                    back="b",
                    source_memory_id=i["m1"],
                    due_on=date.today(),
                    dedup_key=h3,
                ),
                Conversation(id=i["conv"], tenant_id=src),
                Approval(
                    id=i["ap_c"],
                    tenant_id=src,
                    kind="contradiction",
                    source="judgment",
                    source_ref=f"{i['m1']}|{i['m2']}",
                    title="t",
                    payload={"memory_id_old": str(i["m1"]), "memory_id_new": str(i["m2"])},
                ),
                Approval(
                    tenant_id=tgt,
                    kind="merge",
                    source="curator",
                    source_ref=f"shared{tag}",
                    title="t",
                ),
                Approval(
                    id=i["ap_m"],
                    tenant_id=src,
                    kind="merge",
                    source="curator",
                    source_ref=f"shared{tag}",
                    title="t",
                ),
                Approval(
                    id=i["ap_d"],
                    tenant_id=src,
                    kind="driver_plan",
                    source="driver",
                    source_ref=f"task{tag}",
                    title="t",
                ),
            ]
        )
        s.flush()
        s.add(
            ConversationMessage(
                id=i["msg"],
                conversation_id=i["conv"],
                tenant_id=src,
                role="assistant",
                content="c",
                cited_memory_ids=[i["m1"], i["m2"]],
            )
        )
        if cross_ref:
            s.add(AgentSession(tenant_id=src, user_message="hi", memory_session_id=i["s1"]))
    return World(src, tgt, i)


def _snapshot(engine, w: World) -> dict[str, list]:
    """Every row of every MOVE table (and memory_sessions) for both tenants, as text."""
    out: dict[str, list] = {}
    with engine.connect() as c:
        for table in [*mtd.MOVE, *mtd.LEAVE_CONFIG]:
            rows = c.execute(
                text(
                    f"SELECT t::text FROM {mtd._q(table)} t WHERE tenant_id IN (:a, :b) ORDER BY 1"
                ),
                {"a": w.src, "b": w.tgt},
            )
            out[table] = [r[0] for r in rows]
        out["memory_sessions"] = [
            r[0]
            for r in c.execute(
                text("SELECT t::text FROM memory_sessions t WHERE session_id = :s"),
                {"s": w.ids["s1"]},
            )
        ]
    return out


def _quiet(_: str) -> None:
    pass


def _scalar(engine, sql: str, **params):
    with engine.connect() as c:
        return c.execute(text(sql), params).scalar_one()


# ── The schema lists match the migrated schema ────────────────


def test_every_tenant_table_is_classified(engine):
    with engine.connect() as c:
        problems = mtd.check_schema(mtd.discover(c))
    assert problems == []


def test_check_schema_flags_unclassified_table_and_unregistered_fk():
    schema = mtd.Schema(
        tenant_tables={*mtd.MOVE, *mtd.LEAVE_CONFIG, *mtd.LEAVE_OPERATIONAL, "new_thing"},
        fks=[("new_thing", "memory_id", "memories")],
        tenant_uniques={"sessions": {"uq_sessions_new"}},
    )
    problems = "\n".join(mtd.check_schema(schema))
    assert "new_thing: has tenant_id but is not classified" in problems
    assert "new_thing.memory_id references folded table memories" in problems
    assert "sessions: per-tenant unique index uq_sessions_new" in problems


def test_check_schema_refuses_a_shadowed_tenant_table():
    schema = mtd.Schema(
        tenant_tables={*mtd.MOVE, *mtd.LEAVE_CONFIG, *mtd.LEAVE_OPERATIONAL},
        fks=[],
        tenant_uniques={},
        hidden={"other.memories"},
    )
    assert mtd.check_schema(schema) == [
        "other.memories: has tenant_id but bare names do not reach it (shadowed or off search_path)"
    ]


# ── Dry run ───────────────────────────────────────────────────


def test_dry_run_writes_nothing_and_reports_the_plan(engine):
    w = _build(engine)
    before = _snapshot(engine, w)
    lines: list[str] = []
    plan = mtd.run(engine, source=w.src, target=w.tgt, out=lines.append)
    assert _snapshot(engine, w) == before

    mem = plan.tables["memories"]
    assert (mem.source_before, mem.target_before, mem.merged, mem.moving) == (3, 1, 1, 2)
    assert plan.maps["memories"] == {str(w.ids["m1"]): str(w.ids["t1"])}
    assert plan.maps["entities"] == {str(w.ids["ex_s"]): str(w.ids["ex_t"])}
    me = plan.tables["memory_entities"]
    assert (me.merged, me.moving) == (1, 2)
    ap = plan.tables["approvals"]
    assert (ap.source_before, ap.merged, ap.kept, ap.moving) == (3, 1, 1, 1)
    assert "tenant_configs" not in plan.tables
    # The AGE graph is reported, not moved; these synthetic tenants have no vertices.
    assert plan.graph_vertices == 0
    text_out = "\n".join(lines)
    assert "Dry run: nothing was written" in text_out
    assert "memories" in text_out


def test_dry_run_transaction_is_read_only(engine, monkeypatch):
    """Even a buggy plan step cannot write during a dry run: the database refuses."""
    w = _build(engine)
    before = _snapshot(engine, w)
    real = mtd.build_plan

    def writing_plan(conn, *args):
        conn.execute(text("UPDATE memories SET content = 'x' WHERE tenant_id = :t"), {"t": w.src})
        return real(conn, *args)

    monkeypatch.setattr(mtd, "build_plan", writing_plan)
    with pytest.raises(DBAPIError, match="read-only transaction"):
        mtd.run(engine, source=w.src, target=w.tgt, out=_quiet)
    assert _snapshot(engine, w) == before


# ── Apply ─────────────────────────────────────────────────────


def test_apply_moves_memories_with_entities_links_and_approvals(engine, backup):
    w = _build(engine)
    i = {k: str(v) for k, v in w.ids.items()}
    mtd.run(engine, source=w.src, target=w.tgt, apply=True, backup_file=backup, out=_quiet)

    with engine.connect() as c:

        def q(sql: str, **p):
            return c.execute(text(sql), {"src": w.src, "tgt": w.tgt, **p}).all()

        # memories: m1 folded into t1, m2 and m3 moved; nothing left in source.
        assert q("SELECT count(*) FROM memories WHERE tenant_id = :src")[0][0] == 0
        assert {r[0] for r in q("SELECT id::text FROM memories WHERE tenant_id = :tgt")} == {
            i["t1"],
            i["m2"],
            i["m3"],
        }
        # entities: source x merged into target x (mentions added, role taken), y moved.
        assert q("SELECT mentions, role FROM entities WHERE id = :e", e=i["ex_t"])[0] == (5, "pal")
        assert q("SELECT count(*) FROM entities WHERE id = :e", e=i["ex_s"])[0][0] == 0
        assert q("SELECT tenant_id FROM entities WHERE id = :e", e=i["ey"])[0][0] == w.tgt
        # mentions: (m1, x) became (t1, x), which the target had → dropped.
        pairs = q(
            "SELECT memory_id::text, entity_id::text FROM memory_entities WHERE tenant_id = :tgt"
        )
        assert sorted(pairs) == sorted(
            [(i["t1"], i["ex_t"]), (i["m2"], i["ex_t"]), (i["m2"], i["ey"])]
        )
        # links repointed to t1 and moved.
        links = q(
            "SELECT source_memory_id::text, target_memory_id::text, tenant_id FROM memory_links "
            "WHERE source_memory_id::text = ANY(:ids) OR target_memory_id::text = ANY(:ids)",
            ids=[i["t1"], i["m2"], i["m3"]],
        )
        assert sorted(links) == sorted([(i["t1"], i["m2"], w.tgt), (i["m3"], i["t1"], w.tgt)])
        # sessions, memory_sessions, intentions, cards, citations repointed/moved.
        assert q("SELECT tenant_id FROM sessions WHERE id = :s", s=i["s1"])[0][0] == w.tgt
        assert q(
            "SELECT memory_id::text FROM memory_sessions WHERE session_id = :s", s=i["s1"]
        ) == [(i["t1"],)]
        assert q(
            "SELECT source_memory::text, tenant_id FROM intentions WHERE tenant_id IN (:src, :tgt)"
        ) == [(i["t1"], w.tgt)]
        assert q(
            "SELECT source_memory_id::text, tenant_id FROM review_cards WHERE id = :c", c=i["card"]
        ) == [(i["t1"], w.tgt)]
        cited = q(
            "SELECT cited_memory_ids::text[] FROM conversation_messages WHERE id = :m", m=i["msg"]
        )
        assert cited[0][0] == [i["t1"], i["m2"]]
        # approvals: the memory review item moved with its ids repointed; the
        # duplicate curator item was dropped; the dev-agent item stayed.
        ap = q(
            "SELECT tenant_id, source_ref, payload->>'memory_id_old' FROM approvals WHERE id = :a",
            a=i["ap_c"],
        )
        assert ap == [(w.tgt, f"{i['t1']}|{i['m2']}", i["t1"])]
        assert q("SELECT count(*) FROM approvals WHERE id = :a", a=i["ap_m"])[0][0] == 0
        assert q("SELECT tenant_id FROM approvals WHERE id = :a", a=i["ap_d"])[0][0] == w.src
        # configuration stays.
        assert q("SELECT count(*) FROM tenant_configs WHERE tenant_id = :src")[0][0] == 1


def test_apply_rolls_back_on_mismatch(engine, backup):
    w = _build(engine)
    before = _snapshot(engine, w)

    def sneak_in_a_row(conn):
        # A write the plan did not know about: the source is no longer empty.
        conn.execute(Memory.__table__.insert().values(content="late", tenant_id=w.src))

    with pytest.raises(mtd.VerifyError, match="memories: source has 1"):
        mtd.run(
            engine,
            source=w.src,
            target=w.tgt,
            apply=True,
            backup_file=backup,
            out=_quiet,
            before_verify=sneak_in_a_row,
        )
    assert _snapshot(engine, w) == before


def test_apply_refuses_cross_tenant_refs_unless_allowed(engine, backup):
    w = _build(engine, cross_ref=True)
    before = _snapshot(engine, w)
    with pytest.raises(mtd.RefusedError, match="across tenants"):
        mtd.run(engine, source=w.src, target=w.tgt, apply=True, backup_file=backup, out=_quiet)
    assert _snapshot(engine, w) == before

    plan = mtd.run(
        engine,
        source=w.src,
        target=w.tgt,
        apply=True,
        backup_file=backup,
        allow_cross_refs=True,
        out=_quiet,
    )
    assert plan.cross_refs == {"agent_sessions.memory_session_id -> sessions": 1}
    assert _scalar(engine, "SELECT count(*) FROM memories WHERE tenant_id = :t", t=w.src) == 0


# ── Refusals ──────────────────────────────────────────────────


def test_refuses_without_backup_file(engine, tmp_path):
    w = _build(engine)
    before = _snapshot(engine, w)
    with pytest.raises(mtd.RefusedError, match="needs --backup-file"):
        mtd.run(engine, source=w.src, target=w.tgt, apply=True, out=_quiet)
    with pytest.raises(mtd.RefusedError, match="does not exist or is empty"):
        mtd.run(
            engine,
            source=w.src,
            target=w.tgt,
            apply=True,
            backup_file=str(tmp_path / "missing.dump"),
            out=_quiet,
        )
    empty = tmp_path / "empty.dump"
    empty.write_bytes(b"")
    with pytest.raises(mtd.RefusedError, match="does not exist or is empty"):
        mtd.run(engine, source=w.src, target=w.tgt, apply=True, backup_file=str(empty), out=_quiet)
    assert _snapshot(engine, w) == before


def test_refuses_same_or_absent_tenant(engine, backup):
    w = _build(engine)
    with pytest.raises(mtd.RefusedError, match="same tenant"):
        mtd.run(engine, source=w.src, target=w.src, apply=True, backup_file=backup, out=_quiet)
    with pytest.raises(mtd.RefusedError, match="not present"):
        mtd.run(
            engine,
            source=w.src,
            target=f"r3bnobody{uuid.uuid4().hex[:8]}",
            apply=True,
            backup_file=backup,
            out=_quiet,
        )


def test_main_returns_2_on_refusal(capsys):
    assert mtd.main(["--source", "a", "--target", "a"]) == 2
    assert "same tenant" in capsys.readouterr().err
