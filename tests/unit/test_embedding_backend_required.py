"""The app must not boot with no embedding backend at all.

With neither sentence-transformers installed nor a remote client wired, every
``embed()`` call returns an empty vector. Ingestion still reports success, so
memories are stored with no usable vector and semantic search returns nothing
— a silent, total loss of the product's main function.

Moving sentence-transformers into the optional ``local-nlp`` extra made that
state reachable from a plain ``pip install life-graph``, so it is now fatal at
startup unless the operator opts out explicitly.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from life_graph.main import app, lifespan


def _backend(available: bool):
    return lambda: SimpleNamespace(available=available)


@pytest.mark.asyncio
async def test_startup_aborts_when_no_embedding_backend_is_available():
    with (
        patch("life_graph.api.dependencies.get_embedding_service", _backend(False)),
        pytest.raises(RuntimeError) as exc,
    ):
        async with lifespan(app):
            pass  # pragma: no cover - the guard must fire first

    msg = str(exc.value)
    # The message has to be actionable: both remedies and the opt-out.
    assert "local-nlp" in msg
    assert "LIFE_GRAPH_USE_LOCAL_LLM" in msg
    assert "LIFE_GRAPH_REQUIRE_EMBEDDING_BACKEND" in msg


def test_the_guard_is_not_swallowed_by_startup_step():
    """Regression guard for the obvious wrong fix.

    ``startup_step()`` logs and continues on any exception so an optional step
    can never abort boot. Wrapping this check in it would turn a fatal
    misconfiguration back into a warning — exactly what this replaces. Asserted
    structurally: the guard must be a direct statement of the lifespan body,
    not nested inside any ``with`` block.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(lifespan)))
    fn = tree.body[0]
    assert isinstance(fn, ast.AsyncFunctionDef)

    def mentions_guard(node) -> bool:
        return any(
            isinstance(n, ast.Name) and n.id == "get_embedding_service" for n in ast.walk(node)
        )

    top_level = [st for st in fn.body if isinstance(st, ast.If) and mentions_guard(st)]
    assert top_level, "the embedding guard is not a top-level statement of lifespan()"

    nested = [
        st for st in fn.body if isinstance(st, ast.With | ast.AsyncWith) and mentions_guard(st)
    ]
    assert not nested, "the embedding guard is wrapped in a with-block (startup_step swallows)"


@pytest.mark.asyncio
async def test_opting_out_downgrades_the_abort_to_a_warning():
    from life_graph.config import settings

    with (
        patch("life_graph.api.dependencies.get_embedding_service", _backend(False)),
        patch.object(settings, "require_embedding_backend", False),
    ):
        # Must get past the guard. Anything raised after it is a different
        # startup step failing in this bare unit environment, not the guard.
        try:
            async with lifespan(app):
                pass
        except RuntimeError as e:  # pragma: no cover - defensive
            assert "No embedding backend" not in str(e)


def test_available_reports_the_backend_state():
    from life_graph.services.embeddings import EmbeddingService

    svc = EmbeddingService(lm_client=object())
    assert isinstance(svc.available, bool)
    svc._available = False
    assert svc.available is False


def test_require_embedding_backend_defaults_to_fail_closed():
    from life_graph.config import Settings

    assert Settings.model_fields["require_embedding_backend"].default is True
