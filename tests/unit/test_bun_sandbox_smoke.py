"""Opt-in real-docker smoke test of the Bun toolchain (race-app experiment 2c, end to end).

Skipped unless ``LIFE_GRAPH_DOCKER_SMOKE=1``. It runs the real thing on the tiny
workspace in ``tests/fixtures/bun_workspace`` (two workspaces with registry
dependencies, one without, a root ``postinstall`` that must not run):

1. setup: ``bun install --frozen-lockfile --ignore-scripts`` from the manifests
   only, on an internal network whose only way out is the egress proxy
   (``registry.npmjs.org``), ready check, atomic publish;
2. the mount plan: git-ignored mountpoints pre-created in the worktree, one
   read-only mount per ``node_modules``, each accepted by the bind validator;
3. ``tests_pass``: ``bun test`` in place on a read-only ``/work``, no network,
   non-root -- the fixture's tests check that deps resolve, ``/work`` is
   read-only and the network is gone; then a failing test must fail.

Images (defaults are the settings'): ``LIFE_GRAPH_SMOKE_NODE_IMAGE`` (must carry
Bun: ``docker build -t <tag> docker/verifier-node``) and
``LIFE_GRAPH_SMOKE_EGRESS_IMAGE``. Needs network for the install.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.services.dev import sandbox, sandbox_deps
from life_graph.services.dev import verifiers as v
from life_graph.services.dev.sandbox import Bind

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bun_workspace"
NODE_IMAGE = os.environ.get("LIFE_GRAPH_SMOKE_NODE_IMAGE") or settings.verifier_sandbox_node_image
EGRESS_IMAGE = (
    os.environ.get("LIFE_GRAPH_SMOKE_EGRESS_IMAGE") or settings.driver_runtime_egress_image
)

pytestmark = pytest.mark.skipif(
    os.environ.get("LIFE_GRAPH_DOCKER_SMOKE") != "1",
    reason="real-docker smoke test; set LIFE_GRAPH_DOCKER_SMOKE=1",
)


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=120)


@pytest.fixture
def smoke(monkeypatch, tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("no docker CLI")
    for image in (NODE_IMAGE, EGRESS_IMAGE):
        if _docker("image", "inspect", image).returncode != 0:
            pytest.skip(f"image {image} not present")
    probe = _docker("run", "--rm", "--network", "none", "--entrypoint", "bun", NODE_IMAGE, "-v")
    if probe.returncode != 0:
        pytest.skip(f"{NODE_IMAGE} has no bun (rebuild docker/verifier-node)")
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    monkeypatch.setattr(settings, "verifier_sandbox_node_image", NODE_IMAGE)
    monkeypatch.setattr(settings, "driver_runtime_egress_image", EGRESS_IMAGE)
    work = tmp_path / "work"
    shutil.copytree(FIXTURE, work)
    git = ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.invalid"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *args], cwd=work, check=True, capture_output=True)
    yield work
    # Installed trees are owned by this uid (--user); nothing else to clean.
    shutil.rmtree(tmp_path / "envs", ignore_errors=True)


async def test_a_bun_workspace_installs_mounts_and_checks_end_to_end(smoke):
    ctx = {"sandbox_toolchain": "bun"}
    plan = await sandbox_deps.deps_mounts(ctx, smoke)
    assert plan is not None
    env = Path(settings.verifier_sandbox_cache_dir) / plan.env_key
    assert plan.mountpoints == (
        "node_modules",
        "apps/web/node_modules",
        "packages/lib/node_modules",
    )
    assert not (env / "SCRIPT_RAN").exists()  # the root postinstall did not run
    for m in plan.mounts:
        assert sandbox._bind_violations(Bind(str(m.source), m.target, read_only=True)) == []
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=smoke, capture_output=True, text=True
    )
    assert status.stdout == ""

    passed, evidence = await v._verify_tests_pass(smoke, ctx)
    print(evidence.get("stdout"))
    assert passed is True, evidence
    assert "3 pass" in evidence["stdout"] and "0 fail" in evidence["stdout"]
    assert not (smoke / "escaped.txt").exists()

    # Reused, not reinstalled: same env, and a failing test fails.
    (smoke / "apps/web/src/broken.test.ts").write_text(
        'import { expect, test } from "bun:test";\ntest("broken", () => expect(1).toBe(2));\n'
    )
    again = await sandbox_deps.deps_mounts(ctx, smoke)
    assert again is not None and again.env_key == plan.env_key
    passed, evidence = await v._verify_tests_pass(smoke, ctx)
    assert passed is False, evidence
    assert "1 fail" in evidence["stdout"]
