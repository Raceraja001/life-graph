"""The active ``only_models()`` pin, readable without loading litellm.

``services/llm/resilient.py`` ``only_models(models)`` limits every completion
inside it to the caller's model plus *models*: no global fallback chain, no
OmniRoute, no paid model. The pin lives here, not in resilient.py, so code that
only needs to *read* it (connectors/locality.py, deciding whether a run stays on
this machine) does not import litellm to find out.
"""

from __future__ import annotations

import contextvars

#: When set, the only models a completion may fail over to (see
#: ``resilient.only_models``). ``None`` means no pin: the global chain applies.
_allowed_fallbacks: contextvars.ContextVar[tuple[str, ...] | None] = contextvars.ContextVar(
    "resilient_llm_allowed_fallbacks", default=None
)


def pinned_models() -> tuple[str, ...] | None:
    """The models the running code is pinned to, or None when it is not pinned."""
    return _allowed_fallbacks.get()
