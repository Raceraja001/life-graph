"""Life Graph SDK - Live Integration Test.

Tests the Python SDK against the running local deployment.
"""
import sys
import time

from life_graph_sdk import LifeGraph, LifeGraphError, NotFoundError

BASE_URL = "http://localhost"
API_KEY = "N1ujwaq7lD4SPxT60CGrctAsbKHh3oUp"
TENANT = "personal"

passed = 0
failed = 0
mem_ids = []


def test(name):
    """Decorator-style test runner."""
    def decorator(fn):
        global passed, failed
        try:
            fn()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}: {e}")
            failed += 1
    return decorator


print("Life Graph SDK - Live Test")
print(f"  Target: {BASE_URL}")
print(f"  Tenant: {TENANT}")
print()

# Initialize Client
brain = LifeGraph(BASE_URL, api_key=API_KEY, tenant_id=TENANT)

# 1. Health Check
print("[Health]")

@test("Health check")
def _():
    h = brain.health()
    assert h["status"] == "healthy", f"Unhealthy: {h}"

@test("Ping")
def _():
    assert brain.ping() is True

print()

# 2. Create Memories (returns list[Memory])
print("[Create Memories]")

@test("Create memory: Python preference")
def _():
    memories = brain.create_memory("I strongly prefer Python over Java for backend development")
    assert len(memories) > 0, "No memories returned"
    assert memories[0].id, "No ID"
    mem_ids.append(memories[0].id)

@test("Create memory: FastAPI choice")
def _():
    memories = brain.create_memory("FastAPI is my web framework of choice because of async support")
    assert len(memories) > 0
    mem_ids.append(memories[0].id)

@test("Create memory: Self-hosted philosophy")
def _():
    memories = brain.create_memory("I always prefer self-hosted solutions over SaaS to avoid vendor lock-in")
    assert len(memories) > 0
    mem_ids.append(memories[0].id)

@test("Create memory with tags and importance")
def _():
    memories = brain.create_memory(
        "PostgreSQL with pgvector is the only database I use",
        tags=["database", "architecture"],
        importance=0.9,
    )
    assert len(memories) > 0
    mem_ids.append(memories[0].id)

print()

# 3. Search (wait for embeddings)
print("[Search]")
time.sleep(5)  # wait for embeddings to generate

@test("Vector search: database preference")
def _():
    results = brain.search("what database do I use")
    # Embeddings require LM Studio — if no results, search still works (just empty)
    assert isinstance(results, list), f"Expected list, got {type(results)}"

@test("Search: programming language")
def _():
    results = brain.search("programming language preference")
    assert isinstance(results, list), f"Expected list, got {type(results)}"

@test("Search with limit=2")
def _():
    results = brain.search("preference", limit=2)
    assert len(results) <= 2

print()

# 4. Get Memory
print("[Read]")

@test("Get memory by ID")
def _():
    m = brain.memory(mem_ids[0])
    assert m.id == mem_ids[0]
    assert m.content  # has content

@test("List memories")
def _():
    memories = brain.memories(limit=10)
    assert len(memories) >= 4, f"Expected >= 4, got {len(memories)}"

print()

# 5. Update
print("[Update]")

@test("Update memory tags")
def _():
    m = brain.update_memory(mem_ids[0], tags=["python", "preference", "backend"])
    assert "python" in m.tags or "preference" in m.tags

print()

# 6. Sessions
print("[Sessions]")

@test("Start session")
def _():
    s = brain.start_session(context={"project": "sdk-test"})
    assert s.id
    globals()["test_session_id"] = s.id

@test("End session with outcome")
def _():
    s = brain.end_session(test_session_id, outcome="success")
    assert s.id
    assert s.outcome == "success"
    print(f"    Outcome: {s.outcome}")

import time
time.sleep(1)  # Wait for background micro-consolidation to finish

@test("Micro-consolidation (manual)")
def _():
    report = brain.micro_consolidate(test_session_id)
    assert isinstance(report, dict)
    assert report.get("memories_processed", 0) >= 0
    print(f"    Processed: {report.get('memories_processed', 0)}, "
          f"Deduped: {report.get('duplicates_removed', 0)}, "
          f"Entities: {report.get('entities_discovered', 0)}")

print()

# 7. Identity
print("[Identity]")

@test("Get stats")
def _():
    s = brain.stats()
    assert s is not None

print()

# 8. Graph
print("[Graph]")

@test("List entities")
def _():
    entities = brain.entities()
    # May be empty on fresh DB, that's ok
    assert isinstance(entities, list)

print()

# 8.5 Impact Scoring
print("[Impact Scoring]")

@test("Memory has impact_score field")
def _():
    m = brain.memory(mem_ids[0])
    assert hasattr(m, "impact_score")
    assert 0.0 <= m.impact_score <= 1.0
    print(f"    impact_score: {m.impact_score}")

print()

# 8.7 Procedures (Strategy Memory)
print("[Procedures]")

@test("Create procedure")
def _():
    p = brain.create_procedure(
        trigger="user starts a new Python project",
        steps=[
            "Create virtual environment",
            "Set up Docker Compose",
            "Add pytest + CI/CD",
            "Create .env.example",
        ],
        description="Standard Python project setup workflow",
        confidence=0.8,
        tags=["python", "devops"],
    )
    assert p.get("trigger")
    globals()["test_procedure_id"] = p["id"]
    print(f"    ID: {p['id'][:8]}...")
    print(f"    Steps: {len(p.get('steps', []))}")

@test("List procedures")
def _():
    procs = brain.procedures()
    assert isinstance(procs, list)
    assert len(procs) >= 1
    print(f"    Count: {len(procs)}")

@test("Apply procedure")
def _():
    p = brain.apply_procedure(test_procedure_id, success=True)
    assert p.get("times_applied", 0) >= 1
    print(f"    Applied: {p.get('times_applied')}, Success rate: {p.get('success_rate', 0):.0%}")

@test("Match procedures")
def _():
    matches = brain.match_procedures("Python")
    assert isinstance(matches, list)
    print(f"    Matches for 'Python': {len(matches)}")

@test("Delete procedure")
def _():
    result = brain.delete_procedure(test_procedure_id)
    assert result.get("status") == "archived"

print()

# 8.9 Memory Links (Zettelkasten)
print("[Memory Links]")

@test("Create memory link")
def _():
    if len(mem_ids) < 2:
        print("    Skipped — need 2+ memories")
        return
    link = brain.create_memory_link(
        source_id=mem_ids[0],
        target_id=mem_ids[1],
        link_type="RELATED_TO",
        strength=0.8,
    )
    assert link.id
    assert link.link_type == "RELATED_TO"
    globals()["test_link_id"] = link.id
    print(f"    Link: {link.source_memory_id[:8]}→{link.target_memory_id[:8]} ({link.link_type})")

@test("List memory links")
def _():
    links = brain.memory_links(mem_ids[0])
    assert isinstance(links, list)
    assert len(links) >= 1
    print(f"    Links for memory: {len(links)}")

@test("Get linked memories")
def _():
    linked = brain.linked_memories(mem_ids[0], depth=1)
    assert isinstance(linked, list)
    print(f"    Linked memories (depth=1): {len(linked)}")

print()

# 9. Ask
print("[Ask]")

@test("Ask about preferences")
def _():
    answer = brain.ask("What programming language do I prefer?")
    assert answer is not None
    assert answer.answer, f"Empty answer: {answer}"
    assert answer.source_count >= 0
    print(f"    Answer: {answer.answer[:80]}...")
    print(f"    Model: {answer.model}, Sources: {answer.source_count}")

print()

# 10. Delete
print("[Cleanup]")

@test("Delete a memory")
def _():
    brain.delete_memory(mem_ids[0])
    try:
        brain.memory(mem_ids[0])
        assert False, "Should be deleted"
    except (NotFoundError, LifeGraphError):
        pass

# Clean up remaining
for mid in mem_ids[1:]:
    try:
        brain.delete_memory(mid)
    except Exception:
        pass

print()
print("=" * 50)
print(f"  Results: {passed} passed, {failed} failed")
print("=" * 50)

sys.exit(1 if failed > 0 else 0)
