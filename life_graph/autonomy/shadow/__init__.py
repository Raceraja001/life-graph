"""Shadow Mode — dry-run rung on the autonomy ladder (D7.4).

New autonomous actors record 'would-have-done' reports instead of acting, until
they soak long enough and are graded well enough to graduate.
"""

from life_graph.autonomy.shadow.service import ShadowDecision, ShadowService, shadow_service

__all__ = ["ShadowDecision", "ShadowService", "shadow_service"]
