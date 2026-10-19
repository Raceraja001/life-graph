# Autonomous App Development — Roadmap Spec

> **Status: Built (2026-10-14).** All four phases. The user handed this over to build end to
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

### Phase 0 — The pipeline survives on its own — BUILT (ee77965)
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

### Phase 1 — Verify applications, not just Python — BUILT
4. **Node sandbox.** A `node:22` verifier image; `acceptance_tests_pass`
   resolves JS/TS test refs (`path.test.ts::name`) to vitest or jest.
5. **End-to-end verifier `app_e2e_pass`.** It starts the app in the sandbox
   (`sandbox_start_command`), waits for its port, then runs the e2e command
   (Playwright or plain HTTP checks) against it.
6. **Pilot fixture app** with unit and e2e tests, exercised by an
   integration test.

### Phase 2 — Engines and hands-off approvals — BUILT
7. **OpenCode driver.** `opencode run` headless in the sandbox; unavailable
   until the binary is installed, then compared on the scorecards.
8. **Auto-approval policy for plans.**
   - A small plan (at most `auto_plan_max_tasks` tasks, touching no
     sensitive paths) from a driver with an established record approves
     itself.
   - Deploys and dissent never do.
9. **Planner rules.** No verification-only tasks; generated docs are
   regenerated inside the task that changes the code.

### Phase 3 — Close the loop — BUILT
10. **Post-deploy smoke check and rollback.** A `smoke_command` runs after
    `deploy_command`; on failure `rollback_command` runs and a finding is
    filed.
11. **Production findings become dev tasks.** A failing health or smoke
    check files a fix task as a suggestion (an approval), deduplicated per
    finding.

### Phase 4 — Idea to app, commercial readiness — BUILT
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

## What is stubbed, and how to switch it on

Every third-party piece is behind a setting or registry key. The code path is
real and tested; turning a piece on is configuration.

| Piece | Default (stub) | Switch on |
|---|---|---|
| GitHub repo for a new app | local bare repo under `<root>/.lg-remotes/` | `LIFE_GRAPH_BOOTSTRAP_CREATE_GITHUB=true` (uses `gh repo create --private`), or later `git remote set-url origin …` |
| Deploy target | none: `deploy_command` is the operator's own script | set `deploy_command`, `smoke_command`, `rollback_command`, `deploy_on_merge` on the project |
| External monitors (uptime, Sentry, …) | none | point them at `POST /kernel/drivers/projects/{id}/findings` |
| Anthropic API (commercial use) | personal Claude login (`oauth`) | `LIFE_GRAPH_DRIVER_CLAUDE_CODE_AUTH=api_key` + `ANTHROPIC_API_KEY` |
| OpenCode | installed at `~/.local/opencode` on this machine | `LIFE_GRAPH_DRIVER_OPENCODE_BIN`, `…_MODEL` (any `provider/model`) |
| Playwright for e2e | plain HTTP checks (`node tests/e2e/smoke.mjs`) | an image with browsers (`LIFE_GRAPH_VERIFIER_SANDBOX_NODE_IMAGE`) and a Playwright `sandbox_e2e_command` |

Opt-ins that are deliberately **off** until a person turns them on per project:
- `auto_approve_plans`;
- `auto_open_pr`;
- `auto_merge`;
- `deploy_on_merge`.

Deploys are never auto-approved. The $10 monthly budget cap was not raised.

## Where the build differs from the text above

These differences were found while building:
- **CI itself was the first casualty.** Every CI run since 2026-10-03 had died pulling MinIO. Fixing that exposed further problems:
  - SQLAlchemy 2.1 changed a bare `postgresql://` URL's default driver;
  - migration 043 broke on any fresh database;
  - 18 integration tests were stale.

  The integration suite had never run in CI before 2026-10-14; it now passes there, 603 tests.
- **`start.sh` recorded a wrapper's pid.** Its `(cd … && nohup … &)` recorded a wrapper subshell's pid and held the caller's pipe. Both scripts now `exec` uvicorn.
- **Node checks run in a `/tmp` copy of the worktree.** vitest, jest, Vite and Next write caches next to the project, and the worktree mount stays read-only.
- **vitest and jest exit 0 when `-t` matches nothing.** A bound JS test must therefore show at least one passing test.
- **OpenCode waits on an open stdin.** The driver closes it. Its `external_directory: deny` held when the model tried to write outside the worktree.
- **Plan fan-out overwrote the reviewer's note.** Plan fan-out and the deploy result overwrote the approval's reviewer note; they now append to it.
