"""Moved to :mod:`life_graph.services.llm.claude_cli_reply`; this name is an alias.

Same module object (``sys.modules``), not a re-export, so patches through
either name reach every caller. New code imports the new path.
"""

import sys

from life_graph.services.llm import claude_cli_reply as _moved

sys.modules[__name__] = _moved
