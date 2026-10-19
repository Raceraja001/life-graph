"""Cloud Driver — the local driver's agent loop on a free hosted model.

For the hours the GPU belongs to the user (services/compute_router.py): the
same orchestrator, tools, confinement, nudges and self-check as
:class:`LocalDriver`, with three differences that make it safe to hand code
to a free cloud model:

* **Free only, fail closed.** The persona's model must be a free cloud model
  (``openrouter/...:free``, ``nvidia_nim/...``); anything else is refused, and
  the run may fail over only to the other free cloud models
  (:func:`life_graph.services.resilient_llm.only_models`) — never to the GPU,
  OmniRoute or a paid model.
* **No personal data.** Preferences, procedures and memories are dropped from
  the packet; the model sees the task, AGENTS.md and the code.
* **Its own record.** Trust, stats and the auto-PR/auto-merge bar are keyed by
  driver name, so ``cloud`` earns them separately instead of inheriting what
  the local model earned.

Never picked by cheapest-capable selection (no capabilities): only a persona
pinned to ``cloud`` (code-fixer-cloud) runs here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.local import LocalDriver

if TYPE_CHECKING:
    from pathlib import Path


class CloudDriver(LocalDriver):
    """LocalDriver on a free cloud model, with personal context removed."""

    name = "cloud"
    # A pin to this driver must not fall through to another driver when it is
    # unavailable (no key): the persona's model would then run elsewhere.
    pin_required = True

    async def available(self) -> bool:
        """Available once a free cloud model with a provider key is configured."""
        from life_graph.services.compute_router import cloud_models

        return bool(cloud_models())

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        """Run the local agent loop on the persona's free cloud model."""
        from life_graph.services.compute_router import cloud_models, is_free_cloud_model
        from life_graph.services.resilient_llm import only_models

        if not is_free_cloud_model(packet.persona_model):
            return DriverResult(
                success=False,
                error=(
                    "the cloud driver runs free cloud models only; this persona's model "
                    f"is {packet.persona_model!r}"
                ),
                metadata={"stop_reason": "refused"},
            )
        packet.preferences = []
        packet.procedures = []
        packet.memories = []
        with only_models(cloud_models()):
            return await super().dispatch(packet, workdir, timeout)

    def capabilities(self) -> list[str]:
        """None: reached only through a persona pinned to ``cloud``."""
        return []
