"""PRAgentReviewer: a diff-reading second opinion, fail-open on any trouble.

Parsing/fail-open behavior is tested against mocked subprocesses (fast,
deterministic); one real end-to-end test proves the actual wiring against
the installed pr-agent binary and a local Ollama model, skipping gracefully
if either isn't available in this environment.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from life_graph.services.pr_agent_review import PRAgentReviewer, ReviewVerdict


def test_parse_approves_when_no_issues_and_no_security_concern():
    data = {"review": {"key_issues_to_review": [], "security_concerns": "No\n"}}
    verdict = PRAgentReviewer._parse(data)
    assert verdict == ReviewVerdict(approved=True, ran=True, issues=[])


def test_parse_blocks_on_a_real_issue():
    data = {
        "review": {
            "key_issues_to_review": [
                {
                    "relevant_file": "a.py\n",
                    "issue_header": "Division by Zero\n",
                    "issue_content": "No zero check.\n",
                }
            ],
            "security_concerns": "No\n",
        }
    }
    verdict = PRAgentReviewer._parse(data)
    assert verdict.approved is False
    assert verdict.ran is True
    assert "Division by Zero" in verdict.concern
    assert "a.py" in verdict.concern
    assert verdict.issues == data["review"]["key_issues_to_review"]


def test_parse_blocks_on_security_concern_even_with_no_issues():
    data = {
        "review": {
            "key_issues_to_review": [],
            "security_concerns": "Hardcoded API key in config.py\n",
        }
    }
    verdict = PRAgentReviewer._parse(data)
    assert verdict.approved is False
    assert "SECURITY" in verdict.concern
    assert "API key" in verdict.concern


@pytest.mark.parametrize("security_text", ["No\n", "no", "None.", "", "NO"])
def test_parse_treats_common_no_concern_spellings_as_clear(security_text):
    data = {"review": {"key_issues_to_review": [], "security_concerns": security_text}}
    assert PRAgentReviewer._parse(data).approved is True


@pytest.mark.asyncio
async def test_disabled_never_runs_a_process():
    reviewer = PRAgentReviewer(enabled=False)
    verdict = await reviewer.review("code_change", "do a thing", "diff --git a/x b/x\n")
    assert verdict == ReviewVerdict(approved=True, ran=False)


@pytest.mark.asyncio
async def test_empty_diff_never_runs_a_process():
    reviewer = PRAgentReviewer(enabled=True)
    verdict = await reviewer.review("code_change", "do a thing", "")
    assert verdict.ran is False
    assert verdict.approved is True


@pytest.mark.asyncio
async def test_missing_binary_fails_open():
    reviewer = PRAgentReviewer(enabled=True, bin_path="/no/such/pr-agent-binary")
    verdict = await reviewer.review("code_change", "do a thing", "diff --git a/x b/x\n+x\n")
    assert verdict == ReviewVerdict(approved=True, ran=False)


@pytest.mark.asyncio
async def test_nonzero_exit_fails_open(monkeypatch):
    import life_graph.services.pr_agent_review as mod

    class _FakeProc:
        returncode = 1

        async def communicate(self, _input=None):
            return b"", b"boom"

    async def _fake_exec(*_a, **_k):
        return _FakeProc()

    monkeypatch.setattr(mod.asyncio, "create_subprocess_exec", _fake_exec)
    reviewer = PRAgentReviewer(enabled=True)
    verdict = await reviewer.review("code_change", "do a thing", "diff --git a/x b/x\n+x\n")
    assert verdict == ReviewVerdict(approved=True, ran=False)


# ── Real end-to-end: the actual installed binary + a local model ──


def _pr_agent_available() -> bool:
    return shutil.which("pr-agent") is not None


def _ollama_available() -> bool:
    try:
        import httpx

        return httpx.get("http://localhost:11434/api/tags", timeout=1.0).status_code == 200
    except Exception:
        return False


@pytest.mark.asyncio
async def test_real_review_catches_an_obvious_bug():
    if not _pr_agent_available():
        pytest.skip("pr-agent binary not installed in this environment")
    if not _ollama_available():
        pytest.skip("no local Ollama server available in this environment")

    diff_text = (
        "diff --git a/buggy.py b/buggy.py\n"
        "new file mode 100644\n"
        "index 0000000..490f3e7\n"
        "--- /dev/null\n"
        "+++ b/buggy.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def divide(a, b):\n"
        "+    return a / b\n"
    )
    reviewer = PRAgentReviewer(enabled=True, model="ollama_chat/qwen3:4b")
    verdict = await reviewer.review("code_change", "add a divide helper", diff_text)

    assert verdict.ran is True
    # A real model reading real code -- allow it to phrase the finding
    # differently, but it must have found SOMETHING and blocked on it.
    assert verdict.approved is False
    assert verdict.concern


def test_json_schema_assumption_still_holds():
    """Pin the exact PR-Agent output shape _parse() depends on, so a
    version bump that changes it fails here instead of silently
    approving everything in production."""
    if not _pr_agent_available():
        pytest.skip("pr-agent binary not installed in this environment")
    if not _ollama_available():
        pytest.skip("no local Ollama server available in this environment")

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        json_path = Path(tmp) / "review.json"
        diff = (
            "diff --git a/x.py b/x.py\nnew file mode 100644\nindex 0000000..1\n"
            "--- /dev/null\n+++ b/x.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
        )
        subprocess.run(
            [
                "pr-agent",
                "--json-output",
                str(json_path),
                "--stdin",
                "review",
                "--config.model=ollama_chat/qwen3:4b",
                "--config.fallback_models=[]",
            ],
            input=diff.encode(),
            capture_output=True,
            timeout=120,
        )
        data = json.loads(json_path.read_text())
        assert "review" in data
        assert "key_issues_to_review" in data["review"]
        assert "security_concerns" in data["review"]
