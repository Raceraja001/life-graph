"""Silent and traceback-less broad excepts may not grow (audit L7/F12 ratchet).

On 2026-11-20 life_graph/ held 585 broad ``except`` handlers (bare,
``Exception``, ``BaseException``). Before phase-2 item 10, 48 swallowed the
error without a word and 94 logged it without a traceback; most of those were
fixed (a traceback, a narrower type, a warning instead of debug) or marked as
deliberate with a ``# best-effort:`` / ``# fail-open:`` / ``# expected:`` /
``# noqa: BLE001 - <why>`` comment. scripts/exception_audit.py counts them;
the baseline in .github/exception-audit-baseline.json holds the undocumented
remainder per package.

A new broad except should re-raise, log with ``exc_info=True`` (or
``logger.exception``), or carry a comment saying why swallowing is right.
When a change removes some, run ``python scripts/exception_audit.py --update``
and commit the lower baseline (``--check`` says when it can go down). Ruff's
BLE001 is not used: about 100 files would need per-file ignores today.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "exception_audit", ROOT / "scripts" / "exception_audit.py"
)
assert _spec and _spec.loader
audit = importlib.util.module_from_spec(_spec)
sys.modules["exception_audit"] = audit  # dataclasses resolve the module by name
_spec.loader.exec_module(audit)


def test_undocumented_silent_and_traceback_less_excepts_do_not_grow():
    worse, _better = audit.compare(audit.ratchet_counts(audit.scan()), audit.read_baseline())
    assert not worse, (
        "New broad excepts that swallow the error or log it without a traceback "
        f"(package: category baseline -> now): {worse}. Re-raise, log with exc_info=True, "
        "narrow the exception type, or add a '# best-effort: <why>' comment."
    )


def _categories(src: str) -> list[str]:
    tree = ast.parse(src)
    return [audit.classify(n) for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]


def test_the_classifier_puts_each_handler_in_one_category():
    src = """
try: f()
except Exception: raise
try: f()
except Exception as e: raise ValueError() from e
try: f()
except Exception: logger.exception("x")
try: f()
except Exception: log.warning("x", exc_info=True)
try: f()
except Exception: traceback.print_exc()
try: f()
except Exception as e: logger.warning("x: %s", e)
try: f()
except Exception: self._logger.debug("x", exc_info=False)
try: f()
except Exception: pass
try: f()
except Exception: return None
try: f()
except Exception:
    x = []
    continue
try: f()
except Exception as e: errors.append(str(e))
"""
    assert _categories(src) == [
        "reraise",
        "reraise",
        "logged_tb",
        "logged_tb",
        "logged_tb",
        "logged_no_tb",
        "logged_no_tb",
        "silent",
        "silent",
        "silent",
        "other",
    ]


def test_only_broad_handlers_are_counted(tmp_path: Path):
    pkg = tmp_path / "life_graph" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "m.py").write_text(
        "try: f()\nexcept ValueError: pass\n"
        "try: f()\nexcept (OSError, Exception): pass\n"
        "try: f()\nexcept BaseException: pass\n"
        "try: f()\nexcept: pass\n"
    )
    sites = audit.scan(tmp_path / "life_graph", tmp_path)
    assert [s.line for s in sites] == [4, 6, 8]
    assert {s.package for s in sites} == {"demo"}


def test_a_justification_comment_documents_a_site(tmp_path: Path):
    path = tmp_path / "life_graph" / "m.py"
    path.parent.mkdir()
    path.write_text(
        "try: f()\nexcept Exception:  # best-effort: optional\n    pass\n"
        "try: f()\nexcept Exception:\n    # expected: probe\n    pass\n"
        "try: f()\nexcept Exception:  # noqa: BLE001 - a card is a nicety\n    pass\n"
        "try: f()\nexcept Exception:  # noqa: BLE001\n    pass\n"
        "try: f()\nexcept Exception:  # why not\n    pass\n"
    )
    documented = [s.documented for s in audit.scan_file(path, tmp_path)]
    assert documented == [True, True, True, False, False]


def test_the_ratchet_counts_only_undocumented_silent_and_no_traceback_sites():
    sites = [
        audit.Site("life_graph/a/x.py", 1, "silent", False),
        audit.Site("life_graph/a/x.py", 2, "silent", True),
        audit.Site("life_graph/a/x.py", 3, "logged_no_tb", False),
        audit.Site("life_graph/a/x.py", 4, "logged_tb", False),
        audit.Site("life_graph/b.py", 5, "other", False),
    ]
    assert audit.ratchet_counts(sites) == {"a": {"silent": 1, "logged_no_tb": 1}}
    worse, better = audit.compare(
        {"a": {"silent": 2, "logged_no_tb": 0}}, {"a": {"silent": 1, "logged_no_tb": 1}}
    )
    assert worse == ["a: silent 1 -> 2"]
    assert better == ["a: logged_no_tb 1 -> 0"]
