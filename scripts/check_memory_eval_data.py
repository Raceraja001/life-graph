"""Offline checks for the memory eval data: no models, no network.

Checks every test life (evals/memory_structures/test_life*.json) against what
scripts/eval_memory_structures.py expects, and the extraction-meaning cases
against what scripts/eval_extraction_meaning.py expects:

- top-level keys, message and question fields and types;
- message ids unique, dates valid ISO dates, in order, none after "today";
- question ids unique, kind known, must groups non-empty, abstain without must;
- every question's "gold" answer passes the runner's own score(), every
  "traps" answer fails it, and gold plus any must_not term fails it;
- a BIG file keeps all its base file's messages and exactly its questions;
- extraction cases: ids unique, fields known, expect/none consistent.

    python scripts/check_memory_eval_data.py [FILE ...]

Exits 1 on any problem.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "evals" / "memory_structures"
KINDS = {
    "simple",
    "multi_hop",
    "current",
    "past",
    "alias",
    "tamil",
    "abstain",
    "about",
    "decision",
    "connected",
    "old_fact",
}
LIFE_KEYS = {"about", "person", "today", "messages", "questions"}
MESSAGE_KEYS = {"id", "date", "text", "kind"}
QUESTION_KEYS = {"id", "kind", "q", "must", "must_not", "abstain", "gold", "traps"}
CASE_KEYS = {"id", "cat", "text", "expect", "never", "none", "note"}
EXPECT_KEYS = {"about", "must", "negate", "hedged", "reason", "correction"}


def _runner():
    """The bake-off runner's score(), loaded from its file (no package import)."""
    path = ROOT / "scripts" / "eval_memory_structures.py"
    spec = importlib.util.spec_from_file_location("eval_memory_structures", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _groups(value, where: str, errs: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errs.append(f"{where}: must be a non-empty list of groups")
        return
    for g in value:
        if not isinstance(g, list) or not g or not all(isinstance(a, str) and a for a in g):
            errs.append(f"{where}: bad group {g!r}")


def check_life(path: Path, score) -> tuple[list[str], dict]:
    errs: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != LIFE_KEYS:
        errs.append(f"top-level keys {sorted(data)} != {sorted(LIFE_KEYS)}")
        return errs, {}
    try:
        today = date.fromisoformat(data["today"])
    except (TypeError, ValueError):
        return [f"bad today {data['today']!r}"], {}

    seen: set[str] = set()
    prev: date | None = None
    for m in data["messages"]:
        where = f"message {m.get('id')}"
        if not set(m) <= MESSAGE_KEYS or not {"id", "date", "text"} <= set(m):
            errs.append(f"{where}: keys {sorted(m)}")
            continue
        if not isinstance(m["text"], str) or not m["text"].strip():
            errs.append(f"{where}: empty text")
        if m["id"] in seen:
            errs.append(f"{where}: duplicate id")
        seen.add(m["id"])
        try:
            d = date.fromisoformat(m["date"])
        except (TypeError, ValueError):
            errs.append(f"{where}: bad date {m['date']!r}")
            continue
        if d > today:
            errs.append(f"{where}: dated {d} after today {today}")
        if prev and d < prev:
            errs.append(f"{where}: dated {d}, before the message above it ({prev})")
        prev = d

    qids: set[str] = set()
    golds = traps = 0
    for q in data["questions"]:
        where = f"question {q.get('id')}"
        if not set(q) <= QUESTION_KEYS or not {"id", "kind", "q"} <= set(q):
            errs.append(f"{where}: keys {sorted(q)}")
            continue
        if q["id"] in qids:
            errs.append(f"{where}: duplicate id")
        qids.add(q["id"])
        if q["kind"] not in KINDS:
            errs.append(f"{where}: unknown kind {q['kind']!r}")
        if q.get("abstain"):
            if q["kind"] != "abstain" or "must" in q:
                errs.append(f"{where}: abstain question with kind {q['kind']} or a must")
        else:
            if q["kind"] == "abstain":
                errs.append(f"{where}: kind abstain without abstain: true")
            _groups(q.get("must"), where, errs)
        if not all(isinstance(t, str) and t for t in q.get("must_not", [])):
            errs.append(f"{where}: bad must_not")
        if "gold" in q:
            golds += 1
            ok, why = score(q, q["gold"])
            if not ok:
                errs.append(f"{where}: gold fails: {why}")
            for term in q.get("must_not", []):
                if score(q, f"{q['gold']} {term}")[0]:
                    errs.append(f"{where}: must_not {term!r} does not fail the answer")
        for t in q.get("traps", []):
            traps += 1
            if score(q, t)[0]:
                errs.append(f"{where}: trap passes: {t!r}")

    stats = {
        "messages": len(data["messages"]),
        "questions": len(data["questions"]),
        "gold": golds,
        "traps": traps,
    }
    base = path.with_name(path.name.replace("_big", ""))
    if base != path and base.exists():
        b = json.loads(base.read_text(encoding="utf-8"))
        if b["questions"] != data["questions"] or b["today"] != data["today"]:
            errs.append(f"questions/today differ from {base.name}")
        have = {m["id"]: m for m in data["messages"]}
        lost = [m["id"] for m in b["messages"] if have.get(m["id"]) != m]
        if lost:
            errs.append(f"{len(lost)} messages of {base.name} missing or changed, e.g. {lost[:3]}")
    return errs, stats


def check_cases(path: Path) -> tuple[list[str], dict]:
    errs: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"about", "cases"}:
        return [f"top-level keys {sorted(data)}"], {}
    ids: set[str] = set()
    for c in data["cases"]:
        where = f"case {c.get('id')}"
        if not set(c) <= CASE_KEYS or not {"id", "cat", "text"} <= set(c):
            errs.append(f"{where}: keys {sorted(c)}")
            continue
        if c["id"] in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(c["id"])
        if not isinstance(c["text"], str) or not c["text"].strip():
            errs.append(f"{where}: empty text")
        if c.get("none"):
            if c.get("expect"):
                errs.append(f"{where}: none case with expect")
            continue
        if not isinstance(c.get("expect"), list) or not c["expect"]:
            errs.append(f"{where}: no expect")
            continue
        for e in c["expect"]:
            if not set(e) <= EXPECT_KEYS or not isinstance(e.get("about", "owner"), str):
                errs.append(f"{where}: expect keys {sorted(e)}")
            _groups(e.get("must"), where, errs)
            if "reason" in e:
                _groups(e["reason"], where + " reason", errs)
        if not all(isinstance(t, str) and t for t in c.get("never", [])):
            errs.append(f"{where}: bad never")
    return errs, {"cases": len(data["cases"])}


def main(argv: list[str]) -> int:
    score = _runner().score
    files = [Path(a) for a in argv] or sorted(DATA_DIR.glob("*.json"))
    bad = 0
    for path in files:
        if path.name.startswith("test_life"):
            errs, stats = check_life(path, score)
        elif path.name == "extraction_meaning.json":
            errs, stats = check_cases(path)
        else:
            continue
        print(f"{'FAIL' if errs else 'ok  '} {path.name} {stats}")
        for e in errs[:40]:
            print("     ", e)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
