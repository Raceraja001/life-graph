"""Who is asking: a local model, or something that leaves the machine.

Connector tools consult ``current_audience()`` before returning anything. The
orchestrator sets it around each tool call from the model driving the run.
Anything that has not set it (an unknown caller, a future code path) gets
``CLOUD``: this fails closed.

"Local" is stricter than "the persona's model is local". ``ResilientLLM`` fails
over through ``llm_fallback_chain`` (then OmniRoute and an optional paid model)
mid-run, and the conversation — including every tool result so far — goes with
it. So a run is local only when its model *and every model it could fall over
to* run on this machine.

Inside ``only_models()`` (services/llm/resilient.py) the models it could fall
over to are the pinned ones and nothing else: a personal Jarvis route
(services/lead.py ``route``) and a task delegated from one
(kernel/process_manager.py) run pinned to local models, so they are LOCAL even
when the global chain has cloud models in it.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from life_graph.config import settings
from life_graph.services.llm.fallback_pin import pinned_models

if TYPE_CHECKING:
    from collections.abc import Iterator

LOCAL = "local"
CLOUD = "cloud"

# LiteLLM provider prefixes that talk to a runtime on this machine.
_LOCAL_PREFIXES = ("ollama/", "ollama_chat/", "lm_studio/")

# None = nothing has decided yet (reported as CLOUD). Kept distinct from an
# explicit CLOUD so a nested run can tell "no caller" from "a cloud caller".
_audience: ContextVar[str | None] = ContextVar("connector_audience", default=None)


def model_is_local(model: str | None) -> bool:
    """Whether one model id runs on this machine."""
    if not model:
        return False
    prefixes = _LOCAL_PREFIXES + tuple(
        p.strip() for p in settings.connector_local_model_prefixes.split(",") if p.strip()
    )
    return model.startswith(prefixes)


def run_is_local(model: str | None) -> bool:
    """Whether a run on ``model`` stays local even if the model fails over.

    Under an ``only_models()`` pin, ResilientLLM tries ``model`` and then the
    pinned models only, so those are the whole chain: local when every one of
    them is local, and CLOUD as soon as one is not. Without a pin, the global
    chain counts, with OmniRoute and the paid model when they are set.
    """
    pinned = pinned_models()
    if pinned is not None:
        return all(model_is_local(m) for m in (model, *pinned))
    chain = [model, *settings.llm_fallback_chain_list]
    # ResilientLLM._append_last_resorts adds OmniRoute (a hosted router)
    # after the free chain whenever its key is set.
    if settings.omniroute_api_key:
        chain.append(settings.omniroute_model)
    if settings.llm_paid_fallback_model:
        chain.append(settings.llm_paid_fallback_model)
    return all(model_is_local(m) for m in chain)


def current_audience() -> str:
    """LOCAL or CLOUD for the code running now (CLOUD unless proven local)."""
    return LOCAL if _audience.get() == LOCAL else CLOUD


@contextmanager
def audience(value: str) -> Iterator[None]:
    """Run a block as LOCAL or CLOUD, restoring the previous value after."""
    token = _audience.set(LOCAL if value == LOCAL else CLOUD)
    try:
        yield
    finally:
        _audience.reset(token)


@contextmanager
def audience_for_model(model: str | None) -> Iterator[None]:
    """Run a block with the audience implied by the model driving it.

    Never widens: inside something already running for a CLOUD audience (a
    cloud persona delegating to a local one, a scheduled job whose output is
    delivered off the machine), the inner run is CLOUD too, because its answer
    flows back out to that audience.
    """
    outer = _audience.get()
    local = run_is_local(model) and outer != CLOUD
    with audience(LOCAL if local else CLOUD):
        yield
