"""Two copies on one machine: the owner's daily "prod" one and a "dev" one beside
it. The dev copy's worker must not run the scheduled jobs (brief, nudges, Memory
check, connector sync...): on a copy of the same data they would message the
owner twice. Settings are read once per process, so each case runs in its own."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COUNT = (
    "from life_graph.workers.settings import WorkerSettings as W; "
    "print(len(W.cron_jobs), len(W.functions))"
)


def _run(**env: str) -> tuple[int, int]:
    out = subprocess.run(
        [sys.executable, "-c", COUNT],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), **env},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    crons, functions = out.stdout.strip().splitlines()[-1].split()
    return int(crons), int(functions)


@pytest.mark.parametrize("value", ["true", ""])
def test_the_scheduled_jobs_run_by_default(value):
    env = {"LIFE_GRAPH_WORKER_CRON_ENABLED": value} if value else {}
    crons, _ = _run(**env)
    assert crons > 20


def test_a_dev_copy_runs_no_scheduled_jobs_but_keeps_its_functions():
    on, functions_on = _run(LIFE_GRAPH_WORKER_CRON_ENABLED="true")
    crons, functions = _run(LIFE_GRAPH_WORKER_CRON_ENABLED="false")
    assert crons == 0
    assert functions == functions_on  # queued jobs still run


async def test_health_names_the_edition(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from life_graph.config import settings
    from life_graph.main import app

    monkeypatch.setattr(settings, "edition", "dev")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        body = (await c.get("/health")).json()
    assert body["edition"] == "dev"
    assert body["profile"] == settings.profile
