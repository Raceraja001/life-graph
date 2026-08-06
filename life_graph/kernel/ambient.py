"""Ambient advisory roles: the personas that run on a schedule and only report."""

from __future__ import annotations

AMBIENT_ADVISORY: frozenset[str] = frozenset({"scout", "admin", "tutor"})
