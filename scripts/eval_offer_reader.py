"""Score the offer_reader worker on frozen pages (docs/specs/free-llm-offers.md §Eval).

    python scripts/eval_offer_reader.py [--model openrouter/x:free]

Runs the real worker (research envelope, real free cloud model) over
evals/llm_offers/pages, two pages per call as the news scan does, and checks:
every expected offer found with the right provider and kind; nothing reported
on the pages without an offer; and how many of the stated terms are right.
Pass: all offers found, none invented, terms >= 75% right.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVAL = ROOT / "evals" / "llm_offers"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="run on this free cloud model only")
    args = parser.parse_args()

    from life_graph.services import workers
    from life_graph.services.worker_templates import OFFER_READER, validate_offer

    if args.model:
        workers.envelope_models = lambda envelope: [args.model]  # type: ignore[assignment]
    expected = json.loads((EVAL / "expected.json").read_text())
    names = sorted(expected)
    found: dict[str, list[dict]] = {n: [] for n in names}
    model = None
    for i in range(0, len(names), 2):
        chunk = names[i : i + 2]
        sources = {f"https://eval.local/{n}": n for n in chunk}
        inputs = "\n\n".join(
            f"SOURCE: https://eval.local/{n}\n{(EVAL / 'pages' / n).read_text()}" for n in chunk
        )
        result = await workers.run_worker(
            "research",
            brief=OFFER_READER.brief,
            inputs=inputs,
            tenant_id="eval",
            reasoning=OFFER_READER.reasoning,
        )
        model = result.model
        if result.error:
            print(f"worker error on {chunk}: {result.error}")
        for item in workers.json_array(result.text):
            offer = validate_offer(item, set(sources))
            if offer:
                found[sources[offer["source"]]].append(offer)

    missed, invented, wrong_kind = [], [], []
    terms_right = terms_total = 0
    for name in names:
        want, got = expected[name], found[name]
        if not want and got:
            invented.append(f"{name}: {[g['provider'] for g in got]}")
        for w in want:
            match = next((g for g in got if w["provider"] in g["provider"].lower()), None)
            if match is None:
                missed.append(name)
                continue
            if match["kind"] not in w["kind"]:
                wrong_kind.append(f"{name}: {match['kind']}")
            for key, value in w["terms"].items():
                terms_total += 1
                terms_right += match["terms"].get(key) == value
    ratio = terms_right / terms_total if terms_total else 1.0
    ok = not missed and not invented and ratio >= 0.75
    print(f"model: {model}")
    print(f"offers missed: {missed or 'none'}")
    print(f"offers invented: {invented or 'none'}")
    print(f"wrong kind: {wrong_kind or 'none'}")
    print(f"terms right: {terms_right}/{terms_total} ({ratio:.0%})")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
