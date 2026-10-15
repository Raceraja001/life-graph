"""PR-Agent-backed second-opinion reviewer — reads the real diff, not a
narrative summary of it.

Runs PR-Agent (https://github.com/The-PR-Agent/pr-agent, self-hosted,
BYO LLM) as a subprocess against the diff a driver produced, in the same
gate position the older :class:`~life_graph.services.second_opinion.
SecondOpinionReviewer` occupied — after verification, before landing — but
reading the actual code instead of the driver's own narrative account of
what it did. Uses PR-Agent's "plain-diff" local mode (``--stdin``,
``--json-output``): no hosted PR, no git-provider credentials, no
requirement that the worktree be in any particular branch state.

Fail-open by design, same as the reviewer it replaces: if PR-Agent isn't
installed, the call errors, times out, or its output can't be parsed, the
task is approved (``ran=False``) rather than stranded on infrastructure
it doesn't have.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 180


@dataclass
class ReviewVerdict:
    """Outcome of a second-opinion review.

    Same shape :class:`SecondOpinionReviewer` already returns — a drop-in
    replacement for the dispatcher's ``verdict.ran`` / ``.approved`` /
    ``.concern`` usage. ``issues`` is new: the raw per-issue structure from
    PR-Agent, kept for anything downstream that wants more than the
    flattened ``concern`` string (e.g. a future dashboard view).
    """

    approved: bool
    concern: str | None = None
    ran: bool = True
    issues: list[dict] = field(default_factory=list)


class PRAgentReviewer:
    """Diff-reading second-opinion reviewer backed by PR-Agent."""

    def __init__(
        self,
        *,
        model: str | None = None,
        enabled: bool = True,
        bin_path: str = "pr-agent",
    ) -> None:
        self._model = model
        self._enabled = enabled
        self._bin = bin_path

    async def review(
        self, task_type: str, instruction: str, diff_text: str | None
    ) -> ReviewVerdict:
        """Review a real unified diff. Approves unless a concrete concern is found."""
        if not self._enabled or not diff_text or not diff_text.strip():
            return ReviewVerdict(approved=True, ran=False)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                json_path = Path(tmp) / "review.json"
                argv = [self._bin, "--json-output", str(json_path), "--stdin", "review"]
                if self._model:
                    # fallback_models=[] -- a cheap reviewer silently escalating
                    # to PR-Agent's own (possibly expensive) default fallback
                    # chain on failure would defeat the point of picking a
                    # specific model here; fail-open below handles failure.
                    argv += [f"--config.model={self._model}", "--config.fallback_models=[]"]

                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    _out, err = await asyncio.wait_for(
                        proc.communicate(diff_text.encode("utf-8", errors="replace")),
                        timeout=_TIMEOUT_SECONDS,
                    )
                except TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    logger.warning("pr-agent review timed out after %ss", _TIMEOUT_SECONDS)
                    return ReviewVerdict(approved=True, ran=False)

                if proc.returncode != 0 or not json_path.is_file():
                    logger.warning(
                        "pr-agent review failed (exit %s): %s",
                        proc.returncode,
                        err.decode(errors="replace")[-500:],
                    )
                    return ReviewVerdict(approved=True, ran=False)
                data = json.loads(json_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("pr-agent binary not found (%r) — approving", self._bin)
            return ReviewVerdict(approved=True, ran=False)
        except Exception:
            logger.warning("pr-agent review errored — approving", exc_info=True)
            return ReviewVerdict(approved=True, ran=False)

        return self._parse(data)

    @staticmethod
    def _parse(data: dict) -> ReviewVerdict:
        """Turn PR-Agent's review JSON into a verdict.

        PR-Agent's own reviewer prompt already filters for genuine issues —
        ``key_issues_to_review`` isn't a nitpick list — so any non-empty
        result here is treated as a concrete concern, same bar
        SecondOpinionReviewer held its thin LLM skim to.
        """
        review = (data or {}).get("review") or {}
        issues = review.get("key_issues_to_review") or []
        security = str(review.get("security_concerns") or "").strip().lower().rstrip(".")
        has_security_concern = security not in ("", "no", "none")

        if not issues and not has_security_concern:
            return ReviewVerdict(approved=True, ran=True)

        parts: list[str] = []
        if has_security_concern:
            parts.append(f"SECURITY: {str(review.get('security_concerns', '')).strip()}")
        for issue in issues:
            file_ = str(issue.get("relevant_file") or "?").strip()
            header = str(issue.get("issue_header") or "").strip()
            content = str(issue.get("issue_content") or "").strip()
            parts.append(f"{file_}: {header} — {content}")
        concern = "; ".join(parts)[:2000]
        return ReviewVerdict(approved=False, concern=concern or None, ran=True, issues=issues)
