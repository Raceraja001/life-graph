"""build_ok_diff/lint_clean_diff must check ONLY files changed since HEAD,
not the whole workdir tree — the whole-tree originals (build_ok/lint_clean)
would fail on this repo's pre-existing ruff debt the moment workdir points
at a real checkout instead of an always-empty scratch dir.
"""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t.com",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=str(path),
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_lint_clean_diff_ignores_pre_existing_issues_outside_the_diff(tmp_path):
    _init_repo(tmp_path)
    # A pre-existing, already-committed file with a lint issue (unused import) —
    # NOT part of this run's diff, must not fail lint_clean_diff.
    bad_file = tmp_path / "old.py"
    bad_file.write_text("import os\n", encoding="utf-8")
    subprocess.run(["git", "add", "old.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    # A NEW, clean file — the actual change under test. Staged (not committed)
    # so `git diff --name-only HEAD` picks it up — an untracked file would
    # NOT appear in that diff at all, which would make this test pass for
    # the wrong reason (nothing "changed" as far as git is concerned, rather
    # than old.py being correctly excluded by diff-scoping).
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_build_ok_diff_only_compiles_changed_files(tmp_path):
    _init_repo(tmp_path)
    # A pre-existing, already-committed file with a syntax error — not
    # part of the diff, must not fail build_ok_diff.
    broken = tmp_path / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    subprocess.run(["git", "add", "broken.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    # Staged (not committed) so `git diff --name-only HEAD` picks it up —
    # see the comment in test_lint_clean_diff_ignores_pre_existing_issues_
    # outside_the_diff for why an untracked file wouldn't prove anything here.
    (tmp_path / "new.py").write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_build_ok_diff_fails_on_a_syntax_error_in_the_diff(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("def f(:\n", encoding="utf-8")
    # Staged so git diff --name-only HEAD actually reports it as changed —
    # git add doesn't validate Python syntax, so this is fine to stage as-is.
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is False


@pytest.mark.asyncio
async def test_diff_scoped_verifiers_tolerate_a_non_git_directory(tmp_path):
    """No .git at all (the scratch-temp-dir fallback case) — must not raise,
    trivially passes (nothing to check)."""
    results = await verifier_chain.run_chain(["build_ok_diff", "lint_clean_diff"], tmp_path, {})

    assert all(r.passed for r in results)


# ── no_secrets_in_diff ────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_secrets_in_diff_flags_a_private_key_in_a_new_file(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "creds.pem").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "creds.pem"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["no_secrets_in_diff"], tmp_path, {})

    assert results[0].passed is False
    findings = results[0].evidence["findings"]
    assert findings and findings[0]["pattern"] == "private_key_block"
    assert findings[0]["file"] == "creds.pem"


@pytest.mark.asyncio
async def test_no_secrets_in_diff_finding_never_echoes_the_secret_itself(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "config.py").write_text(
        'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "config.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["no_secrets_in_diff"], tmp_path, {})

    assert results[0].passed is False
    blob = str(results[0].evidence)
    assert "AKIAABCDEFGHIJKLMNOP" not in blob
    assert "aws_access_key_id" in blob


@pytest.mark.asyncio
async def test_no_secrets_in_diff_ignores_pre_existing_secret_outside_the_diff(tmp_path):
    _init_repo(tmp_path)
    leaky = tmp_path / "old_creds.py"
    leaky.write_text('KEY = "AKIAABCDEFGHIJKLMNOP"\n', encoding="utf-8")
    subprocess.run(["git", "add", "old_creds.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["no_secrets_in_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_no_secrets_in_diff_allows_the_aws_documented_example_key(tmp_path):
    _init_repo(tmp_path)
    # AWS's own placeholder from their docs — appears in countless tutorials
    # and test fixtures; must not be treated as a real leaked credential.
    (tmp_path / "readme_snippet.py").write_text(
        'EXAMPLE = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8"
    )
    subprocess.run(
        ["git", "add", "readme_snippet.py"], cwd=str(tmp_path), check=True, capture_output=True
    )

    results = await verifier_chain.run_chain(["no_secrets_in_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_no_secrets_in_diff_passes_a_clean_diff(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["no_secrets_in_diff"], tmp_path, {})

    assert results[0].passed is True
    assert results[0].evidence["findings"] == []


# ── Untracked (never `git add`-ed) new files ─────────────────
#
# Nothing in the agent-tool pipeline stages files: there is no git-add tool
# in the registry, and LocalDriver never stages. `git diff --name-only HEAD`
# reports NOTHING for an untracked file, so a fix whose entire shape is
# "write a new module" was invisible to both diff verifiers — they passed
# vacuously, which is the exact bug class this branch exists to close.


@pytest.mark.asyncio
async def test_build_ok_diff_detects_an_untracked_new_file(tmp_path):
    _init_repo(tmp_path)
    # NEVER git add-ed — genuinely untracked, exactly what an agent leaves
    # behind after writing a new module via file_write.
    (tmp_path / "new.py").write_text("def f(:\n", encoding="utf-8")

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is False, (
        "an untracked new file with a syntax error must not be invisible"
    )
    assert results[0].evidence["checked"] == 1


@pytest.mark.asyncio
async def test_lint_clean_diff_checks_an_untracked_new_file(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")

    results = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})

    # Not the vacuous "No changed .py files" pass — the file was really seen.
    assert results[0].evidence.get("note") != "No changed .py files"
    assert results[0].passed is True


@pytest.mark.asyncio
async def test_diff_verifiers_ignore_gitignored_untracked_files(tmp_path):
    """--exclude-standard: a .gitignore'd file is not part of the change."""
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "ignore"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "broken.py").write_text("def f(:\n", encoding="utf-8")

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is True
    assert results[0].evidence["checked"] == 0


@pytest.mark.asyncio
async def test_lint_clean_diff_is_inconclusive_when_ruff_is_not_installed(tmp_path, monkeypatch):
    """A missing linter is neither a pass nor a failure.

    This used to assert ``passed is True``: on any host without ruff (the
    production image ships no dev tooling) the lint gate reported success on
    every dispatch while checking nothing. Failing instead is no better — it
    would bounce to needs_human on every dispatch touching a .py file, and
    re-running the agent cannot install a linter. The check simply did not
    happen, and that is now what it says.
    """
    import life_graph.services.verifiers as verifiers_mod

    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(verifiers_mod, "_project_tool", lambda workdir, tool: None)

    results = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})

    assert results[0].inconclusive is True
    assert results[0].passed is False, "inconclusive must never read as a pass"
    assert not verifier_chain.all_passed(results)
    assert "ruff not available" in results[0].evidence["note"]


@pytest.mark.asyncio
async def test_lint_clean_diff_still_fails_on_real_lint_errors(tmp_path):
    """The ruff-missing skip must NOT swallow a genuine lint failure."""
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("import os\n", encoding="utf-8")

    results = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})

    assert results[0].passed is False


# ── no_vulnerable_deps_in_diff ────────────────────────────────


def _fake_pip_audit(tmp_path, report: dict, returncode: int = 0):
    """A stub pip-audit binary that prints a fixed JSON report."""
    import json

    script = tmp_path / "fake-pip-audit"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"print({json.dumps(json.dumps(report))})\n"
        f"sys.exit({returncode})\n"
    )
    script.chmod(0o755)
    return str(script)


@pytest.mark.asyncio
async def test_no_vulnerable_deps_skips_when_no_manifest_touched(tmp_path, monkeypatch):
    """No dependency manifest in the diff -> a real pass, no tool ever invoked."""
    import life_graph.services.verifiers as verifiers_mod

    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    def must_not_run(workdir, tool):
        raise AssertionError("must not look for pip-audit when no manifest changed")

    monkeypatch.setattr(verifiers_mod, "_project_tool", must_not_run)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})

    assert results[0].passed is True
    assert results[0].inconclusive is False
    assert results[0].evidence["touched"] == []


@pytest.mark.asyncio
async def test_no_vulnerable_deps_inconclusive_without_pip_audit(tmp_path, monkeypatch):
    import life_graph.services.verifiers as verifiers_mod

    _init_repo(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "requirements.txt"], cwd=str(tmp_path), check=True, capture_output=True
    )

    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)
    monkeypatch.setattr(verifiers_mod, "_project_tool", lambda workdir, tool: None)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})

    assert results[0].inconclusive is True
    assert results[0].passed is False, "inconclusive must never read as a pass"
    assert results[0].evidence["touched"] == ["requirements.txt"]
    assert "pip-audit not available" in results[0].evidence["note"]


@pytest.mark.asyncio
async def test_no_vulnerable_deps_passes_when_pip_audit_finds_nothing(tmp_path, monkeypatch):
    import life_graph.services.verifiers as verifiers_mod

    _init_repo(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "requirements.txt"], cwd=str(tmp_path), check=True, capture_output=True
    )

    clean = _fake_pip_audit(tmp_path, {"dependencies": [{"name": "requests", "vulns": []}]})
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)
    monkeypatch.setattr(verifiers_mod, "_project_tool", lambda workdir, tool: clean)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})

    assert results[0].passed is True
    assert results[0].evidence["vulnerabilities"] == []


@pytest.mark.asyncio
async def test_no_vulnerable_deps_fails_when_pip_audit_finds_a_vuln(tmp_path, monkeypatch):
    import life_graph.services.verifiers as verifiers_mod

    _init_repo(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "requirements.txt"], cwd=str(tmp_path), check=True, capture_output=True
    )

    report = {
        "dependencies": [
            {"name": "requests", "version": "2.0.0", "vulns": [{"id": "PYSEC-2018-28"}]}
        ]
    }
    vulnerable = _fake_pip_audit(tmp_path, report, returncode=1)
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)
    monkeypatch.setattr(verifiers_mod, "_project_tool", lambda workdir, tool: vulnerable)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})

    assert results[0].passed is False
    assert results[0].inconclusive is False
    (vuln,) = results[0].evidence["vulnerabilities"]
    assert vuln == {"package": "requests", "version": "2.0.0", "id": "PYSEC-2018-28"}


@pytest.mark.asyncio
async def test_no_vulnerable_deps_inconclusive_when_pip_audit_itself_fails(tmp_path, monkeypatch):
    """A network failure or bad env (exit code neither 0 nor 1) is not a
    verdict on the dependencies — must not be reported as a vulnerability."""
    import life_graph.services.verifiers as verifiers_mod

    _init_repo(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "requirements.txt"], cwd=str(tmp_path), check=True, capture_output=True
    )

    broken = _fake_pip_audit(tmp_path, {}, returncode=2)
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)
    monkeypatch.setattr(verifiers_mod, "_project_tool", lambda workdir, tool: broken)

    results = await verifier_chain.run_chain(["no_vulnerable_deps_in_diff"], tmp_path, {})

    assert results[0].inconclusive is True
    assert results[0].passed is False
