"""Unit tests for the task-execution ContextVar (no DB needed)."""

import uuid

import pytest

from life_graph.core.task_context import (
    get_current_task_context,
    set_task_context,
)


def test_get_current_task_context_returns_none_when_unset():
    assert get_current_task_context() is None


def test_set_and_get_task_context_round_trips():
    task_id = uuid.uuid4()
    set_task_context(task_id=task_id, tenant_id="test_tenant")

    ctx = get_current_task_context()

    assert ctx is not None
    assert ctx.task_id == task_id
    assert ctx.tenant_id == "test_tenant"
