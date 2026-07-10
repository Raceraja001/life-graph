"""Era 6 — Dependency Watcher.

Monitors requirements.txt and package.json for outdated or vulnerable
dependencies, emits events per-package and a summary.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from life_graph.watchers.base import BaseWatcher, Severity
from life_graph.watchers.scrapers.npm import check_npm_version
from life_graph.watchers.scrapers.pypi import check_pypi_version

logger = logging.getLogger(__name__)

# Security-related keywords that escalate to CRITICAL severity
SECURITY_KEYWORDS = frozenset({
    "security", "cve", "vulnerability", "exploit", "patch",
    "xss", "csrf", "injection", "rce", "remote code execution",
    "denial of service", "dos", "buffer overflow", "privilege escalation",
    "authentication bypass", "sql injection", "ssrf", "deserialization",
    "path traversal", "directory traversal",
})

# Regex for requirements.txt lines: package==version
_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*==\s*([^\s#;]+)")


def _parse_requirements_txt(path: Path) -> dict[str, str]:
    """Parse requirements.txt returning ``{package: version}``."""
    deps: dict[str, str] = {}
    if not path.exists():
        return deps
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _REQ_RE.match(line)
        if m:
            deps[m.group(1).lower()] = m.group(2)
    return deps


def _parse_package_json(path: Path) -> dict[str, str]:
    """Parse package.json returning ``{package: version}`` from deps + devDeps."""
    deps: dict[str, str] = {}
    if not path.exists():
        return deps
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies"):
            for name, version_spec in data.get(section, {}).items():
                # Strip ^, ~, >= prefixes to get base version
                clean = re.sub(r"^[~^>=<]+", "", version_spec).strip()
                if clean:
                    deps[name] = clean
    except (json.JSONDecodeError, KeyError):
        pass
    return deps


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse semver string into tuple of ints."""
    parts: list[int] = []
    for p in v.split("."):
        m = re.match(r"(\d+)", p)
        try:
            parts.append(int(m.group(1)) if m else 0)
        except (AttributeError, ValueError):
            parts.append(0)
    return tuple(parts)


def _classify_severity(
    current: str, latest: str, summary: str = "",
) -> Severity:
    """Classify update severity based on version bump and security keywords."""
    # Check security keywords in summary
    summary_lower = summary.lower()
    for kw in SECURITY_KEYWORDS:
        if kw in summary_lower:
            return Severity.CRITICAL

    cur = _parse_version(current)
    lat = _parse_version(latest)

    # Major bump
    if len(cur) >= 1 and len(lat) >= 1 and lat[0] > cur[0]:
        return Severity.IMPORTANT
    # Minor bump
    if len(cur) >= 2 and len(lat) >= 2 and cur[0] == lat[0] and lat[1] > cur[1]:
        return Severity.IMPORTANT
    # Patch or unknown
    return Severity.INFO


async def _get_impact_analysis(
    package: str, current: str, latest: str, summary: str,
) -> str | None:
    """Optional LLM-based impact analysis via litellm."""
    try:
        import litellm

        prompt = (
            f"Analyze the impact of upgrading the package '{package}' "
            f"from version {current} to {latest}.\n\n"
            f"Package summary: {summary}\n\n"
            f"Provide a brief 2-3 sentence impact analysis covering:\n"
            f"1. Breaking changes risk\n"
            f"2. Security implications\n"
            f"3. Recommended action"
        )
        response = await litellm.acompletion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.debug("Impact analysis failed for %s: %s", package, exc)
        return None


class DependencyWatcher(BaseWatcher):
    """Watches for outdated or vulnerable dependencies."""

    name = "dependency_watcher"
    display_name = "Dependency Watcher"
    default_schedule = "0 6 * * 1"  # Weekly on Monday at 6 AM

    async def execute(self) -> None:  # noqa: C901
        config = self.settings or {}
        project_root = Path(config.get("project_root", "."))

        # Parse dependency files
        python_deps = _parse_requirements_txt(project_root / "requirements.txt")
        node_deps = _parse_package_json(project_root / "package.json")

        self.logger.info(
            "Checking %d Python + %d Node dependencies",
            len(python_deps), len(node_deps),
        )

        updates_found: list[dict[str, Any]] = []

        # ── Check Python dependencies ─────────────────────────
        for pkg, current_ver in python_deps.items():
            info = await check_pypi_version(pkg)
            if info and info["version"] != current_ver:
                severity = _classify_severity(
                    current_ver, info["version"], info.get("summary", ""),
                )
                impact = None
                if severity in (Severity.CRITICAL, Severity.IMPORTANT):
                    impact = await _get_impact_analysis(
                        pkg, current_ver, info["version"],
                        info.get("summary", ""),
                    )

                update_info: dict[str, Any] = {
                    "package": pkg,
                    "ecosystem": "python",
                    "current": current_ver,
                    "latest": info["version"],
                    "summary": info.get("summary", ""),
                    "impact_analysis": impact,
                }
                updates_found.append(update_info)

                self.emit_event(
                    severity=severity,
                    title=f"[Python] {pkg}: {current_ver} → {info['version']}",
                    details=update_info,
                    summary=impact,
                )

        # ── Check Node dependencies ───────────────────────────
        for pkg, current_ver in node_deps.items():
            info = await check_npm_version(pkg)
            if info and info["version"] != current_ver:
                severity = _classify_severity(
                    current_ver, info["version"],
                    info.get("description", ""),
                )
                impact = None
                if severity in (Severity.CRITICAL, Severity.IMPORTANT):
                    impact = await _get_impact_analysis(
                        pkg, current_ver, info["version"],
                        info.get("description", ""),
                    )

                update_info = {
                    "package": pkg,
                    "ecosystem": "node",
                    "current": current_ver,
                    "latest": info["version"],
                    "summary": info.get("description", ""),
                    "impact_analysis": impact,
                }
                updates_found.append(update_info)

                self.emit_event(
                    severity=severity,
                    title=f"[Node] {pkg}: {current_ver} → {info['version']}",
                    details=update_info,
                    summary=impact,
                )

        # ── Emit summary event ────────────────────────────────
        if updates_found:
            critical = sum(
                1 for u in updates_found
                if _classify_severity(
                    u["current"], u["latest"], u.get("summary", ""),
                ) == Severity.CRITICAL
            )
            important = sum(
                1 for u in updates_found
                if _classify_severity(
                    u["current"], u["latest"], u.get("summary", ""),
                ) == Severity.IMPORTANT
            )
            info_count = len(updates_found) - critical - important

            summary_text = (
                f"Dependency check complete: {len(updates_found)} updates available "
                f"({critical} critical, {important} important, {info_count} info)"
            )
            self.emit_event(
                severity=(
                    Severity.CRITICAL if critical > 0
                    else Severity.IMPORTANT if important > 0
                    else Severity.INFO
                ),
                title="Dependency Check Summary",
                details={
                    "total": len(updates_found),
                    "critical": critical,
                    "important": important,
                    "info": info_count,
                    "packages": [u["package"] for u in updates_found],
                },
                summary=summary_text,
            )
        else:
            self.emit_event(
                severity=Severity.INFO,
                title="Dependency Check Summary",
                details={"total": 0},
                summary="All dependencies are up to date.",
            )
