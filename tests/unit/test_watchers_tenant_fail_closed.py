"""Watcher routes never fall back to the "default" tenant (audit 2026-11-19, M8)."""

from __future__ import annotations

import contextvars

import pytest

from life_graph.api import watchers as watchers_api
from life_graph.core.tenant import tenant_scope


def test_no_tenant_context_raises_instead_of_default():
    # A fresh context: no tenant set by any earlier test.
    ctx = contextvars.Context()
    with pytest.raises(RuntimeError):
        ctx.run(watchers_api._get_tenant)


def test_tenant_context_is_used():
    with tenant_scope("tenant-a"):
        assert watchers_api._get_tenant() == "tenant-a"
