"""Unit test for the ProcessManager startup invariant added alongside
the delegation-deadlock fix.

delegate_to_persona(wait=True) blocks the parent task's semaphore
permit for the duration of the wait, so a full-depth delegation chain
needs MAX_DELEGATION_DEPTH + 1 permits held at once. If
kernel_max_concurrent_tasks is not strictly greater than
MAX_DELEGATION_DEPTH, a single delegation chain can deadlock waiting
on its own last permit until the ~600s delegate timeout.
ProcessManager.__init__ now asserts this invariant at construction
time so a bad config fails fast instead of deadlocking later.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from life_graph.kernel.process_manager import ProcessManager


class TestConcurrencyInvariant:
    @pytest.mark.parametrize(
        "bad_value",
        [
            ProcessManager.MAX_DELEGATION_DEPTH,
            ProcessManager.MAX_DELEGATION_DEPTH - 1,
            1,
        ],
    )
    def test_construction_rejects_max_concurrent_at_or_below_depth_cap(
        self, bad_value: int,
    ):
        with (
            patch(
                "life_graph.kernel.process_manager.settings.kernel_max_concurrent_tasks",
                bad_value,
            ),
            pytest.raises(ValueError, match="kernel_max_concurrent_tasks"),
        ):
            ProcessManager(session_factory=None, persona_service=None)

    def test_construction_succeeds_when_max_concurrent_exceeds_depth_cap(self):
        with patch(
            "life_graph.kernel.process_manager.settings.kernel_max_concurrent_tasks",
            ProcessManager.MAX_DELEGATION_DEPTH + 1,
        ):
            pm = ProcessManager(session_factory=None, persona_service=None)
            assert pm._max_concurrent == ProcessManager.MAX_DELEGATION_DEPTH + 1

    def test_default_settings_satisfy_the_invariant(self):
        """Guards against the default config regressing back into the
        deadlock-prone range."""
        pm = ProcessManager(session_factory=None, persona_service=None)
        assert pm._max_concurrent > ProcessManager.MAX_DELEGATION_DEPTH
