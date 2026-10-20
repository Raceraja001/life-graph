"""Score research on demand on frozen pages (docs/specs/research-and-tech-watch.md, AC-6.5).

    python scripts/eval_researcher.py [--model openrouter/x:free]

Runs the real research() with the real worker (research envelope, real free
cloud model), but with search and fetch replaced by the frozen pages in
evals/research/pages. The providers and facts there are made up, so a right
answer can only come from the pages. A question passes when every expected
fact is in the claims and every claim cites only pages that state facts for
it (a cited distractor fails); the question with no answer in its pages passes
when nothing is claimed. Pass: >= 5 of 6.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVAL = ROOT / "evals" / "research"
PASS_AT = 5


def _url(name: str) -> str:
    return f"https://eval.local/{name}"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="run on this free cloud model only")
    args = parser.parse_args()

    from life_graph.services import web_pages, web_research, workers

    if args.model:
        workers.envelope_models = lambda envelope: [args.model]  # type: ignore[assignment]
    questions = json.loads((EVAL / "questions.json").read_text())
    passed = 0
    for q in questions:
        pages = {_url(n): (EVAL / "pages" / n).read_text() for n in q["pages"]}

        async def candidates(queries, *, limit, skip=frozenset(), _p=pages):
            return [web_pages.Hit(url=u, title=u.rsplit("/", 1)[-1]) for u in _p]

        async def read(urls, chars=0, _p=pages):
            return {u: _p[u] for u in urls}

        web_pages.candidates = candidates  # type: ignore[assignment]
        web_pages.read = read  # type: ignore[assignment]
        out = await web_research.research(q["question"], "eval")
        text = " ".join(c["text"] for c in out["claims"]).lower()
        allowed = {_url(n) for n in q["sources"]}
        cited = {u for c in out["claims"] for u in c["sources"]}
        if q["expect"]:
            missing = [alts[0] for alts in q["expect"] if not any(a in text for a in alts)]
            stray = sorted(cited - allowed)
            ok = not missing and not stray and bool(out["claims"])
            why = f"missing {missing}" if missing else f"cites {stray}" if stray else ""
        else:
            ok = not out["claims"]
            why = "" if ok else f"claimed {len(out['claims'])} with no answer in the pages"
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {q['question']}  {why}".rstrip())
        if out.get("error"):
            print(f"      worker error: {out['error']}")
        for c in out["claims"]:
            print(f"      - {c['text']}  {[s.rsplit('/', 1)[-1] for s in c['sources']]}")
    print(f"\n{passed}/{len(questions)} questions (pass at {PASS_AT}); model {out['model']}")
    return 0 if passed >= PASS_AT else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
