"""no_diff_in_plan: a plan dispatch must only write a spec, never touch files."""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )


@pytest.mark.asyncio
async def test_passes_when_nothing_changed(tmp_path):
    _init_repo(tmp_path)
    results = await verifier_chain.run_chain(["no_diff_in_plan"], tmp_path, {})
    assert results[0].passed is True
    assert results[0].inconclusive is False


@pytest.mark.asyncio
async def test_fails_on_a_modified_tracked_file(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "existing.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "existing.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "add"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    (tmp_path / "existing.py").write_text("x = 2\n", encoding="utf-8")

    results = await verifier_chain.run_chain(["no_diff_in_plan"], tmp_path, {})
    assert results[0].passed is False
    assert "existing.py" in results[0].evidence["touched"]


@pytest.mark.asyncio
async def test_fails_on_a_new_untracked_file():
    """A driver creating a new file while asked only to plan is exactly the
    failure this verifier exists to catch -- new files don't show up in a
    plain `git diff HEAD`, only via the untracked-file scan."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path

        path = Path(tmp)
        _init_repo(path)
        (path / "new.py").write_text("x = 1\n", encoding="utf-8")

        results = await verifier_chain.run_chain(["no_diff_in_plan"], path, {})
        assert results[0].passed is False
        assert "new.py" in results[0].evidence["touched"]
