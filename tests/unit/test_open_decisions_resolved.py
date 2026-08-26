"""Regression tests for four settled decisions.

Each of these was a loose end rather than a bug: a number that lived in two
places, a constant carrying a ``TODO(config)``, a default that had been left
deliberately conservative, and a dependency whose failure was invisible. They
are grouped here because what needs protecting in each case is the *decision*,
not the mechanism — a future edit that quietly undoes one should fail loudly.
"""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── The version number has one source ────────────────────────────────


def _pyproject_version() -> str:
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    return tomllib.loads(pyproject.read_text())["project"]["version"]


def test_version_is_derived_not_duplicated():
    """``__version__`` must come from distribution metadata, not a literal.

    These drifted apart before: this file said 0.1.0 while pyproject.toml and
    CHANGELOG.md said 1.1.0, because the release checklist asked a human to
    bump both by hand. Deriving it removes the chance to forget.

    Deliberately *not* asserting equality with pyproject.toml: an editable
    install snapshots its metadata at install time, so a dev tree legitimately
    lags between a version bump and the next `pip install -e .`. A built wheel
    or sdist — the thing that actually ships — always agrees by construction.
    """
    import ast
    from importlib.metadata import version as dist_version
    from pathlib import Path

    import life_graph

    assert life_graph.__version__ == dist_version("life-graph")

    tree = ast.parse(Path(life_graph.__file__).read_text())
    assigned = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    ]
    assert assigned, "__init__.py no longer defines __version__"
    assert any(isinstance(v, ast.Call) for v in assigned), (
        "__version__ must be read from distribution metadata, not restated here"
    )
    literals = [v.value for v in assigned if isinstance(v, ast.Constant)]
    assert literals == ["0.0.0+unknown"], (
        f"the only permitted literal is the uninstalled-tree sentinel; found {literals}"
    )


def test_pyproject_and_changelog_agree():
    """The two numbers a human still bumps by hand must match.

    With `__init__.py` derived, these are the only remaining copies — and the
    release checklist in docs/RELEASE.md lists exactly these two.
    """
    import re
    from pathlib import Path

    changelog = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text()
    newest = re.search(r"^## \[([^\]]+)\]", changelog, re.MULTILINE)
    assert newest, "CHANGELOG.md has no '## [X.Y.Z]' heading"
    assert newest.group(1) == _pyproject_version()


def test_version_survives_an_uninstalled_source_tree(monkeypatch):
    """Importing from a tree that was never pip-installed must not explode."""
    from importlib.metadata import PackageNotFoundError

    import life_graph

    def _boom(_name):
        raise PackageNotFoundError("life-graph")

    monkeypatch.setattr("importlib.metadata.version", _boom)
    reloaded = importlib.reload(life_graph)
    try:
        assert reloaded.__version__ == "0.0.0+unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(life_graph)


# ── Progressive-disclosure sizes are configuration ───────────────────


def test_index_content_chars_comes_from_settings():
    from life_graph.config import settings
    from life_graph.scoring.ranking import INDEX_CONTENT_CHARS

    assert settings.recall_index_content_chars == INDEX_CONTENT_CHARS


def test_batch_expand_max_comes_from_settings():
    from life_graph.api.memories import _BATCH_EXPAND_MAX
    from life_graph.config import settings

    assert settings.memory_batch_max == _BATCH_EXPAND_MAX


def test_batch_max_is_enforced_by_the_request_schema():
    """The cap has to reach the schema, not just sit in a module."""
    import uuid

    from pydantic import ValidationError

    from life_graph.api.memories import _BATCH_EXPAND_MAX, MemoryBatchRequest

    MemoryBatchRequest(ids=[uuid.uuid4() for _ in range(_BATCH_EXPAND_MAX)])
    with pytest.raises(ValidationError):
        MemoryBatchRequest(ids=[uuid.uuid4() for _ in range(_BATCH_EXPAND_MAX + 1)])


@pytest.mark.parametrize(
    "name",
    ["recall_index_content_chars", "memory_batch_max"],
)
def test_the_new_settings_are_real_env_overridable_fields(name):
    from life_graph.config import Settings

    assert name in Settings.model_fields


def test_no_todo_config_markers_remain():
    """These two constants were the last ones parked outside config.py."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "life_graph"
    offenders = [
        str(p.relative_to(root)) for p in root.rglob("*.py") if "TODO(config)" in p.read_text()
    ]
    assert offenders == []


# ── A dead embedding backend is visible ──────────────────────────────


def _service(*, available: bool, use_local: bool, embed=None):
    from life_graph.services.embeddings import EmbeddingService

    svc = EmbeddingService.__new__(EmbeddingService)
    svc._available = available
    svc._lm_client = MagicMock()
    if embed is not None:
        svc._lm_client.embed = embed
    svc._use_local = lambda: use_local  # type: ignore[method-assign]
    return svc


@pytest.mark.asyncio
async def test_probe_reports_unavailable_when_nothing_is_configured():
    assert await _service(available=False, use_local=False).probe() == "unavailable"


@pytest.mark.asyncio
async def test_probe_reports_unreachable_when_the_backend_raises():
    """The failure this whole check exists for: configured, but down.

    ``available`` is decided at construction and stays True here, which is
    exactly why a static flag was not enough.
    """
    svc = _service(available=True, use_local=True, embed=AsyncMock(side_effect=OSError("refused")))
    assert await svc.probe() == "unreachable"
    assert svc.available is True, "the static flag cannot see this — hence the probe"


@pytest.mark.asyncio
async def test_probe_reports_unreachable_on_an_empty_vector():
    """Answering with an empty list is the silent-failure mode, not success."""
    svc = _service(available=True, use_local=True, embed=AsyncMock(return_value=[]))
    assert await svc.probe() == "unreachable"


@pytest.mark.asyncio
async def test_probe_reports_healthy_on_a_real_vector():
    svc = _service(available=True, use_local=True, embed=AsyncMock(return_value=[0.1, 0.2]))
    assert await svc.probe() == "healthy"


@pytest.mark.asyncio
async def test_probe_does_not_load_the_in_process_model():
    """A probe that loaded bge-m3 would block the event loop for gigabytes."""
    svc = _service(available=True, use_local=False)
    svc._load_model = MagicMock(side_effect=AssertionError("must not load the model"))
    assert await svc.probe() == "healthy"


@pytest.fixture
def healthy_deps(monkeypatch):
    """Patch /health's dependencies so only the embedding backend varies."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _session():
        session = MagicMock()
        session.execute = AsyncMock()
        yield session

    monkeypatch.setattr("life_graph.main.async_session", _session)
    monkeypatch.setattr("life_graph.main.check_redis", AsyncMock(return_value="ok"))
    monkeypatch.setattr("life_graph.storage.graph.graph_status", AsyncMock(return_value="disabled"))

    # app.state.startup_report is process-global: any earlier test that ran the
    # real lifespan leaves its result behind, and a failed optional subsystem
    # there would degrade the overall verdict no matter what the embedder says.
    # Pin it to "lifespan never ran" so this test measures only the embedder.
    from life_graph.main import app

    monkeypatch.setattr(app.state, "startup_report", None, raising=False)

    def _set_embedding_status(status: str):
        svc = MagicMock()
        svc.probe = AsyncMock(return_value=status)
        monkeypatch.setattr("life_graph.api.dependencies.get_embedding_service", lambda: svc)

    return _set_embedding_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("embedding_status", "expected_overall"),
    [("healthy", "healthy"), ("unreachable", "degraded"), ("unavailable", "degraded")],
)
async def test_a_dead_embedding_backend_degrades_health(
    healthy_deps, embedding_status, expected_overall
):
    """Everything else healthy — only the embedder decides the verdict."""
    import json

    from life_graph.main import health_check

    healthy_deps(embedding_status)
    response = await health_check()
    body = json.loads(response.body)

    assert body["checks"]["embeddings"]["status"] == embedding_status
    assert body["status"] == expected_overall


@pytest.mark.asyncio
async def test_a_dead_embedding_backend_never_returns_503(healthy_deps):
    """Postgres is the only critical dependency; this must not page anyone."""
    from life_graph.main import health_check

    healthy_deps("unreachable")
    assert (await health_check()).status_code == 200
