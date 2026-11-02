"""Entity keys: one thing, one key (services/entities.py)."""

import pytest

from life_graph.services.entities import is_entity, names_a_thing, normalize


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


@pytest.mark.parametrize(
    "name",
    [
        "2026-10-26",
        "2026-10-26 09:00",
        "09:30",
        "20 tools",
        "https://github.com/someone/somerepo",
        "www.example.com",
        "race-home-pc.example.com",
        "~/life-graph-keys/remote-machines.key",
        "/mnt/h/DevTools",
        r"C:\Users\me",
        "remote-machines.key",
        "config.py",
        "X-Tenant-ID",
    ],
)
def test_dates_urls_paths_and_files_name_nothing(name):
    # Seen in the prod people table on 2026-11-02.
    assert names_a_thing(name) is False


@pytest.mark.parametrize(
    "name",
    [
        "Priya",
        "Nila Pickles",
        "Realme X2 Pro",
        "uzhavu.race",
        "Claude Code",
        "dify",
        "tailscale",
        "Open Web UI",
        "race-wsl SSH host",
        "C++",
        "Murugan S.",
        "Dr. Selvaraj",
    ],
)
def test_people_and_named_things_stay(name):
    assert names_a_thing(name) is True


@pytest.mark.parametrize(
    "key", ["backend", "endpoint", "search", "connectors", "http", "bearer api key"]
)
def test_more_generic_words_are_not_entities(key):
    assert is_entity(key) is False
