"""Moved to :mod:`life_graph.services.notifications.telegram_binding`; this name is an alias.

Same module object (``sys.modules``), not a re-export, so patches through
either name reach every caller. New code imports the new path.
"""

import sys

from life_graph.services.notifications import telegram_binding as _moved

sys.modules[__name__] = _moved
