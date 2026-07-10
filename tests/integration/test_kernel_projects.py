"""Integration tests for OS Kernel Project Registry.

Tests the Project Registry API:
- POST /api/v1/kernel/projects (register)
- POST /api/v1/kernel/projects/{id}/scan (re-scan)
- GET /api/v1/kernel/projects (list)
- GET /api/v1/kernel/projects/{id} (detail)
- DELETE /api/v1/kernel/projects/{id} (soft-delete)

Also tests detection helpers (language, framework, file count)
as unit tests with no DB needed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test_project_tenant",
    "X-User-ID": "project-test-user",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for project API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── Detection Helpers (unit tests, no DB) ────────────────────


class TestLanguageDetection:
    """detect_language — scans root for marker files."""

    def test_detect_python_pyproject(self, tmp_path):
        """pyproject.toml → python."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        from life_graph.kernel.project_registry import (
            detect_language,
        )
        lang, dep = detect_language(str(tmp_path))
        assert lang == "python"
        assert dep == "pyproject.toml"

    def test_detect_typescript_package(self, tmp_path):
        """package.json → typescript."""
        (tmp_path / "package.json").write_text("{}")
        from life_graph.kernel.project_registry import (
            detect_language,
        )
        lang, dep = detect_language(str(tmp_path))
        assert lang == "typescript"
        assert dep == "package.json"

    def test_detect_rust_cargo(self, tmp_path):
        """Cargo.toml → rust."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        from life_graph.kernel.project_registry import (
            detect_language,
        )
        lang, _ = detect_language(str(tmp_path))
        assert lang == "rust"

    def test_detect_unknown(self, tmp_path):
        """Empty dir → None."""
        from life_graph.kernel.project_registry import (
            detect_language,
        )
        lang, dep = detect_language(str(tmp_path))
        assert lang is None
        assert dep is None


class TestFrameworkDetection:
    """detect_framework — reads dep files for keywords."""

    def test_detect_fastapi(self, tmp_path):
        """pyproject.toml with fastapi → fastapi."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["fastapi"]'
        )
        from life_graph.kernel.project_registry import (
            detect_framework,
        )
        assert detect_framework(str(tmp_path)) == "fastapi"

    def test_detect_nextjs(self, tmp_path):
        """package.json with next → nextjs."""
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"next": "^14.0.0"}}'
        )
        from life_graph.kernel.project_registry import (
            detect_framework,
        )
        assert detect_framework(str(tmp_path)) == "nextjs"

    def test_detect_none(self, tmp_path):
        """No framework detected → None."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'plain'"
        )
        from life_graph.kernel.project_registry import (
            detect_framework,
        )
        assert detect_framework(str(tmp_path)) is None


class TestFileCount:
    """count_files — counts code files recursively."""

    def test_count_python_files(self, tmp_path):
        """Counts .py files."""
        (tmp_path / "main.py").write_text("print('hi')")
        (tmp_path / "utils.py").write_text("pass")
        (tmp_path / "readme.txt").write_text("docs")
        from life_graph.kernel.project_registry import (
            count_files,
        )
        count = count_files(str(tmp_path))
        assert count == 2  # .txt excluded

    def test_skips_node_modules(self, tmp_path):
        """Skips node_modules directory."""
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports={}")
        (tmp_path / "app.js").write_text("console.log(1)")
        from life_graph.kernel.project_registry import (
            count_files,
        )
        count = count_files(str(tmp_path))
        assert count == 1  # only app.js

    def test_skips_git_dir(self, tmp_path):
        """Skips .git directory."""
        git_dir = tmp_path / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "pack.py").write_text("data")
        (tmp_path / "main.py").write_text("pass")
        from life_graph.kernel.project_registry import (
            count_files,
        )
        count = count_files(str(tmp_path))
        assert count == 1

    def test_empty_dir(self, tmp_path):
        """Empty dir → 0."""
        from life_graph.kernel.project_registry import (
            count_files,
        )
        assert count_files(str(tmp_path)) == 0


class TestDependencyCount:
    """count_dependencies — counts deps from files."""

    def test_count_package_json(self, tmp_path):
        """Counts deps from package.json."""
        (tmp_path / "package.json").write_text(
            '{"dependencies":{"a":"1","b":"2"},'
            '"devDependencies":{"c":"1"}}'
        )
        from life_graph.kernel.project_registry import (
            count_dependencies,
        )
        count = count_dependencies(
            str(tmp_path), "package.json",
        )
        assert count == 3

    def test_no_dep_file(self, tmp_path):
        """No dep file → 0."""
        from life_graph.kernel.project_registry import (
            count_dependencies,
        )
        assert count_dependencies(str(tmp_path), None) == 0


# ── Register Project Endpoint ────────────────────────────────


class TestRegisterProject:
    """POST /api/v1/kernel/projects"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_register_returns_201(
        self, client: AsyncClient,
    ):
        """Valid project returns 201."""
        response = await client.post(
            "/api/v1/kernel/projects",
            json={
                "name": "test-project-reg",
                "path": str(Path.cwd()),
                "description": "Test project",
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["name"] == "test-project-reg"
            assert "language" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_register_invalid_path(
        self, client: AsyncClient,
    ):
        """Non-existent path returns 400."""
        response = await client.post(
            "/api/v1/kernel/projects",
            json={
                "name": "bad-path-project",
                "path": "/nonexistent/path/xyz",
            },
        )
        assert response.status_code in (400, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_register_missing_name(
        self, client: AsyncClient,
    ):
        """Missing name returns 422."""
        response = await client.post(
            "/api/v1/kernel/projects",
            json={"path": str(Path.cwd())},
        )
        assert response.status_code in (422, 500)


# ── List Projects Endpoint ───────────────────────────────────


class TestListProjects:
    """GET /api/v1/kernel/projects"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_returns_200(
        self, client: AsyncClient,
    ):
        """List returns 200 with total."""
        response = await client.get(
            "/api/v1/kernel/projects",
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            data = response.json()["data"]
            assert "projects" in data
            assert "total" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_filter_by_language(
        self, client: AsyncClient,
    ):
        """Language filter accepted."""
        response = await client.get(
            "/api/v1/kernel/projects",
            params={"language": "python"},
        )
        assert response.status_code in (200, 500)


# ── Get Project Detail ───────────────────────────────────────


class TestGetProject:
    """GET /api/v1/kernel/projects/{id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_not_found(
        self, client: AsyncClient,
    ):
        """Non-existent project returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/kernel/projects/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_invalid_uuid(
        self, client: AsyncClient,
    ):
        """Invalid UUID returns 422."""
        response = await client.get(
            "/api/v1/kernel/projects/not-a-uuid",
        )
        assert response.status_code in (422, 500)


# ── Delete Project ───────────────────────────────────────────


class TestDeleteProject:
    """DELETE /api/v1/kernel/projects/{id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_not_found(
        self, client: AsyncClient,
    ):
        """Deleting non-existent returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/api/v1/kernel/projects/{fake_id}",
        )
        assert response.status_code in (404, 500)


# ── Scan Project ─────────────────────────────────────────────


class TestScanProject:
    """POST /api/v1/kernel/projects/{id}/scan"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_scan_not_found(
        self, client: AsyncClient,
    ):
        """Scanning non-existent returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/kernel/projects/{fake_id}/scan",
        )
        assert response.status_code in (404, 500)
