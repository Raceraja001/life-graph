import pytest
from app.store import Store


def test_adds_a_todo():
    s = Store()
    assert s.add("  buy milk ") == {"id": 1, "title": "buy milk", "done": False}


def test_rejects_an_empty_title():
    with pytest.raises(ValueError):
        Store().add("   ")
