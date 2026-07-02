# 05 — Cold Start Bootstrap System

## From Zero to 50+ Memories in Under 10 Minutes — No API Calls

> [!IMPORTANT]
> The cold start problem kills most memory systems. Without pre-existing data, the system provides zero value for weeks while it slowly accumulates knowledge. Life Graph solves this by mining your **existing digital footprint** — Git repos, config files, notes, and code patterns — entirely with local processing. **Zero LLM API calls.**

---

## 1. Overview

### The Problem

A fresh memory system is worthless. It doesn't know your preferences, coding style, tech stack, or past decisions. The user has to manually "teach" it everything — which feels like work, not assistance.

### The Solution

Automatically extract 50+ high-quality memories from data you already have:

| Source | What We Extract | Expected Memories |
|--------|----------------|-------------------|
| Git repositories | Commit patterns, time habits, languages | 10-15 |
| Dependency files | Package preferences, version choices | 5-10 |
| Config files | Linting rules, editor settings, CI/CD | 5-10 |
| Notes (Obsidian) | Decisions, lessons, evaluations | 10-20 |
| Code patterns | Naming conventions, architecture, style | 10-15 |
| Commit messages | Work patterns, technology focus areas | 5-10 |

### Design Principles

1. **All local processing** — spaCy, AST parsing, regex, file parsing. No API calls.
2. **Store patterns and preferences, not raw data** — "Uses snake_case naming" not a code dump.
3. **Filter aggressively** — only store decisions, lessons, and preferences. Skip noise.
4. **Weight by recency and frequency** — recent patterns matter more than ancient history.
5. **Idempotent** — safe to re-run. Duplicate memories are deduplicated.

---

## 2. Git Repository Analysis

### 2.1 Repository Mining with PyDriller

```python
"""Git repository analysis for cold start bootstrap."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydriller import Repository


# Directories to skip during analysis
VENDORED_DIRS = {
    "node_modules", ".venv", "venv", "vendor", "__pycache__",
    ".git", ".tox", "dist", "build", "egg-info", ".eggs",
    "site-packages", ".mypy_cache", ".pytest_cache",
}

# Conventional commit pattern
CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)(\(.+?\))?:\s"
)


def analyze_git_repo(repo_path: str) -> dict[str, Any]:
    """
    Analyze a Git repository to extract developer patterns.

    Returns a dict with commit conventions, time patterns, language
    frequency, average commit size, and directory hotspots.
    """
    repo_path = str(Path(repo_path).resolve())

    # Accumulators
    conventional_count = 0
    total_commits = 0
    hour_counter: Counter[int] = Counter()
    day_counter: Counter[int] = Counter()  # 0=Monday, 6=Sunday
    extension_counter: Counter[str] = Counter()
    lines_changed: list[int] = []
    dir_counter: Counter[str] = Counter()

    for commit in Repository(repo_path).traverse_commits():
        total_commits += 1

        # --- Commit convention detection ---
        if CONVENTIONAL_RE.match(commit.msg):
            conventional_count += 1

        # --- Time patterns ---
        author_dt = commit.author_date
        if author_dt.tzinfo is None:
            author_dt = author_dt.replace(tzinfo=timezone.utc)
        hour_counter[author_dt.hour] += 1
        day_counter[author_dt.weekday()] += 1

        # --- Per-file analysis ---
        commit_lines = 0
        for mod in commit.modified_files:
            # Language frequency from extensions
            if mod.filename and "." in mod.filename:
                ext = mod.filename.rsplit(".", 1)[-1].lower()
                extension_counter[ext] += 1

            # Lines changed
            commit_lines += (mod.added_lines or 0) + (mod.deleted_lines or 0)

            # Directory hotspots
            file_path = mod.new_path or mod.old_path
            if file_path:
                parts = Path(file_path).parts
                # Skip vendored directories
                if any(p in VENDORED_DIRS for p in parts):
                    continue
                if len(parts) > 1:
                    dir_counter[parts[0]] += 1

        lines_changed.append(commit_lines)

    # --- Compute results ---
    if total_commits == 0:
        return {"error": "No commits found", "repo_path": repo_path}

    # Peak coding hours (top 3)
    peak_hours = [h for h, _ in hour_counter.most_common(3)]

    # Most active days
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
    active_days = [day_names[d] for d, _ in day_counter.most_common(3)]

    # Commit convention
    conventional_ratio = conventional_count / total_commits
    commit_convention = (
        "conventional" if conventional_ratio > 0.6
        else "mixed" if conventional_ratio > 0.2
        else "freeform"
    )

    return {
        "repo_path": repo_path,
        "total_commits": total_commits,
        "commit_convention": commit_convention,
        "conventional_ratio": round(conventional_ratio, 2),
        "peak_hours": peak_hours,
        "active_days": active_days,
        "language_frequency": dict(extension_counter.most_common(10)),
        "avg_commit_size": round(sum(lines_changed) / len(lines_changed), 1),
        "directory_hotspots": dict(dir_counter.most_common(10)),
    }
```

### 2.2 Dependency Preference Extraction

```python
"""Extract dependency preferences from package manifests."""

import json
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def extract_dependency_preferences(repo_path: str) -> list[dict[str, Any]]:
    """
    Scan package manifests to find consistently-used dependencies.

    Checks: requirements.txt, pyproject.toml, package.json.
    Returns a list of memory dicts ready for storage.
    """
    root = Path(repo_path)
    memories: list[dict[str, Any]] = []
    dep_counter: Counter[str] = Counter()

    # --- requirements.txt ---
    req_files = list(root.rglob("requirements*.txt"))
    for req_file in req_files:
        if any(p in VENDORED_DIRS for p in req_file.parts):
            continue
        try:
            for line in req_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    # Extract package name (before any version specifier)
                    pkg = re.split(r"[>=<!\[;]", line)[0].strip().lower()
                    if pkg:
                        dep_counter[pkg] += 1
        except (OSError, UnicodeDecodeError):
            continue

    # --- pyproject.toml ---
    pyproject_files = list(root.rglob("pyproject.toml"))
    for pyproject_file in pyproject_files:
        if any(p in VENDORED_DIRS for p in pyproject_file.parts):
            continue
        try:
            data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))

            # Poetry dependencies
            poetry_deps = (
                data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            )
            for pkg in poetry_deps:
                if pkg.lower() != "python":
                    dep_counter[pkg.lower()] += 1

            # PEP 621 dependencies
            pep621_deps = data.get("project", {}).get("dependencies", [])
            for dep_str in pep621_deps:
                pkg = re.split(r"[>=<!\[;]", dep_str)[0].strip().lower()
                if pkg:
                    dep_counter[pkg] += 1

        except (OSError, UnicodeDecodeError, Exception):
            continue

    # --- package.json ---
    pkg_json_files = list(root.rglob("package.json"))
    for pkg_file in pkg_json_files:
        if any(p in VENDORED_DIRS for p in pkg_file.parts):
            continue
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies"):
                for pkg in data.get(section, {}):
                    dep_counter[pkg.lower()] += 1
        except (OSError, json.JSONDecodeError):
            continue

    # --- Convert to memories ---
    for pkg, count in dep_counter.most_common(30):
        importance = min(0.5 + (count * 0.1), 0.9)  # More uses = higher importance
        memories.append({
            "content": f"Uses {pkg} as a dependency (found in {count} manifest(s))",
            "tags": ["dependency", "tooling", pkg],
            "importance": round(importance, 2),
            "confidence": 0.9,
            "properties": {
                "source": "cold_start:dependency_scan",
                "package": pkg,
                "occurrence_count": count,
            },
        })

    return memories
```

---

## 3. Configuration File Parsing

```python
"""Extract developer preferences from configuration files."""

import json
import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import yaml  # pyyaml


def extract_config_preferences(repo_path: str) -> list[dict[str, Any]]:
    """
    Parse configuration files to extract coding style preferences.

    Scans: pyproject.toml, tsconfig.json, .editorconfig, Dockerfile, CI/CD workflows.
    Returns a list of memory dicts ready for storage.
    """
    root = Path(repo_path)
    memories: list[dict[str, Any]] = []

    # --- pyproject.toml ---
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            tool = data.get("tool", {})

            # Ruff configuration
            ruff = tool.get("ruff", {})
            if ruff:
                line_length = ruff.get("line-length")
                if line_length:
                    memories.append({
                        "content": f"Uses ruff linter with line-length={line_length}",
                        "tags": ["preference", "python", "linting", "ruff"],
                        "importance": 0.7,
                        "confidence": 1.0,
                        "properties": {
                            "source": "cold_start:config_parse",
                            "tool": "ruff",
                            "line_length": line_length,
                        },
                    })
                select_rules = ruff.get("select") or ruff.get("lint", {}).get("select")
                if select_rules:
                    memories.append({
                        "content": f"Ruff lint rules selected: {', '.join(select_rules[:10])}",
                        "tags": ["preference", "python", "linting", "ruff"],
                        "importance": 0.6,
                        "confidence": 1.0,
                        "properties": {
                            "source": "cold_start:config_parse",
                            "rules": select_rules,
                        },
                    })

            # Black configuration
            black = tool.get("black", {})
            if black:
                memories.append({
                    "content": f"Uses Black formatter with config: {json.dumps(black)}",
                    "tags": ["preference", "python", "formatting", "black"],
                    "importance": 0.7,
                    "confidence": 1.0,
                    "properties": {"source": "cold_start:config_parse", "tool": "black"},
                })

            # Pytest configuration
            pytest_cfg = tool.get("pytest", {}).get("ini_options", {})
            if pytest_cfg:
                memories.append({
                    "content": f"Pytest configuration: {json.dumps(pytest_cfg)}",
                    "tags": ["preference", "python", "testing", "pytest"],
                    "importance": 0.6,
                    "confidence": 1.0,
                    "properties": {"source": "cold_start:config_parse", "tool": "pytest"},
                })

            # Mypy configuration
            mypy = tool.get("mypy", {})
            if mypy:
                strict = mypy.get("strict", False)
                memories.append({
                    "content": f"Uses mypy for type checking (strict={strict})",
                    "tags": ["preference", "python", "typing", "mypy"],
                    "importance": 0.7,
                    "confidence": 1.0,
                    "properties": {"source": "cold_start:config_parse", "strict": strict},
                })
        except Exception:
            pass

    # --- tsconfig.json ---
    tsconfig = root / "tsconfig.json"
    if tsconfig.exists():
        try:
            # Handle JSON with comments (common in tsconfig)
            raw = tsconfig.read_text(encoding="utf-8")
            raw = re.sub(r"//.*$", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
            data = json.loads(raw)
            compiler = data.get("compilerOptions", {})

            parts = []
            if compiler.get("strict"):
                parts.append("strict mode enabled")
            if compiler.get("target"):
                parts.append(f"target={compiler['target']}")
            if compiler.get("module"):
                parts.append(f"module={compiler['module']}")

            if parts:
                memories.append({
                    "content": f"TypeScript config: {', '.join(parts)}",
                    "tags": ["preference", "typescript", "config"],
                    "importance": 0.7,
                    "confidence": 1.0,
                    "properties": {
                        "source": "cold_start:config_parse",
                        "compiler_options": compiler,
                    },
                })
        except Exception:
            pass

    # --- .editorconfig ---
    editorconfig = root / ".editorconfig"
    if editorconfig.exists():
        try:
            text = editorconfig.read_text(encoding="utf-8")
            indent_style = re.search(r"indent_style\s*=\s*(\w+)", text)
            indent_size = re.search(r"indent_size\s*=\s*(\w+)", text)
            end_of_line = re.search(r"end_of_line\s*=\s*(\w+)", text)

            parts = []
            if indent_style:
                parts.append(f"indent_style={indent_style.group(1)}")
            if indent_size:
                parts.append(f"indent_size={indent_size.group(1)}")
            if end_of_line:
                parts.append(f"end_of_line={end_of_line.group(1)}")

            if parts:
                memories.append({
                    "content": f"Editor config preferences: {', '.join(parts)}",
                    "tags": ["preference", "editor", "formatting"],
                    "importance": 0.6,
                    "confidence": 1.0,
                    "properties": {"source": "cold_start:config_parse"},
                })
        except Exception:
            pass

    # --- Dockerfile ---
    for dockerfile in root.rglob("Dockerfile*"):
        if any(p in VENDORED_DIRS for p in dockerfile.parts):
            continue
        try:
            text = dockerfile.read_text(encoding="utf-8")
            # Base image extraction
            from_lines = re.findall(r"^FROM\s+(\S+)", text, re.MULTILINE)
            if from_lines:
                is_multistage = len(from_lines) > 1
                memories.append({
                    "content": (
                        f"Docker base image(s): {', '.join(from_lines)}"
                        f"{' (multi-stage build)' if is_multistage else ''}"
                    ),
                    "tags": ["preference", "docker", "infrastructure"],
                    "importance": 0.7,
                    "confidence": 1.0,
                    "properties": {
                        "source": "cold_start:config_parse",
                        "base_images": from_lines,
                        "multi_stage": is_multistage,
                    },
                })
        except Exception:
            pass

    # --- CI/CD Workflows ---
    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.is_dir():
        for wf_file in workflow_dir.glob("*.yml"):
            try:
                data = yaml.safe_load(wf_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue

                for job_name, job in data.get("jobs", {}).items():
                    # Runner type
                    runs_on = job.get("runs-on", "")
                    if runs_on:
                        memories.append({
                            "content": f"CI job '{job_name}' runs on: {runs_on}",
                            "tags": ["preference", "ci", "github-actions"],
                            "importance": 0.5,
                            "confidence": 1.0,
                            "properties": {
                                "source": "cold_start:config_parse",
                                "workflow": wf_file.name,
                            },
                        })

                    # Python version matrix
                    strategy = job.get("strategy", {})
                    matrix = strategy.get("matrix", {})
                    py_versions = matrix.get("python-version", [])
                    if py_versions:
                        memories.append({
                            "content": (
                                f"Tests against Python versions: "
                                f"{', '.join(str(v) for v in py_versions)}"
                            ),
                            "tags": ["preference", "python", "testing", "ci"],
                            "importance": 0.6,
                            "confidence": 1.0,
                            "properties": {
                                "source": "cold_start:config_parse",
                                "python_versions": py_versions,
                            },
                        })
            except Exception:
                continue

    # --- GitLab CI ---
    gitlab_ci = root / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        memories.append({
            "content": "Uses GitLab CI/CD for continuous integration",
            "tags": ["preference", "ci", "gitlab"],
            "importance": 0.6,
            "confidence": 1.0,
            "properties": {"source": "cold_start:config_parse"},
        })

    # --- Jenkinsfile ---
    jenkinsfile = root / "Jenkinsfile"
    if jenkinsfile.exists():
        memories.append({
            "content": "Uses Jenkins for CI/CD pipeline",
            "tags": ["preference", "ci", "jenkins"],
            "importance": 0.6,
            "confidence": 1.0,
            "properties": {"source": "cold_start:config_parse"},
        })

    return memories
```

---

## 4. Note-Taking Import

### 4.1 What to Extract vs What to Ignore

| Extract | Ignore |
|---------|--------|
| Decisions with reasoning | Pure bookmark collections |
| Lessons learned | Copy-pasted articles |
| Personal preferences | Meeting notes without decisions |
| Tool evaluations | Daily journal entries without insights |
| Architecture choices | Link dumps |

> [!CAUTION]
> **Collector's Fallacy**: Importing every note is worse than importing none. A memory system full of noise provides no value. Filter ruthlessly for decisions and lessons only.

### 4.2 Obsidian Vault Parser

```python
"""Extract knowledge from Obsidian vaults and markdown notes."""

import re
from pathlib import Path
from typing import Any

import yaml


# Decision signal keywords
DECISION_SIGNALS = [
    "decided", "chose", "switched to", "prefer", "going with",
    "picked", "selected", "opted for", "moving to", "replacing",
    "will use", "settled on", "committed to",
]

# Lesson signal keywords
LESSON_SIGNALS = [
    "learned", "mistake", "never again", "turns out", "important",
    "realized", "discovered", "gotcha", "pitfall", "lesson",
    "takeaway", "insight", "the trick is", "key finding",
    "don't forget", "remember that", "pro tip",
]

# Wikilink pattern: [[link|optional display text]]
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Tag pattern: #tag-name (not inside code blocks)
TAG_RE = re.compile(r"(?<!\S)#([a-zA-Z][a-zA-Z0-9_/-]*)")


def _parse_obsidian_note(file_path: Path) -> dict[str, Any] | None:
    """
    Parse a single Obsidian markdown file.

    Returns parsed content with frontmatter, wikilinks, tags, and body text.
    Returns None if the file is unparseable.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    frontmatter: dict[str, Any] = {}
    body = text

    # Extract YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2]

    # Extract wikilinks
    wikilinks = WIKILINK_RE.findall(body)

    # Extract inline tags
    inline_tags = TAG_RE.findall(body)

    # Combine frontmatter tags with inline tags
    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [fm_tags]
    all_tags = list(set(fm_tags + inline_tags))

    # Strip markdown formatting for analysis
    clean_body = re.sub(r"```[\s\S]*?```", "", body)  # Remove code blocks
    clean_body = re.sub(r"`[^`]+`", "", clean_body)    # Remove inline code
    clean_body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_body)  # Simplify links

    return {
        "file_name": file_path.stem,
        "frontmatter": frontmatter,
        "body": clean_body.strip(),
        "wikilinks": wikilinks,
        "tags": all_tags,
        "word_count": len(clean_body.split()),
        "link_count": len(wikilinks) + body.count("](http"),
    }


def _is_bookmark_only(note: dict[str, Any]) -> bool:
    """
    Detect if a note is just a collection of links/bookmarks.

    Returns True if the note has more links than substantive text.
    """
    word_count = note["word_count"]
    link_count = note["link_count"]

    if word_count < 20:
        return True
    if link_count > 0 and (link_count / word_count) > 0.3:
        return True

    return False


def _detect_signals(text: str) -> dict[str, list[str]]:
    """Detect decision and lesson signals in text."""
    text_lower = text.lower()
    found: dict[str, list[str]] = {"decisions": [], "lessons": []}

    # Find sentences containing decision signals
    sentences = re.split(r"[.!?\n]", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue
        sentence_lower = sentence.lower()

        for signal in DECISION_SIGNALS:
            if signal in sentence_lower:
                found["decisions"].append(sentence)
                break

        for signal in LESSON_SIGNALS:
            if signal in sentence_lower:
                found["lessons"].append(sentence)
                break

    return found


def extract_knowledge_from_notes(vault_path: str) -> list[dict[str, Any]]:
    """
    Extract decisions and lessons from an Obsidian vault.

    Filters aggressively: only stores notes with clear decision or
    lesson signals. Skips bookmark collections and link dumps.

    Args:
        vault_path: Path to the Obsidian vault root directory.

    Returns:
        List of memory dicts ready for storage.
    """
    root = Path(vault_path)
    memories: list[dict[str, Any]] = []

    if not root.is_dir():
        return memories

    md_files = list(root.rglob("*.md"))

    for md_file in md_files:
        # Skip hidden directories and templates
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue
        if "template" in str(md_file).lower():
            continue

        note = _parse_obsidian_note(md_file)
        if note is None:
            continue

        # Skip bookmark-only notes (collector's fallacy)
        if _is_bookmark_only(note):
            continue

        # Detect decision and lesson signals
        signals = _detect_signals(note["body"])

        # Create memories from decisions
        for decision in signals["decisions"]:
            memories.append({
                "content": decision,
                "tags": ["decision", "note-import"] + note["tags"][:5],
                "importance": 0.7,
                "confidence": 0.8,  # Lower confidence since auto-extracted
                "properties": {
                    "source": "cold_start:obsidian_import",
                    "source_file": str(md_file.relative_to(root)),
                    "signal_type": "decision",
                    "wikilinks": note["wikilinks"][:10],
                },
            })

        # Create memories from lessons
        for lesson in signals["lessons"]:
            memories.append({
                "content": lesson,
                "tags": ["lesson", "note-import"] + note["tags"][:5],
                "importance": 0.8,  # Lessons are high value
                "confidence": 0.8,
                "properties": {
                    "source": "cold_start:obsidian_import",
                    "source_file": str(md_file.relative_to(root)),
                    "signal_type": "lesson",
                    "wikilinks": note["wikilinks"][:10],
                },
            })

    return memories
```

> [!TIP]
> The confidence is set to 0.8 (not 1.0) for imported notes because auto-extraction may misinterpret context. The user can later confirm or dismiss these memories, adjusting confidence accordingly.

---

## 5. Code Pattern Analysis

### 5.1 Python AST Visitor

```python
"""Extract coding patterns from Python source files using AST analysis."""

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any


class CodePatternVisitor(ast.NodeVisitor):
    """
    AST visitor that extracts coding style patterns from Python files.

    Tracks: naming conventions, docstrings, type hints, error handling,
    test frameworks, async usage, dataclass/pydantic patterns, imports.
    """

    def __init__(self) -> None:
        self.function_count = 0
        self.functions_with_docstrings = 0
        self.functions_with_type_hints = 0
        self.async_function_count = 0
        self.class_count = 0

        # Naming tracking
        self.snake_case_names: int = 0
        self.camel_case_names: int = 0

        # Error handling
        self.bare_excepts = 0
        self.specific_excepts = 0

        # Import tracking
        self.imports: Counter[str] = Counter()
        self.decorators: Counter[str] = Counter()

        # Framework detection
        self.uses_pytest = False
        self.uses_unittest = False
        self.uses_pydantic = False
        self.uses_dataclass = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef,
                          is_async: bool) -> None:
        self.function_count += 1
        if is_async:
            self.async_function_count += 1

        # Naming convention detection
        name = node.name
        if not name.startswith("_"):
            if re.match(r"^[a-z][a-z0-9_]*$", name):
                self.snake_case_names += 1
            elif re.match(r"^[a-z][a-zA-Z0-9]*$", name):
                self.camel_case_names += 1

        # Docstring detection
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            self.functions_with_docstrings += 1

        # Type hint detection (return annotation or any arg annotation)
        has_hints = node.returns is not None
        if not has_hints:
            for arg in node.args.args:
                if arg.annotation is not None:
                    has_hints = True
                    break
        if has_hints:
            self.functions_with_type_hints += 1

        # Test framework detection
        if name.startswith("test_"):
            self.uses_pytest = True  # Convention-based
        if node.decorator_list:
            for dec in node.decorator_list:
                dec_name = self._get_decorator_name(dec)
                if dec_name:
                    self.decorators[dec_name] += 1
                    if dec_name == "pytest.fixture":
                        self.uses_pytest = True

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_count += 1

        # Check for unittest.TestCase inheritance
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name and "TestCase" in base_name:
                self.uses_unittest = True
            if base_name and "BaseModel" in base_name:
                self.uses_pydantic = True

        # Check for dataclass decorator
        for dec in node.decorator_list:
            dec_name = self._get_decorator_name(dec)
            if dec_name and "dataclass" in dec_name:
                self.uses_dataclass = True
            if dec_name:
                self.decorators[dec_name] += 1

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.bare_excepts += 1
        else:
            self.specific_excepts += 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_module = alias.name.split(".")[0]
            self.imports[top_module] += 1

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top_module = node.module.split(".")[0]
            self.imports[top_module] += 1

    def _get_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parent = self._get_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

    def _get_decorator_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Call):
            return self._get_name(node.func)
        return self._get_name(node)

    def to_memories(self) -> list[dict[str, Any]]:
        """Convert collected patterns into memory dicts."""
        memories: list[dict[str, Any]] = []

        if self.function_count == 0:
            return memories

        # Naming convention
        total_names = self.snake_case_names + self.camel_case_names
        if total_names > 0:
            snake_ratio = self.snake_case_names / total_names
            convention = (
                "snake_case" if snake_ratio > 0.8
                else "camelCase" if snake_ratio < 0.2
                else "mixed"
            )
            memories.append({
                "content": f"Uses {convention} naming convention for functions "
                           f"({self.snake_case_names} snake_case, "
                           f"{self.camel_case_names} camelCase)",
                "tags": ["preference", "python", "naming-convention"],
                "importance": 0.7,
                "confidence": 0.9,
                "properties": {
                    "source": "cold_start:code_analysis",
                    "snake_ratio": round(snake_ratio, 2),
                },
            })

        # Docstring rate
        doc_rate = self.functions_with_docstrings / self.function_count
        memories.append({
            "content": f"Docstring rate: {doc_rate:.0%} of functions have docstrings "
                       f"({self.functions_with_docstrings}/{self.function_count})",
            "tags": ["preference", "python", "documentation"],
            "importance": 0.6,
            "confidence": 0.9,
            "properties": {
                "source": "cold_start:code_analysis",
                "docstring_rate": round(doc_rate, 2),
            },
        })

        # Type hint rate
        hint_rate = self.functions_with_type_hints / self.function_count
        memories.append({
            "content": f"Type hint rate: {hint_rate:.0%} of functions have type "
                       f"annotations ({self.functions_with_type_hints}/{self.function_count})",
            "tags": ["preference", "python", "typing"],
            "importance": 0.7,
            "confidence": 0.9,
            "properties": {
                "source": "cold_start:code_analysis",
                "type_hint_rate": round(hint_rate, 2),
            },
        })

        # Error handling style
        total_excepts = self.bare_excepts + self.specific_excepts
        if total_excepts > 0:
            style = (
                "specific exceptions"
                if self.bare_excepts == 0
                else "bare excepts"
                if self.specific_excepts == 0
                else f"mixed ({self.bare_excepts} bare, {self.specific_excepts} specific)"
            )
            memories.append({
                "content": f"Error handling style: {style}",
                "tags": ["preference", "python", "error-handling"],
                "importance": 0.6,
                "confidence": 0.9,
                "properties": {"source": "cold_start:code_analysis"},
            })

        # Test framework
        if self.uses_pytest:
            memories.append({
                "content": "Uses pytest as the testing framework",
                "tags": ["preference", "python", "testing", "pytest"],
                "importance": 0.7,
                "confidence": 0.95,
                "properties": {"source": "cold_start:code_analysis"},
            })
        elif self.uses_unittest:
            memories.append({
                "content": "Uses unittest as the testing framework",
                "tags": ["preference", "python", "testing", "unittest"],
                "importance": 0.7,
                "confidence": 0.95,
                "properties": {"source": "cold_start:code_analysis"},
            })

        # Async usage
        if self.async_function_count > 0:
            async_ratio = self.async_function_count / self.function_count
            memories.append({
                "content": f"Uses async/await pattern ({async_ratio:.0%} of functions "
                           f"are async, {self.async_function_count} total)",
                "tags": ["preference", "python", "async"],
                "importance": 0.6,
                "confidence": 0.9,
                "properties": {
                    "source": "cold_start:code_analysis",
                    "async_ratio": round(async_ratio, 2),
                },
            })

        # Pydantic vs dataclass
        if self.uses_pydantic:
            memories.append({
                "content": "Uses Pydantic BaseModel for data validation and modeling",
                "tags": ["preference", "python", "pydantic", "data-modeling"],
                "importance": 0.7,
                "confidence": 0.95,
                "properties": {"source": "cold_start:code_analysis"},
            })
        if self.uses_dataclass:
            memories.append({
                "content": "Uses Python dataclasses for data structures",
                "tags": ["preference", "python", "dataclass", "data-modeling"],
                "importance": 0.7,
                "confidence": 0.95,
                "properties": {"source": "cold_start:code_analysis"},
            })

        # Top imports
        top_imports = self.imports.most_common(20)
        if top_imports:
            import_names = [name for name, _ in top_imports]
            memories.append({
                "content": f"Most-used Python imports: {', '.join(import_names[:10])}",
                "tags": ["preference", "python", "imports"],
                "importance": 0.5,
                "confidence": 0.9,
                "properties": {
                    "source": "cold_start:code_analysis",
                    "top_imports": dict(top_imports),
                },
            })

        # Top decorators
        top_decorators = self.decorators.most_common(10)
        if top_decorators:
            dec_names = [name for name, _ in top_decorators]
            memories.append({
                "content": f"Most-used decorators: {', '.join(dec_names[:5])}",
                "tags": ["preference", "python", "decorators"],
                "importance": 0.5,
                "confidence": 0.9,
                "properties": {
                    "source": "cold_start:code_analysis",
                    "top_decorators": dict(top_decorators),
                },
            })

        return memories


def analyze_python_code(repo_path: str) -> list[dict[str, Any]]:
    """
    Analyze all Python files in a repo and extract coding patterns.

    Skips vendored directories and files that fail to parse.
    """
    root = Path(repo_path)
    visitor = CodePatternVisitor()

    py_files = list(root.rglob("*.py"))
    parsed_count = 0

    for py_file in py_files:
        # Skip vendored directories
        if any(p in VENDORED_DIRS for p in py_file.parts):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            visitor.visit(tree)
            parsed_count += 1
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    memories = visitor.to_memories()

    # Add file count metadata
    if memories:
        memories[0]["properties"]["files_analyzed"] = parsed_count

    return memories
```

### 5.2 Architecture Detection

```python
"""Detect project architecture patterns from file structure."""

import json
from pathlib import Path
from typing import Any


def detect_architecture(repo_path: str) -> list[dict[str, Any]]:
    """
    Detect architectural patterns from file and directory structure.

    Detects: monorepo, Docker, CI, frontend/backend frameworks,
    architecture patterns (MVC, clean arch, flat).
    """
    root = Path(repo_path)
    memories: list[dict[str, Any]] = []

    # --- Monorepo detection ---
    pkg_jsons = list(root.rglob("package.json"))
    pkg_jsons = [p for p in pkg_jsons
                 if not any(v in p.parts for v in VENDORED_DIRS)]
    pyprojects = list(root.rglob("pyproject.toml"))
    pyprojects = [p for p in pyprojects
                  if not any(v in p.parts for v in VENDORED_DIRS)]

    if len(pkg_jsons) > 2 or len(pyprojects) > 2:
        memories.append({
            "content": (
                f"Uses monorepo structure ({len(pkg_jsons)} package.json, "
                f"{len(pyprojects)} pyproject.toml found)"
            ),
            "tags": ["architecture", "monorepo", "project-structure"],
            "importance": 0.8,
            "confidence": 0.85,
            "properties": {"source": "cold_start:architecture_detection"},
        })

    # --- Docker detection ---
    dockerfiles = list(root.rglob("Dockerfile*"))
    compose_files = list(root.rglob("docker-compose*.yml")) + \
                    list(root.rglob("docker-compose*.yaml"))
    if dockerfiles or compose_files:
        memories.append({
            "content": (
                f"Uses Docker for containerization"
                f"{' with docker-compose' if compose_files else ''}"
            ),
            "tags": ["architecture", "docker", "infrastructure"],
            "importance": 0.7,
            "confidence": 0.95,
            "properties": {"source": "cold_start:architecture_detection"},
        })

    # --- CI detection ---
    ci_systems: list[str] = []
    if (root / ".github" / "workflows").is_dir():
        ci_systems.append("GitHub Actions")
    if (root / ".gitlab-ci.yml").exists():
        ci_systems.append("GitLab CI")
    if (root / "Jenkinsfile").exists():
        ci_systems.append("Jenkins")
    if (root / ".circleci").is_dir():
        ci_systems.append("CircleCI")
    if (root / ".travis.yml").exists():
        ci_systems.append("Travis CI")

    if ci_systems:
        memories.append({
            "content": f"Uses {', '.join(ci_systems)} for CI/CD",
            "tags": ["architecture", "ci", "infrastructure"],
            "importance": 0.7,
            "confidence": 0.95,
            "properties": {
                "source": "cold_start:architecture_detection",
                "ci_systems": ci_systems,
            },
        })

    # --- Frontend framework detection ---
    for pkg_file in pkg_jsons[:3]:  # Check first 3 package.json files
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            all_deps = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
            }
            if "next" in all_deps:
                memories.append({
                    "content": "Uses Next.js as frontend framework",
                    "tags": ["architecture", "frontend", "nextjs", "react"],
                    "importance": 0.8,
                    "confidence": 0.95,
                    "properties": {"source": "cold_start:architecture_detection"},
                })
                break
            elif "react" in all_deps:
                memories.append({
                    "content": "Uses React as frontend framework",
                    "tags": ["architecture", "frontend", "react"],
                    "importance": 0.8,
                    "confidence": 0.95,
                    "properties": {"source": "cold_start:architecture_detection"},
                })
                break
            elif "vue" in all_deps:
                memories.append({
                    "content": "Uses Vue.js as frontend framework",
                    "tags": ["architecture", "frontend", "vue"],
                    "importance": 0.8,
                    "confidence": 0.95,
                    "properties": {"source": "cold_start:architecture_detection"},
                })
                break
        except (OSError, json.JSONDecodeError):
            continue

    # --- Backend framework detection ---
    all_requirements_text = ""
    for req in list(root.rglob("requirements*.txt"))[:5]:
        if not any(v in req.parts for v in VENDORED_DIRS):
            try:
                all_requirements_text += req.read_text(encoding="utf-8") + "\n"
            except (OSError, UnicodeDecodeError):
                pass

    for pyp in pyprojects[:3]:
        try:
            all_requirements_text += pyp.read_text(encoding="utf-8") + "\n"
        except (OSError, UnicodeDecodeError):
            pass

    req_lower = all_requirements_text.lower()
    if "fastapi" in req_lower:
        memories.append({
            "content": "Uses FastAPI as backend framework",
            "tags": ["architecture", "backend", "fastapi", "python"],
            "importance": 0.8,
            "confidence": 0.95,
            "properties": {"source": "cold_start:architecture_detection"},
        })
    elif "django" in req_lower:
        memories.append({
            "content": "Uses Django as backend framework",
            "tags": ["architecture", "backend", "django", "python"],
            "importance": 0.8,
            "confidence": 0.95,
            "properties": {"source": "cold_start:architecture_detection"},
        })
    elif "flask" in req_lower:
        memories.append({
            "content": "Uses Flask as backend framework",
            "tags": ["architecture", "backend", "flask", "python"],
            "importance": 0.8,
            "confidence": 0.95,
            "properties": {"source": "cold_start:architecture_detection"},
        })

    # --- Architecture pattern detection ---
    dir_names = {d.name.lower() for d in root.iterdir() if d.is_dir()}
    all_dirs = {d.name.lower() for d in root.rglob("*") if d.is_dir()
                and not any(v in d.parts for v in VENDORED_DIRS)}

    # MVC pattern
    mvc_signals = {"models", "views", "controllers", "templates"}
    if len(mvc_signals & all_dirs) >= 3:
        memories.append({
            "content": "Project follows MVC (Model-View-Controller) architecture pattern",
            "tags": ["architecture", "pattern", "mvc"],
            "importance": 0.7,
            "confidence": 0.8,
            "properties": {"source": "cold_start:architecture_detection"},
        })

    # Clean architecture pattern
    clean_signals = {"domain", "application", "infrastructure", "interfaces", "adapters",
                     "use_cases", "usecases", "entities", "repositories"}
    if len(clean_signals & all_dirs) >= 3:
        memories.append({
            "content": "Project follows Clean Architecture / hexagonal pattern",
            "tags": ["architecture", "pattern", "clean-architecture"],
            "importance": 0.8,
            "confidence": 0.8,
            "properties": {"source": "cold_start:architecture_detection"},
        })

    # Flat structure (everything in root or one level deep, few subdirs)
    top_level_dirs = {d.name for d in root.iterdir()
                      if d.is_dir() and not d.name.startswith(".")}
    src_like = {"src", "lib", "app", "core", "pkg"}
    if not (src_like & {d.lower() for d in top_level_dirs}):
        py_in_root = list(root.glob("*.py"))
        if len(py_in_root) > 5:
            memories.append({
                "content": "Project uses flat file structure (no src/ directory)",
                "tags": ["architecture", "pattern", "flat-structure"],
                "importance": 0.5,
                "confidence": 0.7,
                "properties": {"source": "cold_start:architecture_detection"},
            })

    return memories
```

---

## 6. NLP on Commit Messages

```python
"""Extract patterns from commit messages using spaCy NLP."""

from collections import Counter
from typing import Any

import spacy
from pydriller import Repository


# Verb-to-commit-type mapping (rule-based, no LLM needed)
VERB_TYPE_MAP: dict[str, str] = {
    "add": "feature",
    "implement": "feature",
    "create": "feature",
    "build": "feature",
    "introduce": "feature",
    "fix": "bugfix",
    "repair": "bugfix",
    "resolve": "bugfix",
    "patch": "bugfix",
    "correct": "bugfix",
    "refactor": "refactor",
    "restructure": "refactor",
    "reorganize": "refactor",
    "simplify": "refactor",
    "clean": "refactor",
    "update": "maintenance",
    "upgrade": "maintenance",
    "bump": "maintenance",
    "migrate": "maintenance",
    "remove": "maintenance",
    "delete": "maintenance",
    "deprecate": "maintenance",
    "document": "documentation",
    "describe": "documentation",
    "explain": "documentation",
    "test": "testing",
    "verify": "testing",
    "validate": "testing",
    "optimize": "performance",
    "improve": "performance",
    "speed": "performance",
    "cache": "performance",
}


def analyze_commit_messages(repo_path: str, max_commits: int = 500) -> list[dict[str, Any]]:
    """
    Analyze commit messages with spaCy NLP to extract work patterns.

    Uses en_core_web_sm for verb/noun extraction, technology NER,
    and rule-based commit type classification.

    Args:
        repo_path: Path to the Git repository.
        max_commits: Maximum number of recent commits to analyze.

    Returns:
        List of memory dicts ready for storage.
    """
    nlp = spacy.load("en_core_web_sm")
    memories: list[dict[str, Any]] = []

    verb_counter: Counter[str] = Counter()
    noun_counter: Counter[str] = Counter()
    tech_mentions: Counter[str] = Counter()
    commit_types: Counter[str] = Counter()

    commit_count = 0
    for commit in Repository(repo_path, order="reverse").traverse_commits():
        if commit_count >= max_commits:
            break
        commit_count += 1

        msg = commit.msg.split("\n")[0]  # First line only
        doc = nlp(msg)

        # Verb extraction
        for token in doc:
            if token.pos_ == "VERB":
                lemma = token.lemma_.lower()
                verb_counter[lemma] += 1

                # Rule-based commit type classification
                if lemma in VERB_TYPE_MAP:
                    commit_types[VERB_TYPE_MAP[lemma]] += 1

        # Noun extraction
        for token in doc:
            if token.pos_ == "NOUN" and len(token.text) > 2:
                noun_counter[token.lemma_.lower()] += 1

        # Named entity recognition for technology mentions
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PRODUCT", "GPE"):
                tech_mentions[ent.text] += 1

    if commit_count == 0:
        return memories

    # --- Convert to memories ---

    # Top verbs = what actions the developer takes
    top_verbs = verb_counter.most_common(10)
    if top_verbs:
        verb_list = [f"{v} ({c}x)" for v, c in top_verbs[:5]]
        memories.append({
            "content": f"Most common development actions: {', '.join(verb_list)}",
            "tags": ["pattern", "git", "work-style"],
            "importance": 0.5,
            "confidence": 0.8,
            "properties": {
                "source": "cold_start:commit_nlp",
                "top_verbs": dict(top_verbs),
                "commits_analyzed": commit_count,
            },
        })

    # Top nouns = what entities are worked on
    top_nouns = noun_counter.most_common(10)
    if top_nouns:
        noun_list = [f"{n} ({c}x)" for n, c in top_nouns[:5]]
        memories.append({
            "content": f"Most worked-on entities: {', '.join(noun_list)}",
            "tags": ["pattern", "git", "focus-areas"],
            "importance": 0.5,
            "confidence": 0.7,
            "properties": {
                "source": "cold_start:commit_nlp",
                "top_nouns": dict(top_nouns),
            },
        })

    # Commit type distribution = work style
    if commit_types:
        total_typed = sum(commit_types.values())
        type_dist = {t: round(c / total_typed, 2)
                     for t, c in commit_types.most_common()}
        primary_type = commit_types.most_common(1)[0][0]
        memories.append({
            "content": (
                f"Primary development activity: {primary_type} "
                f"({type_dist[primary_type]:.0%} of classified commits)"
            ),
            "tags": ["pattern", "git", "work-style", primary_type],
            "importance": 0.6,
            "confidence": 0.7,
            "properties": {
                "source": "cold_start:commit_nlp",
                "type_distribution": type_dist,
            },
        })

    # Technology mentions from NER
    if tech_mentions:
        tech_list = [name for name, _ in tech_mentions.most_common(10)]
        memories.append({
            "content": f"Technologies mentioned in commits: {', '.join(tech_list)}",
            "tags": ["pattern", "git", "technology"],
            "importance": 0.5,
            "confidence": 0.6,  # NER on short text is noisy
            "properties": {
                "source": "cold_start:commit_nlp",
                "tech_mentions": dict(tech_mentions.most_common(10)),
            },
        })

    return memories
```

> [!NOTE]
> spaCy's NER on short commit messages is noisy — confidence is set to 0.6 for technology mentions. The verb-based commit type classification is far more reliable (rule-based, no ambiguity).

---

## 7. Complete Orchestrator

```python
"""Cold start bootstrap orchestrator — ties all analysis together."""

from __future__ import annotations

import hashlib
import time
from typing import Any


async def cold_start_bootstrap(config: dict[str, Any]) -> dict[str, Any]:
    """
    Complete cold start bootstrap pipeline.

    Analyzes Git repos, config files, notes, and code patterns to
    create 50+ memories with zero API calls.

    Args:
        config: Configuration dict with keys:
            - repo_paths: list[str] — paths to Git repositories to analyze
            - vault_path: str | None — path to Obsidian vault (optional)
            - max_commits: int — max commits to analyze per repo (default: 500)
            - deduplicate: bool — whether to deduplicate results (default: True)

    Returns:
        Summary dict with total memories created, breakdown by source,
        and processing time.

    Example config:
        {
            "repo_paths": ["/home/user/projects/life-graph", "/home/user/projects/api"],
            "vault_path": "/home/user/obsidian-vault",
            "max_commits": 500,
            "deduplicate": True
        }
    """
    start_time = time.monotonic()
    all_memories: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    repo_paths = config.get("repo_paths", [])
    vault_path = config.get("vault_path")
    max_commits = config.get("max_commits", 500)

    # --- Phase 1: Git Repository Analysis ---
    for repo_path in repo_paths:
        # Git commit patterns
        try:
            git_result = analyze_git_repo(repo_path)
            if "error" not in git_result:
                git_memories = _git_result_to_memories(git_result)
                all_memories.extend(git_memories)
                source_counts["git_analysis"] = (
                    source_counts.get("git_analysis", 0) + len(git_memories)
                )
        except Exception as e:
            print(f"Warning: Git analysis failed for {repo_path}: {e}")

        # Dependency preferences
        try:
            dep_memories = extract_dependency_preferences(repo_path)
            all_memories.extend(dep_memories)
            source_counts["dependencies"] = (
                source_counts.get("dependencies", 0) + len(dep_memories)
            )
        except Exception as e:
            print(f"Warning: Dependency scan failed for {repo_path}: {e}")

        # Config file parsing
        try:
            config_memories = extract_config_preferences(repo_path)
            all_memories.extend(config_memories)
            source_counts["config_files"] = (
                source_counts.get("config_files", 0) + len(config_memories)
            )
        except Exception as e:
            print(f"Warning: Config parsing failed for {repo_path}: {e}")

        # Code pattern analysis
        try:
            code_memories = analyze_python_code(repo_path)
            all_memories.extend(code_memories)
            source_counts["code_patterns"] = (
                source_counts.get("code_patterns", 0) + len(code_memories)
            )
        except Exception as e:
            print(f"Warning: Code analysis failed for {repo_path}: {e}")

        # Architecture detection
        try:
            arch_memories = detect_architecture(repo_path)
            all_memories.extend(arch_memories)
            source_counts["architecture"] = (
                source_counts.get("architecture", 0) + len(arch_memories)
            )
        except Exception as e:
            print(f"Warning: Architecture detection failed for {repo_path}: {e}")

        # Commit message NLP
        try:
            nlp_memories = analyze_commit_messages(repo_path, max_commits)
            all_memories.extend(nlp_memories)
            source_counts["commit_nlp"] = (
                source_counts.get("commit_nlp", 0) + len(nlp_memories)
            )
        except Exception as e:
            print(f"Warning: Commit NLP failed for {repo_path}: {e}")

    # --- Phase 2: Note Import ---
    if vault_path:
        try:
            note_memories = extract_knowledge_from_notes(vault_path)
            all_memories.extend(note_memories)
            source_counts["notes"] = len(note_memories)
        except Exception as e:
            print(f"Warning: Note import failed for {vault_path}: {e}")

    # --- Phase 3: Deduplication ---
    pre_dedup_count = len(all_memories)
    if config.get("deduplicate", True):
        all_memories = _deduplicate_memories(all_memories)

    # --- Phase 4: Importance Adjustment ---
    all_memories = _adjust_importance(all_memories)

    elapsed = time.monotonic() - start_time

    return {
        "total_memories": len(all_memories),
        "pre_dedup_count": pre_dedup_count,
        "duplicates_removed": pre_dedup_count - len(all_memories),
        "by_source": source_counts,
        "elapsed_seconds": round(elapsed, 1),
        "memories": all_memories,
        "api_calls_made": 0,  # Always zero — fully local
    }


def _git_result_to_memories(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert analyze_git_repo results into memory dicts."""
    memories: list[dict[str, Any]] = []

    # Commit convention
    memories.append({
        "content": (
            f"Uses {result['commit_convention']} commit style "
            f"({result['conventional_ratio']:.0%} conventional commits)"
        ),
        "tags": ["preference", "git", "commit-style"],
        "importance": 0.6,
        "confidence": 0.9,
        "properties": {
            "source": "cold_start:git_analysis",
            "repo": result["repo_path"],
        },
    })

    # Peak hours
    if result["peak_hours"]:
        hours_str = ", ".join(f"{h}:00" for h in result["peak_hours"])
        memories.append({
            "content": f"Peak coding hours: {hours_str}",
            "tags": ["pattern", "time", "work-schedule"],
            "importance": 0.5,
            "confidence": 0.8,
            "properties": {
                "source": "cold_start:git_analysis",
                "peak_hours": result["peak_hours"],
            },
        })

    # Active days
    if result["active_days"]:
        memories.append({
            "content": f"Most active coding days: {', '.join(result['active_days'])}",
            "tags": ["pattern", "time", "work-schedule"],
            "importance": 0.5,
            "confidence": 0.8,
            "properties": {
                "source": "cold_start:git_analysis",
                "active_days": result["active_days"],
            },
        })

    # Primary languages
    if result["language_frequency"]:
        top_langs = list(result["language_frequency"].keys())[:5]
        memories.append({
            "content": f"Primary languages (by file changes): {', '.join(top_langs)}",
            "tags": ["preference", "language"] + top_langs[:3],
            "importance": 0.7,
            "confidence": 0.9,
            "properties": {
                "source": "cold_start:git_analysis",
                "language_frequency": result["language_frequency"],
            },
        })

    # Commit size
    memories.append({
        "content": f"Average commit size: {result['avg_commit_size']} lines changed",
        "tags": ["pattern", "git", "commit-size"],
        "importance": 0.4,
        "confidence": 0.9,
        "properties": {"source": "cold_start:git_analysis"},
    })

    return memories


def _deduplicate_memories(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove near-duplicate memories based on content hashing.

    When duplicates are found, keeps the one with highest importance.
    """
    seen: dict[str, dict[str, Any]] = {}

    for memory in memories:
        # Create a normalized key from content
        content_key = hashlib.md5(
            memory["content"].lower().strip().encode()
        ).hexdigest()

        if content_key not in seen:
            seen[content_key] = memory
        else:
            # Keep the one with higher importance
            if memory.get("importance", 0) > seen[content_key].get("importance", 0):
                seen[content_key] = memory

    return list(seen.values())


def _adjust_importance(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Adjust importance scores based on frequency patterns.

    Memories that appear across multiple sources get a boost.
    """
    # Count tag frequency across all memories
    tag_freq: Counter[str] = Counter()
    for memory in memories:
        for tag in memory.get("tags", []):
            tag_freq[tag] += 1

    # Boost importance for memories with frequently-occurring tags
    for memory in memories:
        tag_boost = 0.0
        for tag in memory.get("tags", []):
            if tag_freq[tag] > 3:  # Tag appears in 3+ memories
                tag_boost = max(tag_boost, 0.05)
            if tag_freq[tag] > 5:
                tag_boost = max(tag_boost, 0.1)

        memory["importance"] = min(
            memory.get("importance", 0.5) + tag_boost,
            0.95  # Cap at 0.95
        )

    return memories
```

### Example Usage

```python
import asyncio

config = {
    "repo_paths": [
        "/home/user/projects/life-graph",
        "/home/user/projects/deployment-platform",
    ],
    "vault_path": "/home/user/obsidian-vault",
    "max_commits": 500,
    "deduplicate": True,
}

result = asyncio.run(cold_start_bootstrap(config))

print(f"Created {result['total_memories']} memories in {result['elapsed_seconds']}s")
print(f"Duplicates removed: {result['duplicates_removed']}")
print(f"API calls made: {result['api_calls_made']}")
print(f"Breakdown: {result['by_source']}")
```

Expected output:
```
Created 67 memories in 8.3s
Duplicates removed: 12
API calls made: 0
Breakdown: {'git_analysis': 10, 'dependencies': 8, 'config_files': 7,
            'code_patterns': 12, 'architecture': 5, 'commit_nlp': 6, 'notes': 19}
```

---

## 8. Dependencies

| Package | Version | Required | Purpose |
|---------|---------|----------|---------|
| `pydriller` | >=2.0 | ✅ Yes | Git repository mining |
| `pyyaml` | >=6.0 | ✅ Yes | YAML parsing (CI/CD, Obsidian frontmatter) |
| `tomli` | >=2.0 | ✅ Yes (Python <3.11) | TOML parsing (pyproject.toml) |
| `spacy` | >=3.5 | ✅ Yes | NLP on commit messages |
| `en_core_web_sm` | — | ✅ Yes | spaCy language model |
| `radon` | >=5.0 | ⬜ Optional | Code complexity metrics |
| `obsidiantools` | >=0.10 | ⬜ Optional | Enhanced Obsidian vault parsing |

### Installation

```bash
pip install pydriller pyyaml spacy
python -m spacy download en_core_web_sm

# Optional
pip install radon obsidiantools

# Python <3.11 only
pip install tomli
```

> [!TIP]
> The `en_core_web_sm` model is ~12MB. For better NER accuracy on technology names, consider `en_core_web_md` (~40MB) or `en_core_web_lg` (~560MB), but the small model is sufficient for cold start.

---

## 9. Anti-Patterns

> [!CAUTION]
> These are common mistakes that will make the cold start system produce low-quality memories. Avoid them.

### ❌ DON'T: Send Commits to LLM for Summarization

**Why it's wrong:** Commits are short, structured text. spaCy + regex handles them perfectly. LLM calls cost money, add latency, and don't improve quality for this use case.

**Do instead:** Use the rule-based `VERB_TYPE_MAP` and spaCy NER shown above.

### ❌ DON'T: Import Every Note

**Why it's wrong:** Most notes are bookmarks, meeting notes, or copy-pasted content. Importing everything creates noise that drowns out real knowledge. This is the **Collector's Fallacy** — hoarding ≠ knowing.

**Do instead:** Filter for decision signals (`decided`, `chose`, `prefer`) and lesson signals (`learned`, `mistake`, `gotcha`) only.

### ❌ DON'T: Parse Vendored Code

**Why it's wrong:** `node_modules/`, `.venv/`, `vendor/` contain thousands of files you didn't write. Analyzing them will produce preferences and patterns that aren't yours.

**Do instead:** Always check against `VENDORED_DIRS` before processing any file.

### ❌ DON'T: Store Raw Code Snippets as Memories

**Why it's wrong:** Code changes frequently. A stored snippet becomes stale immediately. The memory system should store **patterns and preferences**, not implementation details.

**Do instead:** Extract "Uses snake_case naming" not `def my_function_name():`. Extract "Prefers FastAPI" not the actual router code.

### ❌ DON'T: Treat All Memories Equally

**Why it's wrong:** A single-use import is not as important as a consistently-used framework. Without importance weighting, the proactive recall engine has no signal for what matters.

**Do instead:** Weight by frequency (how often a pattern appears) and recency (recent patterns matter more). The `_adjust_importance()` function handles this.
