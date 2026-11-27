"""Agent accounts: named logins per driver CLI, an ordered pool, cooldown, limits.

Spec: docs/specs/agent-drivers.md, "Phase 3b (2026-11-27): accounts, pool,
limits, resume". Modules:

- ``catalog`` — drivers, kinds, and the variables each may set (verified flags)
- ``env`` — the run environment overlay, checked against the catalog
- ``homes`` — the private per-account CLI home directories
- ``identity`` — masked identity and its keyed hash (never the raw value)
- ``pool`` — pure selection, cooldown and reordering
- ``limits`` — plan-limit windows from runs, and the opt-in Codex probe
- ``service`` — the database side (tenant-scoped CRUD, secret, outcome)

The driver-side hook is ``life_graph/drivers/accounts_hook.py``.
"""
