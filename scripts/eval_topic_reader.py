"""Score the tech watch's topic reader on frozen pages (docs/specs/research-and-tech-watch.md).

    python scripts/eval_topic_reader.py [--model openrouter/x:free]

Runs the real topic_reader worker (research envelope, real free cloud model) over
evals/tech_watch/pages, two pages per call as scan_topic does, with "today"
fixed by expected.json, and keeps what validate_finding keeps. The models,
tools and dates are made up, so only the pages can tell the reader what is new.

Per topic: every expected release must be found (a kept title names it), and
nothing forbidden may be kept: old releases, models over the topic's size limit,
off-topic items, and the guides, comparisons or tutorials themselves.
Pass: every topic finds all and keeps nothing forbidden.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVAL = ROOT / "evals" / "tech_watch"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="run on this free cloud model only")
    args = parser.parse_args()

    from life_graph.config import settings
    from life_graph.services import web_pages, workers
    from life_graph.services.worker_templates import topic_reader, validate_finding

    if args.model:
        workers.envelope_models = lambda envelope: [args.model]  # type: ignore[assignment]
    spec = json.loads((EVAL / "expected.json").read_text())
    today = date.fromisoformat(spec["today"])
    ok_all, model = True, None
    for topic, t in spec["topics"].items():
        reader = topic_reader(topic, today)
        # The real rules for the topic, as configured (settings.tech_watch_topics).
        rules = settings.tech_watch_topic_specs.get(topic, {})
        kept: list[dict] = []
        pages = [(f"https://eval.local/{n}", (EVAL / "pages" / n).read_text()) for n in t["pages"]]
        for i in range(0, len(pages), 2):
            chunk = pages[i : i + 2]
            result = await workers.run_worker(
                reader.envelope,
                brief=reader.brief,
                inputs=web_pages.as_inputs(chunk),
                tenant_id="eval",
                reasoning=reader.reasoning,
            )
            model = result.model
            if result.error:
                print(f"  worker error on {[u for u, _ in chunk]}: {result.error}")
            sources = {u for u, _ in chunk}
            kept += [
                f
                for f in (
                    validate_finding(
                        x,
                        sources,
                        today=today,
                        kind=rules.get("kind"),
                        max_memory_gb=rules.get("max_memory_gb"),
                    )
                    for x in workers.json_array(result.text)
                )
                if f
            ]
        titles = [f["title"].lower() for f in kept]
        missing = [e for e in t["expect"] if not any(e in x for x in titles)]
        bad = sorted({f for f in t["forbid"] for x in titles if f in x})
        ok = not missing and not bad
        ok_all &= ok
        print(
            f"{'PASS' if ok else 'FAIL'}  {topic}"
            + (f"  missing {missing}" if missing else "")
            + (f"  kept forbidden {bad}" if bad else "")
        )
        for f in kept:
            print(f"      - {f['title']}  ({f['published_on']}, {f['source'].rsplit('/', 1)[-1]})")
    print(f"\n{'PASS' if ok_all else 'FAIL'}; model {model}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
