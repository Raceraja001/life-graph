"""Moved to :mod:`life_graph.services.dev.code_graph`; this name is an alias.

Same module object (``sys.modules``), not a re-export, so patches through
either name reach every caller. New code imports the new path.
"""

import sys

from life_graph.services.dev import code_graph as _moved

sys.modules[__name__] = _moved
