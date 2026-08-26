"""Claude Code lifecycle-hook adapter — a capture surface for coding work.

Claude Code fires ``command`` hooks at session/prompt/tool boundaries. This
package is the single entrypoint those hooks run
(``python3 -m life_graph.integrations.claude_code.hook``): it turns the hook's
stdin JSON into Capture Spine events, and turns proactive recall back into
``additionalContext`` at session start.

Design posture, in priority order:

1. **Never break Claude Code.** Every path is wrapped; the process always
   exits 0; stdout carries nothing but deliberate hook JSON.
2. **Correct provenance.** Surfaces are chosen from the existing default-deny
   map in :mod:`life_graph.core.trust` — ``cli`` (SELF) for what the developer
   typed, ``tool_exhaust`` (VERIFIED) for deterministic observations of our own
   work. No new surface is invented, because an unknown surface is EXTERNAL and
   would be prompt-fenced as untrusted.
3. **Bounded volume.** The sampling policy from
   :mod:`life_graph.services.tool_observation` is enforced *client-side*, so a
   throttled event never makes an HTTP call at all.
"""

__all__ = ["config", "hook", "policy", "render", "transport"]
