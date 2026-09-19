#!/usr/bin/env python3
"""Generate ``docs/STATE.md`` — the exact, current inventory of Life Graph.

Why this exists
---------------
Hand-maintained documentation drifts. ``KNOWLEDGE.md`` claimed "70 endpoints,
13 tables, 18 events" long after the real numbers were 242 / 64 / 77. The fix is
to stop writing the inventory by hand: everything in ``docs/STATE.md`` is derived
from the code itself, so a stale document becomes a visible ``git diff`` instead
of a silent lie.

``CHARTER.md`` holds intent (why we build, what the invariants are) and is
hand-written. This script owns the other half — what exists, right now.

Usage
-----
    python scripts/gen_state.py            # write docs/STATE.md
    python scripts/gen_state.py --html     # also write docs/feature-inventory.html
    python scripts/gen_state.py --check    # exit 1 if docs/STATE.md is stale

Runs with no database and no environment variables — every source below is a
pure import or a static parse.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import html
import logging
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Importing life_graph.main configures logging and emits a banner line. Silence
# everything before the import so --check produces clean, diffable output.
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

STATE_MD = REPO_ROOT / "docs" / "STATE.md"
INVENTORY_HTML = REPO_ROOT / "docs" / "feature-inventory.html"

HTTP_VERBS = ("get", "post", "put", "patch", "delete")

BANNER = (
    "<!-- GENERATED FILE — DO NOT EDIT BY HAND.\n"
    "     Produced by scripts/gen_state.py. Run `python scripts/gen_state.py`\n"
    "     to refresh. Intent and rationale live in CHARTER.md, not here. -->"
)


# ─────────────────────────────────────────────────────────────────────
# Collectors — each returns plain data, no formatting
# ─────────────────────────────────────────────────────────────────────


def collect_endpoints() -> dict[str, Any]:
    """Every HTTP operation the app actually serves, grouped by OpenAPI tag.

    Uses ``app.openapi()`` rather than walking ``app.routes``: this FastAPI
    version nests included routers as ``_IncludedRouter`` objects, so a naive
    walk of ``app.routes`` reports 12 routes and *zero* under ``/api/v1``.
    """
    from life_graph.main import app

    spec = app.openapi()
    by_tag: dict[str, list[dict[str, str]]] = defaultdict(list)
    total = 0

    for path, methods in sorted(spec.get("paths", {}).items()):
        for verb, op in methods.items():
            if verb.lower() not in HTTP_VERBS or not isinstance(op, dict):
                continue
            total += 1
            tags = op.get("tags") or ["(untagged)"]
            by_tag[tags[0]].append(
                {
                    "method": verb.upper(),
                    "path": path,
                    "summary": (op.get("summary") or "").strip(),
                }
            )

    return {
        "total": total,
        "path_count": len(spec.get("paths", {})),
        "by_tag": dict(sorted(by_tag.items(), key=lambda kv: (-len(kv[1]), kv[0]))),
    }


def collect_tables() -> dict[str, Any]:
    """All SQLAlchemy tables, cross-referenced to the migration that created them."""
    # These modules define additional tables on the same declarative Base.
    # Importing them for their registration side effect is the whole point.
    import life_graph.autonomy.models  # noqa: F401
    import life_graph.self_improving.models  # noqa: F401
    import life_graph.watchers.models  # noqa: F401
    from life_graph.models.db import Base

    created_by = _table_to_migration()
    tables = []
    for name, table in sorted(Base.metadata.tables.items()):
        tables.append(
            {
                "name": name,
                "columns": len(table.columns),
                "migration": created_by.get(name, "—"),
                "tenant_scoped": "tenant_id" in table.columns,
            }
        )
    return {"total": len(tables), "tables": tables}


def _table_to_migration() -> dict[str, str]:
    """Map each table name to the first migration file that creates it."""
    mapping: dict[str, str] = {}
    pattern = re.compile(r"""create_table\(\s*["']([a-z0-9_]+)["']""")
    for path in sorted((REPO_ROOT / "alembic" / "versions").glob("*.py")):
        for table_name in pattern.findall(path.read_text(encoding="utf-8")):
            mapping.setdefault(table_name, path.stem)
    return mapping


def collect_events() -> dict[str, Any]:
    """Event types on the bus, grouped by their name prefix."""
    from life_graph.core.events import EventType

    groups: dict[str, list[str]] = defaultdict(list)
    for member in EventType:
        groups[member.name.split("_")[0].title()].append(member.value)
    return {
        "total": len(list(EventType)),
        "groups": dict(sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))),
    }


def collect_personas() -> dict[str, Any]:
    """Built-in agent personas seeded at startup."""
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    personas = []
    for p in _BUILTIN_PERSONAS:
        personas.append(
            {
                "name": p.get("name", "—"),
                "display_name": p.get("display_name", ""),
                "description": (p.get("description") or "").strip(),
                "driver": p.get("driver") or "—",
                "task_types": list(p.get("task_types") or []),
                "verifier_chain": list(p.get("verifier_chain") or []),
                "tools": list(p.get("allowed_tools") or []),
                "intent_tags": list(p.get("intent_tags") or []),
            }
        )
    return {"total": len(personas), "personas": personas}


def collect_tools() -> dict[str, Any]:
    """Agent tools, discovered the same way main.py registers them.

    Importing each tool module triggers its ``@tool`` decorator, which registers
    against the module-level ``registry`` singleton.
    """
    from life_graph.tools.registry import registry

    for module in (
        "browser",
        "calculator",
        "datetime_tool",
        "delegate",
        "filesystem",
        "git",
        "system_inspect",
        "terminal",
        "web_search",
    ):
        __import__(f"life_graph.tools.{module}")

    descriptions: dict[str, str] = {}
    for spec in registry.get_tools():
        fn = spec.get("function", spec) if isinstance(spec, dict) else {}
        name = fn.get("name")
        if name:
            first_line = (fn.get("description") or "").strip().split("\n")[0]
            descriptions[name] = first_line

    names = sorted(registry.tool_names)
    return {
        "total": len(names),
        "names": names,
        "tools": [{"name": n, "description": descriptions.get(n, "")} for n in names],
    }


def collect_cron_jobs() -> dict[str, Any]:
    """Scheduled ARQ jobs, parsed from the cron() calls in workers/settings.py."""
    source = (REPO_ROOT / "life_graph" / "workers" / "settings.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    jobs = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "cron"):
            continue
        if not node.args:
            continue
        func_path = _literal(node.args[0])
        if not isinstance(func_path, str):
            continue
        kwargs = {kw.arg: _literal(kw.value) for kw in node.keywords if kw.arg}
        jobs.append(
            {
                "func": func_path,
                "name": func_path.rsplit(".", 1)[-1],
                "schedule": _format_schedule(
                    kwargs.get("hour"), kwargs.get("minute"), kwargs.get("weekday")
                ),
            }
        )

    jobs.sort(key=lambda j: j["name"])
    return {"total": len(jobs), "jobs": jobs}


def _literal(node: ast.AST) -> Any:
    """Best-effort evaluation of a cron keyword argument.

    Handles plain literals, plus the ``set(range(n))`` idiom used in
    workers/settings.py. Config-driven values like ``settings.brief_hour_utc``
    cannot be resolved statically and come back as a marker string.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        pass
    try:
        # Deliberately tiny namespace: only the builders our own source uses.
        return eval(  # noqa: S307 - restricted namespace over first-party source
            compile(ast.Expression(node), "<cron>", "eval"),
            {"__builtins__": {}},
            {"set": set, "range": range, "list": list, "tuple": tuple},
        )
    except Exception:  # noqa: BLE001 - any failure means "not statically known"
        return _Dynamic(ast.unparse(node))


class _Dynamic(str):
    """A value that depends on runtime config rather than a literal."""


_ALL_HOURS = set(range(24))
_ALL_MINUTES = set(range(60))
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _as_set(value: Any) -> set[int] | None:
    """Normalise an int / set / list into a set of ints, or None if dynamic."""
    if isinstance(value, _Dynamic) or value is None:
        return None
    if isinstance(value, int):
        return {value}
    if isinstance(value, (set, frozenset, list, tuple)):
        ints = {v for v in value if isinstance(v, int)}
        return ints or None
    return None


def _step_of(values: set[int], universe: set[int]) -> int | None:
    """Return N if `values` is exactly every-Nth across `universe`, else None."""
    ordered = sorted(values)
    if len(ordered) < 2 or ordered[0] != 0:
        return None
    steps = {b - a for a, b in zip(ordered, ordered[1:], strict=False)}
    if len(steps) != 1:
        return None
    step = steps.pop()
    return step if set(range(0, max(universe) + 1, step)) == values else None


def _format_schedule(hour: Any, minute: Any, weekday: Any) -> str:
    """Render cron kwargs as something a human can read at a glance."""
    hours, minutes = _as_set(hour), _as_set(minute)
    prefix = ""

    days = _as_set(weekday)
    if days is not None:
        prefix = ",".join(_WEEKDAYS[d] for d in sorted(days) if 0 <= d < 7) + " "

    # Fully dynamic hour (e.g. hour=settings.brief_hour_utc).
    if isinstance(hour, _Dynamic):
        mm = f"{min(minutes):02d}" if minutes else "00"
        return f"{prefix}daily at {hour}:{mm}"

    if minutes == _ALL_MINUTES:
        return f"{prefix}every minute"

    hourly = hours is None or hours == _ALL_HOURS
    if minutes and hourly:
        step = _step_of(minutes, _ALL_MINUTES)
        if step:
            return f"{prefix}every {step} min"
        if len(minutes) == 1:
            return f"{prefix}hourly at :{min(minutes):02d}"
        joined = ",".join(f":{m:02d}" for m in sorted(minutes))
        return f"{prefix}hourly at {joined}"

    if hours:
        mm = f"{min(minutes):02d}" if minutes else "00"
        if len(hours) == 1:
            return f"{prefix}{min(hours):02d}:{mm}"
        step = _step_of(hours, _ALL_HOURS)
        if step:
            return f"{prefix}every {step}h at :{mm}"
        return f"{prefix}{','.join(f'{h:02d}:{mm}' for h in sorted(hours))}"

    return f"{prefix}—".strip()


def collect_config() -> dict[str, Any]:
    """Every settable config field and its LIFE_GRAPH_* environment variable."""
    from life_graph.config import Settings

    prefix = "LIFE_GRAPH_"
    with contextlib.suppress(AttributeError):
        prefix = Settings.model_config.get("env_prefix", prefix) or prefix

    fields = []
    for name, field in Settings.model_fields.items():
        default = field.default
        rendered = (
            "—"
            if default is None or repr(default).startswith("PydanticUndefined")
            else repr(default)
        )
        if len(rendered) > 60:
            rendered = rendered[:57] + "…"
        fields.append({"env": f"{prefix}{name.upper()}", "name": name, "default": rendered})
    return {"total": len(fields), "prefix": prefix, "fields": fields}


def collect_migrations() -> dict[str, Any]:
    versions = sorted(p.stem for p in (REPO_ROOT / "alembic" / "versions").glob("*.py"))
    return {"total": len(versions), "versions": versions, "head": versions[-1] if versions else "—"}


def collect_tests() -> dict[str, Any]:
    """Test file and test-function counts, split by suite.

    Counts ``def test_*`` declarations. This is deliberately the number of test
    *functions*, which is lower than the number of cases pytest collects —
    ``@pytest.mark.parametrize`` expands one function into many.
    """
    pattern = re.compile(r"^\s*(?:async\s+)?def\s+test_", re.MULTILINE)
    tests_dir = REPO_ROOT / "tests"
    suites: dict[str, dict[str, int]] = {}
    total_files = total_funcs = 0

    def tally(label: str, files: list[Path]) -> None:
        nonlocal total_files, total_funcs
        if not files:
            return
        funcs = sum(
            len(pattern.findall(f.read_text(encoding="utf-8", errors="ignore"))) for f in files
        )
        suites[label] = {"files": len(files), "functions": funcs}
        total_files += len(files)
        total_funcs += funcs

    for suite in ("unit", "integration"):
        directory = tests_dir / suite
        if directory.exists():
            tally(f"tests/{suite}/", sorted(directory.rglob("test_*.py")))

    # Stragglers directly under tests/ (e.g. tests/test_integration.py).
    tally("tests/ (root)", sorted(tests_dir.glob("test_*.py")))

    return {"suites": suites, "total_files": total_files, "total_functions": total_funcs}


def collect_dashboard() -> dict[str, Any]:
    app_dir = REPO_ROOT / "dashboard" / "app"
    if not app_dir.exists():
        return {"total": 0, "pages": []}
    pages = []
    for page in sorted(app_dir.rglob("page.tsx")):
        rel = page.relative_to(app_dir).parent.as_posix()
        route = "/" if rel == "." else "/" + rel
        # Next.js route groups like (mobile) do not appear in the URL.
        route = re.sub(r"/\([^)]+\)", "", route) or "/"
        pages.append({"route": route, "file": page.relative_to(REPO_ROOT).as_posix()})
    return {"total": len(pages), "pages": pages}


def collect_specs() -> dict[str, Any]:
    """Triage docs/specs/ by checking each spec against the code that implements it.

    Verdicts come from a filesystem probe, not from assumption. Each entry maps a
    spec to the module or package that would exist if it were built.
    """
    probes: dict[str, tuple[str, str]] = {
        "os-kernel": ("life_graph/kernel/process_manager.py", "Built"),
        "era4-personal-ai": ("life_graph/api/advisor.py", "Built"),
        # Finish line: an optimized prompt reaching production. The optimizer
        # file existed for months while nothing read prompt_versions and the
        # nightly job crashed on its first query — and this probe said "Built".
        "era5-self-improving": ("life_graph/self_improving/prompt_resolver.py", "Built"),
        "era6-ambient-ai": ("life_graph/watchers/framework.py", "Built"),
        "era7-agent-networks": ("life_graph/api/agent_workflows.py", "Built"),
        "era8-autonomous-ai": ("life_graph/autonomy/router.py", "Built"),
        "era8-autonomy-reconciliation": ("life_graph/autonomy/kill_switch.py", "Built"),
        "capture-spine": ("life_graph/services/capture.py", "Built"),
        "judgment-engine": ("life_graph/services/judgment.py", "Built"),
        "agent-drivers": ("life_graph/drivers/dispatcher.py", "Built"),
        "approvals-feed": ("life_graph/api/approvals.py", "Built"),
        "personal-roles": ("life_graph/kernel/ambient.py", "Built"),
        "dashboard-pwa": ("dashboard/app/(mobile)/m/page.tsx", "Built"),
        "pwa-mobile": ("dashboard/app/(mobile)/m/page.tsx", "Built"),
        "mcp-tool-server": ("life_graph/mcp_server.py", "Built"),
        "eval-harness": ("life_graph/self_improving/eval_service.py", "Built"),
        "prompt-registry": ("life_graph/self_improving/prompt_version_service.py", "Built"),
        "natural-language-queries": ("life_graph/api/search.py", "Built"),
        "llm-trace-viewer": ("life_graph/api/model_health.py", "Built"),
        # Probes the API router, which is the last phase of the spec. Earlier
        # probes (the schema, then the poller) each went green while most of
        # the spec was still unbuilt, which is precisely the drift this file
        # exists to prevent — a probe must test the finish line, not the start.
        "telegram-bridge": ("life_graph/api/integrations_telegram.py", "Built"),
        # Finish line is the automatic weekly cycle (Phase 4), not the Phase 0 tables.
        "personal-model-tuning": ("life_graph/tuning/cycle.py", "Built"),
    }
    # Specs that describe a different product (Uzhavu SaaS / commercial work).
    other_product = {"razorpay-upi", "whatsapp-bot", "template-gallery"}

    specs = []
    for path in sorted((REPO_ROOT / "docs" / "specs").glob("*.md")):
        stem = path.stem
        if stem in other_product:
            status, evidence = "Not this product", "—"
        elif stem in probes:
            probe, label = probes[stem]
            exists = (REPO_ROOT / probe).exists()
            status = label if exists else "Spec'd, not built"
            evidence = probe if exists else "—"
        else:
            status, evidence = "Unclassified", "—"
        specs.append({"name": stem, "status": status, "evidence": evidence})
    return {"total": len(specs), "specs": specs}


def collect_meta() -> dict[str, Any]:
    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "unknown"

    py_files = list((REPO_ROOT / "life_graph").rglob("*.py"))
    loc = sum(
        len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        for f in py_files
        if "__pycache__" not in f.parts
    )
    return {
        "commit": git("rev-parse", "--short", "HEAD") or "unknown",
        "branch": git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        "py_files": len([f for f in py_files if "__pycache__" not in f.parts]),
        "loc": loc,
    }


def collect_all() -> dict[str, Any]:
    return {
        "meta": collect_meta(),
        "endpoints": collect_endpoints(),
        "tables": collect_tables(),
        "events": collect_events(),
        "personas": collect_personas(),
        "tools": collect_tools(),
        "cron": collect_cron_jobs(),
        "config": collect_config(),
        "migrations": collect_migrations(),
        "tests": collect_tests(),
        "dashboard": collect_dashboard(),
        "specs": collect_specs(),
    }


# ─────────────────────────────────────────────────────────────────────
# Markdown rendering
# ─────────────────────────────────────────────────────────────────────


def render_markdown(d: dict[str, Any]) -> str:
    m, ep, tb = d["meta"], d["endpoints"], d["tables"]
    ev, pe, tl = d["events"], d["personas"], d["tools"]
    cr, cf, mg = d["cron"], d["config"], d["migrations"]
    ts, db, sp = d["tests"], d["dashboard"], d["specs"]

    out: list[str] = [BANNER, "", "# Life Graph — State", ""]
    out += [
        "> **What exists right now.** Generated from the code by `scripts/gen_state.py`.",
        ">",
        "> This file deliberately contains **no rationale** — for why any of it exists, "
        "read [CHARTER.md](../CHARTER.md).",
        "",
        f"Generated `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}` "
        f"from `{m['branch']}` @ `{m['commit']}`",
        "",
        "---",
        "",
        "## At a glance",
        "",
        "| | |",
        "|---|---|",
        f"| HTTP operations | **{ep['total']}** across {ep['path_count']} paths, "
        f"{len(ep['by_tag'])} tags |",
        f"| Database tables | **{tb['total']}** |",
        f"| Migrations | **{mg['total']}** (head: `{mg['head']}`) |",
        f"| Event types | **{ev['total']}** |",
        f"| Built-in personas | **{pe['total']}** |",
        f"| Agent tools | **{tl['total']}** |",
        f"| Scheduled jobs | **{cr['total']}** |",
        f"| Config settings | **{cf['total']}** (prefix `{cf['prefix']}`) |",
        f"| Test functions | **{ts['total_functions']}** in {ts['total_files']} files |",
        f"| Dashboard pages | **{db['total']}** |",
        f"| Python | {m['py_files']} files, {m['loc']:,} lines |",
        "",
        "---",
        "",
    ]

    # ── Endpoints
    out += ["## HTTP API", "", f"{ep['total']} operations, grouped by OpenAPI tag.", ""]
    for tag, ops in ep["by_tag"].items():
        out += [f"### `{tag}` — {len(ops)}", "", "| Method | Path | Summary |", "|---|---|---|"]
        for op in sorted(ops, key=lambda o: (o["path"], o["method"])):
            out.append(f"| {op['method']} | `{op['path']}` | {op['summary'] or '—'} |")
        out.append("")

    # ── Tables
    out += [
        "---",
        "",
        "## Database tables",
        "",
        f"{tb['total']} tables. **Tenant** marks a `tenant_id` column — the "
        "multi-tenancy invariant requires every query to filter on it.",
        "",
        "| Table | Columns | Tenant | Created by |",
        "|---|---:|:---:|---|",
    ]
    for t in tb["tables"]:
        mark = "✓" if t["tenant_scoped"] else "—"
        out.append(f"| `{t['name']}` | {t['columns']} | {mark} | `{t['migration']}` |")
    out.append("")

    # ── Events
    out += ["---", "", "## Events", "", f"{ev['total']} event types on the async EventBus.", ""]
    for group, names in ev["groups"].items():
        joined = " · ".join(f"`{n}`" for n in sorted(names))
        out += [f"**{group}** ({len(names)}) — {joined}", ""]

    # ── Personas
    out += [
        "---",
        "",
        "## Built-in personas",
        "",
        f"{pe['total']} personas seeded at startup.",
        "",
        "| Persona | Driver | Task types | Verifiers | Tools |",
        "|---|---|---|---|---:|",
    ]
    for p in pe["personas"]:
        tt = ", ".join(f"`{t}`" for t in p["task_types"]) or "—"
        vc = ", ".join(f"`{v}`" for v in p["verifier_chain"]) or "—"
        out.append(
            f"| **{p['name']}** — {p['description']} | `{p['driver']}` | {tt} | {vc} "
            f"| {len(p['tools'])} |"
        )
    out.append("")

    # ── Tools
    out += [
        "---",
        "",
        "## Agent tools",
        "",
        f"{tl['total']} tools registered via the `@tool` decorator.",
        "",
        "| Tool | Description |",
        "|---|---|",
    ]
    for t in tl["tools"]:
        out.append(f"| `{t['name']}` | {t['description'] or '—'} |")
    out.append("")

    # ── Jobs
    out += [
        "---",
        "",
        "## Scheduled jobs",
        "",
        f"{cr['total']} ARQ cron jobs (times are UTC).",
        "",
        "| Job | Schedule | Function |",
        "|---|---|---|",
    ]
    for j in cr["jobs"]:
        out.append(f"| `{j['name']}` | {j['schedule']} | `{j['func']}` |")
    out.append("")

    # ── Dashboard
    out += [
        "---",
        "",
        "## Dashboard",
        "",
        f"{db['total']} pages.",
        "",
        "| Route | File |",
        "|---|---|",
    ]
    for p in db["pages"]:
        out.append(f"| `{p['route']}` | `{p['file']}` |")
    out.append("")

    # ── Specs
    out += [
        "---",
        "",
        "## Spec status",
        "",
        "Each spec in `docs/specs/` checked against the code that would implement it.",
        "",
        "| Spec | Status | Evidence |",
        "|---|---|---|",
    ]
    for s in sp["specs"]:
        evidence = f"`{s['evidence']}`" if s["evidence"] != "—" else "—"
        out.append(f"| `{s['name']}` | {s['status']} | {evidence} |")
    out.append("")

    # ── Migrations
    out += ["---", "", "## Migrations", "", f"{mg['total']} revisions, head `{mg['head']}`.", ""]
    out += [" · ".join(f"`{v}`" for v in mg["versions"]), ""]

    # ── Tests
    out += [
        "---",
        "",
        "## Tests",
        "",
        "Counts `def test_*` declarations. pytest collects more cases than this \u2014 "
        "`@pytest.mark.parametrize` expands one function into many.",
        "",
        "| Suite | Files | Functions |",
        "|---|---:|---:|",
    ]
    for suite, counts in ts["suites"].items():
        out.append(f"| `{suite}` | {counts['files']} | {counts['functions']} |")
    out.append(f"| **total** | **{ts['total_files']}** | **{ts['total_functions']}** |")
    out.append("")

    # ── Config
    out += [
        "---",
        "",
        "## Configuration",
        "",
        f"{cf['total']} settings, all overridable by environment variable.",
        "",
        "| Environment variable | Default |",
        "|---|---|",
    ]
    for f in cf["fields"]:
        out.append(f"| `{f['env']}` | `{f['default']}` |")
    out.append("")

    return "\n".join(out).rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────
# HTML rendering — a browsable view of the same data
# ─────────────────────────────────────────────────────────────────────

HTML_CSS = """
:root{
  --bg:#fbfaf8; --fg:#23201d; --muted:#6b645c; --line:#e2ddd6;
  --card:#fff; --accent:#8a5a2b; --ok:#2f6b3f; --warn:#9a3412; --cold:#5b5f8a;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#17161a; --fg:#eae6e0; --muted:#a49c93; --line:#333038;
    --card:#1f1e23; --accent:#d9a066; --ok:#7fbf90; --warn:#f0876a; --cold:#9aa0d6;
  }
}
:root[data-theme="dark"]{
  --bg:#17161a; --fg:#eae6e0; --muted:#a49c93; --line:#333038;
  --card:#1f1e23; --accent:#d9a066; --ok:#7fbf90; --warn:#f0876a; --cold:#9aa0d6;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;
  font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
.wrap{max-width:1080px;margin:0 auto;padding:48px 24px 96px}
h1{font-size:2rem;margin:0 0 .2em;letter-spacing:-.02em}
h2{font-size:1.25rem;margin:2.5em 0 .6em;padding-bottom:.3em;
  border-bottom:1px solid var(--line);letter-spacing:-.01em}
h3{font-size:1rem;margin:1.8em 0 .5em;color:var(--accent)}
.sub{color:var(--muted);margin:0 0 2em}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.88em;
  background:color-mix(in srgb,var(--fg) 7%,transparent);padding:.12em .38em;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:1.5em 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat .n{font-size:1.7rem;font-weight:650;letter-spacing:-.02em;display:block}
.stat .l{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1em 0}
table{border-collapse:collapse;width:100%;font-size:.88rem;min-width:520px}
th,td{text-align:left;padding:7px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:.76rem;text-transform:uppercase;
  letter-spacing:.05em;white-space:nowrap}
tbody tr:hover{background:color-mix(in srgb,var(--fg) 3%,transparent)}
.pill{display:inline-block;padding:.1em .5em;border-radius:99px;font-size:.75rem;
  border:1px solid currentColor}
.ok{color:var(--ok)} .warn{color:var(--warn)} .cold{color:var(--cold)}
.tags code{margin:0 .15em .3em 0;display:inline-block}
"""


def _h(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{_h(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_html(d: dict[str, Any]) -> str:
    m, ep, tb = d["meta"], d["endpoints"], d["tables"]
    ev, pe, tl = d["events"], d["personas"], d["tools"]
    cr, cf, mg = d["cron"], d["config"], d["migrations"]
    ts, db, sp = d["tests"], d["dashboard"], d["specs"]

    stats = [
        (ep["total"], "operations"),
        (tb["total"], "tables"),
        (ev["total"], "events"),
        (pe["total"], "personas"),
        (tl["total"], "tools"),
        (cr["total"], "cron jobs"),
        (cf["total"], "settings"),
        (mg["total"], "migrations"),
        (ts["total_functions"], "tests"),
        (db["total"], "pages"),
    ]
    parts = [
        # A standalone local file, not an Artifact fragment: it needs its own document
        # shell. Without an explicit charset a browser guesses, and every em dash in the
        # page renders as mojibake.
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Life Graph — Feature Inventory</title>",
        f"<style>{HTML_CSS}</style>",
        "</head>",
        "<body>",
        '<div class="wrap">',
        "<h1>Life Graph — Feature Inventory</h1>",
        f'<p class="sub">Generated from <code>{_h(m["branch"])}</code> @ '
        f"<code>{_h(m['commit'])}</code> · "
        f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{m['py_files']} Python files, {m['loc']:,} lines</p>",
        '<div class="grid">'
        + "".join(
            f'<div class="stat"><span class="n">{n}</span><span class="l">{_h(label)}</span></div>'
            for n, label in stats
        )
        + "</div>",
    ]

    parts.append(f"<h2>HTTP API — {ep['total']} operations</h2>")
    for tag, ops in ep["by_tag"].items():
        parts.append(f"<h3>{_h(tag)} — {len(ops)}</h3>")
        parts.append(
            _table(
                ["Method", "Path", "Summary"],
                [
                    [
                        f"<code>{_h(o['method'])}</code>",
                        f"<code>{_h(o['path'])}</code>",
                        _h(o["summary"] or "—"),
                    ]
                    for o in sorted(ops, key=lambda o: (o["path"], o["method"]))
                ],
            )
        )

    parts.append(f"<h2>Database — {tb['total']} tables</h2>")
    parts.append(
        _table(
            ["Table", "Columns", "Tenant", "Created by"],
            [
                [
                    f"<code>{_h(t['name'])}</code>",
                    str(t["columns"]),
                    '<span class="ok">✓</span>' if t["tenant_scoped"] else "—",
                    f"<code>{_h(t['migration'])}</code>",
                ]
                for t in tb["tables"]
            ],
        )
    )

    parts.append(f"<h2>Events — {ev['total']}</h2>")
    for group, names in ev["groups"].items():
        tags = " ".join(f"<code>{_h(n)}</code>" for n in sorted(names))
        parts.append(f'<h3>{_h(group)} — {len(names)}</h3><p class="tags">{tags}</p>')

    parts.append(f"<h2>Personas — {pe['total']}</h2>")
    parts.append(
        _table(
            ["Persona", "Description", "Driver", "Task types", "Tools"],
            [
                [
                    f"<strong>{_h(p['name'])}</strong>",
                    _h(p["description"]),
                    f"<code>{_h(p['driver'])}</code>",
                    " ".join(f"<code>{_h(t)}</code>" for t in p["task_types"]) or "—",
                    str(len(p["tools"])),
                ]
                for p in pe["personas"]
            ],
        )
    )

    parts.append(f"<h2>Tools — {tl['total']}</h2>")
    parts.append(
        _table(
            ["Tool", "Description"],
            [[f"<code>{_h(t['name'])}</code>", _h(t["description"] or "—")] for t in tl["tools"]],
        )
    )

    parts.append(f"<h2>Scheduled jobs — {cr['total']}</h2>")
    parts.append(
        _table(
            ["Job", "Schedule", "Function"],
            [
                [
                    f"<code>{_h(j['name'])}</code>",
                    _h(j["schedule"]),
                    f"<code>{_h(j['func'])}</code>",
                ]
                for j in cr["jobs"]
            ],
        )
    )

    parts.append(f"<h2>Dashboard — {db['total']} pages</h2>")
    parts.append(
        _table(
            ["Route", "File"],
            [
                [f"<code>{_h(p['route'])}</code>", f"<code>{_h(p['file'])}</code>"]
                for p in db["pages"]
            ],
        )
    )

    status_class = {"Built": "ok", "Spec'd, not built": "warn", "Not this product": "cold"}
    parts.append(f"<h2>Spec status — {sp['total']}</h2>")
    parts.append(
        _table(
            ["Spec", "Status", "Evidence"],
            [
                [
                    f"<code>{_h(s['name'])}</code>",
                    f'<span class="pill {status_class.get(s["status"], "")}">{_h(s["status"])}</span>',
                    f"<code>{_h(s['evidence'])}</code>" if s["evidence"] != "—" else "—",
                ]
                for s in sp["specs"]
            ],
        )
    )

    parts.append(f"<h2>Configuration — {cf['total']} settings</h2>")
    parts.append(
        _table(
            ["Environment variable", "Default"],
            [
                [f"<code>{_h(f['env'])}</code>", f"<code>{_h(f['default'])}</code>"]
                for f in cf["fields"]
            ],
        )
    )

    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


# ─────────────────────────────────────────────────────────────────────


def _strip_timestamp(text: str) -> str:
    """Drop the provenance stamp so --check compares content, not clock or SHA.

    The stamp records the commit the file was generated from, which is by
    construction the commit *before* the one that records the file itself.
    Comparing it would make --check report drift after every single commit
    while the inventory was in fact identical, so the whole line is
    normalised, not just the timestamp.
    """
    text = re.sub(
        r"Generated `[^`]*` from `[^`]*` @ `[^`]*`",
        "Generated `<ts>` from `<branch>` @ `<commit>`",
        text,
    )
    return re.sub(r"Generated `[^`]*`", "Generated `<ts>`", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if docs/STATE.md is stale")
    parser.add_argument(
        "--html", action="store_true", help="also write docs/feature-inventory.html"
    )
    args = parser.parse_args()

    data = collect_all()
    markdown = render_markdown(data)

    if args.check:
        if not STATE_MD.exists():
            print(f"STALE: {STATE_MD.relative_to(REPO_ROOT)} does not exist", file=sys.stderr)
            return 1
        current = STATE_MD.read_text(encoding="utf-8")
        if _strip_timestamp(current) != _strip_timestamp(markdown):
            import difflib

            diff = difflib.unified_diff(
                _strip_timestamp(current).splitlines(),
                _strip_timestamp(markdown).splitlines(),
                fromfile="docs/STATE.md (committed)",
                tofile="docs/STATE.md (regenerated)",
                lineterm="",
                n=1,
            )
            print("\n".join(diff), file=sys.stderr)
            print(
                "\nSTALE: docs/STATE.md is out of date. Run `python scripts/gen_state.py`.",
                file=sys.stderr,
            )
            return 1
        print("OK: docs/STATE.md is up to date.")
        return 0

    STATE_MD.parent.mkdir(parents=True, exist_ok=True)
    STATE_MD.write_text(markdown, encoding="utf-8")
    print(f"wrote {STATE_MD.relative_to(REPO_ROOT)} ({len(markdown.splitlines())} lines)")

    if args.html:
        INVENTORY_HTML.write_text(render_html(data), encoding="utf-8")
        print(f"wrote {INVENTORY_HTML.relative_to(REPO_ROOT)}")

    e, t = data["endpoints"], data["tables"]
    print(
        f"  {e['total']} operations · {t['total']} tables · {data['events']['total']} events · "
        f"{data['personas']['total']} personas · {data['config']['total']} settings · "
        f"{data['cron']['total']} cron jobs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
