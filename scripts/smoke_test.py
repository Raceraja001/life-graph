#!/usr/bin/env python3
"""
Life Graph — Smoke Test
Proves the full memory → search → recall loop works end-to-end.

Usage:
    python scripts/smoke_test.py [--base-url http://localhost:8000]
"""
import argparse
import sys
import httpx
import time


BASE_URL = "http://localhost:8000"
TENANT = "smoke_test"
HEADERS = {"X-Tenant-ID": TENANT, "Content-Type": "application/json"}

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    BASE_URL = args.base_url

    client = httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30.0)

    print("\n🧪 Life Graph Smoke Test\n")

    # ── Step 1: Health Check ─────────────────────────────────────
    print("Step 1: Health Check")
    try:
        r = client.get("/health")
        check("Health endpoint responds", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("Postgres connected", data.get("postgres", {}).get("status") == "healthy",
                  str(data.get("postgres")))
            check("Redis connected", data.get("redis", {}).get("status") == "healthy",
                  str(data.get("redis")))
    except httpx.ConnectError:
        check("Server reachable", False, f"Cannot connect to {BASE_URL}")
        print("\n💀 Server not running. Start with: docker compose up -d")
        sys.exit(1)

    # ── Step 2: Create Memories ──────────────────────────────────
    print("\nStep 2: Create Memories")

    memories_to_create = [
        {
            "content": "I prefer FastAPI over Django and always use async Python. "
                       "I think Django is too opinionated for microservices.",
            "source_type": "manual",
        },
        {
            "content": "My deployment target is a self-hosted VPS running Ubuntu. "
                       "I use Docker Compose for everything and avoid Kubernetes.",
            "source_type": "manual",
        },
        {
            "content": "I decided to use PostgreSQL with pgvector instead of ChromaDB "
                       "because I want a single database for relational, vector, and graph data.",
            "source_type": "manual",
        },
    ]

    memory_ids = []
    for i, mem in enumerate(memories_to_create):
        r = client.post("/api/v1/memories/", json=mem)
        ok = r.status_code in (200, 201)
        check(f"Memory {i+1} created", ok, f"status={r.status_code} body={r.text[:200]}")
        if ok:
            data = r.json()
            mid = data.get("id") or data.get("memory", {}).get("id")
            if mid:
                memory_ids.append(mid)

    # Small delay for embedding generation
    time.sleep(2)

    # ── Step 3: List Memories ────────────────────────────────────
    print("\nStep 3: List Memories")
    r = client.get("/api/v1/memories/")
    check("List endpoint works", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("memories", []))
        check(f"Found {len(items)} memories", len(items) >= 3, f"only {len(items)}")

    # ── Step 4: Semantic Search ──────────────────────────────────
    print("\nStep 4: Semantic Search")
    r = client.post("/api/v1/search/", json={
        "query": "what web framework does the user prefer?",
        "limit": 5,
    })
    check("Search endpoint works", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        results = data if isinstance(data, list) else data.get("results", data.get("memories", []))
        check(f"Search returned {len(results)} results", len(results) >= 1)
        if results:
            top = results[0]
            content = top.get("content", "")
            check("Top result mentions FastAPI", "fastapi" in content.lower(),
                  f"got: {content[:80]}")

    # ── Step 5: Start Session + Proactive Recall ─────────────────
    print("\nStep 5: Session + Proactive Recall")
    r = client.post("/api/v1/sessions/start", json={
        "context": {"project": "new-saas-app", "task": "deploy to VPS"},
    })
    session_ok = r.status_code in (200, 201)
    check("Session started", session_ok, f"status={r.status_code}")

    session_id = None
    if session_ok:
        data = r.json()
        session_id = data.get("id") or data.get("session_id")

    if session_id:
        r = client.post("/api/v1/search/recall", json={
            "context": {"project": "new-saas-app", "task": "deploy to VPS"},
            "session_id": session_id,
        })
        check("Recall endpoint works", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            # Recall should surface VPS/Docker memory
            all_text = str(data).lower()
            check("Recall surfaces deployment memory",
                  "vps" in all_text or "docker" in all_text or "ubuntu" in all_text,
                  f"recall response did not mention VPS/Docker")

    # ── Step 6: Natural Language Q&A ─────────────────────────────
    print("\nStep 6: Natural Language Q&A")
    r = client.post("/api/v1/search/ask", json={
        "question": "Why did the user choose PostgreSQL over ChromaDB?",
    })
    check("Ask endpoint works", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        answer = str(data).lower()
        check("Answer references single database",
              "single" in answer or "relational" in answer or "vector" in answer or "pgvector" in answer,
              f"answer: {str(data)[:200]}")

    # ── Step 7: End Session ──────────────────────────────────────
    print("\nStep 7: Cleanup")
    if session_id:
        r = client.post(f"/api/v1/sessions/{session_id}/end", json={
            "summary": "Smoke test session",
        })
        check("Session ended", r.status_code == 200, f"status={r.status_code}")

    # ── Results ──────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    if failed == 0:
        print("🎉 All checks passed! Life Graph is working end-to-end.")
    else:
        print("⚠️  Some checks failed. Review output above.")
    print(f"{'='*50}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
