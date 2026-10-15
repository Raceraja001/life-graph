"""Node toolchain in the verifier sandbox, end to end, against a real app.

The pilot app (tests/fixtures/apps/node-todo) is copied to a temp dir and
checked the way a dev task's worktree is:
- tests_pass runs its `npm test`;
- acceptance_tests_pass runs one bound vitest test by name;
- app_e2e_pass starts the server inside the sandbox and drives it over HTTP.

Each check must pass on the app as written and FAIL once the app is broken,
otherwise it proves nothing.

Needs docker, the node image (docker build -t life-graph-verifier:node22
docker/verifier-node) and network for the one-time `npm ci` into the cache.
Skipped otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "apps" / "node-todo"
NODE = {"sandbox_toolchain": "node"}
E2E = {
    **NODE,
    "sandbox_start_command": "node src/server.mjs",
    "sandbox_app_port": 3456,
    "sandbox_e2e_command": "node tests/e2e/smoke.mjs",
}


def _docker_image(image: str) -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "image", "inspect", image], capture_output=True, timeout=30
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def app(tmp_path, monkeypatch):
    from life_graph.config import settings

    if not _docker_image(settings.verifier_sandbox_node_image):
        pytest.skip(f"{settings.verifier_sandbox_node_image} not built")
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    # Shared across tests in the run so `npm ci` happens once.
    cache = Path("/tmp/lg-node-sandbox-test-cache")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(cache))
    work = tmp_path / "work"
    shutil.copytree(FIXTURE, work)
    return work


async def _check(name: str, workdir: Path, ctx: dict):
    from life_graph.services.verifiers import verifier_chain

    (result,) = await verifier_chain.run_chain([name], workdir, ctx)
    return result


@pytest.mark.asyncio
async def test_tests_pass_runs_the_apps_own_test_script(app):
    result = await _check("tests_pass", app, NODE)
    assert result.passed is True, result.evidence


@pytest.mark.asyncio
async def test_a_bound_js_acceptance_test_passes_and_a_missing_one_fails(app):
    ok = await _check(
        "acceptance_tests_pass",
        app,
        {**NODE, "acceptance_tests": ["tests/todos.test.mjs::adds a todo"]},
    )
    assert ok.passed is True, ok.evidence

    missing = await _check(
        "acceptance_tests_pass",
        app,
        {**NODE, "acceptance_tests": ["tests/todos.test.mjs::flies to the moon"]},
    )
    assert missing.passed is False, missing.evidence


@pytest.mark.asyncio
async def test_a_broken_app_fails_its_acceptance_test(app):
    store = app / "src" / "todos.mjs"
    store.write_text(store.read_text().replace(".trim()", ""))  # the bug: no trimming

    result = await _check(
        "acceptance_tests_pass",
        app,
        {**NODE, "acceptance_tests": ["tests/todos.test.mjs::adds a todo"]},
    )
    assert result.passed is False, result.evidence


@pytest.mark.asyncio
async def test_app_e2e_pass_starts_the_app_and_drives_it(app):
    result = await _check("app_e2e_pass", app, E2E)
    assert result.passed is True, result.evidence
    assert result.evidence["app_started"] is True


@pytest.mark.asyncio
async def test_app_e2e_pass_fails_when_the_api_misbehaves(app):
    server = app / "src" / "server.mjs"
    # The bug: creating a todo answers 500.
    server.write_text(
        server.read_text().replace("send(res, 201, store.add", "send(res, 500, store.add")
    )

    result = await _check("app_e2e_pass", app, E2E)
    assert result.passed is False, result.evidence
    assert result.evidence["app_started"] is True


@pytest.mark.asyncio
async def test_app_e2e_pass_reports_an_app_that_never_starts(app):
    result = await _check(
        "app_e2e_pass", app, {**E2E, "sandbox_start_command": "node src/nope.mjs"}
    )
    assert result.passed is False
    assert result.evidence["app_started"] is False


@pytest.mark.asyncio
async def test_e2e_without_configuration_is_inconclusive(app):
    result = await _check("app_e2e_pass", app, NODE)
    assert result.inconclusive is True and result.passed is False
