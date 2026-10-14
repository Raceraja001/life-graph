# Autonomous App Development — Roadmap Spec

> **Status: In progress (2026-10-13).** The user handed this over to build end to
> end ("you can decide and complete these… third party info needed means, use
> stubs"). Each item records what was built and what is stubbed.

## Goal

Take an application from idea → plan → code → verification → merge → deploy →
monitoring → fix, with a human needed only for real decisions:
- disagreements;
- deploys;
- spending more money.

The pipeline already worked for one Python project, but only under close
watch. On 2026-10-13 a human had to rescue it from:
- restarts killing tasks;
- a stale backend;
- a preview server stealing tasks;
- an unpushed base branch;
- an exhausted budget;
- a Python-only verifier.

## Constraints kept

- **Budget:** the $10 monthly cap is not raised; that spends the user's
  money. The free local driver and in-session work carry the load.
- **Pilot project:** the real product (uzhavu) is not the pilot, because
  agent PRs would land on a live product's repo. A fixture app in
  `tests/fixtures/apps/` stands in, and uzhavu can opt in later through
  project settings.
- **Third parties are stubbed behind settings:** a GitHub repo for new apps,
  a deploy target, an Anthropic API key and OpenCode's binary. Code paths are
  real and tested with fakes, and switching on is configuration.

## Phases

### Phase 0 — The pipeline survives on its own
1. **Restart safety.**
   - The API runs without `--reload` by default (`DEV_RELOAD=1` opts in).
   - `scripts/restart-api.sh` restarts only once no dev task is running.
   - A task interrupted by a restart is re-queued once instead of failed.
2. **Pinned base branch.** Setting `base_branch` on a project means:
   - each dispatch fetches `origin/<base>` and cuts its worktree from it,
     not from whatever the local checkout is on;
   - the PR targets that same branch.
3. **CI on agent PRs.** CI runs on pull requests into any branch, not just
   master. The merge gate already requires every reported check to pass.

### Phase 1 — Verify applications, not just Python
4. **Node sandbox.** A `node:22` verifier image; `acceptance_tests_pass`
   resolves JS/TS test refs (`path.test.ts::name`) to vitest or jest.
5. **End-to-end verifier `app_e2e_pass`.** It starts the app in the sandbox
   (`sandbox_start_command`), waits for its port, then runs the e2e command
   (Playwright or plain HTTP checks) against it.
6. **Pilot fixture app** with unit and e2e tests, exercised by an
   integration test.

### Phase 2 — Engines and hands-off approvals
7. **OpenCode driver.** `opencode run` headless in the sandbox; unavailable
   until the binary is installed, then compared on the scorecards.
8. **Auto-approval policy for plans.**
   - A small plan (at most `auto_plan_max_tasks` tasks, touching no
     sensitive paths) from a driver with an established record approves
     itself.
   - Deploys and dissent never do.
9. **Planner rules.** No verification-only tasks; generated docs are
   regenerated inside the task that changes the code.

### Phase 3 — Close the loop
10. **Post-deploy smoke check and rollback.** A `smoke_command` runs after
    `deploy_command`; on failure `rollback_command` runs and a finding is
    filed.
11. **Production findings become dev tasks.** A failing health or smoke
    check files a fix task as a suggestion (an approval), deduplicated per
    finding.

### Phase 4 — Idea to app, commercial readiness
12. **Bootstrap.**
    - `POST /kernel/drivers/projects/bootstrap` scaffolds a new app from a
      local template, `git init`s it and registers it as a project.
    - It optionally starts a plan-only task from the idea.
    - Creating the GitHub remote is stubbed (a local bare repo).
13. **Commercial switches.**
    - **Auth:** `driver_claude_code_auth = oauth | api_key`. The API-key
      mode passes `ANTHROPIC_API_KEY` into the sandbox instead of the
      personal login.
    - **Recording consent:** a per-tenant opt-out for step recording.
    - **Isolation:** per-tenant sandbox and worktree directories.
