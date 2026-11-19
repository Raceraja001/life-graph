"""Every third-party package the app imports lazily is declared in pyproject.toml.

Lazy imports (inside a function, behind an ImportError guard) are invisible
to an import-time smoke test: the app starts fine without them and the
feature just quietly turns itself off. Several such packages were used but
never declared, so no install, extra or lock ever carried them (audit M21).
Conversely, two packages were declared that nothing imported.

This pins both directions for the packages the audit found, and reads the
source so a moved import does not leave a stale entry here.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: (source file, import statement it contains, distribution that provides it)
LAZY_IMPORTS = [
    ("life_graph/watchers/channels/email_channel.py", "import aiosmtplib", "aiosmtplib"),
    ("life_graph/extraction/parsers.py", "from docx import Document", "python-docx"),
    ("life_graph/watchers/server_health_watcher.py", "import asyncssh", "asyncssh"),
    ("life_graph/services/llm/client.py", "from openai import", "openai"),
    ("life_graph/watchers/code_quality_watcher.py", "import git", "gitpython"),
]

#: Declared once but imported nowhere. Kept out so they do not ride along
#: into every install (and every vulnerability report) for nothing.
UNUSED = ["orjson", "testcontainers"]

SEARCHED_DIRS = ["life_graph", "plugins", "tests", "scripts", "alembic"]


def _name(requirement: str) -> str:
    """The normalised distribution name of a PEP 508 requirement string."""
    name = re.split(r"[\s\[<>=!~;]", requirement.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared() -> dict[str, set[str]]:
    """Distribution name -> the groups ("core" or an extra) that declare it."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    groups: dict[str, set[str]] = {}
    for req in project["dependencies"]:
        groups.setdefault(_name(req), set()).add("core")
    for extra, reqs in project["optional-dependencies"].items():
        for req in reqs:
            groups.setdefault(_name(req), set()).add(extra)
    return groups


@pytest.mark.parametrize(("path", "statement", "dist"), LAZY_IMPORTS)
def test_lazily_imported_package_is_declared(path: str, statement: str, dist: str) -> None:
    source = (ROOT / path).read_text(encoding="utf-8")
    assert statement in source, f"{path} no longer contains {statement!r}; update this test"
    assert dist in _declared(), f"{path} imports {dist} but pyproject.toml never declares it"


@pytest.mark.parametrize("dist", UNUSED)
def test_unused_package_is_not_declared(dist: str) -> None:
    importers = [
        str(p.relative_to(ROOT))
        for d in SEARCHED_DIRS
        for p in (ROOT / d).rglob("*.py")
        if re.search(rf"^\s*(import|from)\s+{dist}\b", p.read_text(encoding="utf-8"), re.M)
    ]
    if importers:
        pytest.skip(f"{dist} is imported again by {importers}; declaring it is fine")
    assert dist not in _declared(), f"{dist} is declared but nothing imports it"


def test_no_duplicate_declaration_of_a_core_dependency_in_dev() -> None:
    dupes = sorted(n for n, groups in _declared().items() if {"core", "dev"} <= groups)
    assert not dupes, f"already core dependencies, drop them from the dev extra: {dupes}"
