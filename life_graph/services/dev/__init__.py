"""Dev-agent services: tasks, verification, and landing the work.

- tasks: "do X in project Y" -- submit, run, track (was dev_tasks)
- verifiers, proof_checks, sandbox: the verifier chain and its container
- acceptance, conformance: acceptance criteria bound to tests; re-checks
- change_policy, plan_policy: what may land or approve itself unattended
- second_opinion, pr_agent_review: independent reviews of a change
- github_pr, local_merge, pr_description: landing verified work
- outcomes, failure_causes, trajectories: learning from what happened
  (outcomes was dev_outcomes)
- suggestions, production_findings: where new tasks come from
  (suggestions was dev_suggestions)
- code_graph, project_learning: what the agent knows about a project

Grouped here 2026-11-17; they were flat modules in life_graph/services/.
Each old module (services/dev_tasks.py and the rest) is an alias of the new
one -- the same module object -- for code on other branches. Nothing is
imported here, so importing one submodule loads only that one.
"""
