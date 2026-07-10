"""Code quality watcher — analyzes git repositories for quality metrics.

Runs weekly, compares to rolling averages, and surfaces insights
about test coverage, file churn, and commit patterns.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Lazy git import
_git = None
_git_checked = False


def _get_git():
    """Try to import gitpython. Returns module or None."""
    global _git, _git_checked
    if not _git_checked:
        try:
            import git
            _git = git
        except ImportError:
            logger.warning(
                "gitpython not installed — code quality watcher disabled. "
                "Install with: pip install gitpython"
            )
            _git = None
        _git_checked = True
    return _git


class CodeQualityWatcher:
    """Analyzes git repositories for code quality metrics and trends.

    Inherits from BaseWatcher once it exists. For now, uses a
    compatible interface.

    Attributes:
        name: Watcher identifier.
        default_schedule: Cron expression (Sunday 9 AM).
    """

    name = "code_quality"
    default_schedule = "0 9 * * 0"

    # Churn threshold: file appears in >50% of commits
    HIGH_CHURN_THRESHOLD = 0.5

    def __init__(self, config: dict[str, Any] | None = None, session_factory=None):
        self.config = config or {}
        self._session_factory = session_factory

    async def execute(self) -> list[dict[str, Any]]:
        """Analyze all configured projects.

        Returns:
            List of event dicts for insights found.
        """
        git_mod = _get_git()
        if git_mod is None:
            return [{
                "severity": "important",
                "title": "Code quality watcher skipped — gitpython not installed",
                "details": "Install gitpython to enable code quality analysis.",
                "watcher_name": self.name,
                "timestamp": datetime.now(timezone.utc),
            }]

        projects = self.config.get("projects", [])
        if not projects:
            logger.info("No projects configured for code quality watcher")
            return []

        events: list[dict[str, Any]] = []
        for project in projects:
            try:
                project_events = self._analyze_project(project)
                events.extend(project_events)
            except Exception as e:
                events.append({
                    "severity": "important",
                    "title": f"Code quality analysis failed: {project.get('name', project.get('path', 'unknown'))}",
                    "details": str(e),
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })

        return events

    def _analyze_project(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        """Analyze a single project's git history.

        Args:
            project: Dict with keys: path, name, days (default 7).

        Returns:
            List of insight events.
        """
        repo_path = project["path"]
        name = project.get("name", repo_path)
        days = project.get("days", 7)

        metrics = self._analyze_git_history(repo_path, days)
        if not metrics:
            return []

        # Get rolling average for comparison
        rolling = self._analyze_git_history(repo_path, days=28)

        events: list[dict[str, Any]] = []

        # Generate insights
        events.extend(self._check_test_coverage(name, metrics, rolling))
        events.extend(self._check_high_churn(name, metrics))
        events.extend(self._check_unusual_hours(name, metrics))
        events.extend(self._generate_summary(name, metrics, rolling))

        return events

    def _analyze_git_history(
        self,
        repo_path: str,
        days: int = 7,
    ) -> dict[str, Any] | None:
        """Extract metrics from git history.

        Args:
            repo_path: Path to git repository.
            days: Number of days to analyze.

        Returns:
            Dict of metrics or None if analysis fails.
        """
        git_mod = _get_git()
        if git_mod is None:
            return None

        try:
            repo = git_mod.Repo(repo_path)
        except Exception as e:
            logger.warning("Cannot open repo %s: %s", repo_path, e)
            return None

        since = datetime.now(timezone.utc) - timedelta(days=days)

        files_changed: set[str] = set()
        file_commit_counts: dict[str, int] = defaultdict(int)
        lines_added = 0
        lines_removed = 0
        commit_count = 0
        commit_by_day: dict[str, int] = defaultdict(int)
        commit_by_hour: dict[int, int] = defaultdict(int)
        test_files_changed: set[str] = set()
        source_files_changed: set[str] = set()

        try:
            for commit in repo.iter_commits(since=since.isoformat()):
                commit_count += 1
                commit_dt = datetime.fromtimestamp(
                    commit.committed_date, tz=timezone.utc
                )
                day_key = commit_dt.strftime("%A")
                commit_by_day[day_key] += 1
                commit_by_hour[commit_dt.hour] += 1

                # Diff stats
                try:
                    stats = commit.stats
                    for filepath, stat in stats.files.items():
                        files_changed.add(filepath)
                        file_commit_counts[filepath] += 1
                        lines_added += stat.get("insertions", 0)
                        lines_removed += stat.get("deletions", 0)

                        # Classify as test or source
                        lower = filepath.lower()
                        if "test" in lower or "spec" in lower:
                            test_files_changed.add(filepath)
                        elif lower.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
                            source_files_changed.add(filepath)
                except Exception:
                    pass

        except Exception as e:
            logger.warning("Error iterating commits in %s: %s", repo_path, e)

        if commit_count == 0:
            return None

        # Test-to-source ratio
        test_ratio = (
            len(test_files_changed) / len(source_files_changed)
            if source_files_changed
            else 0.0
        )

        return {
            "commit_count": commit_count,
            "files_changed": len(files_changed),
            "file_commit_counts": dict(file_commit_counts),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "commit_by_day": dict(commit_by_day),
            "commit_by_hour": dict(commit_by_hour),
            "test_files_changed": len(test_files_changed),
            "source_files_changed": len(source_files_changed),
            "test_to_source_ratio": round(test_ratio, 2),
            "days_analyzed": days,
        }

    def _check_test_coverage(
        self,
        project_name: str,
        current: dict[str, Any],
        rolling: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Check for test coverage drops relative to rolling average."""
        events: list[dict[str, Any]] = []

        if rolling and rolling.get("test_to_source_ratio", 0) > 0:
            current_ratio = current.get("test_to_source_ratio", 0)
            rolling_ratio = rolling["test_to_source_ratio"]

            if current_ratio < rolling_ratio * 0.7:
                drop_pct = ((rolling_ratio - current_ratio) / rolling_ratio) * 100
                events.append({
                    "severity": "important",
                    "title": f"Test coverage drop in {project_name}",
                    "details": (
                        f"Test-to-source ratio dropped {drop_pct:.0f}% "
                        f"(current: {current_ratio:.2f}, "
                        f"4-week avg: {rolling_ratio:.2f})"
                    ),
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })

        return events

    def _check_high_churn(
        self,
        project_name: str,
        metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify high-churn files (appear in >50% of commits)."""
        events: list[dict[str, Any]] = []
        commit_count = metrics.get("commit_count", 0)
        if commit_count == 0:
            return events

        file_counts = metrics.get("file_commit_counts", {})
        threshold = commit_count * self.HIGH_CHURN_THRESHOLD

        high_churn = [
            (f, c) for f, c in file_counts.items() if c >= threshold
        ]

        if high_churn:
            # Sort by count descending
            high_churn.sort(key=lambda x: x[1], reverse=True)
            files_list = "\n".join(
                f"  • {f} ({c}/{commit_count} commits)"
                for f, c in high_churn[:10]
            )
            events.append({
                "severity": "info",
                "title": f"High-churn files in {project_name}",
                "details": (
                    f"{len(high_churn)} files appeared in >50% of "
                    f"commits this week:\n{files_list}"
                ),
                "watcher_name": self.name,
                "timestamp": datetime.now(timezone.utc),
            })

        return events

    def _check_unusual_hours(
        self,
        project_name: str,
        metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Flag unusual commit hours (midnight–6 AM)."""
        events: list[dict[str, Any]] = []
        commit_by_hour = metrics.get("commit_by_hour", {})

        late_night = sum(
            commit_by_hour.get(h, 0) for h in range(0, 6)
        )
        total = metrics.get("commit_count", 0)

        if total > 0 and late_night > 0:
            pct = (late_night / total) * 100
            if pct >= 20:
                events.append({
                    "severity": "info",
                    "title": f"Unusual commit hours in {project_name}",
                    "details": (
                        f"{late_night}/{total} commits ({pct:.0f}%) "
                        f"were made between midnight and 6 AM."
                    ),
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })

        return events

    def _generate_summary(
        self,
        project_name: str,
        current: dict[str, Any],
        rolling: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Generate a weekly summary event."""
        details = (
            f"Commits: {current['commit_count']}\n"
            f"Files changed: {current['files_changed']}\n"
            f"Lines: +{current['lines_added']} / -{current['lines_removed']}\n"
            f"Test/source ratio: {current['test_to_source_ratio']:.2f}"
        )

        if rolling:
            weekly_avg = rolling["commit_count"] / 4
            delta = current["commit_count"] - weekly_avg
            direction = "▲" if delta > 0 else "▼" if delta < 0 else "─"
            details += f"\nVs 4-week avg: {direction} {abs(delta):.0f} commits"

        return [{
            "severity": "info",
            "title": f"Weekly code quality summary: {project_name}",
            "details": details,
            "watcher_name": self.name,
            "timestamp": datetime.now(timezone.utc),
        }]
