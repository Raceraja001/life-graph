"""Entity keys: one thing, one key (services/entities.py)."""

import pytest

from life_graph.services.entities import is_entity, normalize


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Life-Graph", "life graph"),
        ("life_graph", "life graph"),
        ("  Life  Graph ", "life graph"),
        ("The School App", "school app"),
        ("uzhavu.race", "uzhavu race"),
        ("C++", "c++"),
        ("Murugan S.", "murugan s"),
    ],
)
def test_normalize(name, key):
    assert normalize(name) == key


@pytest.mark.parametrize(
    ("key", "ok"),
    [("murugan", True), ("user", False), ("app", False), ("x", False), ("3006", False)],
)
def test_generic_words_are_not_entities(key, ok):
    assert is_entity(key) is ok
