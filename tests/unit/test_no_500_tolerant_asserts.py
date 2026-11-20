"""Guard: no integration test may accept HTTP 500 as a pass.

An assertion like ``assert r.status_code in (200, 500)`` passes when the
route crashes. Written for runs with no database, it outlived the reason:
CI has a real Postgres, ``skip_on_db_error`` already turns an unreachable
database into a skip, and in the meantime a crashing route reported green
(audit H5: 266 of these in 30 files on 2026-11-19).

They were converted file by file under a ratchet; since 2026-11-20 none is
left, so the ratchet is now a hard rule: zero, everywhere. Use
``assert_ok(response, expected)`` from tests/integration/conftest.py, which
never accepts a 5xx, or assert the exact status the route returns.

A deliberate 5xx in a tuple is fine when it is not 500 itself -- e.g. a
health probe that may answer 503 -- so only a literal 500 counts.
"""

from __future__ import annotations

import re
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"

# `status_code in (..., 500, ...)` -- also lists/sets; `not in` is excluded.
PATTERN = re.compile(r"(?<!not )\bin\s+[(\[{][^)\]}]*\b500\b")
STATUS = re.compile(r"status_code\s+in\s")


def count_500_tolerant(text: str) -> int:
    """Lines asserting on a status code with 500 among the accepted values."""
    return sum(1 for line in text.splitlines() if STATUS.search(line) and PATTERN.search(line))


def test_pattern_matches_what_it_should() -> None:
    assert count_500_tolerant("assert r.status_code in (200, 500)") == 1
    assert count_500_tolerant("assert r.status_code in (200, 202, 500), (") == 1
    assert count_500_tolerant("assert resp.status_code in [404, 500]") == 1
    assert count_500_tolerant("assert r.status_code in (200, 503)") == 0
    assert count_500_tolerant("if r.status_code not in (200, 500):") == 0
    assert count_500_tolerant("assert_ok(r, 200)") == 0


def test_no_integration_test_accepts_500() -> None:
    found = {}
    for path in sorted(INTEGRATION.rglob("*.py")):
        count = count_500_tolerant(path.read_text(encoding="utf-8"))
        if count:
            found[path.relative_to(INTEGRATION).as_posix()] = count
    assert not found, (
        "integration tests that accept HTTP 500 as a pass (file: count). Use "
        "assert_ok(response, expected) from tests/integration/conftest.py, or "
        f"assert the exact status: {found}"
    )
