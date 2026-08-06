"""Shared PROPOSE-mode contract text for scheduled ambient-action personas.

An ambient-action persona (``ops`` today, ``cody`` soon — see
``kernel.ambient.AMBIENT_ACTION``) runs read-only on a schedule and ends its
reply with ONLY a JSON array of proposed actions. ``ActionProposalBridge``
(``services/action_proposal_bridge.py``) parses that array and routes each
item through the autonomy engine. These constants are appended verbatim to a
persona's ``system_prompt`` in ``kernel/personas.py`` so every persona that
opts into propose mode emits a JSON shape the bridge already understands.

``COMMAND_PROPOSE_CONTRACT`` is the original ops contract (shell-command
proposals), moved here unchanged from its former inline location in the ops
persona definition — this move must not alter the seeded prompt text for
existing tenants (seeding skips rows that already exist).

``AGENT_TASK_PROPOSE_CONTRACT`` is the newer, open-ended contract (Task 6
appends it to cody's persona): proposals are natural-language instructions
for an engineer agent rather than shell commands.
"""

from __future__ import annotations

COMMAND_PROPOSE_CONTRACT = (
    " When run on a schedule you are in PROPOSE mode: investigate read-only, do"
    " not perform any change, and end your reply with ONLY a JSON array of"
    ' proposed actions, each {"name": str, "command": str, "rationale":'
    ' str, "risk_hint": "safe"|"moderate"|"dangerous"}. Return [] if'
    " nothing needs doing. Each command must be a single concrete shell command."
)

AGENT_TASK_PROPOSE_CONTRACT = (
    " When run on a schedule you are in PROPOSE mode: investigate read-only, do"
    " not perform any change, and end your reply with ONLY a JSON array of"
    ' proposed tasks, each {"kind": "agent_task", "name": str,'
    ' "instruction": str, "rationale": str, "risk_hint":'
    ' "safe"|"moderate"|"dangerous"}. Return [] if nothing needs doing.'
    " Each instruction is a concrete, self-contained task for an engineer agent."
)
