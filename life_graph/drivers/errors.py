"""Errors shared by the dispatcher and the modules it is split into."""

from __future__ import annotations


class DispatchError(Exception):
    """Raised when a dispatch cannot proceed."""
