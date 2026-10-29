"""LIFE_GRAPH_PROFILE (docs/modular_memory_service_plan.md, phase 1).

``memory_core`` serves the memory engine alone: its routers, none of the
extended domains', and no ARQ pool, agent drivers or personas at startup.
``full`` is everything, as before. Settings are read once per process, so each
profile is exercised in its own process: route tables by import, and a real
``uvicorn`` boot against the test database for memory_core.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

from tests.integration.conftest import db_reachable

ROOT = Path(__file__).resolve().parents[2]
CORE = [
    "/api/v1/memories",
    "/api/v1/search",
    "/api/v1/preferences",
    "/api/v1/identity",
    "/api/v1/capture",
    "/api/v1/graph",
    "/api/v1/sessions",
    "/api/v1/intentions",
    "/api/v1/health/memory",
]
EXTENDED = [
    "/api/v1/jarvis",
    "/api/v1/kernel",
    "/api/v1/kernel/drivers",
    "/api/v1/approvals",
    "/api/v1/watchers",
    "/api/v1/connectors",
    "/api/v1/documents",
    "/api/v1/integrations/telegram",
    "/api/v1/self-improving",
    "/api/v1/devices",
]

# The OpenAPI paths, not app.routes: FastAPI keeps an included router nested
# (_IncludedRouter) rather than copying its routes onto the app.
ROUTES = (
    "import json; from life_graph.main import app; "
    "print(json.dumps(sorted(app.openapi()['paths'])))"
)


def _env(profile: str, **extra: str) -> dict[str, str]:
    from life_graph.config import settings

    env = {**os.environ, "LIFE_GRAPH_PROFILE": profile, "PYTHONPATH": str(ROOT)}
    # The child must use the test database, never the development one.
    env["LIFE_GRAPH_DATABASE_URL"] = settings.database_url
    env["LIFE_GRAPH_DATABASE_URL_SYNC"] = settings.database_url_sync
    env.update(extra)
    return env


def _paths(profile: str) -> set[str]:
    out = subprocess.run(
        [sys.executable, "-c", ROUTES],
        cwd=ROOT,
        env=_env(profile),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return set(json.loads(out.stdout.strip().splitlines()[-1]))


def _has(paths: set[str], prefix: str) -> bool:
    return any(p == prefix or p.startswith(prefix + "/") for p in paths)


def test_memory_core_registers_the_memory_engine_only():
    paths = _paths("memory_core")
    assert [p for p in CORE if not _has(paths, p)] == []
    assert [p for p in EXTENDED if _has(paths, p)] == []


def test_full_registers_every_domain():
    paths = _paths("full")
    assert [p for p in CORE + EXTENDED if not _has(paths, p)] == []


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def core_server():
    if not db_reachable():
        pytest.skip("database unreachable")
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "life_graph.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=_env(
            "memory_core",
            LIFE_GRAPH_REQUIRE_EMBEDDING_BACKEND="false",
            LIFE_GRAPH_SERVICE_API_KEYS="",
            LIFE_GRAPH_API_KEY="",
            LIFE_GRAPH_ENVIRONMENT="development",
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    started = time.monotonic()
    try:
        while time.monotonic() - started < 120:
            if proc.poll() is not None:
                pytest.fail(f"memory_core did not boot: {proc.stderr.read()[-3000:]}")
            try:
                if httpx.get(f"{base}/live", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            pytest.fail("memory_core did not answer /live within 120 s")
        yield base, time.monotonic() - started
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_memory_core_boots_without_the_extended_domains_and_serves_memory(core_server):
    base, boot_s = core_server
    tenant = {"X-Tenant-ID": f"core_{uuid.uuid4().hex[:8]}"}

    health = httpx.get(f"{base}/health", timeout=30).json()
    started = set(health["checks"]["startup"]["subsystems"])
    for skipped in (
        "webhook_arq_pool",
        "webhook_handler",
        "agent_drivers",
        "seed_personas",
        "dev_task_queue",
        "connectors",
        "mcp_bridge",
    ):
        assert skipped not in started, skipped
    assert {"redis", "capture_processors", "preference_graph_sync"} <= started

    r = httpx.get(f"{base}/api/v1/health/memory", headers=tenant, timeout=60)
    body = r.json()
    assert body["profile"] == "memory_core"
    assert body["checks"]["postgres"]["status"] == "healthy"
    assert body["checks"]["pgvector"]["status"] == "healthy", body["checks"]["pgvector"]
    assert body["checks"]["memories"] == {"active": 0, "pending": 0, "total": 0}
    assert set(body["checks"]["capture_events"]) == {"total", "last_24h", "last_at"}
    assert "latency_ms" in body["checks"]["embeddings"]

    # Structured input is stored as given (no extraction).
    r = httpx.post(
        f"{base}/api/v1/memories/",
        json={
            "content": "The owner's test locker is number 41.",
            "tags": ["test"],
            "importance": 0.6,
            "source_type": "test",
        },
        headers=tenant,
        timeout=60,
    )
    assert r.status_code == 201, r.text
    r = httpx.post(
        f"{base}/api/v1/search/",
        json={"query": "locker number", "search_mode": "hybrid", "include_pending": True},
        headers=tenant,
        timeout=60,
    )
    assert r.status_code == 200, r.text

    assert httpx.get(f"{base}/api/v1/jarvis/conversations", headers=tenant).status_code == 404
    print(f"memory_core boot to /live: {boot_s:.1f}s")
