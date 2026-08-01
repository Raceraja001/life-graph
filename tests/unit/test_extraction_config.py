"""Extraction quality knobs exist on Settings with sane defaults."""

from life_graph.config import settings


def test_capture_quality_settings_exist():
    assert isinstance(settings.capture_llm_clean, bool)
    assert isinstance(settings.extraction_language_guard, bool)
    assert isinstance(settings.extraction_tag_only_entities, bool)
    assert 0.0 <= settings.extraction_min_confidence <= 1.0
    assert settings.extraction_llm_min_words >= 1
    assert 0.0 <= settings.extraction_llm_confidence_threshold <= 1.0
