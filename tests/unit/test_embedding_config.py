"""Unit tests: the embedder is config-driven (model + vector dimension)."""

from __future__ import annotations

from life_graph.config import settings
from life_graph.models.db import Memory
from life_graph.services.embeddings import EmbeddingService


def test_service_defaults_to_configured_model():
    svc = EmbeddingService()
    assert svc._model_name == settings.embedding_model
    assert svc._dimension == settings.embedding_dimension


def test_service_explicit_model_overrides_config():
    svc = EmbeddingService(model_name="some/other-model")
    assert svc._model_name == "some/other-model"


def test_model_info_reflects_config():
    info = EmbeddingService().get_model_info()
    assert info["model_name"] == settings.embedding_model
    assert info["dimension"] == settings.embedding_dimension


def test_vector_column_dimension_is_config_driven():
    # The pgvector column type dimension tracks settings.embedding_dimension.
    assert Memory.__table__.c.embedding.type.dim == settings.embedding_dimension


def test_config_targets_modern_1024_dim_model():
    assert settings.embedding_dimension == 1024
    assert "bge-m3" in settings.embedding_model
