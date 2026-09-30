"""Migration 036 must stay in step with the trust policy it copies.

The migration writes the surface→tier map out as literal SQL instead of
importing ``life_graph.core.trust`` — a deliberate choice (migration 022 made
it too), because a migration has to keep running years later even if that
module is renamed or its imports grow. The cost of that choice is a second copy
of the policy, and a copy nobody checks is a copy that drifts. These tests are
the check.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from life_graph.core.trust import _SURFACE_TIER, TrustTier, classify_surface

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "036_backfill_memory_trust_tiers.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("migration_036", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _migration_module()


# Surfaces added to _SURFACE_TIER *after* migration 036 was written and applied.
#
# 036 is a one-time backfill of rows that existed when it ran, and it has run.
# Editing an applied migration to mention a surface that had no rows at the time
# would rewrite history to no effect, so the migration is left as the snapshot it
# is and new surfaces are recorded here instead.
#
# This stays an explicit list rather than a loosened assertion: adding a surface
# to core/trust.py still fails these tests until someone writes it down, which is
# the moment to ask whether existing rows need a backfill of their own. Entries
# are only correct here if the surface genuinely postdates 036 and has no rows
# predating it.
_ADDED_AFTER_036 = {
    # Telegram bridge, migration 037. No rows can predate it: the tables that
    # produce this surface are created by that same migration.
    "telegram",
    # Agent closing messages, split off "tool_exhaust" once that surface
    # stopped being extracted. Rows *do* predate it, so they got a backfill of
    # their own — migration 043 relabels the capture events, and both surfaces
    # are VERIFIED, so no row's tier changes and 036's work still holds.
    "assistant_message",
}


def _expected(tier: TrustTier) -> set[str]:
    """Surfaces at `tier` that migration 036 was written to cover."""
    return {
        surface
        for surface, t in _SURFACE_TIER.items()
        if t is tier and surface not in _ADDED_AFTER_036
    }


@pytest.mark.parametrize(
    ("attr", "tier"),
    [
        ("_SELF", TrustTier.SELF),
        ("_VERIFIED", TrustTier.VERIFIED),
        ("_HOSTILE", TrustTier.HOSTILE_POSSIBLE),
    ],
)
def test_the_sql_lists_match_the_policy_map(migration, attr, tier):
    assert set(getattr(migration, attr)) == _expected(tier), (
        f"migration 036's {attr} has drifted from _SURFACE_TIER — "
        f"update the migration's literal list to match core/trust.py"
    )


def test_external_surfaces_are_left_to_the_default_branch(migration):
    """EXTERNAL is the ELSE, so listing it too would be a second, silent copy."""
    listed = set(migration._SELF) | set(migration._VERIFIED) | set(migration._HOSTILE)
    assert listed.isdisjoint(_expected(TrustTier.EXTERNAL))
    assert listed == set(_SURFACE_TIER) - _ADDED_AFTER_036 - _expected(TrustTier.EXTERNAL)


def test_every_mapped_surface_appears_exactly_once(migration):
    """A surface in two lists would make the CASE order decide the policy."""
    all_listed = list(migration._SELF) + list(migration._VERIFIED) + list(migration._HOSTILE)
    assert len(all_listed) == len(set(all_listed))


def test_the_sql_is_downgrade_only(migration):
    """The whole safety argument rests on this comparison being strictly '>'."""
    import inspect

    source = inspect.getsource(migration.upgrade)
    assert "array_position" in source
    assert ">" in source and ">=" not in source, (
        "a '>=' would rewrite rows whose tier is already correct, and an "
        "inverted comparison would promote untrusted rows to trusted"
    )


def test_downgrade_is_a_documented_no_op(migration):
    """Restoring a blanket 'verified' would re-open the hole 022 left."""
    import inspect

    body = inspect.getsource(migration.downgrade)
    assert "op.execute" not in body
    assert migration.downgrade() is None


def test_the_migration_chains_onto_the_previous_head(migration):
    assert migration.revision == "036"
    assert migration.down_revision == "035"


# ── The policy the SQL is copying ────────────────────────────────────


@pytest.mark.parametrize(
    ("source_type", "expected"),
    [
        # First-party writers must not be fenced from the user's own agents.
        ("manual", TrustTier.SELF),
        ("chat", TrustTier.SELF),
        ("explicit", TrustTier.SELF),
        # System producers.
        ("inferred", TrustTier.VERIFIED),
        ("consolidation", TrustTier.VERIFIED),
        ("bulk_import", TrustTier.VERIFIED),
        ("transcript", TrustTier.VERIFIED),
        # Default-deny.
        ("test", TrustTier.EXTERNAL),
        ("something_invented_later", TrustTier.EXTERNAL),
        (None, TrustTier.EXTERNAL),
        ("", TrustTier.EXTERNAL),
    ],
)
def test_memory_source_types_classify_as_intended(source_type, expected):
    assert classify_surface(source_type) is expected


def test_the_two_vocabularies_share_one_map():
    """Capture surfaces and memory source_types are graded by the same policy.

    They are separate vocabularies that overlap. A value must not be able to
    mean 'trusted' as a capture surface and 'untrusted' as a memory source, so
    there is deliberately only one map for both.
    """
    for surface in ("cli", "tool_exhaust", "interview_answer", "whatsapp"):
        assert surface in _SURFACE_TIER
    for source_type in ("manual", "inferred", "bulk_import", "consolidation"):
        assert source_type in _SURFACE_TIER


def test_the_post_036_allowlist_is_honest(migration):
    """The allowlist must not hide a surface the migration does cover, or a typo."""
    listed = set(migration._SELF) | set(migration._VERIFIED) | set(migration._HOSTILE)
    assert _ADDED_AFTER_036.isdisjoint(listed), (
        "a surface cannot both postdate migration 036 and be listed in it"
    )
    assert set(_SURFACE_TIER) >= _ADDED_AFTER_036, (
        "_ADDED_AFTER_036 names a surface that is no longer in _SURFACE_TIER — remove it here too"
    )
