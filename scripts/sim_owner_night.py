"""A simulated owner lives a test life through the live API, then asks Jarvis about it.

The bake-off (eval_memory_structures.py) stores a test life straight through
MemoryManager. This goes the way the owner does: every message is said to
Jarvis (POST /jarvis/chat, captured like the phone's), the worker extracts it,
the "owner" keeps every pending memory that is not hedged, and then Jarvis is
asked the test questions in temporary chats (nothing is saved) and scored with
the bake-off's own score(). Run nightly against dev, the same life each night,
so a drop from one night to the next is a regression in the live path.

    PYTHONPATH=. python scripts/sim_owner_night.py [--life test_life_2]
        [--api http://localhost:8180] [--limit-messages N] [--limit-questions N]

Each run uses a fresh tenant (sim-<life>-<YYYYMMDDHHMM>) in the API's database,
whose built-in personas it seeds first: LIFE_GRAPH_DATABASE_URL(_SYNC) must be
that API's database (run from its checkout, or export them).
The API key comes from LIFE_GRAPH_SIM_API_KEY, else the Claude Code hook's
config (~/.life-graph/claude-code/config.json). Results go to
evals/local/sim/<tenant>.json and one line per run to evals/local/sim/history.tsv.

Known limits: messages are said within one night, so memories are dated that
night (their order is kept), and Jarvis answers with the real date as today.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals" / "memory_structures"
OUT = ROOT / "evals" / "local" / "sim"
#: What the simulated owner does not keep: the owner was only considering it.
HEDGED = re.compile(
    r"\b(consider(s|ed|ing)?|might|maybe|perhaps|not sure|unsure|thinking (about|of)|whether)\b",
    re.I,
)


def _score():
    """The bake-off's score(q, answer), loaded from its file."""
    path = ROOT / "scripts" / "eval_memory_structures.py"
    spec = importlib.util.spec_from_file_location("eval_memory_structures", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.score


def _api_key() -> str:
    key = os.environ.get("LIFE_GRAPH_SIM_API_KEY")
    if key:
        return key
    cfg = Path("~/.life-graph/claude-code/config.json").expanduser()
    return json.loads(cfg.read_text(encoding="utf-8")).get("api_key", "")


class Jarvis:
    def __init__(self, api: str, tenant: str, key: str) -> None:
        self.api = api.rstrip("/")
        self.headers = {"X-Tenant-ID": tenant, "Authorization": f"Bearer {key}"}
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))

    async def say(self, message: str, *, temporary: bool = False) -> tuple[str, str | None]:
        """(reply, error) for one message; the reply is rebuilt from the token stream."""
        parts: list[str] = []
        for attempt in range(3):
            try:
                async with self.client.stream(
                    "POST",
                    f"{self.api}/api/v1/jarvis/chat",
                    json={"message": message, "temporary": temporary},
                    headers=self.headers,
                ) as r:
                    if r.status_code == 429:
                        await asyncio.sleep(30 * (attempt + 1))
                        continue
                    if r.status_code >= 300:
                        return "", f"HTTP {r.status_code}"
                    async for line in r.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        if event.get("type") == "token":
                            parts.append(event.get("content", ""))
                        elif event.get("type") == "error":
                            return "".join(parts), event.get("message") or "error"
                    return "".join(parts).strip(), None
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == 2:
                    return "".join(parts), exc.__class__.__name__
                await asyncio.sleep(10)
        return "".join(parts), "rate limited"

    async def pending(self) -> list[dict]:
        r = await self.client.get(
            f"{self.api}/api/v1/jarvis/memories/pending",
            params={"limit": 200},
            headers=self.headers,
        )
        r.raise_for_status()
        body = r.json()
        data = body.get("data", body)
        return data.get("memories", data) if isinstance(data, dict) else data

    async def keep(self, memory_id: str) -> bool:
        r = await self.client.post(
            f"{self.api}/api/v1/jarvis/memories/{memory_id}/approve", headers=self.headers
        )
        return r.status_code < 300


async def _settle(
    j: Jarvis, quiet_polls: int = 4, every: float = 30.0, most: float = 3600.0
) -> int:
    """Wait until the pending count stops changing (the worker has caught up)."""
    started, last, same = time.monotonic(), -1, 0
    while time.monotonic() - started < most:
        n = len(await j.pending())
        same = same + 1 if n == last else 0
        if same >= quiet_polls:
            return n
        last = n
        await asyncio.sleep(every)
    return last


async def run(life: str, api: str, limit_messages: int | None, limit_questions: int | None) -> dict:
    data = json.loads((DATA / f"{life}.json").read_text(encoding="utf-8"))
    tenant = f"sim-{life.replace('_', '-')}-{datetime.now(UTC):%Y%m%d%H%M}"
    j = Jarvis(api, tenant, _api_key())
    health = (await j.client.get(f"{j.api}/health")).json()
    if health.get("status") != "healthy":
        raise SystemExit(f"API not healthy: {health}")
    # A new tenant has no personas ("Unknown persona: 'jarvis'"); the API seeds
    # only LIFE_GRAPH_SEED_TENANTS at startup. Needs the API's database settings.
    from life_graph.api.dependencies import get_persona_service

    print(
        f"[{tenant}] seeded {await get_persona_service().seed_builtins(tenant)} personas",
        flush=True,
    )
    msgs = sorted(data["messages"], key=lambda m: (m["date"], m["id"]))[:limit_messages]
    started = time.monotonic()
    said_errors = 0
    for n, m in enumerate(msgs, 1):
        _, err = await j.say(m["text"])
        said_errors += err is not None
        if n % 20 == 0:
            print(f"[{tenant}] said {n}/{len(msgs)}", flush=True)
    said_s = time.monotonic() - started
    left = await _settle(j)
    kept = skipped = 0
    for _ in range(10):  # pages of up to 200
        batch = await j.pending()
        todo = [m for m in batch if not HEDGED.search(m.get("content", ""))]
        if not todo:
            break
        for m in todo:
            kept += await j.keep(str(m["id"]))
    skipped = len(await j.pending())

    score = _score()
    qs = data["questions"][:limit_questions]
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    rows, ask_errors = [], 0
    for n, q in enumerate(qs, 1):
        answer, err = await j.say(q["q"], temporary=True)
        ask_errors += err is not None
        ok, why = score(q, answer)
        per[q["kind"]][0] += ok
        per[q["kind"]][1] += 1
        rows.append(
            {
                "id": q["id"],
                "kind": q["kind"],
                "q": q["q"],
                "answer": answer,
                "ok": ok,
                "why": why,
                "error": err,
            }
        )
        if n % 20 == 0:
            print(f"[{tenant}] asked {n}/{len(qs)}", flush=True)
    passed = sum(v[0] for v in per.values())
    summary = {
        "tenant": tenant,
        "life": life,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "messages": len(msgs),
        "said_errors": said_errors,
        "said_minutes": round(said_s / 60, 1),
        "pending_after_settle": left,
        "kept": kept,
        "left_pending_hedged": skipped,
        "questions": len(qs),
        "ask_errors": ask_errors,
        "passed": passed,
        "score": round(100 * passed / max(1, len(qs)), 1),
        "by_kind": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per.items())},
        "minutes": round((time.monotonic() - started) / 60, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{tenant}.json").write_text(
        json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    history = OUT / "history.tsv"
    if not history.exists():
        history.write_text(
            "at\tlife\tscore\tpassed\tquestions\tkept\tsaid_errors\task_errors\tminutes\n"
        )
    with history.open("a", encoding="utf-8") as f:
        f.write(
            f"{summary['at']}\t{life}\t{summary['score']}\t{passed}\t{len(qs)}\t{kept}\t"
            f"{said_errors}\t{ask_errors}\t{summary['minutes']}\n"
        )
    await j.client.aclose()
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--life", default="test_life_2")
    ap.add_argument("--api", default="http://localhost:8180")
    ap.add_argument("--limit-messages", type=int)
    ap.add_argument("--limit-questions", type=int)
    a = ap.parse_args()
    summary = asyncio.run(run(a.life, a.api, a.limit_messages, a.limit_questions))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
