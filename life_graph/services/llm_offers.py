"""Moved to :mod:`life_graph.services.llm.offers`; this name is an alias.

Same module object (``sys.modules``), not a re-export, so patches through
either name reach every caller. New code imports the new path.
"""

import sys

from life_graph.services.llm import offers as _moved

sys.modules[__name__] = _moved
