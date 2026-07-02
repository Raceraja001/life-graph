"""Configuration file parsing for cold start bootstrap.

Extracts developer preferences from project configuration files:
pyproject.toml, tsconfig.json, .editorconfig, Dockerfile, and
package.json. All processing is local — zero API calls.
"""

from __future__ import annotations

import json
import logging
import re
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories to skip
VENDORED_DIRS = {
    "node_modules", ".venv", "venv", "vendor", "__pycache__",
    ".git", ".tox", "dist", "build", "egg-info", ".eggs",
    "site-packages", ".mypy_cache", ".pytest_cache", "migrations",
}


class ConfigParser:
    """Parse project configuration files to extract coding preferences.

    Scans pyproject.toml, tsconfig.json, .editorconfig, Dockerfile,
    and package.json. Returns memory dicts for the Life Graph system.
    """

    def parse(self, repo_path: str) -> list[dict[str, Any]]:
        """Parse all config files in a repository root.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of memory dicts ready for storage.
        """
        root = Path(repo_path).resolve()
        memories: list[dict[str, Any]] = []

        memories.extend(self._parse_pyproject(root))
        memories.extend(self._parse_tsconfig(root))
        memories.extend(self._parse_editorconfig(root))
        memories.extend(self._parse_dockerfiles(root))
        memories.extend(self._parse_package_json(root))

        logger.info(
            "Config parsing produced %d memories from %s",
            len(memories), repo_path,
        )
        return memories

    # ── pyproject.toml ────────────────────────────────────────

    def _parse_pyproject(self, root: Path) -> list[dict[str, Any]]:
        """Extract preferences from pyproject.toml."""
        memories: list[dict[str, Any]] = []
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return memories

        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Failed to parse pyproject.toml")
            return memories

        tool = data.get("tool", {})

        # Ruff configuration
        ruff = tool.get("ruff", {})
        if ruff:
            memories.extend(self._extract_ruff(ruff))

        # Black configuration
        black = tool.get("black", {})
        if black:
            line_length = black.get("line-length", "default")
            memories.append({
                "content": f"Uses Black formatter (line-length={line_length})",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:config_parse",
                "tags": ["preference", "python", "formatting", "black"],
            })

        # Pytest configuration
        pytest_cfg = tool.get("pytest", {}).get("ini_options", {})
        if pytest_cfg:
            parts = []
            if "addopts" in pytest_cfg:
                parts.append(f"addopts={pytest_cfg['addopts']}")
            if "testpaths" in pytest_cfg:
                parts.append(f"testpaths={pytest_cfg['testpaths']}")
            detail = ": " + ", ".join(parts) if parts else ""
            memories.append({
                "content": f"Pytest configuration{detail}",
                "type_tag": "preference",
                "importance": 0.6,
                "source": "cold_start:config_parse",
                "tags": ["preference", "python", "testing", "pytest"],
            })

        # Mypy configuration
        mypy = tool.get("mypy", {})
        if mypy:
            strict = mypy.get("strict", False)
            memories.append({
                "content": f"Uses mypy for type checking (strict={strict})",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:config_parse",
                "tags": ["preference", "python", "typing", "mypy"],
            })

        return memories

    def _extract_ruff(self, ruff: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract Ruff linter settings."""
        memories: list[dict[str, Any]] = []

        line_length = ruff.get("line-length")
        if line_length:
            memories.append({
                "content": f"Uses ruff linter with line-length={line_length}",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:config_parse",
                "tags": ["preference", "python", "linting", "ruff"],
            })

        select_rules = ruff.get("select") or ruff.get("lint", {}).get("select")
        if select_rules:
            memories.append({
                "content": f"Ruff lint rules selected: {', '.join(select_rules[:10])}",
                "type_tag": "preference",
                "importance": 0.6,
                "source": "cold_start:config_parse",
                "tags": ["preference", "python", "linting", "ruff"],
            })

        return memories

    # ── tsconfig.json ─────────────────────────────────────────

    def _parse_tsconfig(self, root: Path) -> list[dict[str, Any]]:
        """Extract preferences from tsconfig.json (handles comments)."""
        memories: list[dict[str, Any]] = []
        tsconfig = root / "tsconfig.json"
        if not tsconfig.exists():
            return memories

        try:
            raw = tsconfig.read_text(encoding="utf-8")
            # Strip single-line comments (common in tsconfig)
            raw = re.sub(r"//.*$", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
            data = json.loads(raw)
        except Exception:
            logger.debug("Failed to parse tsconfig.json")
            return memories

        compiler = data.get("compilerOptions", {})
        parts: list[str] = []
        if compiler.get("strict"):
            parts.append("strict mode enabled")
        if compiler.get("target"):
            parts.append(f"target={compiler['target']}")
        if compiler.get("module"):
            parts.append(f"module={compiler['module']}")
        if compiler.get("jsx"):
            parts.append(f"jsx={compiler['jsx']}")

        if parts:
            memories.append({
                "content": f"TypeScript config: {', '.join(parts)}",
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:config_parse",
                "tags": ["preference", "typescript", "config"],
            })

        return memories

    # ── .editorconfig ─────────────────────────────────────────

    def _parse_editorconfig(self, root: Path) -> list[dict[str, Any]]:
        """Extract preferences from .editorconfig."""
        memories: list[dict[str, Any]] = []
        editorconfig = root / ".editorconfig"
        if not editorconfig.exists():
            return memories

        try:
            text = editorconfig.read_text(encoding="utf-8")
        except Exception:
            return memories

        parts: list[str] = []
        indent_style = re.search(r"indent_style\s*=\s*(\w+)", text)
        indent_size = re.search(r"indent_size\s*=\s*(\w+)", text)
        if indent_style:
            parts.append(f"indent_style={indent_style.group(1)}")
        if indent_size:
            parts.append(f"indent_size={indent_size.group(1)}")

        if parts:
            memories.append({
                "content": f"Editor config preferences: {', '.join(parts)}",
                "type_tag": "preference",
                "importance": 0.6,
                "source": "cold_start:config_parse",
                "tags": ["preference", "editor", "formatting"],
            })

        return memories

    # ── Dockerfile ────────────────────────────────────────────

    def _parse_dockerfiles(self, root: Path) -> list[dict[str, Any]]:
        """Extract preferences from Dockerfiles."""
        memories: list[dict[str, Any]] = []

        for dockerfile in root.rglob("Dockerfile*"):
            if any(p in VENDORED_DIRS for p in dockerfile.parts):
                continue
            try:
                text = dockerfile.read_text(encoding="utf-8")
            except Exception:
                continue

            from_lines = re.findall(r"^FROM\s+(\S+)", text, re.MULTILINE)
            if not from_lines:
                continue

            is_multistage = len(from_lines) > 1
            uses_alpine = any("alpine" in img.lower() for img in from_lines)
            uses_slim = any("slim" in img.lower() for img in from_lines)

            details: list[str] = []
            if is_multistage:
                details.append("multi-stage build")
            if uses_alpine:
                details.append("alpine-based")
            if uses_slim:
                details.append("slim-based")

            content = f"Docker base image(s): {', '.join(from_lines)}"
            if details:
                content += f" ({', '.join(details)})"

            memories.append({
                "content": content,
                "type_tag": "preference",
                "importance": 0.7,
                "source": "cold_start:config_parse",
                "tags": ["preference", "docker", "infrastructure"],
            })
            break  # Only first Dockerfile to avoid noise

        return memories

    # ── package.json ──────────────────────────────────────────

    def _parse_package_json(self, root: Path) -> list[dict[str, Any]]:
        """Extract top dependencies from package.json."""
        memories: list[dict[str, Any]] = []
        pkg_file = root / "package.json"
        if not pkg_file.exists():
            return memories

        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
        except Exception:
            return memories

        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())

        if deps:
            top = deps[:10]
            memories.append({
                "content": f"Node.js dependencies: {', '.join(top)}",
                "type_tag": "preference",
                "importance": 0.6,
                "source": "cold_start:config_parse",
                "tags": ["preference", "javascript", "dependencies"],
            })

        if dev_deps:
            top = dev_deps[:10]
            memories.append({
                "content": f"Node.js dev dependencies: {', '.join(top)}",
                "type_tag": "preference",
                "importance": 0.5,
                "source": "cold_start:config_parse",
                "tags": ["preference", "javascript", "devDependencies"],
            })

        return memories
