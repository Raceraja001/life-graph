"""Approvals — human-in-the-loop approval queue management.

``policy_checker`` is the structured, prompt-injection-blind gate in front of
the queue: it decides from the owner's request, the owner's standing rules,
the action type, the target's origin and bounded structured parameters, and
never from the page or mail body the action was proposed out of.
"""

from life_graph.autonomy.approvals.policy_checker import (
    ACTION_TYPES,
    ALLOW,
    CONSIDERED_FIELDS,
    DENY,
    REQUIRE_APPROVAL,
    ActionPolicyChecker,
    ActionRequest,
    ActionType,
    OwnerRequest,
    PolicyDecision,
    StandingRule,
    is_outside_origin,
    normalise_params,
    request_from_payload,
)

__all__ = [
    "ACTION_TYPES",
    "ALLOW",
    "CONSIDERED_FIELDS",
    "DENY",
    "REQUIRE_APPROVAL",
    "ActionPolicyChecker",
    "ActionRequest",
    "ActionType",
    "OwnerRequest",
    "PolicyDecision",
    "StandingRule",
    "is_outside_origin",
    "normalise_params",
    "request_from_payload",
]
