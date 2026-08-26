"""Life Graph — Brain-inspired personal memory system."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

# Single-sourced from `[project] version` in pyproject.toml via the installed
# distribution's metadata. This file used to carry its own literal and drifted
# to 0.1.0 while pyproject and CHANGELOG.md had moved on to 1.1.0, because the
# release ritual asked a human to bump both by hand. Deriving it removes the
# opportunity to forget.
try:
    __version__ = _dist_version("life-graph")
except PackageNotFoundError:  # source tree that was never pip-installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
