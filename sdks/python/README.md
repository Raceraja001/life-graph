# Life Graph SDK

Python SDK for the [Life Graph](http://localhost:8000) memory system. Store, search, and explore memories with a clean Pythonic API.

## Installation

```bash
pip install life-graph-sdk

# Or install from source
pip install -e /path/to/sdks/python
```

## Quick Start

```python
from life_graph_sdk import LifeGraph

brain = LifeGraph("http://localhost:8000")

# Store a memory
memories = brain.remember("I prefer Python over Java for backend work")
print(f"Created {len(memories)} memories")

# Search memories
results = brain.search("programming language preference")
for r in results:
    print(f"[{r.score:.2f}] {r.content}")

# List all memories
for m in brain.memories():
    print(f"{m.id}: {m.content[:80]}")
```

## Sync Client

```python
from life_graph_sdk import LifeGraph

# Basic initialization
brain = LifeGraph("http://localhost:8000")

# With authentication
brain = LifeGraph("http://localhost:8000", api_key="your-api-key")

# As a context manager (auto-closes connections)
with LifeGraph() as brain:
    brain.remember("Context-managed memory")
```

### Health Check

```python
# Get health info
health = brain.health()

# Simple ping
if brain.ping():
    print("API is up!")
```

### Memory Operations

```python
# Store text as memories
memories = brain.remember("I graduated from MIT in 2020 with a CS degree")

# List all memories
all_memories = brain.memories()

# Get a specific memory
memory = brain.memory("some-memory-id")

# Delete a memory
brain.delete_memory("some-memory-id")
```

### Search

```python
# Semantic search
results = brain.search("education background", limit=5)
for result in results:
    print(f"Score: {result.score}")
    print(f"Content: {result.content}")
    print(f"Tags: {result.tags}")
```

### Multi-Modal Ingestion

```python
# Voice memo
result = brain.ingest_voice("recording.mp3")
print(f"Transcript: {result.transcript}")

# Image (OCR)
result = brain.ingest_image("whiteboard.jpg")
print(f"OCR text: {result.ocr_text}")

# Document (PDF, DOCX, etc.)
result = brain.ingest_document("notes.pdf")
print(f"Chunks: {result.chunks}")

# Also accepts file-like objects
with open("photo.png", "rb") as f:
    result = brain.ingest_image(f)
```

### Knowledge Graph

```python
# List entities (optionally filter by label)
people = brain.entities(label="Person")
for entity in people:
    print(f"{entity.name} ({entity.label})")

# Get entity details
details = brain.entity("Python")

# Find path between entities
path = brain.graph_path(from_name="Python", to_name="MIT")

# Raw Cypher query
results = brain.graph_query("MATCH (n:Person) RETURN n.name LIMIT 10")

# Hybrid graph + vector search
results = brain.graph_search("programming skills", limit=5)
```

### Statistics

```python
stats = brain.stats()
print(f"Memories: {stats.memory_count}")
print(f"Intentions: {stats.intention_count}")
print(f"Knowledge gaps: {stats.gap_count}")
print(f"Sessions: {stats.session_count}")
```

## Async Client

The async client has an identical API — just use `await` and `async with`:

```python
import asyncio
from life_graph_sdk import AsyncLifeGraph

async def main():
    async with AsyncLifeGraph("http://localhost:8000") as brain:
        # Store memories
        memories = await brain.remember("Async memory storage")

        # Search
        results = await brain.search("memory", limit=5)
        for r in results:
            print(r.content)

        # Multi-modal
        result = await brain.ingest_voice("meeting.mp3")
        print(result.transcript)

        # Graph
        entities = await brain.entities(label="Person")
        stats = await brain.stats()

asyncio.run(main())
```

## Error Handling

The SDK raises specific exceptions for different error types:

```python
from life_graph_sdk import LifeGraph, NotFoundError, ValidationError, ServerError

brain = LifeGraph()

try:
    memory = brain.memory("nonexistent-id")
except NotFoundError as e:
    print(f"Not found: {e} (status: {e.status_code})")
except ValidationError as e:
    print(f"Bad request: {e}")
except ServerError as e:
    print(f"Server error: {e}")
```

| Exception | HTTP Status | When |
|---|---|---|
| `NotFoundError` | 404 | Resource doesn't exist |
| `ValidationError` | 400, 422 | Invalid request data |
| `ServerError` | 5xx | Internal server error |
| `LifeGraphError` | any other | Catch-all for other errors |

## Data Types

All API responses are returned as typed dataclasses:

- **`Memory`** — id, content, tags, properties, importance, confidence, reasoning, source_type, created_at, access_count
- **`SearchResult`** — content, tags, score, importance, properties
- **`IngestResult`** — memories_created, minio_key, transcript, ocr_text, text_length, chunks
- **`GraphEntity`** — name, label, properties
- **`Stats`** — memory_count, intention_count, gap_count, session_count

## License

MIT
