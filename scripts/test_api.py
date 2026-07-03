"""Quick end-to-end test of the Life Graph API."""
import httpx
import json
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

base = "http://localhost:8000"
client = httpx.Client(timeout=60.0)

# 1. Ingest memories via text
print("=== Ingesting memories ===")
texts = [
    "I always use PostgreSQL for databases. Remember this: never use eval() in production.",
    "I decided to use Docker for all deployments. TODO: add rate limiting to the API endpoints.",
    "I switched to Ruff from Flake8 for linting. My go-to testing framework is pytest.",
    "I prefer dark mode in all my editors. I use VS Code as my primary editor.",
    "Important: always run tests before deploying. I should refactor the auth module later.",
]

for i, text in enumerate(texts, 1):
    r = client.post(f"{base}/admin/ingest", json={"text": text})
    count = len(r.json()) if r.status_code == 201 else 0
    print(f"  Ingest {i}: {r.status_code} ({count} memories created)")

# 2. Search
print("\n=== Semantic Search ===")
queries = [
    "what database do I prefer",
    "what linter do I use",
    "what should I remember about production",
]
for q in queries:
    r = client.post(f"{base}/search/", json={"query": q, "limit": 3})
    print(f"\n  Q: {q}")
    if r.status_code == 200:
        data = r.json()
        for m in data.get("results", [])[:3]:
            content = m.get("content", "")[:70]
            score = m.get("score", 0)
            print(f"    [{score:.2f}] {content}")
    else:
        print(f"    Error: {r.status_code} {r.text[:100]}")

# 3. List all memories
print("\n=== All memories ===")
r = client.get(f"{base}/memories/")
memories = r.json()
print(f"  Total: {len(memories)} memories stored")
for m in memories[:8]:
    content = m.get("content", "")[:60]
    tags = m.get("tags", [])
    print(f"  [{','.join(tags):<12}] {content}")

# 4. Stats
print("\n=== Stats ===")
r = client.get(f"{base}/admin/stats")
print(json.dumps(r.json(), indent=2))

print("\n=== Life Graph is ALIVE! ===")
