# ⚡ Life Graph — Quickstart

Get Life Graph running locally in under 5 minutes.

---

## 📋 Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Docker + Docker Compose** | Latest | Required for Option 1; also needed for Postgres/Redis in Option 2 |
| **Python** | 3.11+ | Required for Option 2 (local development) |
| **LM Studio** | Any | _Optional_ — only needed if you want local LLM inference |

---

## 🐳 Option 1: Docker (Recommended)

The fastest path. One command spins up everything.

```bash
# Clone and start
git clone <repo-url>
cd agents

# Create .env from the example
cp .env.example .env

# Start all services
docker compose up -d
```

This brings up four services:

| Service | URL / Address | Purpose |
|---|---|---|
| **app** | [http://localhost:8000](http://localhost:8000) | API server + Swagger UI |
| **postgres** | `localhost:5432` | Primary database |
| **redis** | `localhost:6379` | Caching & task queue |
| **minio** | [http://localhost:9001](http://localhost:9001) | Object storage console |

Once containers are healthy, run migrations and verify:

```bash
# Run database migrations
docker compose exec app alembic upgrade head

# Check health
curl http://localhost:8000/health
```

> [!TIP]
> If `curl` returns `{"status": "ok"}`, you're good to go. Jump to [First API Call](#-first-api-call).

---

## 🛠️ Option 2: Local Development

Use this when you want hot-reload, breakpoints, or are actively developing.

### 1. Create & activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 3. Start infrastructure services

Postgres and Redis are still required — run them via Docker:

```bash
docker compose up -d postgres redis
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the API server

```bash
uvicorn life_graph.main:app --reload --port 8000
```

### 6. Start the background worker (separate terminal)

```bash
arq life_graph.workers.settings.WorkerSettings
```

> [!NOTE]
> The worker handles async tasks like embedding generation and deduplication. The API will accept requests without it, but background processing won't run.

---

## 🚀 First API Call

With the server running at `http://localhost:8000`, try these commands:

### Create a memory

```bash
curl -X POST http://localhost:8000/api/v1/memories/ \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo' \
  -d '{"content": "I prefer dark mode and use Vim keybindings", "source_type": "manual"}'
```

### Search memories

```bash
curl -X POST http://localhost:8000/api/v1/search/ \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo' \
  -d '{"query": "what editor settings does the user prefer?"}'
```

### List all memories

```bash
curl http://localhost:8000/api/v1/memories/ \
  -H 'X-Tenant-ID: demo'
```

### Start a session

```bash
curl -X POST http://localhost:8000/api/v1/sessions/start \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo' \
  -d '{"context": {"project": "my-app", "task": "fix login bug"}}'
```

### Proactive recall

Use the `session_id` returned from the previous call:

```bash
curl -X POST http://localhost:8000/api/v1/search/recall \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo' \
  -d '{"context": {"project": "my-app"}, "session_id": "<session-id>"}'
```

> [!IMPORTANT]
> Every request requires the `X-Tenant-ID` header. Use `demo` for local development.

---

## 🗺️ Key Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI (interactive API docs) |
| `POST` | `/api/v1/memories/` | Create a new memory |
| `GET` | `/api/v1/memories/` | List all memories |
| `GET` | `/api/v1/memories/{id}` | Get a specific memory |
| `PUT` | `/api/v1/memories/{id}` | Update a memory |
| `DELETE` | `/api/v1/memories/{id}` | Delete a memory |
| `POST` | `/api/v1/search/` | Semantic search across memories |
| `POST` | `/api/v1/search/recall` | Proactive context recall |
| `POST` | `/api/v1/sessions/start` | Start a new session |
| `GET` | `/api/v1/sessions/{id}` | Get session details |
| `POST` | `/api/v1/sessions/{id}/end` | End a session |
| `GET` | `/api/v1/graph/` | Query the knowledge graph |
| `GET` | `/api/v1/graph/entities` | List extracted entities |
| `GET` | `/api/v1/graph/relationships` | List entity relationships |

---

## ⚙️ Environment Variables

All configuration is managed through environment variables prefixed with `LIFE_GRAPH_`.

| Variable | Description | Default |
|---|---|---|
| `LIFE_GRAPH_DATABASE_URL` | PostgreSQL connection URL (asyncpg format) | — |
| `LIFE_GRAPH_REDIS_URL` | Redis connection URL | — |
| `LIFE_GRAPH_ENVIRONMENT` | Runtime environment: `development`, `staging`, `production` | `development` |
| `LIFE_GRAPH_LOG_FORMAT` | Log output format: `text` or `json` | `text` |
| `LIFE_GRAPH_SERVICE_API_KEYS` | Comma-separated API keys for authentication | — |
| `LIFE_GRAPH_LM_STUDIO_URL` | Endpoint for local LLM via LM Studio | — |
| `LIFE_GRAPH_EMBEDDING_MODEL` | Sentence-transformer model for embeddings | `all-mpnet-base-v2` |
| `LIFE_GRAPH_DEDUP_ENABLED` | Enable memory deduplication | `true` |
| `LIFE_GRAPH_DEDUP_THRESHOLD` | Cosine similarity threshold for dedup | `0.92` |

> [!TIP]
> Copy `.env.example` to `.env` and edit — all variables are documented there with sensible defaults for local development.

---

## 🧪 Running Tests

```bash
# Install dev dependencies (if you haven't already)
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests (requires Postgres + Redis running)
pytest tests/integration/ -v
```

---

## 📖 Swagger UI

Once the server is running, open your browser to:

👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

This gives you a fully interactive API explorer — try requests directly from the browser, inspect schemas, and see response formats without writing any code.

---

## 🧭 What's Next?

- Browse the [Swagger UI](http://localhost:8000/docs) to explore all endpoints
- Read the full [Architecture docs](./ARCHITECTURE.md) to understand the system design
- Check [Contributing guidelines](./CONTRIBUTING.md) before submitting PRs
