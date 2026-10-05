"""Which tenants get seeded at startup.

A tenant that is never seeded has no safety rules, and an action with no
matching rule is classified dangerous — so the whole point of this setting is
that leaving a tenant out of it silently disables its autonomy.
"""

from life_graph.config import Settings


def test_default_is_the_default_tenant_alone():
    assert Settings().seed_tenants_list == ["default"]


def test_several_tenants_keep_their_order():
    s = Settings(seed_tenants="default,raja")
    assert s.seed_tenants_list == ["default", "raja"]


def test_whitespace_around_names_is_ignored():
    s = Settings(seed_tenants=" default , raja ")
    assert s.seed_tenants_list == ["default", "raja"]


def test_empty_names_are_dropped_rather_than_seeding_a_blank_tenant():
    # "default,,raja" and a trailing comma are the two ways a hand-edited env
    # file produces an empty entry; seeding tenant "" would create rules nobody
    # can reach.
    s = Settings(seed_tenants="default,,raja,")
    assert s.seed_tenants_list == ["default", "raja"]


def test_seeding_can_be_turned_off_entirely():
    assert Settings(seed_tenants="").seed_tenants_list == []
