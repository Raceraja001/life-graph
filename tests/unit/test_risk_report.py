"""The change risk report and the opt-in no_high_entropy_in_diff verifier."""

from __future__ import annotations

import json
import subprocess

import pytest

from life_graph.services.dev import risk_report as rr
from life_graph.services.dev.verifiers import verifier_chain

# Random-looking, but not any known credential shape (no sk-/ghp_/AKIA prefix).
KEY = "q7Rt2LxW9vBn4ZpK8sYd3MfJ6hGc1Ae5"
HEX = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _diff(path: str, added: list[str], *, removed: int = 0, start: int = 1) -> str:
    head = (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -{start},{removed} +{start},{len(added)} @@\n"
    )
    return (
        head
        + "".join(f"-old {i}\n" for i in range(removed))
        + "".join(f"+{line}\n" for line in added)
    )


def test_entropy():
    assert rr.shannon_entropy("") == 0.0
    assert rr.shannon_entropy("aaaa") == 0.0
    assert rr.shannon_entropy("abcd") == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("token", "kind"),
    [
        (KEY, "random"),
        (HEX, "hex"),
        ("123e4567-e89b-12d3-a456-426614174000", None),  # a UUID
        ("test_verify_no_secrets_in_diff", None),  # an identifier
        ("MAX_SCANNED_FILE_BYTES_DEFAULT", None),
        ("life_graph/services/dev/risk_report", None),  # a path
        ("deadbeefdeadbeef", None),  # too short
        ("abc", None),
    ],
)
def test_classify_token(token, kind):
    got = rr.classify_token(token)
    assert (got[0] if got else None) == kind


def test_random_string_in_code_blocks_with_file_and_line():
    report = rr.build_report(_diff("app/config.py", ["x = 1", f'API = "{KEY}"'], start=10))
    assert report["block"] == 1 and report["complete"]
    f = report["findings"][0]
    assert (f["severity"], f["rule"], f["file"], f["line"]) == (
        "block",
        "high_entropy_string",
        "app/config.py",
        11,
    )
    assert KEY not in json.dumps(report)  # never the value itself
    assert KEY[:8] not in json.dumps(report)


def test_known_secret_shape_blocks_once():
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
    report = rr.build_report(_diff("app/x.py", [f'TOKEN = "{token}"']))
    assert [f["rule"] for f in report["findings"]] == ["secret_pattern"]
    assert token not in json.dumps(report)


def test_aws_example_key_is_not_a_secret():
    assert rr.build_report(_diff("app/x.py", ['k = "AKIAIOSFODNN7EXAMPLE"']))["block"] == 0


@pytest.mark.parametrize(
    ("path", "line"),
    [
        ("tests/unit/test_x.py", f'KEY = "{KEY}"'),
        ("app/fixtures/data.py", f'KEY = "{KEY}"'),
        ("app/x.py", f'sha256 = "{KEY}"'),
    ],
)
def test_tests_fixtures_and_digests_only_warn(path, line):
    report = rr.build_report(_diff(path, [line]))
    assert report["block"] == 0 and report["warn"] == 1
    assert report["findings"][0]["rule"] == "high_entropy_string"


def test_hex_warns_and_lockfiles_are_skipped():
    report = rr.build_report(_diff("app/x.py", [f'EMPTY_TREE = "{HEX}"']))
    assert report["block"] == 0 and report["findings"][0]["rule"] == "hex_string"
    assert rr.build_report(_diff("uv.lock", [f'hash = "{KEY}"']))["findings"] == [
        {
            "severity": "warn",
            "rule": "protected_path",
            "file": "uv.lock",
            "line": None,
            "detail": "protected path",
        }
    ]


def test_secret_assignment_warns_but_placeholders_do_not():
    report = rr.build_report(_diff("app/x.py", ['password = "hunter2hunter2"']))
    assert [f["rule"] for f in report["findings"]] == ["secret_assignment"]
    for placeholder in ('password = "changeme123"', 'api_key = "${API_KEY}"', 'token = "xxxxxxxx"'):
        assert rr.build_report(_diff("app/x.py", [placeholder]))["findings"] == []


def test_removed_lines_are_not_scanned():
    text = (
        "diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n"
        f'@@ -1,1 +1,1 @@\n-API = "{KEY}"\n+API = os.environ["API"]\n'
    )
    assert rr.build_report(text)["block"] == 0


def test_change_level_warnings():
    deleted = "diff --git a/app/old.py b/app/old.py\n--- a/app/old.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a\n-b\n"
    report = rr.build_report(
        deleted
        + _diff("app/big.py", ["x"], removed=rr.LARGE_DELETION_LINES + 1)
        + _diff(".github/workflows/ci.yml", ["on: push"])
        + _diff("app/other.py", ["y = 2"])
        + _diff("tests/test_app.py", ["def test(): pass"]),
        instruction="Fix the bug in app/big.py",
        protected_globs=["app/old.py"],
    )
    rules = {(f["rule"], f["file"]) for f in report["findings"]}
    assert ("large_deletion", "app/old.py") in rules
    assert ("large_deletion", "app/big.py") in rules
    assert ("protected_path", ".github/workflows/ci.yml") in rules
    assert ("protected_path", "app/old.py") in rules  # the project's own glob
    assert ("out_of_scope", "app/other.py") in rules
    assert ("out_of_scope", "app/big.py") not in rules
    assert ("out_of_scope", "tests/test_app.py") not in rules  # tests are always in scope
    assert report["block"] == 0 and report["warn"] == len(report["findings"])


def test_incomplete_report_and_summary():
    report = rr.build_report("", complete=False)
    assert rr.summary(report) == {"block": 0, "warn": 0, "complete": False}
    assert rr.summary(None) is None


def test_junk_input_never_raises():
    for junk in ("@@ nonsense", "+++ b/x\n+" + "a" * 50_000, "\x00\x01", None):
        rr.build_report(junk)  # type: ignore[arg-type]


def test_findings_are_capped():
    lines = [f'K{i} = "{KEY[i % 5 :]}{i:04d}Zz"' for i in range(rr.MAX_FINDINGS + 20)]
    report = rr.build_report(_diff("app/many.py", lines))
    assert len(report["findings"]) == rr.MAX_FINDINGS and report["truncated"]
    assert report["block"] == rr.MAX_FINDINGS + 20


# ── no_high_entropy_in_diff (opt-in verifier) ────────────────


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "app.py").write_text(f'OLD = "{KEY}"\n')  # already there: not the change's
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


async def test_verifier_is_registered_but_not_default():
    from life_graph.drivers.verify_chain import _ALWAYS_ON_CHECKS, DEFAULT_VERIFY_CHAIN

    assert "no_high_entropy_in_diff" in verifier_chain.names
    assert "no_high_entropy_in_diff" not in DEFAULT_VERIFY_CHAIN
    assert "no_high_entropy_in_diff" not in _ALWAYS_ON_CHECKS


async def test_verifier_passes_on_preexisting_and_fails_on_added(repo):
    (repo / "app.py").write_text(f'OLD = "{KEY}"\nNEW = 1\n')
    [result] = await verifier_chain.run_chain(["no_high_entropy_in_diff"], repo, {})
    assert result.passed, result.evidence

    (repo / "new_module.py").write_text(f'TOKEN = "{KEY[::-1]}"\n')  # untracked new file
    [result] = await verifier_chain.run_chain(["no_high_entropy_in_diff"], repo, {})
    assert not result.passed
    assert result.evidence["findings"][0]["file"] == "new_module.py"
    assert result.evidence["findings"][0]["line"] == 1
    assert KEY[::-1] not in json.dumps(result.evidence)


async def test_verifier_outside_git_passes(tmp_path):
    [result] = await verifier_chain.run_chain(["no_high_entropy_in_diff"], tmp_path, {})
    assert result.passed
