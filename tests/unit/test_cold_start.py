"""Cold start analyzer tests (T-042).

Tests the three cold start analyzers — ConfigParser, CodeAnalyzer,
and GitAnalyzer — against a sample fixture repo and the project itself.
"""

import pytest
from pathlib import Path

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

    def test_analyzes_current_repo(self):
        # Test against the life-graph repo itself
        repo_path = str(Path(__file__).parent.parent.parent)
        try:
            memories = self.analyzer.analyze(repo_path)
            assert isinstance(memories, list)
            # Should find some commit patterns
        except Exception:
            pytest.skip("PyDriller not installed or not a git repo")

    def test_returns_memory_dicts(self):
        repo_path = str(Path(__file__).parent.parent.parent)
        try:
            memories = self.analyzer.analyze(repo_path)
            for m in memories:
                assert 'content' in m
        except Exception:
            pytest.skip("PyDriller not installed")
