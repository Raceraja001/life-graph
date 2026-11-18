"""Where data lives: Postgres, Redis, the graph, object storage, the vault.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StorageSettings(BaseModel):
    """Where data lives: Postgres, Redis, the graph, object storage, the vault."""

    # ── Database ───────────────────────────────────────
    database_url: str = "postgresql+asyncpg://life_graph:life_graph@localhost:5432/life_graph"
    database_url_sync: str = "postgresql://life_graph:life_graph@localhost:5432/life_graph"
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)

    # ── Redis ──────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Knowledge Graph (Apache AGE) ───────────────────
    graph_enabled: bool = True
    """Whether the Apache AGE knowledge graph is available.

    AGE is a *compiled* Postgres extension needing ``shared_preload_libraries
    = age``, so it cannot be installed on managed Postgres (Supabase, Neon,
    RDS) or on the stock ``pgvector/pgvector:pg16`` image. Setting this to
    ``False`` short-circuits every graph call to an empty result instead of a
    connection attempt, and search degrades from vector+BM25+graph to
    vector+BM25. Nothing is lost in correctness: the graph leg only ever adds
    a proximity *boost* on top of the vector+BM25 score, so ranking is
    unchanged in kind, only in the ordering of entity-adjacent hits. Leave it
    ``True`` on a self-hosted server built from ``Dockerfile.postgres``; the
    runtime probes for AGE anyway and disables itself if it is missing."""

    # ── MinIO / Object Storage ─────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "life-graph"

    # ── Vault (services/vault.py — secrets the agent fills in) ──────────────
    # The key that encrypts vault_secrets. Urlsafe-base64 or hex, 32 bytes.
    # Never in git: set LIFE_GRAPH_VAULT_KEY, or leave empty and a key is
    # generated once into vault_key_file (mode 600) so a self-host works out
    # of the box. Losing the key loses the secrets — nothing can decrypt them.
    vault_key: str = ""
    vault_key_file: str = "~/.config/life-graph/vault.key"
