"""What the phone's More screens read: who decided an approval, and deck counts."""

import uuid
from datetime import UTC, datetime

from life_graph.models.agents import Approval
from life_graph.services.approvals import ApprovalService
from life_graph.services.study import deck_row


def _approval(**kw) -> Approval:
    fields = {
        "id": uuid.uuid4(),
        "tenant_id": "t",
        "kind": "driver_pr",
        "title": "Merge PR",
        "status": "pending",
        "source": "drivers",
        "payload": {},
        "created_at": datetime(2026, 10, 25, 9, 0, tzinfo=UTC),
    }
    return Approval(**(fields | kw))


def test_a_pending_approval_has_no_resolver():
    out = ApprovalService._serialize(_approval())
    assert out["resolved_by"] is None and out["resolved_at"] is None


def test_a_decided_approval_says_who_and_when():
    at = datetime(2026, 10, 25, 10, 30, tzinfo=UTC)
    out = ApprovalService._serialize(
        _approval(status="approved", resolved_by="phone:pixel", resolved_at=at)
    )
    assert out["resolved_by"] == "phone:pixel"
    assert out["resolved_at"] == at.isoformat()


def test_deck_retention_counts_reviewed_cards_only():
    assert deck_row("go", 10, 3, 4, 3) == {
        "deck": "go",
        "cards": 10,
        "due": 3,
        "reviewed": 4,
        "retention": 0.75,
    }
    assert deck_row("new", 5, 5, 0, 0)["retention"] is None
