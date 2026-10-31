"""Does extraction keep the meaning of what the owner said?

Runs Life Graph's real extraction pipeline (the one capture uses, capture=True)
on evals/memory_structures/extraction_meaning.json: synthetic messages, so no
owner data, each with what must be kept. Checks, per expected fact: it was
found; it is about the right person (Ravi's fact never becomes the owner's);
"not" and "maybe" survived; a reason given is in it; a correction is flagged.
Also counts facts that would be kept without review although they are hedged or
about someone else (core/memory_manager._auto_approved with trust "self").

The 2026-10-30 memory bake-off traced most wrong answers to exactly these losses.

    PYTHONPATH=. python scripts/eval_extraction_meaning.py [--only subject,hedge] [--out FILE]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "memory_structures" / "extraction_meaning.json"

NEGATION = re.compile(
    r"\b(?:not|no|never|none|no longer|nor|without|stopped|quit|won'?t|didn'?t|doesn'?t|don'?t|"
    r"isn'?t|aren'?t|wasn'?t|decided against|dropped|cancel(?:led)?|avoid|stop(?:s|ped)?|dislike[sd]?|hate[sd]?|anymore|any more)\b|n't\b",
    re.I,
)
HEDGE = re.compile(
    r"\b(?:maybe|might|may|perhaps|possibly|consider(?:s|ed|ing)?|thinking (?:about|of)|"
    r"not sure|unsure|whether|could|undecided|we'?ll see)\b",
    re.I,
)


def _has_all(groups: list[list[str]], text: str) -> bool:
    return all(any(alt.lower() in text for alt in group) for group in groups)


def check(case: dict, facts: list) -> dict:
    """Pass/fail and why, for one case."""
    from life_graph.core.memory_manager import _auto_approved

    contents = [" ".join(f.content.lower().split()) for f in facts]
    why: list[str] = []
    auto_wrong = 0
    if case.get("none"):
        if facts:
            why.append(f"kept {len(facts)} fact(s) from small talk")
        return {"ok": not why, "why": why, "auto_wrong": 0}
    for phrase in case.get("never", []):
        if any(phrase.lower() in c for c in contents):
            why.append(f"wrong fact: '{phrase}'")
    for exp in case["expect"]:
        matches = [f for f, c in zip(facts, contents, strict=True) if _has_all(exp["must"], c)]
        if not matches:
            why.append("not extracted: " + " + ".join("/".join(g) for g in exp["must"]))
            continue
        f = matches[0]
        c = " ".join(f.content.lower().split())
        about = exp.get("about", "owner")
        subject = (getattr(f, "subject", "") or "").lower()
        if about != "owner":
            if about.lower() not in c and about.lower() not in subject:
                why.append(f"lost who it is about ({about})")
            if subject in ("", "owner", "self", "user") and getattr(f, "subject", None) is not None:
                why.append(f"subject recorded as the owner, not {about}")
        if exp.get("negate") and not (getattr(f, "polarity", "") == "negate" or NEGATION.search(c)):
            why.append("lost the 'not'")
        if exp.get("hedged"):
            if not (getattr(f, "certainty", "") == "hedged" or HEDGE.search(c)):
                why.append("lost the 'maybe' (stated as a plain fact)")
        if "reason" in exp:
            reason_text = c + " " + (getattr(f, "reason", "") or "").lower()
            if not _has_all(exp["reason"], reason_text):
                why.append("lost the reason")
        if exp.get("correction") and not getattr(f, "correction", False):
            why.append("correction not flagged")
        # Kept without review although the owner only said "maybe". (Facts about
        # other people the owner told us may be kept; the subject field keeps them
        # from being read as the owner's.)
        risky = bool(exp.get("hedged"))
        if risky and _auto_approved(f, "self") is not None:
            auto_wrong += 1
            why.append("would be kept without review")
    return {"ok": not why, "why": why, "auto_wrong": auto_wrong}


async def main(only: set[str] | None, out: Path | None) -> None:
    from life_graph.api.dependencies import get_extraction_pipeline
    from life_graph.config import settings

    data = json.loads(CASES.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if not only or c["cat"] in only]
    pipeline = get_extraction_pipeline()
    per_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    rows = []
    started = time.monotonic()
    for case in cases:
        result = await pipeline.extract(case["text"], capture=True)
        facts = list(result.facts)
        verdict = check(case, facts)
        per_cat[case["cat"]][0] += verdict["ok"]
        per_cat[case["cat"]][1] += 1
        rows.append(
            {
                "id": case["id"],
                "cat": case["cat"],
                "text": case["text"],
                **verdict,
                "facts": [
                    {
                        "content": f.content,
                        "type": f.fact_type,
                        "confidence": round(f.confidence, 2),
                        **{
                            k: getattr(f, k)
                            for k in ("subject", "polarity", "certainty", "reason", "correction")
                            if getattr(f, k, None) not in (None, "", False)
                        },
                    }
                    for f in facts
                ],
            }
        )
    passed = sum(v[0] for v in per_cat.values())
    auto_wrong = sum(r["auto_wrong"] for r in rows)
    print(
        f"model {settings.lm_extraction_model} · {len(cases)} cases · {time.monotonic() - started:.0f}s"
    )
    print(
        f"PASS {passed}/{len(cases)} = {100 * passed / max(1, len(cases)):.1f}%   kept without review wrongly: {auto_wrong}"
    )
    for cat, (ok, n) in sorted(per_cat.items()):
        print(f"  {cat:<11} {ok:>2}/{n}")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print("details:", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="comma-separated categories")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    asyncio.run(main(set(a.only.split(",")) if a.only else None, a.out))
