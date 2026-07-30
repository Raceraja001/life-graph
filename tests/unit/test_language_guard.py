"""Non-Latin text skips English NER (which only produces garbage)."""

from life_graph.extraction.nlp import SpacyExtractor, is_predominantly_non_latin


def test_script_detector():
    assert is_predominantly_non_latin("பலன் இல் கவனம் வைத்து")  # Tamil
    assert not is_predominantly_non_latin("I like FastAPI and Postgres")
    assert not is_predominantly_non_latin("naalaikku insurance kattanum")  # romanized Tamil = Latin


def test_extract_skips_non_latin():
    ex = SpacyExtractor()
    assert ex.extract("இந்த உரை தமிழில் உள்ளது ஆகவே ஆங்கில") == []
