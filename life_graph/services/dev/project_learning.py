"""Learn a registered project's conventions into the preference store.

The cold-start analyzers (``life_graph/cold_start/``) mine a repository's git
history, config files and code for conventions — commit style, linter
settings, typing and naming habits. Until now their output only reached a
JSON file: the CLI printed "run with --store" for a flag that never existed,
so nothing they found ever reached an agent.

This stores each finding as a ``Preference`` (``source="cold_start"``) tagged
with the project, which is what ``ContextPacketBuilder`` injects into driver
dispatches. Findings are scoped to their project so one repo's ruff config is
not handed to an agent working in another.

Re-running is a refresh, not an append: a finding is matched to its earlier
row by a key that ignores the numbers in it ("Docstring rate: 40%" and
"Docstring rate: 45%" are the same finding), updated in place, and findings no
longer detected are archived.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from life_graph.services.preference_store import PreferenceStore

logger = logging.getLogger(__name__)

SOURCE = "cold_start"

# Tags that classify a finding rather than name its subject.
_GENERIC_TAGS = frozenset({"preference", "pattern", "architecture"})
# Findings about the person's schedule, not how code should be written.
_NOT_CODING_GUIDANCE = frozenset({"work-schedule"})


def finding_key(finding: dict[str, Any]) -> str:
    """Stable identity for a finding across re-runs (measured numbers excluded)."""
    stem = re.split(r"[\d:(]", finding.get("content", ""), maxsplit=1)[0]
    return f"{finding.get('source', '')}|{stem.strip().lower()}"


def _topic(project_name: str, finding: dict[str, Any]) -> str:
    subject = [t for t in finding.get("tags") or [] if t not in _GENERIC_TAGS]
    label = " / ".join(subject) if subject else finding.get("type_tag", "convention")
    return f"{project_name}: {label}"


def analyze(path: str, authors: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Run every cold-start analyzer. Returns (findings, notes on skipped parts)."""
    from life_graph.cold_start.code_analyzer import CodeAnalyzer
    from life_graph.cold_start.config_parser import ConfigParser
    from life_graph.cold_start.git_analyzer import GitAnalyzer

    findings: list[dict] = []
    notes: list[str] = []
    try:
        import pydriller  # noqa: F401

        findings += GitAnalyzer().analyze(path, author_filter=authors)
    except ImportError:
        notes.append("git history skipped: install the `cold-start` extra (pydriller)")
    except Exception as exc:
        notes.append(f"git history skipped: {exc}")
    for label, run in (
        ("config files", lambda: ConfigParser().parse(path)),
        ("code patterns", lambda: CodeAnalyzer().analyze(path)),
    ):
        try:
            findings += run()
        except Exception as exc:
            notes.append(f"{label} skipped: {exc}")
    return findings, notes


async def learn_project(
    store: PreferenceStore,
    tenant_id: str,
    project: dict[str, Any],
    *,
    authors: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze *project* and sync its findings into the preference store."""
    findings, notes = await asyncio.to_thread(analyze, project["path"], authors)
    project_id = project["id"]

    wanted: dict[str, dict] = {}
    for f in findings:
        if not f.get("content") or _NOT_CODING_GUIDANCE & set(f.get("tags") or []):
            continue
        wanted.setdefault(finding_key(f), f)

    existing: dict[str, Any] = {}
    offset = 0
    while True:
        page = await store.list(tenant_id, source=SOURCE, limit=200, offset=offset)
        for pref in page:
            props = pref.properties or {}
            if props.get("project_id") == project_id and props.get("finding_key"):
                existing[props["finding_key"]] = pref
        if len(page) < 200:
            break
        offset += 200

    created = updated = archived = 0
    for key, f in wanted.items():
        pref = existing.pop(key, None)
        if pref is None:
            await store.create(
                tenant_id,
                {
                    "topic": _topic(project["name"], f),
                    "choice": f["content"],
                    "context": f"project:{project['name']}",
                    "confidence": f.get("importance", 0.5),
                    "source": SOURCE,
                    "source_detail": f.get("source"),
                    "tags": [*(f.get("tags") or []), f"project:{project['name']}"],
                    "category": f.get("type_tag"),
                    "properties": {"project_id": project_id, "finding_key": key},
                },
            )
            created += 1
        elif pref.choice != f["content"]:
            # Confidence is left alone: it may carry validation since creation.
            await store.update(tenant_id, pref.id, {"choice": f["content"]})
            updated += 1
    for stale in existing.values():
        await store.delete(tenant_id, stale.id)
        archived += 1

    logger.info(
        "Learned project %s: %d created, %d updated, %d archived (%d findings)",
        project["name"],
        created,
        updated,
        archived,
        len(findings),
    )
    return {
        "project_id": project_id,
        "findings": len(wanted),
        "created": created,
        "updated": updated,
        "archived": archived,
        "notes": notes,
    }
