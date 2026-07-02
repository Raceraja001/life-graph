"""Python AST code analysis for cold start bootstrap.

Uses the stdlib ``ast`` module (zero external dependencies) to extract
coding style patterns: naming conventions, docstring rates, type hint
usage, error handling style, test framework detection, async patterns,
Pydantic/dataclass usage, top imports, and top decorators.

Also detects project architecture from directory structure.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories to skip during analysis
VENDORED_DIRS = {
    "node_modules", ".venv", "venv", "vendor", "__pycache__",
    ".git", ".tox", "dist", "build", "egg-info", ".eggs",
    "site-packages", ".mypy_cache", ".pytest_cache", "migrations",
}


class _PatternVisitor(ast.NodeVisitor):
    """AST visitor that collects coding style metrics from Python files."""

    def __init__(self) -> None:
        self.function_count: int = 0
        self.functions_with_docstrings: int = 0
        self.functions_with_type_hints: int = 0
        self.async_function_count: int = 0
        self.class_count: int = 0

        self.snake_case_names: int = 0
        self.camel_case_names: int = 0

        self.bare_excepts: int = 0
        self.specific_excepts: int = 0

        self.imports: Counter[str] = Counter()
        self.decorators: Counter[str] = Counter()

        self.uses_pytest: bool = False
        self.uses_unittest: bool = False
        self.uses_pydantic: bool = False
        self.uses_dataclass: bool = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def _analyze_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
    ) -> None:
        """Analyze a single function/method definition."""
        self.function_count += 1
        if is_async:
            self.async_function_count += 1

        # Naming convention
        name = node.name
        if not name.startswith("_"):
            if re.match(r"^[a-z][a-z0-9_]*$", name):
                self.snake_case_names += 1
            elif re.match(r"^[a-z][a-zA-Z0-9]*$", name):
                self.camel_case_names += 1

        # Docstring detection
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.functions_with_docstrings += 1

        # Type hint detection
        has_hints = node.returns is not None
        if not has_hints:
            for arg in node.args.args:
                if arg.annotation is not None:
                    has_hints = True
                    break
        if has_hints:
            self.functions_with_type_hints += 1

        # Test framework / decorators
        if name.startswith("test_"):
            self.uses_pytest = True
        for dec in node.decorator_list:
            dec_name = self._get_decorator_name(dec)
            if dec_name:
                self.decorators[dec_name] += 1
                if dec_name == "pytest.fixture":
                    self.uses_pytest = True

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_count += 1
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name and "TestCase" in base_name:
                self.uses_unittest = True
            if base_name and "BaseModel" in base_name:
                self.uses_pydantic = True
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
            self.imports[alias.name.split(".")[0]] += 1

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports[node.module.split(".")[0]] += 1

    def _get_name(self, node: ast.expr) -> str | None:
        """Recursively extract a dotted name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

    def _get_decorator_name(self, node: ast.expr) -> str | None:
        """Extract a decorator name, handling both @deco and @deco()."""
        if isinstance(node, ast.Call):
            return self._get_name(node.func)
        return self._get_name(node)


class CodeAnalyzer:
    """Analyze Python source code to extract coding patterns.

    Uses the stdlib ``ast`` module for zero-dependency parsing.
    Also detects project architecture from directory structure.
    """

    def analyze(self, repo_path: str) -> list[dict[str, Any]]:
        """Analyze a repository and return memory dicts.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of memory dicts ready for storage.
        """
        root = Path(repo_path).resolve()
        logger.info("Analyzing Python code in: %s", root)

        visitor = self._visit_python_files(root)
        memories = self._visitor_to_memories(visitor)
        memories.extend(self._detect_architecture(root))

        logger.info(
            "Code analysis produced %d memories from %s",
            len(memories), repo_path,
        )
        return memories

    # ── AST Analysis ──────────────────────────────────────────

    def _visit_python_files(self, root: Path) -> _PatternVisitor:
        """Walk all .py files and collect patterns via AST visitor."""
        visitor = _PatternVisitor()
        parsed = 0

        for py_file in root.rglob("*.py"):
            if any(p in VENDORED_DIRS for p in py_file.parts):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                visitor.visit(tree)
                parsed += 1
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue

        logger.debug("Parsed %d Python files", parsed)
        return visitor

    def _visitor_to_memories(
        self, v: _PatternVisitor
    ) -> list[dict[str, Any]]:
        """Convert visitor statistics into memory dicts."""
        memories: list[dict[str, Any]] = []

        if v.function_count == 0:
            return memories

        # Naming convention
        total_names = v.snake_case_names + v.camel_case_names
        if total_names > 0:
            snake_ratio = v.snake_case_names / total_names
            convention = (
                "snake_case" if snake_ratio > 0.8
                else "camelCase" if snake_ratio < 0.2
                else "mixed"
            )
            memories.append({
                "content": (
                    f"Uses {convention} naming convention "
                    f"({v.snake_case_names} snake_case, "
                    f"{v.camel_case_names} camelCase)"
                ),
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "naming-convention"],
            })

        # Docstring rate
        doc_rate = v.functions_with_docstrings / v.function_count
        memories.append({
            "content": (
                f"Docstring rate: {doc_rate:.0%} of functions have docstrings "
                f"({v.functions_with_docstrings}/{v.function_count})"
            ),
            "type_tag": "pattern",
            "importance": 0.6,
            "source": "cold_start:code_analysis",
            "tags": ["preference", "python", "documentation"],
        })

        # Type hint rate
        hint_rate = v.functions_with_type_hints / v.function_count
        memories.append({
            "content": (
                f"Type hint rate: {hint_rate:.0%} of functions have type "
                f"annotations ({v.functions_with_type_hints}/{v.function_count})"
            ),
            "type_tag": "pattern",
            "importance": 0.7,
            "source": "cold_start:code_analysis",
            "tags": ["preference", "python", "typing"],
        })

        # Error handling style
        total_excepts = v.bare_excepts + v.specific_excepts
        if total_excepts > 0:
            style = (
                "specific exceptions" if v.bare_excepts == 0
                else "bare excepts" if v.specific_excepts == 0
                else f"mixed ({v.bare_excepts} bare, {v.specific_excepts} specific)"
            )
            memories.append({
                "content": f"Error handling style: {style}",
                "type_tag": "preference",
                "importance": 0.6,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "error-handling"],
            })

        # Test framework
        if v.uses_pytest:
            memories.append({
                "content": "Uses pytest as the testing framework",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "testing", "pytest"],
            })
        elif v.uses_unittest:
            memories.append({
                "content": "Uses unittest as the testing framework",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "testing", "unittest"],
            })

        # Async usage
        if v.async_function_count > 0:
            async_ratio = v.async_function_count / v.function_count
            memories.append({
                "content": (
                    f"Uses async/await pattern ({async_ratio:.0%} of functions "
                    f"are async, {v.async_function_count} total)"
                ),
                "type_tag": "pattern",
                "importance": 0.6,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "async"],
            })

        # Pydantic / dataclass
        if v.uses_pydantic:
            memories.append({
                "content": "Uses Pydantic BaseModel for data validation",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "pydantic"],
            })
        if v.uses_dataclass:
            memories.append({
                "content": "Uses Python dataclasses for data structures",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "dataclass"],
            })

        # Top 15 imports
        top_imports = v.imports.most_common(15)
        if top_imports:
            names = [n for n, _ in top_imports[:15]]
            memories.append({
                "content": f"Most-used Python imports: {', '.join(names[:10])}",
                "type_tag": "pattern",
                "importance": 0.5,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "imports"],
            })

        # Top decorators
        top_decorators = v.decorators.most_common(10)
        if top_decorators:
            dec_names = [n for n, _ in top_decorators[:5]]
            memories.append({
                "content": f"Most-used decorators: {', '.join(dec_names)}",
                "type_tag": "pattern",
                "importance": 0.5,
                "source": "cold_start:code_analysis",
                "tags": ["preference", "python", "decorators"],
            })

        return memories

    # ── Architecture Detection ────────────────────────────────

    def _detect_architecture(self, root: Path) -> list[dict[str, Any]]:
        """Detect project architecture from directory structure."""
        memories: list[dict[str, Any]] = []

        # Monorepo detection
        has_packages = (root / "packages").is_dir()
        has_apps = (root / "apps").is_dir()
        if has_packages or has_apps:
            memories.append({
                "content": "Uses monorepo structure",
                "type_tag": "architecture",
                "importance": 0.8,
                "source": "cold_start:code_analysis",
                "tags": ["architecture", "monorepo", "project-structure"],
            })

        # Docker presence
        has_docker = any(root.glob("Dockerfile*"))
        has_compose = any(root.glob("docker-compose*"))
        if has_docker or has_compose:
            detail = " with docker-compose" if has_compose else ""
            memories.append({
                "content": f"Uses Docker for containerization{detail}",
                "type_tag": "architecture",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["architecture", "docker", "infrastructure"],
            })

        # CI/CD presence
        ci_systems: list[str] = []
        if (root / ".github" / "workflows").is_dir():
            ci_systems.append("GitHub Actions")
        if (root / ".gitlab-ci.yml").exists():
            ci_systems.append("GitLab CI")
        if (root / "Jenkinsfile").exists():
            ci_systems.append("Jenkins")
        if (root / ".circleci").is_dir():
            ci_systems.append("CircleCI")
        if ci_systems:
            memories.append({
                "content": f"Uses {', '.join(ci_systems)} for CI/CD",
                "type_tag": "architecture",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["architecture", "ci", "infrastructure"],
            })

        # Frontend framework detection
        memories.extend(self._detect_frontend(root))

        # Backend framework detection
        memories.extend(self._detect_backend(root))

        # Structure pattern detection
        memories.extend(self._detect_structure_pattern(root))

        return memories

    def _detect_frontend(self, root: Path) -> list[dict[str, Any]]:
        """Detect frontend framework from package.json."""
        pkg_file = root / "package.json"
        if not pkg_file.exists():
            return []

        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            all_deps = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
            }
        except Exception:
            return []

        frameworks = [
            ("next", "Next.js"),
            ("nuxt", "Nuxt.js"),
            ("@angular/core", "Angular"),
            ("vue", "Vue.js"),
            ("react", "React"),
            ("vite", "Vite"),
        ]

        for key, name in frameworks:
            if key in all_deps:
                return [{
                    "content": f"Uses {name} as frontend framework",
                    "type_tag": "architecture",
                    "importance": 0.8,
                    "source": "cold_start:code_analysis",
                    "tags": ["architecture", "frontend", name.lower()],
                }]

        return []

    def _detect_backend(self, root: Path) -> list[dict[str, Any]]:
        """Detect backend framework from Python imports/requirements."""
        # Check pyproject.toml and requirements
        texts: list[str] = []
        for candidate in ["pyproject.toml", "requirements.txt", "setup.py"]:
            path = root / candidate
            if path.exists():
                try:
                    texts.append(path.read_text(encoding="utf-8").lower())
                except Exception:
                    pass

        combined = " ".join(texts)

        frameworks = [
            ("fastapi", "FastAPI"),
            ("django", "Django"),
            ("flask", "Flask"),
        ]

        for key, name in frameworks:
            if key in combined:
                return [{
                    "content": f"Uses {name} as backend framework",
                    "type_tag": "architecture",
                    "importance": 0.8,
                    "source": "cold_start:code_analysis",
                    "tags": ["architecture", "backend", key, "python"],
                }]

        return []

    def _detect_structure_pattern(self, root: Path) -> list[dict[str, Any]]:
        """Detect MVC / clean architecture / flat patterns."""
        all_dirs = set()
        for d in root.rglob("*"):
            if d.is_dir() and not any(v in d.parts for v in VENDORED_DIRS):
                all_dirs.add(d.name.lower())

        # MVC pattern
        mvc_signals = {"models", "views", "controllers", "templates"}
        if len(mvc_signals & all_dirs) >= 3:
            return [{
                "content": "Project follows MVC architecture pattern",
                "type_tag": "architecture",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["architecture", "pattern", "mvc"],
            }]

        # Clean architecture
        clean_signals = {
            "domain", "application", "infrastructure", "interfaces",
            "adapters", "use_cases", "usecases", "entities", "repositories",
        }
        if len(clean_signals & all_dirs) >= 3:
            return [{
                "content": "Project follows Clean Architecture pattern",
                "type_tag": "architecture",
                "importance": 0.8,
                "source": "cold_start:code_analysis",
                "tags": ["architecture", "pattern", "clean-architecture"],
            }]

        # FastAPI standard (routers, models, schemas, services)
        fastapi_signals = {"routers", "models", "schemas", "services"}
        if len(fastapi_signals & all_dirs) >= 3:
            return [{
                "content": "Project follows FastAPI standard structure",
                "type_tag": "architecture",
                "importance": 0.7,
                "source": "cold_start:code_analysis",
                "tags": ["architecture", "pattern", "fastapi-standard"],
            }]

        # Flat structure
        top_dirs = {d.name.lower() for d in root.iterdir()
                    if d.is_dir() and not d.name.startswith(".")}
        src_like = {"src", "lib", "app", "core", "pkg"}
        if not (src_like & top_dirs):
            py_in_root = list(root.glob("*.py"))
            if len(py_in_root) > 5:
                return [{
                    "content": "Project uses flat file structure (no src/ directory)",
                    "type_tag": "architecture",
                    "importance": 0.5,
                    "source": "cold_start:code_analysis",
                    "tags": ["architecture", "pattern", "flat-structure"],
                }]

        return []
