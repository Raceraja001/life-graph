"""Approvals — human-in-the-loop approval queue management.

``policy_checker`` is the structured, prompt-injection-blind gate in front of
the queue: it decides from the owner's request, the owner's standing rules,
the action type, the target's origin and bounded structured parameters, and
never from the page or mail body the action was proposed out of.

``capability`` is the other half of that — where the owner's permission comes
from. The two authority fields are not accepted from payloads at all
(``request_from_payload`` drops them); a mandate exists as an
:class:`~life_graph.autonomy.approvals.capability.AuthorizationCapability`
that only this server can issue and verify, and standing rules are loaded per
tenant from a store trusted code writes.
"""

from life_graph.autonomy.approvals.capability import (
    DEFAULT_TTL,
    MAX_TTL,
    AuthorizationCapability,
    CapabilityCheck,
    CapabilityStore,
    StandingRuleStore,
    capability_store,
    rules_from_config,
    standing_rule_store,
)
from life_graph.autonomy.approvals.policy_checker import (
    ACTION_TYPES,
    ALLOW,
    AUTHORITY_FIELDS,
    CAPABILITY_WITHOUT_TENANT,
    CONSIDERED_FIELDS,
    DENY,
    PAYLOAD_FIELDS,
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
    "AUTHORITY_FIELDS",
    "CAPABILITY_WITHOUT_TENANT",
    "CONSIDERED_FIELDS",
    "DEFAULT_TTL",
    "DENY",
    "MAX_TTL",
    "PAYLOAD_FIELDS",
    "REQUIRE_APPROVAL",
    "ActionPolicyChecker",
    "ActionRequest",
    "ActionType",
    "AuthorizationCapability",
    "CapabilityCheck",
    "CapabilityStore",
    "OwnerRequest",
    "PolicyDecision",
    "StandingRule",
    "StandingRuleStore",
    "capability_store",
    "is_outside_origin",
    "normalise_params",
    "request_from_payload",
    "rules_from_config",
    "standing_rule_store",
]
