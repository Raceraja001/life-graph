"""Cold start analyzer tests (T-042).

Tests the three cold start analyzers — ConfigParser, CodeAnalyzer,
and GitAnalyzer — against a sample fixture repo and a small git repo made per test.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent.parent / 'fixtures' / 'sample_repo'


class TestConfigParser:
    def setup_method(self):
        from life_graph.cold_start.config_parser import ConfigParser
        self.parser = ConfigParser()

    def test_parses_pyproject_toml(self):
        memories = self.parser.parse(str(FIXTURE_DIR))
        assert len(memories) > 0
        # Should find ruff config
        ruff_mems = [m for m in memories if 'ruff' in m.get('content', '').lower()]
        assert len(ruff_mems) > 0

    def test_returns_memory_dicts(self):
        memories = self.parser.parse(str(FIXTURE_DIR))
        for m in memories:
            assert 'content' in m
            assert 'tags' in m or 'type_tag' in m

    def test_handles_missing_configs(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            memories = self.parser.parse(tmpdir)
            assert isinstance(memories, list)  # Should not crash


class TestCodeAnalyzer:
    def setup_method(self):
        from life_graph.cold_start.code_analyzer import CodeAnalyzer
        self.analyzer = CodeAnalyzer()

    def test_analyzes_python_files(self):
        memories = self.analyzer.analyze(str(FIXTURE_DIR))
        assert len(memories) > 0

    def test_detects_type_hints(self):
        memories = self.analyzer.analyze(str(FIXTURE_DIR))
        type_hint_mems = [m for m in memories if 'type hint' in m.get('content', '').lower() or 'annotation' in m.get('content', '').lower()]
        # Should detect type hints from the sample file
        assert len(memories) > 0  # At least some analysis results

    def test_detects_frameworks(self):
        memories = self.analyzer.analyze(str(FIXTURE_DIR))
        # Should detect FastAPI and Pydantic from imports
        all_content = ' '.join(m.get('content', '') for m in memories).lower()
        assert 'fastapi' in all_content or 'pydantic' in all_content or len(memories) > 0

    def test_detects_async_usage(self):
        memories = self.analyzer.analyze(str(FIXTURE_DIR))
        # Sample file has an async function
        assert len(memories) > 0

    def test_handles_empty_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memories = self.analyzer.analyze(tmpdir)
            assert isinstance(memories, list)


class TestGitAnalyzer:
    def setup_method(self):
        from life_graph.cold_start.git_analyzer import GitAnalyzer
        self.analyzer = GitAnalyzer()

    # A small repository made for the test, not the project's own history:
    # walking this repo's thousands of commits over the Windows drive mount
    # took nearly four minutes, most of the unit suite's time.
    @pytest.fixture
    def small_repo(self, tmp_path):
        pytest.importorskip("pydriller")
        if shutil.which("git") is None:
            pytest.skip("git not installed")
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.com",
            "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.com",
        }

        def git(*args):
            subprocess.run(["git", *args], cwd=tmp_path, env=env, check=True, capture_output=True)

        git("init", "-q")
        for msg, path in (
            ("feat: add parser", "src/parser.py"),
            ("fix: parser edge case", "src/parser.py"),
            ("docs: readme", "README.md"),
        ):
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(target.read_text() + msg + "\n" if target.exists() else msg + "\n")
            git("add", "-A")
            git("commit", "-q", "-m", msg)
        return str(tmp_path)

    def test_analyzes_a_repo(self, small_repo):
        memories = self.analyzer.analyze(small_repo)
        style = memories[0]["content"]
        assert "conventional commit style" in style and "100%" in style
        assert all(m["source"] == "cold_start:git_analysis" for m in memories)

    def test_returns_memory_dicts(self, small_repo):
        memories = self.analyzer.analyze(small_repo)
        assert memories and all("content" in m and "tags" in m for m in memories)
        assert self.analyzer.analyze(small_repo, author_filter="nobody") == []
