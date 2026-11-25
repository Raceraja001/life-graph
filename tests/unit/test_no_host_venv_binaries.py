"""No binary from the project venv runs on the host (Stage 0 finding 2, M1.2).

The venv is built from manifests the agent edited, so its ``bin/ruff``,
``bin/pip-audit`` and interpreter are the agent's code. mechanical_autofix
runs the image's ruff inside the check sandbox; no_vulnerable_deps_in_diff
runs Life Graph's own pip-audit with ``--path`` (metadata only) and a
minimal environment.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from life_graph.services.dev import sandbox
from life_graph.services.dev import verifiers as verifiers_mod
from life_graph.services.dev.verifiers import mechanical_autofix, verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )  # fmt: skip


def _planted(venv, name, marker):
    """A venv binary that, if ever run, leaves *marker* behind."""
    bindir = venv / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / name
    script.write_text(f"#!/bin/sh\ntouch {marker}\necho '{{}}'\n")
    script.chmod(0o755)


@pytest.mark.asyncio
async def test_autofix_runs_the_images_ruff_in_the_sandbox_never_the_venvs(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("import os\n\nx = 1\n")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)
    venv = tmp_path.parent / f"{tmp_path.name}-venv"
    marker = tmp_path.parent / f"{tmp_path.name}-ran"
    _planted(venv, "ruff", marker)

    async def prepare_env(*_a, **_k):
        return venv

    calls = []

    async def run(argv, workdir, **kw):
        calls.append((argv, kw))
        return sandbox.SandboxResult(0, "", "")

    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(verifiers_mod.sandbox, "prepare_env", prepare_env)
    monkeypatch.setattr(verifiers_mod.sandbox, "run", run)

    await mechanical_autofix(tmp_path, {})

    assert not marker.exists(), "the venv's ruff ran on the host"
    assert [argv[:2] for argv, _ in calls] == [["ruff", "check"], ["ruff", "format"]]
    assert all(kw.get("writable") is True and "venv" not in kw for _, kw in calls)


@pytest.mark.asyncio
async def test_autofix_with_the_sandbox_down_does_nothing_on_the_host(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("import os\n")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    async def down(*_a, **_k):
        raise sandbox.SandboxUnavailableError("docker is not running")

    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(verifiers_mod.sandbox, "run", down)

    out = await mechanical_autofix(tmp_path, {})
    assert out["ran"] is False and "sandbox unavailable" in out["note"]


@pytest.mark.asyncio
async def test_a_writable_check_mounts_only_the_worktree_read_write(tmp_path, monkeypatch):
    seen = {}

    async def _exec(argv, **_k):
        seen["argv"] = argv
        return sandbox.SandboxResult(0, "ok", "")

    monkeypatch.setattr(sandbox, "_exec", _exec)
    await sandbox.run(["ruff", "format"], tmp_path, writable=True)
    argv = seen["argv"]
    assert f"{tmp_path}:/work" in argv and f"{tmp_path}:/work:ro" not in argv
    assert argv[argv.index("--network") + 1] == "none" and "--read-only" in argv

    await sandbox.run(["ruff", "check"], tmp_path)
    assert f"{tmp_path}:/work:ro" in seen["argv"]  # read-only stays the default


def _manifest_change(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.0.0\n")
    subprocess.run(
        ["git", "add", "requirements.txt"], cwd=str(tmp_path), check=True, capture_output=True
    )


def _trusted_audit(monkeypatch, report, returncode=0):
    """Fake only Life Graph's own pip-audit; every other subprocess is real."""
    seen = {}
    real_run = subprocess.run

    def fake_run(argv, *a, **kw):
        if list(argv[:3]) == [sys.executable, "-m", "pip_audit"]:
            seen["argv"], seen["env"] = list(argv), kw.get("env")
            return subprocess.CompletedProcess(argv, returncode, json.dumps(report), "")
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


@pytest.mark.asyncio
async def test_the_audit_reads_the_sandbox_venv_as_data_and_runs_nothing_from_it(
    tmp_path, monkeypatch
):
    _manifest_change(tmp_path)
    venv = tmp_path.parent / f"{tmp_path.name}-venv"
    site = venv / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    marker = tmp_path.parent / f"{tmp_path.name}-audit-ran"
    _planted(venv, "pip-audit", marker)
    _planted(venv, "python", marker)

    async def prepare_env(*_a, **_k):
        return venv

    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(verifiers_mod.sandbox, "prepare_env", prepare_env)
    monkeypatch.setenv("LIFE_GRAPH_SECRET_PROBE", "must-not-leak")
    seen = _trusted_audit(monkeypatch, {"dependencies": [{"name": "requests", "vulns": []}]})

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})

    assert results[0].passed is True
    assert not marker.exists(), "a venv binary ran on the host"
    argv = seen["argv"]
    assert argv[argv.index("--path") + 1] == str(site)
    assert "LIFE_GRAPH_SECRET_PROBE" not in seen["env"]
    assert set(seen["env"]) <= {"PATH", "LANG", "HOME", "HTTPS_PROXY", "HTTP_PROXY",
                                "NO_PROXY", "SSL_CERT_FILE"}  # fmt: skip


@pytest.mark.asyncio
async def test_the_audit_is_inconclusive_when_the_venv_has_no_site_packages(tmp_path, monkeypatch):
    _manifest_change(tmp_path)
    venv = tmp_path.parent / f"{tmp_path.name}-empty-venv"
    venv.mkdir()

    async def prepare_env(*_a, **_k):
        return venv

    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(verifiers_mod.sandbox, "prepare_env", prepare_env)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})
    assert results[0].inconclusive is True and results[0].passed is False


@pytest.mark.asyncio
async def test_a_found_vulnerability_still_fails_the_check(tmp_path, monkeypatch):
    _manifest_change(tmp_path)
    venv = tmp_path.parent / f"{tmp_path.name}-venv2"
    (venv / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

    async def prepare_env(*_a, **_k):
        return venv

    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(verifiers_mod.sandbox, "prepare_env", prepare_env)
    report = {"dependencies": [{"name": "requests", "version": "2.0.0",
                                "vulns": [{"id": "PYSEC-2018-28"}]}]}  # fmt: skip
    _trusted_audit(monkeypatch, report, returncode=1)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})
    assert results[0].passed is False and results[0].inconclusive is False
    assert results[0].evidence["vulnerabilities"][0]["id"] == "PYSEC-2018-28"
