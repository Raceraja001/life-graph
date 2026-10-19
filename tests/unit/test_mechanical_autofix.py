"""mechanical_autofix: ruff --fix/--format on the diff, for free, before the
one-bounce rule would spend a real driver call re-dispatching a failure a
formatter could have resolved on its own.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from life_graph.services import verifiers as verifiers_mod
from life_graph.services.verifiers import mechanical_autofix, verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )


def _real_ruff_path():
    import shutil
    import sys

    candidates = [
        shutil.which("ruff"),
        str(pathlib.Path(sys.executable).parent / "ruff"),
    ]
    return next((c for c in candidates if c and pathlib.Path(c).is_file()), None)


def _install_real_ruff(workdir):
    """Symlink this venv's real ruff into workdir/.venv/bin/ruff — the real
    lookup path (_project_tool), not a mock, so the test proves ruff
    actually ran and actually fixed something."""
    real_ruff = _real_ruff_path()
    if real_ruff is None:
        pytest.skip("no ruff binary available in this environment")
    bindir = workdir / ".venv" / "bin"
    bindir.mkdir(parents=True)
    os.symlink(real_ruff, bindir / "ruff")


@pytest.fixture(autouse=True)
def _host_mode(monkeypatch):
    """Force the non-sandboxed lookup path regardless of this environment's
    LIFE_GRAPH_VERIFIER_SANDBOX setting, so the test is deterministic."""
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)


@pytest.mark.asyncio
async def test_fixes_an_unused_import_and_the_diff_check_then_passes(tmp_path):
    _init_repo(tmp_path)
    _install_real_ruff(tmp_path)
    bad_file = tmp_path / "new.py"
    bad_file.write_text("import os\n\nx = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    before = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})
    assert before[0].passed is False  # unused import: a real, fixable lint failure

    result = await mechanical_autofix(tmp_path, {})
    assert result["fixed"] is True
    assert "new.py" in result["candidates"]
    assert "import os" not in bad_file.read_text(encoding="utf-8")  # ruff --fix removed it

    after = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})
    assert after[0].passed is True


@pytest.mark.asyncio
async def test_no_changed_files_is_a_noop(tmp_path):
    _init_repo(tmp_path)
    _install_real_ruff(tmp_path)
    result = await mechanical_autofix(tmp_path, {})
    assert result == {"ran": False, "note": "no changed .py files"}


@pytest.mark.asyncio
async def test_no_ruff_available_reports_ran_false(tmp_path, monkeypatch):
    # Never trust an ambient PATH ruff for a project that has none of its
    # own — same lookup discipline as the pip-audit fix.
    monkeypatch.setattr(verifiers_mod.shutil, "which", lambda _tool: None)
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    result = await mechanical_autofix(tmp_path, {})  # no .venv/bin/ruff installed
    assert result["ran"] is False
