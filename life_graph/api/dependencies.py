"""Alias of :mod:`life_graph.runtime`, kept for route modules and tests.

The providers moved to ``life_graph/runtime.py`` so that code outside the
API (services, workers, tools) can reach them without importing the API
package. This name is replaced by that module itself in ``sys.modules``:
``life_graph.api.dependencies is life_graph.runtime``. A re-export
(``from life_graph.runtime import *``) would make a second module object,
and a test's ``monkeypatch.setattr(dependencies, "get_store", fake)`` would
then miss every caller that imports from ``life_graph.runtime``.

New code outside ``life_graph/api/`` should import ``life_graph.runtime``.
"""

import sys
from typing import TYPE_CHECKING

from life_graph import runtime as _runtime

if TYPE_CHECKING:
    # For the type checker only, which cannot follow the sys.modules swap
    # below: it sees this module's names as runtime's. Never executed, so
    # there is still exactly one module object at run time.
    from life_graph.runtime import *  # noqa: F403

sys.modules[__name__] = _runtime
