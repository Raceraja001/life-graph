"""Every candidate key the ranker reads must be one retrieval produces.

The ranker reads its inputs out of plain dicts with ``.get(key, default)``.
A key nothing populates therefore does not raise -- it silently yields the
default, and the signal becomes a constant. That is not hypothetical:

* ``impact_score`` was never read into the candidate, so 0.15 of every score
  was the 0.5 default and services/impact.py's learned usefulness was
  discarded at the one place it decides anything.
* ``type`` was never populated either, so every candidate bucketed as
  "unknown" and the type-diversity rule truncated proactive recall to three
  results when five were asked for.

Neither shows up in a test that feeds the ranker a hand-built dict, because
hand-built dicts have whatever keys the test author remembered. This compares
what the ranker reads against what retrieval actually builds.
"""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RANKING_PY = ROOT / "life_graph" / "scoring" / "ranking.py"
RECALL_PY = ROOT / "life_graph" / "services" / "recall.py"

# Names bound to a candidate dict inside ranking.py.
_CANDIDATE_NAMES = {"cand", "candidate"}

# Keys the ranker may read that retrieval deliberately does not build.
_ALLOWED_UNPRODUCED = {
    # Written by rank() onto its own output, then read by rerank()/inert_signals.
    "final_score": "produced by rank(), not by retrieval",
    "_sub_scores": "produced by rank(), not by retrieval",
    # Accepted as an alternative to last_accessed by _resolve_days_since_access.
    "days_since_access": "alternative form of last_accessed, which is produced",
    # ProactiveRecallService tracks cooldown in _surfaced_memory_ids instead,
    # so it never puts this on the candidate. Other callers may.
    "last_surfaced": "recall applies its own cooldown via _surfaced_memory_ids",
    # _candidate_type() falls back to source_type, which retrieval produces.
    "type": "optional; falls back to source_type",
}


def _read_keys(path: pathlib.Path) -> set[str]:
    """String keys read off a candidate dict anywhere in *path*."""
    tree = ast.parse(path.read_text())
    keys: set[str] = set()
    for node in ast.walk(tree):
        # cand.get("key"[, default])
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in _CANDIDATE_NAMES
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)
        # cand["key"]
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in _CANDIDATE_NAMES
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
    return keys


def _produced_keys() -> set[str]:
    """Keys the candidate dict in _retrieve_candidates is built with."""
    tree = ast.parse(RECALL_PY.read_text())
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and node.name == "_retrieve_candidates"):
            continue
        keys: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Dict):
                keys |= {
                    k.value
                    for k in sub.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
            # cand["key"] = ... assignments
            elif (
                isinstance(sub, ast.Subscript)
                and isinstance(sub.value, ast.Name)
                and sub.value.id == "cand"
                and isinstance(sub.slice, ast.Constant)
            ):
                keys.add(sub.slice.value)
        return keys
    raise AssertionError("recall.py has no _retrieve_candidates()")


def test_scan_finds_the_keys_it_is_supposed_to():
    """Guard the guard: a scan that finds nothing would pass vacuously."""
    read = _read_keys(RANKING_PY)
    produced = _produced_keys()
    assert len(read) >= 10, f"only found {len(read)} candidate reads in ranking.py"
    assert len(produced) >= 15, f"only found {len(produced)} produced keys"
    # Anchor on keys known to exist on both sides.
    assert {"importance", "access_count", "trust_score"} <= read
    assert {"importance", "access_count", "trust_score"} <= produced


def test_every_ranker_key_is_populated_by_retrieval():
    read = _read_keys(RANKING_PY)
    produced = _produced_keys()
    missing = {k for k in read - produced if k not in _ALLOWED_UNPRODUCED}
    assert not missing, (
        f"ranking.py reads {sorted(missing)} off each candidate, but "
        "_retrieve_candidates never sets them. The ranker will silently use "
        "its defaults and those signals become constants. Populate them in "
        "recall.py, or add them to _ALLOWED_UNPRODUCED with the reason."
    )


def test_allowlist_has_no_stale_entries():
    """An allowlisted key that is now produced should leave the allowlist."""
    produced = _produced_keys()
    stale = {k for k in _ALLOWED_UNPRODUCED if k in produced and k != "type"}
    assert not stale, (
        f"{sorted(stale)} are produced by retrieval now; drop them from "
        "_ALLOWED_UNPRODUCED so it keeps documenting real exceptions."
    )


def test_impact_score_is_read_from_the_column():
    """Regression: the impact subsystem's output must reach the ranker."""
    assert "impact_score" in _produced_keys()
