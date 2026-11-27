"""Dev automation (docs/specs/dev-automation.md): intake → backlog, dev-task
schedules and chains, the circuit breaker, and the morning digest push.

Every feature is off by default except the breaker, which only ever stops
automatic starts. Nothing here approves, publishes or merges: tasks go
through the normal dev-task pipeline and its approvals.
"""
