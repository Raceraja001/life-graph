"""Git repository analysis for cold start bootstrap.

Mines commit history with PyDriller to extract developer patterns:
commit conventions, time habits, language distribution, commit sizes,
and directory hotspots. All processing is local — zero API calls.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories to skip during analysis
VENDORED_DIRS = {
    "node_modules", ".venv", "venv", "vendor", "__pycache__",
    ".git", ".tox", "dist", "build", "egg-info", ".eggs",
    "site-packages", ".mypy_cache", ".pytest_cache", "migrations",
}

# Conventional commit pattern
CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)(\(.+?\))?:\s"
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


class GitAnalyzer:
    """Analyze Git repositories to extract developer patterns.

    Uses PyDriller to mine commit history and produce memory dicts
    suitable for direct storage in the Life Graph memory system.
    """

    def analyze(
        self,
        repo_path: str,
        author_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Analyze a Git repository and return memory dicts.

        Args:
            repo_path: Absolute path to the Git repository root.
            author_filter: Optional author name to filter commits by.

        Returns:
            List of memory dicts ready for storage.
        """
        try:
            from pydriller import Repository
        except ImportError:
            logger.warning("pydriller not installed — skipping Git analysis")
            return []

        repo_path = str(Path(repo_path).resolve())
        logger.info("Analyzing Git repo: %s", repo_path)

        result = self._mine_commits(Repository, repo_path, author_filter)
        if result is None:
            return []

        return self._result_to_memories(result, repo_path)

    # ── Private ───────────────────────────────────────────────

    def _mine_commits(
        self,
        repository_cls: type,
        repo_path: str,
        author_filter: str | None,
    ) -> dict[str, Any] | None:
        """Walk up to 1000 commits and collect statistics."""
        conventional_count = 0
        total_commits = 0
        prefix_counter: Counter[str] = Counter()
        hour_counter: Counter[int] = Counter()
        day_counter: Counter[int] = Counter()
        extension_counter: Counter[str] = Counter()
        lines_changed: list[int] = []
        files_per_commit: list[int] = []
        dir_counter: Counter[str] = Counter()

        for commit in repository_cls(repo_path).traverse_commits():
            if total_commits >= 1000:
                break

            # Author filter
            if author_filter and author_filter.lower() not in (
                commit.author.name or ""
            ).lower():
                continue

            total_commits += 1

            # Commit convention detection
            match = CONVENTIONAL_RE.match(commit.msg)
            if match:
                conventional_count += 1
                prefix_counter[match.group(1)] += 1

            # Time patterns
            author_dt = commit.author_date
            if author_dt.tzinfo is None:
                author_dt = author_dt.replace(tzinfo=timezone.utc)
            hour_counter[author_dt.hour] += 1
            day_counter[author_dt.weekday()] += 1

            # Per-file analysis
            commit_lines = 0
            file_count = 0
            for mod in commit.modified_files:
                if mod.filename and "." in mod.filename:
                    ext = mod.filename.rsplit(".", 1)[-1].lower()
                    extension_counter[ext] += 1

                commit_lines += (mod.added_lines or 0) + (mod.deleted_lines or 0)
                file_count += 1

                file_path = mod.new_path or mod.old_path
                if file_path:
                    parts = Path(file_path).parts
                    if any(p in VENDORED_DIRS for p in parts):
                        continue
                    if len(parts) > 1:
                        dir_counter[parts[0]] += 1

            lines_changed.append(commit_lines)
            files_per_commit.append(file_count)

        if total_commits == 0:
            logger.warning("No commits found in %s", repo_path)
            return None

        # Compute results
        conventional_ratio = conventional_count / total_commits
        commit_convention = (
            "conventional" if conventional_ratio > 0.6
            else "mixed" if conventional_ratio > 0.2
            else "freeform"
        )

        peak_hours = [h for h, _ in hour_counter.most_common(3)]
        active_days = [DAY_NAMES[d] for d, _ in day_counter.most_common(3)]
        top_prefixes = [p for p, _ in prefix_counter.most_common(5)]

        return {
            "total_commits": total_commits,
            "commit_convention": commit_convention,
            "conventional_ratio": round(conventional_ratio, 2),
            "top_prefixes": top_prefixes,
            "peak_hours": peak_hours,
            "active_days": active_days,
            "language_frequency": dict(extension_counter.most_common(10)),
            "avg_commit_size": round(
                sum(lines_changed) / len(lines_changed), 1
            ),
            "avg_files_per_commit": round(
                sum(files_per_commit) / len(files_per_commit), 1
            ),
            "top_directories": dict(dir_counter.most_common(10)),
        }

    def _result_to_memories(
        self, result: dict[str, Any], repo_path: str
    ) -> list[dict[str, Any]]:
        """Convert mined statistics into memory dicts."""
        memories: list[dict[str, Any]] = []
        base_props = {"source": "cold_start:git_analysis", "repo": repo_path}

        # Commit convention
        content = (
            f"Uses {result['commit_convention']} commit style "
            f"({result['conventional_ratio']:.0%} conventional commits)"
        )
        if result["top_prefixes"]:
            content += f". Top prefixes: {', '.join(result['top_prefixes'])}"
        memories.append({
            "content": content,
            "type_tag": "preference",
            "importance": 0.6,
            "source": "cold_start:git_analysis",
            "tags": ["preference", "git", "commit-style"],
        })

        # Peak hours
        if result["peak_hours"]:
            hours_str = ", ".join(f"{h}:00" for h in result["peak_hours"])
            memories.append({
                "content": f"Peak coding hours: {hours_str}",
                "type_tag": "pattern",
                "importance": 0.5,
                "source": "cold_start:git_analysis",
                "tags": ["pattern", "time", "work-schedule"],
            })

        # Most active days
        if result["active_days"]:
            memories.append({
                "content": f"Most active coding days: {', '.join(result['active_days'])}",
                "type_tag": "pattern",
                "importance": 0.5,
                "source": "cold_start:git_analysis",
                "tags": ["pattern", "time", "work-schedule"],
            })

        # Language distribution
        if result["language_frequency"]:
            top_langs = list(result["language_frequency"].keys())[:5]
            memories.append({
                "content": f"Primary languages (by file changes): {', '.join(top_langs)}",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:git_analysis",
                "tags": ["preference", "language"] + top_langs[:3],
            })

        # Commit size
        memories.append({
            "content": (
                f"Average commit size: {result['avg_commit_size']} lines changed, "
                f"{result['avg_files_per_commit']} files per commit"
            ),
            "type_tag": "pattern",
            "importance": 0.4,
            "source": "cold_start:git_analysis",
            "tags": ["pattern", "git", "commit-size"],
        })

        # Top directories
        if result["top_directories"]:
            top_dirs = list(result["top_directories"].keys())[:5]
            memories.append({
                "content": f"Most-changed directories: {', '.join(top_dirs)}",
                "type_tag": "pattern",
                "importance": 0.4,
                "source": "cold_start:git_analysis",
                "tags": ["pattern", "git", "project-structure"],
            })

        logger.info(
            "Git analysis produced %d memories from %d commits",
            len(memories), result["total_commits"],
        )
        return memories
