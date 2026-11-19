"""Every redaction entry point removes every modern API-key shape (audit H1).

``core.redaction`` used to stop ``sk-`` keys at the first hyphen, so
``sk-ant-…``, ``sk-proj-…``, ``sk-or-v1-…``, ``AIza…`` and ``github_pat_…``
all survived it — and it is what the Claude Code hook redacts every capture
with. The shapes now live in one canonical list that the other redactors
reuse; this test runs each shape through all of them.

Samples are assembled at runtime so no literal credential sits in the source.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from clients.desktop.redact import redact as desktop_redact
from life_graph.core import redaction as core_redaction
from life_graph.core.redaction import redact_secrets, summarize_args
from life_graph.integrations.claude_code.transport import build_capture_payload
from life_graph.services.capture import CaptureService
from life_graph.services.dev import verifiers
from life_graph.services.redaction import redact as services_redact

_ALNUM = "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zC5"  # 36 chars

# (name, prefix, tail): the tail is the part that must never survive.
SHAPES: list[tuple[str, str, str]] = [
    ("anthropic", "sk-ant-api03-", "Xq7_" + _ALNUM + "-Zz9AAA"),
    ("openai_project", "sk-proj-", "Pr0j" + _ALNUM + "_T4il-x"),
    ("openrouter", "sk-or-v1-", "0f1e2d3c4b5a6978" * 4),
    ("openai_legacy", "sk-", "L3gacy" + _ALNUM[:26]),
    ("google", "AIza", "Sy" + _ALNUM[:31] + "-_"),
    ("github_fine_grained", "github_pat_", "11ABCDEFG0" + "_" + _ALNUM),
    ("github_classic", "ghp_", _ALNUM),
    ("gitlab", "glpat-", "Gl4b" + _ALNUM[:20]),
    ("aws", "AKIA", "QWERTYUIOPASDFGH"),
    ("slack", "xoxb-", "123456789012-" + _ALNUM[:24]),
    ("stripe_live", "sk_live_", "Str1pe" + _ALNUM[:24]),
    ("npm", "npm_", "Npm0" + _ALNUM[:32]),
    ("jwt", "eyJhbGciOiJIUzI1NiJ9.", "eyJzdWIiOiIxMjM0NTY3ODkwIn0.Sfl" + _ALNUM[:20]),
    (
        "pem",
        "-----BEGIN RSA PRIVATE KEY-----\n",
        "MIIEow" + _ALNUM + "\n" + _ALNUM[::-1] + "\n-----END RSA PRIVATE KEY-----",
    ),
    (
        # A capture clipped mid-key never reaches the END line; the body must
        # still go.
        "pem_truncated",
        "-----BEGIN OPENSSH PRIVATE KEY-----\n",
        "b3BlbnNzaC1rZXktdjE" + _ALNUM + "\n" + _ALNUM[::-1],
    ),
]

_IDS = [name for name, _, _ in SHAPES]


def _secret_parts(prefix: str, tail: str) -> list[str]:
    """The substrings that must not survive: each line of the secret body."""
    return [line for line in tail.splitlines() if len(line) >= 12 and "-----" not in line]


def _assert_gone(out: str, prefix: str, tail: str) -> None:
    for part in _secret_parts(prefix, tail):
        assert part not in out, f"secret fragment survived: {out!r}"


def _sentence(prefix: str, tail: str) -> str:
    return f"here is the key {prefix}{tail} — keep it safe"


@pytest.mark.parametrize(("name", "prefix", "tail"), SHAPES, ids=_IDS)
def test_core_redact_secrets(name, prefix, tail):
    _assert_gone(redact_secrets(_sentence(prefix, tail)), prefix, tail)


@pytest.mark.parametrize(("name", "prefix", "tail"), SHAPES, ids=_IDS)
def test_core_summarize_args(name, prefix, tail):
    out = summarize_args({"command": _sentence(prefix, tail)}, max_len=10_000)
    # JSON-escaped: compare against the escaped secret body as well.
    _assert_gone(out, prefix, tail)
    _assert_gone(out, prefix, json.dumps(tail)[1:-1])


@pytest.mark.parametrize(("name", "prefix", "tail"), SHAPES, ids=_IDS)
def test_services_redact(name, prefix, tail):
    _assert_gone(services_redact(_sentence(prefix, tail)), prefix, tail)


@pytest.mark.parametrize(("name", "prefix", "tail"), SHAPES, ids=_IDS)
def test_desktop_client_redact(name, prefix, tail):
    _assert_gone(desktop_redact(_sentence(prefix, tail)), prefix, tail)


@pytest.mark.parametrize(("name", "prefix", "tail"), SHAPES, ids=_IDS)
def test_claude_code_transport(name, prefix, tail):
    payload = build_capture_payload(
        surface="claude_code",
        content=_sentence(prefix, tail),
        cfg=SimpleNamespace(max_content_chars=100_000),
        properties={"tool_input": {"command": _sentence(prefix, tail)}},
    )
    _assert_gone(payload["content"], prefix, tail)
    _assert_gone(json.dumps(payload["properties"]), prefix, json.dumps(tail)[1:-1])
    _assert_gone(payload["properties"]["tool_input"]["command"], prefix, tail)


class _NoDuplicate:
    def scalars(self):
        return self

    def first(self):
        return None


class _Session:
    def __init__(self):
        self.added = []

    async def execute(self, *_a, **_k):
        return _NoDuplicate()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.parametrize(("name", "prefix", "tail"), SHAPES, ids=_IDS)
async def test_capture_ingest_redacts_server_side(name, prefix, tail):
    # A client that skipped redaction (or an old hook build) still cannot get
    # a key stored: the capture spine redacts before hashing and storing.
    session = _Session()
    event = await CaptureService(session, event_bus=None).ingest(
        tenant_id="t1", surface="cli", content=_sentence(prefix, tail)
    )
    _assert_gone(event.content, prefix, tail)
    # The hash is of what is stored, so dedup compares stored content.
    assert event.content_hash == hashlib.sha256(event.content.encode()).hexdigest()


_HIGH_CONFIDENCE = {
    "anthropic",
    "openai_project",
    "openrouter",
    "google",
    "github_fine_grained",
    "github_classic",
    "gitlab",
    "aws",
    "slack",
    "stripe_live",
    "npm",
    "pem",
    "pem_truncated",
}


@pytest.mark.parametrize(
    ("name", "prefix", "tail"),
    [s for s in SHAPES if s[0] in _HIGH_CONFIDENCE],
    ids=[s[0] for s in SHAPES if s[0] in _HIGH_CONFIDENCE],
)
def test_diff_secret_gate_catches_high_confidence_shapes(name, prefix, tail):
    # The dev-agent's no_secrets_in_diff gate scans line by line.
    first_line = (prefix + tail).splitlines()[0]
    assert any(p.search(first_line) for _, p in verifiers._SECRET_RE), first_line


@pytest.mark.parametrize("generic", ["openai_legacy", "jwt"])
def test_diff_secret_gate_stays_high_confidence_only(generic):
    # Generic sk-/JWT shapes false-positive on fixtures; the gate must not
    # start refusing diffs over them.
    prefix, tail = next((p, t) for n, p, t in SHAPES if n == generic)
    assert not any(p.search(prefix + tail) for _, p in verifiers._SECRET_RE)


def test_desktop_mirror_matches_core_token_shapes():
    # clients/desktop/redact.py cannot import the backend; keep it in lockstep.
    from clients.desktop import redact as desktop

    core = [p.pattern for p in core_redaction._TOKEN_SHAPES]
    mirror = [p.pattern for p in desktop._TOKEN_SHAPES]
    assert mirror == core
    assert desktop._URL_PASSWORD.pattern == core_redaction.URL_PASSWORD.pattern


@pytest.mark.parametrize(
    "prose",
    [
        "the risk-assessment-for-the-quarter-2026 doc",
        "task-0123456789abcdefghij is done",
        "author: Ana, token count 42",
    ],
)
def test_ordinary_prose_survives(prose):
    assert redact_secrets(prose) == prose
    assert "REDACTED" not in services_redact(prose)
