"""Sourced answers: a research answer must cite what its tools actually returned.

The 2026-10-12 survey caught the scout persona reporting a "finding" (a
library release) that no tool had returned; it came from the model's memory
and was two years stale. A prompt rule ("cite sources") is not enough on a
local model, so the check is deterministic and runs on every research
persona's answer:

- every URL the answer cites must appear in a tool result from the same run
  (normalised: scheme, ``www.``, trailing slash and fragment ignored);
- a substantive answer (``MIN_SUBSTANTIVE_CHARS``) that cites nothing fetched
  is marked unverified.

The answer is not rewritten or blocked; a note is appended so the reader
knows, and the run records the outcome for later study.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from life_graph.config import settings

_URL = re.compile(r"https?://[^\s<>\"'\)\]\}]+")
MIN_SUBSTANTIVE_CHARS = 280

UNSOURCED_NOTE = (
    "\n\n> ⚠️ Unverified: this answer cites {n} link(s) that no search or fetch "
    "returned during this run: {urls}. Check them before relying on them."
)
NO_SOURCES_NOTE = (
    "\n\n> ⚠️ Unverified: nothing in this answer comes from a search or a page "
    "fetched during this run, so it may be out of date or wrong."
)


def required_for(persona_name: str | None) -> bool:
    names = {n.strip() for n in settings.require_sources_personas.split(",") if n.strip()}
    return bool(persona_name) and persona_name in names


def normalise(url: str) -> str:
    url = url.rstrip(".,;:!?*_`")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return f"{host}{path}" + (f"?{parts.query}" if parts.query else "")


def urls_in(text: str) -> list[str]:
    seen: dict[str, str] = {}
    for raw in _URL.findall(text or ""):
        seen.setdefault(normalise(raw), raw.rstrip(".,;:!?*_`"))
    return list(seen.values())


def check(answer: str, tool_results: list[str]) -> dict[str, Any]:
    """Compare the answer's citations with what the tools returned."""
    fetched = {normalise(u) for result in tool_results for u in urls_in(result)}
    cited = urls_in(answer)
    verified = [u for u in cited if normalise(u) in fetched]
    unsourced = [u for u in cited if normalise(u) not in fetched]
    substantive = len((answer or "").strip()) >= MIN_SUBSTANTIVE_CHARS
    return {
        "cited": len(cited),
        "verified": verified,
        "unsourced_urls": unsourced,
        "fetched": len(fetched),
        "unverified": bool(unsourced) or (substantive and not verified),
    }


def annotate(answer: str, outcome: dict[str, Any]) -> str:
    """The answer with a visible note when the check failed."""
    if outcome["unsourced_urls"]:
        shown = ", ".join(outcome["unsourced_urls"][:3])
        return answer + UNSOURCED_NOTE.format(n=len(outcome["unsourced_urls"]), urls=shown)
    if outcome["unverified"]:
        return answer + NO_SOURCES_NOTE
    return answer


def _fetched(tool_results: list[str]) -> set[str]:
    return {normalise(u) for result in tool_results for u in urls_in(result)}


def check_findings(
    findings: list[Any], tool_results: list[str]
) -> tuple[list[Any], dict[str, Any]]:
    """Mark each finding whose source no tool returned as ``unverified``.

    Advisory personas end their reply with a JSON findings array that
    services/findings_bridge.py parses, so a note appended after it would
    break the contract. Each finding is checked on its own instead: its
    ``source`` (and any URL in its ``detail``) must be one this run fetched.
    """
    fetched = _fetched(tool_results)
    marked: list[Any] = []
    unverified = 0
    for item in findings:
        if not isinstance(item, dict):
            marked.append(item)
            continue
        cited = urls_in(f"{item.get('source') or ''} {item.get('detail') or ''}")
        item = {k: v for k, v in item.items() if k != "unverified"}
        if not any(normalise(u) in fetched for u in cited):
            item["unverified"] = True
            unverified += 1
        marked.append(item)
    return marked, {
        "findings": len([f for f in findings if isinstance(f, dict)]),
        "unverified_findings": unverified,
        "fetched": len(fetched),
        "unverified": unverified > 0,
    }


def apply(answer: str, tool_results: list[str]) -> tuple[str, dict[str, Any]]:
    """The checked answer and the outcome, for either reply shape."""
    import json

    from life_graph.services.findings_bridge import trailing_json_array

    found = trailing_json_array(answer)
    if found is not None:
        start, end, findings = found
        marked, outcome = check_findings(findings, tool_results)
        return answer[:start] + json.dumps(marked, ensure_ascii=False) + answer[end:], outcome
    outcome = check(answer, tool_results)
    return annotate(answer, outcome), outcome
