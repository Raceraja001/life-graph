"""Offline evaluation code: benchmarks the CI and scripts/ run, never the API.

Kept out of ``life_graph/services`` (the runtime domain logic) so it is plain
which modules serve requests. Nothing in the running app imports this package.
"""
