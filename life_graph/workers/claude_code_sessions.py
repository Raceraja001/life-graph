"""Close Claude Code memory sessions that are due (services/claude_code_sessions.py).

Every 10 minutes: a session whose SessionEnd marker arrived over
``claude_code_session_end_grace_minutes`` ago, or that has had no new memory
for ``claude_code_session_idle_minutes``, is summarised (local model only),
ended and micro-consolidated, exactly as ``POST /sessions/{id}/end`` would.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def close_claude_code_sessions(ctx: dict | None = None) -> dict:
    """Cron: close the Claude Code memory sessions that are due."""
    from life_graph.services.claude_code_sessions import close_due

    closed = await close_due()
    return {"closed": len(closed)}
