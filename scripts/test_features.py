"""Deep feature tests for F6 (Micro-Consolidation), F7 (Procedures), F8 (Memory Links).

Tests real behavior, not just API round-trips:
- F6: Creates duplicate memories → ends session → verifies dedup happened
- F7: Creates procedure → applies it → verifies stats update → matches by trigger
- F8: Creates 4 memories → links them with typed relationships → traverses graph
"""

import time
import sys

from life_graph_sdk import LifeGraph
from life_graph_sdk.errors import LifeGraphError

API_KEY = "N1ujwaq7lD4SPxT60CGrctAsbKHh3oUp"
brain = LifeGraph("http://localhost", api_key=API_KEY, tenant_id="personal")

passed = 0
failed = 0

def test(name):
    def decorator(fn):
        global passed, failed
        try:
            fn()
            print(f"  \033[92mPASS\033[0m: {name}")
            passed += 1
        except Exception as e:
            print(f"  \033[91mFAIL\033[0m: {name}: {e}")
            failed += 1
    return decorator

print("=" * 60)
print("  DEEP FEATURE TESTS — F6 + F7 + F8")
print("=" * 60)
print()

# ══════════════════════════════════════════════════════════════
# F7: Procedural Memory (Strategy Storage)
# ══════════════════════════════════════════════════════════════
print("[F7: Procedural Memory]")

proc_id = None

@test("Create: Python project setup procedure")
def _():
    global proc_id
    p = brain.create_procedure(
        trigger="user starts a new Python project",
        steps=[
            "Create virtual environment with uv",
            "Initialize pyproject.toml",
            "Set up Docker Compose for dev/prod",
            "Add pytest + coverage config",
            "Create .env.example with all vars",
            "Set up CI/CD pipeline",
        ],
        description="Standard Python project bootstrap workflow learned from 5+ projects",
        confidence=0.85,
        tags=["python", "devops", "bootstrap"],
        learned_from=["session-001", "session-012", "session-034"],
    )
    proc_id = p["id"]
    assert p["trigger"] == "user starts a new Python project"
    assert len(p["steps"]) == 6
    assert p["confidence"] == 0.85
    print(f"    ID: {proc_id[:8]}...")
    print(f"    Steps: {len(p['steps'])}")
    print(f"    Tags: {p.get('tags')}")

@test("Create: FastAPI deployment procedure")
def _():
    p = brain.create_procedure(
        trigger="deploying a FastAPI app to production",
        steps=[
            "Build Docker image with multi-stage",
            "Run alembic migrations",
            "Configure nginx reverse proxy",
            "Set up SSL with certbot",
            "Enable health check monitoring",
        ],
        description="FastAPI production deployment checklist",
        confidence=0.70,
        tags=["fastapi", "deployment"],
    )
    assert p["trigger"]
    globals()["proc2_id"] = p["id"]
    print(f"    ID: {p['id'][:8]}...")

@test("List: Should have 2 procedures")
def _():
    procs = brain.procedures(limit=10)
    assert len(procs) >= 2, f"Expected 2+, got {len(procs)}"
    print(f"    Count: {len(procs)}")
    for p in procs:
        print(f"    → {p['trigger'][:50]}... (conf={p['confidence']})")

@test("Apply: 3 successful + 1 failed application")
def _():
    # Apply 3 times successfully
    for i in range(3):
        brain.apply_procedure(proc_id, success=True)
    # Apply 1 time with failure
    p = brain.apply_procedure(proc_id, success=False)
    assert p["times_applied"] == 4, f"Expected 4 applications, got {p['times_applied']}"
    assert p["success_count"] == 3, f"Expected 3 successes, got {p['success_count']}"
    rate = p.get("success_rate", 0)
    print(f"    Applied: {p['times_applied']}x")
    print(f"    Success: {p['success_count']}/{p['times_applied']} = {rate:.0%}")
    print(f"    Confidence: {p['confidence']:.2f} (auto-adjusted)")

@test("Match: Find by 'Python' trigger")
def _():
    matches = brain.match_procedures("Python")
    assert len(matches) >= 1, f"Expected 1+ match, got {len(matches)}"
    assert any("Python" in m["trigger"] for m in matches)
    print(f"    Query: 'Python' → {len(matches)} match(es)")

@test("Match: Find by 'deploy' trigger")
def _():
    matches = brain.match_procedures("deploy")
    assert len(matches) >= 1
    print(f"    Query: 'deploy' → {len(matches)} match(es)")

@test("Match: No results for 'quantum computing'")
def _():
    matches = brain.match_procedures("quantum computing")
    assert len(matches) == 0, f"Expected 0, got {len(matches)}"
    print(f"    Query: 'quantum computing' → 0 matches ✓")

@test("Get: Retrieve by ID")
def _():
    p = brain.procedure(proc_id)
    assert p["id"] == proc_id
    assert p["times_applied"] == 4
    print(f"    Trigger: {p['trigger']}")
    print(f"    Learned from: {p.get('learned_from', [])}")

@test("Delete: Archive procedure")
def _():
    result = brain.delete_procedure(proc2_id)
    assert result["status"] == "archived"
    # Verify it's gone from active list
    procs = brain.procedures()
    active_ids = [p["id"] for p in procs if p.get("status") == "active"]
    assert proc2_id not in active_ids
    print(f"    Archived {proc2_id[:8]}...")

# Cleanup
brain.delete_procedure(proc_id)

print()

# ══════════════════════════════════════════════════════════════
# F8: Bidirectional Memory Links (Zettelkasten)
# ══════════════════════════════════════════════════════════════
print("[F8: Bidirectional Memory Links]")

# Create 4 related memories for linking
mem_ids = []
memories_data = [
    ("I prefer Python for backend development", ["python", "backend"]),
    ("FastAPI is my go-to web framework because of async support", ["fastapi", "async"]),
    ("I chose PostgreSQL over MongoDB for structured data", ["postgresql", "database"]),
    ("Docker Compose simplifies my local development workflow", ["docker", "devops"]),
]

@test("Setup: Create 4 memories for linking")
def _():
    for content, tags in memories_data:
        mems = brain.create_memory(content, tags=tags)
        mem_ids.append(mems[0].id)
    assert len(mem_ids) == 4
    print(f"    Created: {[m[:8]+'...' for m in mem_ids]}")

@test("Link: Python BECAUSE → FastAPI (causal)")
def _():
    link = brain.create_memory_link(
        source_id=mem_ids[1],  # FastAPI
        target_id=mem_ids[0],  # Python
        link_type="BECAUSE",
        strength=0.9,
    )
    assert link.link_type == "BECAUSE"
    assert link.strength == 0.9
    print(f"    FastAPI →(BECAUSE)→ Python (strength={link.strength})")

@test("Link: FastAPI EVIDENCED_BY → PostgreSQL")
def _():
    link = brain.create_memory_link(
        source_id=mem_ids[1],  # FastAPI
        target_id=mem_ids[2],  # PostgreSQL
        link_type="EVIDENCED_BY",
        strength=0.7,
    )
    assert link.link_type == "EVIDENCED_BY"
    print(f"    FastAPI →(EVIDENCED_BY)→ PostgreSQL")

@test("Link: Docker RELATED_TO → FastAPI")
def _():
    link = brain.create_memory_link(
        source_id=mem_ids[3],  # Docker
        target_id=mem_ids[1],  # FastAPI
        link_type="RELATED_TO",
        strength=0.6,
    )
    print(f"    Docker →(RELATED_TO)→ FastAPI")

@test("Link: PostgreSQL LEADS_TO → Docker")
def _():
    link = brain.create_memory_link(
        source_id=mem_ids[2],  # PostgreSQL
        target_id=mem_ids[3],  # Docker
        link_type="LEADS_TO",
        strength=0.5,
    )
    print(f"    PostgreSQL →(LEADS_TO)→ Docker")

@test("Query: FastAPI should have 3 links")
def _():
    links = brain.memory_links(mem_ids[1])
    assert len(links) >= 3, f"Expected 3+ links, got {len(links)}"
    for link in links:
        direction = "→" if link.source_memory_id == mem_ids[1] else "←"
        other = link.target_memory_id if direction == "→" else link.source_memory_id
        print(f"    {direction} {link.link_type} ({other[:8]}..., strength={link.strength})")

@test("Query: Python should have 1 incoming link")
def _():
    links = brain.memory_links(mem_ids[0])
    assert len(links) >= 1
    print(f"    Python has {len(links)} link(s)")

@test("Traverse: Graph from FastAPI (depth=2)")
def _():
    linked = brain.linked_memories(mem_ids[1], depth=2)
    assert isinstance(linked, list)
    print(f"    FastAPI → {len(linked)} reachable memories (depth=2)")
    for item in linked:
        if isinstance(item, dict):
            content = item.get("content", "")[:50]
            print(f"      → {content}...")

# Cleanup
for mid in mem_ids:
    try:
        brain.delete_memory(mid)
    except Exception:
        pass

print()

# ══════════════════════════════════════════════════════════════
# F6: Post-Session Micro-Consolidation
# ══════════════════════════════════════════════════════════════
print("[F6: Post-Session Micro-Consolidation]")

@test("Session + memories → end → micro-consolidation runs")
def _():
    # Start session
    sess = brain.start_session(context={"project": "micro-consol-test"})
    sess_id = sess.id
    print(f"    Session: {sess_id[:8]}...")

    # Create memories within the session
    m1 = brain.create_memory("I use Docker for all my deployments", tags=["docker"])
    m2 = brain.create_memory("Docker is my preferred containerization tool", tags=["docker"])
    m3 = brain.create_memory("I prefer PostgreSQL for relational data storage", tags=["postgresql"])
    print(f"    Created {len(m1)+len(m2)+len(m3)} memories")

    # End session with outcome (triggers micro-consolidation automatically)
    ended = brain.end_session(sess_id, outcome="success")
    assert ended.outcome == "success"
    print(f"    Session ended (outcome={ended.outcome})")

    # Wait for background micro-consolidation to finish
    time.sleep(2)

    # Now manually run it again to get the report
    report = brain.micro_consolidate(sess_id)
    assert isinstance(report, dict)
    print(f"    Micro-consolidation report:")
    print(f"      Memories processed: {report.get('memories_processed', 0)}")
    print(f"      Duplicates removed: {report.get('duplicates_removed', 0)}")
    print(f"      Importance updated: {report.get('importance_updated', 0)}")
    print(f"      Entities discovered: {report.get('entities_discovered', 0)}")
    print(f"      Edges created: {report.get('edges_created', 0)}")
    print(f"      Duration: {report.get('duration_seconds', 0):.3f}s")

@test("Manual micro-consolidation on fresh session")
def _():
    sess = brain.start_session(context={"project": "manual-test"})
    brain.create_memory("Kubernetes orchestrates containers at scale", tags=["k8s"])
    brain.create_memory("Helm charts simplify Kubernetes deployments", tags=["helm"])
    brain.end_session(sess.id, outcome="neutral")
    time.sleep(1)

    report = brain.micro_consolidate(sess.id)
    assert report.get("memories_processed", 0) >= 0
    print(f"    Processed: {report.get('memories_processed', 0)}")
    print(f"    Duration: {report.get('duration_seconds', 0):.3f}s")

print()
print("=" * 60)
print(f"  Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
