"""The keyword leg of hybrid search matches ANY word of the question (storage/postgres.py)."""

from life_graph.storage.postgres import _or_tsquery


def test_words_are_ored_lowercased_and_deduplicated():
    assert _or_tsquery("Which port does Life Graph use? life graph") == (
        "which | port | does | life | graph | use"
    )


def test_tsquery_operators_cannot_be_injected():
    q = _or_tsquery("a & !b | (c:*) 'd' e<->f")
    assert set(q.replace(" | ", " ").split()) == {"a", "b", "c", "d", "e", "f"}
    assert not any(ch in q.replace(" | ", "") for ch in "&!():*'<>-")


def test_no_words_means_no_query():
    assert _or_tsquery("?? !!") == "" and _or_tsquery("") == ""


def test_long_questions_are_capped():
    assert len(_or_tsquery(" ".join(f"w{i}" for i in range(100))).split(" | ")) == 32
