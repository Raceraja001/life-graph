"""How far a tech-watch source can be trusted (the feature watch, 2026-10-27).

The first feature-watch run reported "Open WebUI 2026 for Windows released"
from github.com/mapchancellorhaul/open-webui-2026: a repo named after a
popular project, outside that project's organisation — the usual shape of a
malware lure. A finding is

- ``official`` when it comes from the vendor's own site or GitHub organisation,
- ``suspicious`` when it is a GitHub repo named after a watched app but owned
  by someone else,
- ``unknown`` otherwise (news sites, blogs, release trackers).

Suspicious findings are kept as a record but never shown as ideas or sent in
the brief (services/feature_ideas.py, services/web_research.digest_lines).
"""

from __future__ import annotations

from urllib.parse import urlsplit

# The vendors' own sites. A subdomain counts (help.openai.com, docs.openwebui.com).
OFFICIAL_DOMAINS = frozenset(
    {
        "openai.com",
        "chatgpt.com",
        "anthropic.com",
        "claude.com",
        "claude.ai",
        "blog.google",
        "gemini.google",
        "gemini.google.com",
        "perplexity.ai",
        "microsoft.com",
        "openwebui.com",
        "librechat.ai",
        "lobehub.com",
        "anythingllm.com",
        "useanything.com",
        "ollama.com",
    }
)

# GitHub organisations (lower-case) that publish the watched apps.
OFFICIAL_GITHUB_ORGS = frozenset(
    {
        "openai",
        "anthropics",
        "google-gemini",
        "google",
        "microsoft",
        "open-webui",
        "danny-avila",  # LibreChat
        "lobehub",
        "mintplex-labs",  # AnythingLLM
        "ollama",
    }
)

# Names a lookalike repo borrows.
WATCHED_NAMES = (
    "open-webui",
    "openwebui",
    "librechat",
    "lobechat",
    "lobe-chat",
    "anythingllm",
    "chatgpt",
    "claude",
    "gemini",
    "copilot",
    "perplexity",
    "ollama",
)


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def source_trust(url: str) -> str:
    """``official``, ``suspicious`` or ``unknown`` for a finding's source URL."""
    host = _host(url)
    if not host:
        return "unknown"
    if any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS):
        return "official"
    if host == "github.com":
        parts = [p for p in urlsplit(url).path.lower().split("/") if p]
        if parts and parts[0] in OFFICIAL_GITHUB_ORGS:
            return "official"
        repo = parts[1] if len(parts) > 1 else ""
        if any(name in repo for name in WATCHED_NAMES):
            return "suspicious"
    return "unknown"
