# Codebase Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a private `knowledge-base` hub repo that documents ~13 personal and client app codebases — agent-primed and cross-project searchable — and prove the generation workflow on two repos.

**Architecture:** A separate **private** git repo at `D:\DevTools\Projects\knowledge-base\` holds the registry, the doc template, cross-cutting notes, client-app docs (pinned to a commit SHA), and a `_mirror/` of own-repo docs so one `ripgrep` searches everything. Own repos keep their canonical knowledge in-repo at `docs/knowledge/` (co-versioned with the code). A user-level Claude Code skill generates docs from a fixed checklist; a bash script reports staleness.

**Tech Stack:** Markdown, git, GitHub CLI (`gh`), bash (Git Bash on Windows), Claude Code skills.

**Spec:** `docs/superpowers/specs/2026-07-21-codebase-knowledge-base-design.md`

## Global Constraints

- **Projects root** is `D:\DevTools\Projects\` (Git Bash: `/d/DevTools/Projects`). All `kb:source` paths in doc headers are **relative to this root** (e.g. `work/fin-tech`).
- **The hub repo MUST be private.** It holds candid analysis of a client's production fintech platform. Verify with `gh repo view --json isPrivate` before pushing any client content.
- **Never commit anything into client repos.** `work/fin-tech` and `work/SIP` tracked contents stay untouched; local-only files go in `.git/info/exclude`.
- **Machine-readable doc header**, first line of every knowledge doc:
  `<!-- kb:source=<path-rel-to-projects-root> kb:sha=<short-sha> kb:branch=<branch> kb:analysed=YYYY-MM-DD -->`
- **Tier vocabulary:** `T0` = registry row only, `T1` = orientation card, `T2` = subsystem deep dive.
- **Owner vocabulary:** `own` | `client` | `third-party`. Determines doc location (own → in-repo; client/third-party → hub).
- **Docs are "a map, not truth"** — every generated doc repeats this caveat verbatim.
- **Deviation from spec (deliberate, DRY):** the spec named three commands. `/kb-refresh` is **not** a separate skill — refreshing is `/kb-analyse` run against an app that already has a doc (the skill detects this and updates in place, bumping `kb:sha`). `/kb-stale` is a **bash script** (`scripts/kb-stale.sh`), not a skill, because it is pure git plumbing with no judgement.
- **`gh` auth note:** the authenticated GitHub account is `raja4lmx`. Create the hub under that account. If `gh repo create` is blocked by a permission prompt, fall back to creating the repo in the GitHub UI and adding the remote manually (both paths given in Task 2).

---

### Task 1: Stop life-graph from leaking the client notes

`life-graph` is a **public** repo. `knowledge/startgold/` is untracked but **not** gitignored — one `git add -A` publishes a client's security-gap analysis permanently. This task is standalone and ships the urgent fix before anything else.

**Files:**
- Modify: `D:\DevTools\Projects\life-graph\.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `knowledge/` is ignored in life-graph. Task 2 relies on the directory still existing on disk (ignored ≠ deleted).

- [ ] **Step 1: Confirm the exposure exists (this is the failing test)**

```bash
cd /d/DevTools/Projects/life-graph
git check-ignore -v knowledge/startgold/00-index.md; echo "exit=$?"
```

Expected: no output, `exit=1` — meaning **NOT ignored**. This is the failure we are fixing.

- [ ] **Step 2: Confirm nothing has leaked yet**

```bash
git log --all --oneline -- knowledge | head -5
```

Expected: empty output (never committed). **If this prints commits, STOP** — the notes are already in history and need `git filter-repo` plus a force-push, which is outside this plan. Report to the user.

- [ ] **Step 3: Add the ignore rule**

Append to the end of `D:\DevTools\Projects\life-graph\.gitignore`:

```gitignore

# Cross-repo knowledge base — lives in the private ../knowledge-base repo.
# life-graph is PUBLIC and this directory has held candid analysis of client
# codebases. Never track it here. See docs/superpowers/specs/2026-07-21-codebase-knowledge-base-design.md
knowledge/
```

- [ ] **Step 4: Verify the rule works**

```bash
git check-ignore -v knowledge/startgold/00-index.md
```

Expected: `.gitignore:<N>:knowledge/	knowledge/startgold/00-index.md`

- [ ] **Step 5: Verify a bulk add cannot stage it**

```bash
git add -A --dry-run 2>&1 | grep -c "knowledge/"
```

Expected: `0`

- [ ] **Step 6: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore knowledge/ — public repo must not hold client notes

life-graph is public; knowledge/ has held candid security analysis of a
client codebase. The canonical home is the private knowledge-base repo."
```

---

### Task 2: Create the private hub repo and move startgold into it

**Files:**
- Create: `D:\DevTools\Projects\knowledge-base\.gitignore`
- Create: `D:\DevTools\Projects\knowledge-base\README.md` (placeholder; Task 3 fills it)
- Move: `D:\DevTools\Projects\life-graph\knowledge\startgold\*` → `D:\DevTools\Projects\knowledge-base\startgold\`

**Interfaces:**
- Consumes: Task 1's ignore rule (so the source dir is safe while being moved).
- Produces: hub repo at `/d/DevTools/Projects/knowledge-base` with remote `origin`, private, containing `startgold/`.

- [ ] **Step 1: Create the hub directory and initialise git**

```bash
mkdir -p /d/DevTools/Projects/knowledge-base
cd /d/DevTools/Projects/knowledge-base
git init -b main
```

- [ ] **Step 2: Add the .gitignore**

Create `D:\DevTools\Projects\knowledge-base\.gitignore`:

```gitignore
# OS / editor noise
Thumbs.db
.DS_Store
.vscode/
.idea/

# _mirror/ is generated from own repos by /kb-analyse. It IS committed so that
# a single ripgrep over this hub searches every app offline. Nothing else generated.
```

- [ ] **Step 3: Placeholder README so the first commit is meaningful**

Create `D:\DevTools\Projects\knowledge-base\README.md`:

```markdown
# Knowledge Base

Cross-repo knowledge about every application I work on. **Private** — contains candid
analysis of client codebases.

Registry, template and usage notes land in the next commit.
```

- [ ] **Step 4: First commit**

```bash
cd /d/DevTools/Projects/knowledge-base
git add .gitignore README.md
git commit -m "chore: initialise private knowledge base hub"
```

- [ ] **Step 5: Create the PRIVATE GitHub repo and push**

```bash
gh repo create knowledge-base --private --source=. --remote=origin --push
```

If that command is blocked by a permission prompt, create `knowledge-base` as a **private** repo in the GitHub UI under the `raja4lmx` account, then:

```bash
git remote add origin https://github.com/raja4lmx/knowledge-base.git
git push -u origin main
```

- [ ] **Step 6: Verify it is actually private (gate — do not proceed if this fails)**

```bash
gh repo view raja4lmx/knowledge-base --json isPrivate,visibility
```

Expected: `{"isPrivate":true,"visibility":"PRIVATE"}`

**If `isPrivate` is false, STOP.** Do not move client notes into a public repo. Fix visibility first:
`gh repo edit raja4lmx/knowledge-base --visibility private --accept-visibility-change-consequences`

- [ ] **Step 7: Move startgold out of life-graph**

```bash
mkdir -p /d/DevTools/Projects/knowledge-base/startgold
mv /d/DevTools/Projects/life-graph/knowledge/startgold/* /d/DevTools/Projects/knowledge-base/startgold/
rmdir /d/DevTools/Projects/life-graph/knowledge/startgold /d/DevTools/Projects/life-graph/knowledge
```

- [ ] **Step 8: Add the machine-readable header to the moved index**

In `D:\DevTools\Projects\knowledge-base\startgold\00-index.md`, insert as the very first line (above the `# StartGOLD` heading):

```markdown
<!-- kb:source=work/fin-tech kb:sha=3d98b9bc kb:branch=main kb:analysed=2026-07-21 -->
```

- [ ] **Step 9: Verify the move**

```bash
ls /d/DevTools/Projects/knowledge-base/startgold/ | wc -l          # expect 9
ls /d/DevTools/Projects/life-graph/knowledge 2>&1                  # expect "No such file or directory"
head -1 /d/DevTools/Projects/knowledge-base/startgold/00-index.md  # expect the kb: comment
```

- [ ] **Step 10: Commit**

```bash
cd /d/DevTools/Projects/knowledge-base
git add startgold/
git commit -m "docs: import startgold study notes from life-graph

Moved out of the public life-graph repo. Adds the machine-readable
kb: header so staleness tooling can track drift from work/fin-tech."
git push
```

---

### Task 3: Hub scaffolding — template, checklist, agent guide, registry skeleton

**Files:**
- Create: `knowledge-base/_template/00-index.md`
- Create: `knowledge-base/_template/CHECKLIST.md`
- Create: `knowledge-base/CLAUDE.md`
- Create: `knowledge-base/_cross/patterns.md`
- Create: `knowledge-base/_cross/stack-decisions.md`
- Create: `knowledge-base/_mirror/.gitkeep`
- Modify: `knowledge-base/README.md` (replace placeholder with the registry)

**Interfaces:**
- Consumes: hub repo from Task 2.
- Produces: `_template/00-index.md` (the shape every T1 card copies), `_template/CHECKLIST.md` (the questions `/kb-analyse` in Task 6 must answer), and the registry table in `README.md` that Task 4 fills.

- [ ] **Step 1: Write the doc template**

Create `D:\DevTools\Projects\knowledge-base\_template\00-index.md`:

```markdown
<!-- kb:source=PATH/REL/TO/PROJECTS_ROOT kb:sha=SHORTSHA kb:branch=BRANCH kb:analysed=YYYY-MM-DD -->
# <App Name> — Codebase Study Notes

Personal notes on **<App Name>** (repo: `<remote or owner/name>`).

- **Analysed:** YYYY-MM-DD, at commit `<shortsha>` (branch `<branch>`)
- **Source repo:** `d:/DevTools/Projects/<path>`
- **Related repos:** `<path>` (or "none")

> File references below are relative to the repo root.

---

## The 60-second version

<One paragraph: what the product is, for whom. Then one paragraph: what it is
technically — language, framework, topology, datastore.>

```
<ASCII architecture sketch: services, ports, datastores, external providers>
```

## Three things that will bite you first

1. **<Trap>.** <Why it bites, and the exact file that enforces it.>
2. **<Trap>.** <...>
3. **<Trap>.** <...>

## Data model

<The main entities and how they relate. Table count. Anything unusual about
schema ownership, migrations, or multi-tenancy.>

## Core flows

<The 2-5 flows that matter, each traced through real file paths.>

## Patterns & conventions

<The idioms you must internalise before writing code here. Naming, error
handling, auth, config, testing.>

## Where to look for X

| I want to… | Look at |
|---|---|
| <task> | `<path>` |

## Where the project's own docs live

<Any in-repo docs, and how much to trust them.>

Treat generated/in-repo docs as a **map, not as truth** — verify against source before
relying on a detail.

## Risks & gotchas

<Consolidated traps, inconsistencies, fragile spots.>
```

- [ ] **Step 2: Write the analysis checklist**

Create `D:\DevTools\Projects\knowledge-base\_template\CHECKLIST.md`:

```markdown
# T1 Analysis Checklist

Every question here must be answered (or explicitly marked "n/a") before a T1 card
is considered complete. Consistency across repos comes from this list.

## Identity
- [ ] What is the product, in one sentence a non-engineer understands?
- [ ] Who uses it? Is it live, prototype, or abandoned?
- [ ] Owner: own / client / third-party?
- [ ] Current branch + short SHA at time of analysis.
- [ ] Related repos (mobile companion, infra, design system)?

## Shape
- [ ] Language(s), framework(s), major libraries.
- [ ] Topology: monolith / services / monorepo? How many deployables?
- [ ] Datastores, caches, queues, external providers.
- [ ] How is it run locally? (exact command)
- [ ] How is it deployed?

## Data
- [ ] Main entities and relationships. Rough table/collection count.
- [ ] Who owns migrations? Any schema-ownership rules?
- [ ] Multi-tenancy or scoping model, if any.

## Behaviour
- [ ] The 2–5 flows that carry the product's value, traced to real files.
- [ ] Background work: jobs, crons, workers, webhooks.
- [ ] AuthN/AuthZ approach.

## Conventions
- [ ] Naming, file layout, error handling, response envelope.
- [ ] Testing approach and how to run tests.
- [ ] Anything a newcomer would get wrong on day one.

## Traps (mandatory — at least three)
- [ ] What silently fails?
- [ ] What only fails at runtime, never at dev time?
- [ ] What looks standard but is not?

## Meta
- [ ] Does the repo carry its own docs? How stale are they?
- [ ] Any candid/sensitive content here that means this doc must stay private?
```

- [ ] **Step 3: Write the hub agent guide**

Create `D:\DevTools\Projects\knowledge-base\CLAUDE.md`:

```markdown
# CLAUDE.md — Knowledge Base Hub

This repo is a **knowledge base about other codebases**. There is no application here.

**It is private.** It contains candid analysis of client codebases (`startgold` =
`LOGIMAX-CLIENTS/fin-tech`), including security gaps. Never copy this content into a
public repo, an issue, or a PR description.

## How to use it

1. **`README.md` is the registry** — every app I work on, one row each: what it is,
   stack, path, owner, status, depth, when it was last analysed. Start here.
2. **`<app>/` folders** hold docs for **client / third-party** apps, pinned to a commit SHA.
3. **`_mirror/<app>/`** holds read-only copies of **own** repos' docs, whose canonical
   location is `<repo>/docs/knowledge/`. Never edit `_mirror/` by hand.
4. **`_cross/patterns.md`** answers "how do I do X across all my apps" — read this for
   cross-project questions.

## Depth tiers

- **T0** — registry row only.
- **T1** — orientation card (`00-index.md`): 60-second version, architecture, traps, conventions.
- **T2** — subsystem deep dive. Written lazily, only when that subsystem matters.

## Rules

- Docs are **a map, not truth**. Verify against source before relying on a detail.
- Every doc's first line is `<!-- kb:source=… kb:sha=… kb:branch=… kb:analysed=… -->`.
  Keep it accurate; `scripts/kb-stale.sh` depends on it.
- For **own** repos, edit `<repo>/docs/knowledge/`, not `_mirror/`.
```

- [ ] **Step 4: Seed the cross-cutting notes**

Create `D:\DevTools\Projects\knowledge-base\_cross\patterns.md`:

```markdown
# Cross-App Patterns

How the same recurring concern is solved (or not) across every app. This is the file
that answers "where did I implement X?".

Add an entry the moment you notice a second app solving the same problem.

## Webhook authentication

- **life-graph** — HMAC-SHA256 signed delivery, `life_graph/core/events.py` → webhook dispatch.
- **startgold** — provider-specific verification, no shared verifier; see
  `startgold/06-payments-gateway-deep-dive.md`.

## Offline / queued writes

- **life-graph (mobile PWA)** — IndexedDB queue + service worker, `dashboard/lib/offline-queue.ts`.

## Multi-tenancy

- **life-graph** — `tenant_id` on every table, set from `X-Tenant-ID` via a contextvar
  (`life_graph/core/tenant.py`); every query filters by it.
- **startgold** — none; single-tenant with router-separated DB apps.

## Background jobs

- **life-graph** — ARQ workers + cron (`life_graph/workers/settings.py`).
- **startgold** — Celery worker + beat in `notification_service`.
```

Create `D:\DevTools\Projects\knowledge-base\_cross\stack-decisions.md`:

```markdown
# Recurring Stack Decisions

Choices made more than once, and why — so the next project does not re-litigate them.

| Concern | Choice | Where used | Why |
|---|---|---|---|
| Python API framework | FastAPI (async) | life-graph | Async-native, typed, auto docs |
| Frontend | Next.js + React | life-graph, uzhavu | Familiarity, one deploy target |
| LLM cost posture | Cheap models (Gemini Flash / DeepSeek), LLM as advisor not authority | life-graph | Self-hosted, cost-conscious |
```

- [ ] **Step 5: Create the mirror directory**

```bash
mkdir -p /d/DevTools/Projects/knowledge-base/_mirror
touch /d/DevTools/Projects/knowledge-base/_mirror/.gitkeep
```

- [ ] **Step 6: Replace the placeholder README with the registry**

Overwrite `D:\DevTools\Projects\knowledge-base\README.md`:

```markdown
# Knowledge Base

Cross-repo knowledge about every application I work on. **Private** — contains candid
analysis of client codebases.

- Agent usage: see `CLAUDE.md`
- Doc template: `_template/00-index.md` · analysis checklist: `_template/CHECKLIST.md`
- Cross-app answers: `_cross/patterns.md`
- Staleness report: `bash scripts/kb-stale.sh`

## Registry

`Owner`: own = docs live in that repo's `docs/knowledge/` (mirrored here under `_mirror/`).
client/third-party = docs live here in `<app>/`.
`Depth`: T0 registry only · T1 orientation card · T2 deep dives.

| App | What it is | Stack | Path | Owner | Status | Depth | Analysed |
|---|---|---|---|---|---|---|---|
| startgold | Digital gold/silver savings platform | Django monorepo, MySQL, Celery | `work/fin-tech` | client | active | T2 | 2026-07-21 `3d98b9bc` |
```

- [ ] **Step 7: Verify the structure**

```bash
cd /d/DevTools/Projects/knowledge-base
find . -path ./.git -prune -o -type f -print | sort
```

Expected to include: `./CLAUDE.md`, `./README.md`, `./_cross/patterns.md`,
`./_cross/stack-decisions.md`, `./_mirror/.gitkeep`, `./_template/00-index.md`,
`./_template/CHECKLIST.md`, and the 9 `./startgold/*.md` files.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: hub scaffolding — template, checklist, agent guide, registry"
git push
```

---

### Task 4: T0 registry sweep — every project directory

Fill one registry row for **every** directory under the projects root, including dormant
and unknown ones. A row reading "unknown, dormant" is still more useful than absence.

**Files:**
- Modify: `knowledge-base/README.md` (registry table)

**Interfaces:**
- Consumes: registry table skeleton from Task 3.
- Produces: the authoritative list of apps and their `Owner`/`Status`, which Task 8 uses to pick the second T1 repo.

- [ ] **Step 1: List the candidates**

```bash
ls -d /d/DevTools/Projects/*/ /d/DevTools/Projects/work/*/ 2>/dev/null
```

Known at planning time: `New folder`, `agentic`, `app`, `csharp-extension`, `lca`,
`life-graph`, `lr_cls`, `lr_saas`, `lr_saas - Copy`, `my_apps`, `study-planner`,
`uzhavu.race`, `uzhavu.race.worktrees`, `work`, `work/fin-tech`, `work/SIP`.

- [ ] **Step 2: Identify each one cheaply**

For each directory, spend **under two minutes**. Do not read source deeply — this is T0.

```bash
d=/d/DevTools/Projects/<name>
ls "$d" | head -20
head -20 "$d"/README.md 2>/dev/null
cat "$d"/package.json 2>/dev/null | head -15
cat "$d"/pyproject.toml 2>/dev/null | head -15
git -C "$d" log -1 --format='%h %ad %s' --date=short 2>/dev/null
git -C "$d" remote get-url origin 2>/dev/null
```

Use the last-commit date to *propose* `Status` (active if touched recently, dormant
otherwise), but **the developer confirms** active/dormant — do not decide alone.

- [ ] **Step 3: Add one row per directory**

Append rows to the registry table in `README.md`. Rules:
- `Owner` = `client` for anything under `work/`, `own` otherwise, unless the remote says otherwise.
- `Depth` = `T0` for all new rows.
- `Analysed` = `—` for T0 rows.
- Skip nothing. If a directory is unidentifiable, write `unknown` in "What it is" and
  `dormant?` in Status.
- Exclude `uzhavu.race.worktrees` if it is only git worktrees of `uzhavu.race` — note it
  in the `uzhavu.race` row instead.

Two rows that can be written as-is (already known), shown as the target quality bar —
every other row must reach this level of specificity, filled from Step 2's inspection:

```markdown
| life-graph | Brain-inspired memory + agent OS | FastAPI, Next.js, Postgres/pgvector | `life-graph` | own | active | T0 | — |
| SIP | StartGOLD companion mobile app | Flutter | `work/SIP` | client | active | T0 | — |
```

No row may be left with a bracketed blank. If Step 2 genuinely cannot identify a
directory, write `unknown` / `dormant?` — those are real answers; `<fill>` is not.

- [ ] **Step 4: Ask the developer to confirm active/dormant**

Present the table and ask which repos are **active** (work expected in the foreseeable
future). Update `Status` from their answer. This gates Task 8's repo choice.

- [ ] **Step 5: Verify every directory is represented**

```bash
cd /d/DevTools/Projects/knowledge-base
for d in $(ls -d /d/DevTools/Projects/*/ /d/DevTools/Projects/work/*/ 2>/dev/null); do
  n=$(basename "$d")
  grep -q -- "$n" README.md || echo "MISSING from registry: $n"
done
```

Expected: no `MISSING` lines (except any intentionally folded in, e.g. `uzhavu.race.worktrees`).

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: T0 registry rows for every project directory"
git push
```

---

### Task 5: `kb-stale.sh` — drift reporting

**Files:**
- Create: `knowledge-base/scripts/kb-stale.sh`
- Test: `knowledge-base/scripts/test-kb-stale.sh`

**Interfaces:**
- Consumes: the `<!-- kb:source=… kb:sha=… -->` header written by Task 2 and the template from Task 3.
- Produces: `bash scripts/kb-stale.sh` printing one line per doc: `<app>: <N> commits behind (<sha>..HEAD)`, and `scripts/kb-stale.sh` used by the `/kb-analyse` skill in Task 6.

- [ ] **Step 1: Write the failing test**

Create `D:\DevTools\Projects\knowledge-base\scripts\test-kb-stale.sh`:

```bash
#!/usr/bin/env bash
# Test for kb-stale.sh. Builds a throwaway source repo + a doc pinned to its
# first commit, then asserts the script reports the right drift.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $1"; exit 1; }

# Fake projects root: <TMP>/projects, hub at <TMP>/projects/kb
mkdir -p "$TMP/projects/demoapp" "$TMP/projects/kb/demoapp"
cd "$TMP/projects/demoapp"
git init -q -b main; git config user.email t@t; git config user.name t
echo one > a.txt; git add .; git commit -qm one
SHA=$(git rev-parse --short HEAD)
echo two > b.txt; git add .; git commit -qm two
echo three > c.txt; git add .; git commit -qm three

cat > "$TMP/projects/kb/demoapp/00-index.md" <<EOF
<!-- kb:source=demoapp kb:sha=$SHA kb:branch=main kb:analysed=2026-01-01 -->
# Demo
EOF

OUT="$(bash "$HERE/kb-stale.sh" "$TMP/projects/kb" 2>&1)"

echo "$OUT" | grep -q "demoapp" || fail "no demoapp line in output: $OUT"
echo "$OUT" | grep -q "2 commits behind" || fail "expected '2 commits behind', got: $OUT"

# Up-to-date doc reports 0
CUR=$(git rev-parse --short HEAD)
sed -i "s/kb:sha=$SHA/kb:sha=$CUR/" "$TMP/projects/kb/demoapp/00-index.md"
OUT2="$(bash "$HERE/kb-stale.sh" "$TMP/projects/kb" 2>&1)"
echo "$OUT2" | grep -q "up to date" || fail "expected 'up to date', got: $OUT2"

echo "PASS"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /d/DevTools/Projects/knowledge-base
bash scripts/test-kb-stale.sh
```

Expected: FAIL — `kb-stale.sh: No such file or directory`

- [ ] **Step 3: Write the script**

Create `D:\DevTools\Projects\knowledge-base\scripts\kb-stale.sh`:

```bash
#!/usr/bin/env bash
# kb-stale.sh — report how far each knowledge doc has drifted from its source repo.
#
# Usage: bash scripts/kb-stale.sh [HUB_DIR]
#   HUB_DIR defaults to the repo this script lives in.
#
# Reads the header on each doc:
#   <!-- kb:source=<path-rel-to-projects-root> kb:sha=<sha> ... -->
# Projects root is the hub's parent directory.
set -u

HUB="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
ROOT="$(cd "$HUB/.." && pwd)"
status=0

while IFS= read -r doc; do
  header="$(head -1 "$doc")"
  case "$header" in *kb:source=*) ;; *) continue ;; esac

  src="$(printf '%s' "$header" | sed -n 's/.*kb:source=\([^ ]*\).*/\1/p')"
  sha="$(printf '%s' "$header" | sed -n 's/.*kb:sha=\([^ ]*\).*/\1/p')"
  name="$(basename "$(dirname "$doc")")"
  repo="$ROOT/$src"

  if [ ! -d "$repo/.git" ]; then
    echo "$name: SOURCE MISSING ($src)"; status=1; continue
  fi
  if ! git -C "$repo" cat-file -e "${sha}^{commit}" 2>/dev/null; then
    echo "$name: SHA $sha not found in $src (rebased or wrong repo?)"; status=1; continue
  fi

  behind="$(git -C "$repo" rev-list --count "$sha"..HEAD 2>/dev/null || echo '?')"
  if [ "$behind" = "0" ]; then
    echo "$name: up to date ($sha)"
  else
    echo "$name: $behind commits behind ($sha..HEAD)"
    status=1
  fi
done < <(find "$HUB" -name '*.md' -not -path '*/.git/*' -not -path '*/_template/*')

exit $status
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /d/DevTools/Projects/knowledge-base
bash scripts/test-kb-stale.sh
```

Expected: `PASS`

- [ ] **Step 5: Run it for real**

```bash
bash scripts/kb-stale.sh
```

Expected: a line for `startgold`, e.g. `startgold: 0 commits behind` or `startgold: N commits behind (3d98b9bc..HEAD)`. A non-zero exit code just means "something is stale" — that is informational, not an error.

- [ ] **Step 6: Commit**

```bash
git add scripts/
git commit -m "feat: kb-stale.sh drift report + test"
git push
```

---

### Task 6: The `/kb-analyse` skill

A **user-level** skill (available in every project, not just one repo).

**Files:**
- Create: `C:\Users\admin\.claude\skills\kb-analyse\SKILL.md`

**Interfaces:**
- Consumes: `_template/00-index.md`, `_template/CHECKLIST.md` (Task 3), `scripts/kb-stale.sh` (Task 5), registry in `README.md` (Task 4).
- Produces: `/kb-analyse <path>` — the command Tasks 7 and 8 invoke.

- [ ] **Step 1: Write the skill**

Create `C:\Users\admin\.claude\skills\kb-analyse\SKILL.md`:

```markdown
---
name: kb-analyse
description: Analyse an application codebase and write or refresh its knowledge-base card. Use when the user asks to document, analyse, or onboard onto a repo, or says "kb this repo", "/kb-analyse", or asks to refresh existing knowledge docs.
---

# kb-analyse

Produce a **T1 orientation card** for an application codebase, in the shape of the
knowledge-base template, and register it.

**Hub:** `D:\DevTools\Projects\knowledge-base` · **Projects root:** `D:\DevTools\Projects`

## Inputs

`$ARGUMENTS` is the repo path, absolute or relative to the projects root
(e.g. `uzhavu.race` or `work/SIP`). If missing, ask which repo.

## Where the output goes — decide FIRST

Read the repo's row in the hub `README.md` registry.

- **Owner = own** → canonical doc is `<repo>/docs/knowledge/00-index.md` (committed in
  that repo), then copy it to `<hub>/_mirror/<app>/00-index.md`.
- **Owner = client / third-party** → doc lives at `<hub>/<app>/00-index.md`. **Never**
  write into the client repo.

If the repo is not in the registry, add a row first.

## Refresh vs. create

If the target doc already exists, this is a **refresh**: update the content in place and
bump `kb:sha`/`kb:analysed`. Preserve any T2 deep-dive files untouched.

## Procedure

1. **Pin the commit.** In the repo: `git rev-parse --short HEAD` and
   `git rev-parse --abbrev-ref HEAD`. Record both.
2. **Survey cheaply first** — `README`, `package.json` / `pyproject.toml` / `pubspec.yaml`,
   directory layout, entry points, config, migrations, CI. Prefer breadth over depth.
3. **Walk `_template/CHECKLIST.md`.** Every question answered or explicitly `n/a`.
   The **Traps** section needs at least three real entries — if you cannot find three,
   you have not read enough.
4. **Write the card** using `_template/00-index.md` as the skeleton. First line must be:
   `<!-- kb:source=<rel-path> kb:sha=<sha> kb:branch=<branch> kb:analysed=<YYYY-MM-DD> -->`
5. **Update the registry row** in the hub `README.md`: set `Depth` to `T1` and `Analysed`
   to the date + SHA.
6. **Mirror** (own repos only): copy the card to `<hub>/_mirror/<app>/`.
7. **Add cross-app entries.** If this app solves a concern already listed in
   `_cross/patterns.md`, add its line. If it introduces a new recurring concern, add a
   section.
8. **Verify:** `bash scripts/kb-stale.sh` shows the app `up to date`.

## Style

Match the existing `startgold/` notes:

- Narrative prose a human enjoys, not bullet soup. Opinionated and candid.
- **Exact file paths** for every claim, so an agent can act on it.
- Lead with the **60-second version**, then **"Three things that will bite you first"** —
  this section is mandatory and is the highest-value part of the doc.
- Include an ASCII architecture sketch.
- Close with the caveat verbatim: docs are **"a map, not truth — verify against source
  before relying on a detail."**

## Limits

- **T1 only.** ~150–250 lines. Do **not** write T2 subsystem deep dives unless explicitly
  asked — they are written lazily, when that subsystem actually matters.
- Never copy secrets, credentials, `.env` contents, or customer data into a doc.
- Client analysis is sensitive: it stays in the private hub, never in the client repo and
  never in a public repo.
- Report what you could not determine rather than guessing. "Unclear how X works" is a
  useful, honest line.
```

- [ ] **Step 2: Verify the skill is discoverable**

Start a fresh Claude Code session and run `/kb-analyse` with no arguments.

Expected: the skill loads and asks which repo to analyse (rather than "unknown command").

- [ ] **Step 3: Commit a copy into the hub for versioning**

The live skill must sit in `~/.claude/skills/` to be discoverable, but keep a tracked copy so it is backed up and reviewable:

```bash
mkdir -p /d/DevTools/Projects/knowledge-base/skills/kb-analyse
cp /c/Users/admin/.claude/skills/kb-analyse/SKILL.md \
   /d/DevTools/Projects/knowledge-base/skills/kb-analyse/SKILL.md
cd /d/DevTools/Projects/knowledge-base
git add skills/
git commit -m "feat: /kb-analyse skill (tracked copy; live copy in ~/.claude/skills)"
git push
```

---

### Task 7: First T1 card — life-graph (proves the **own-repo** path)

**Files:**
- Create: `life-graph/docs/knowledge/00-index.md`
- Create: `knowledge-base/_mirror/life-graph/00-index.md`
- Modify: `life-graph/CLAUDE.md` (add the pointer)
- Modify: `knowledge-base/README.md` (life-graph row → T1)

**Interfaces:**
- Consumes: `/kb-analyse` from Task 6.
- Produces: a worked example of the own-repo path (in-repo canonical + hub mirror) for Task 8 to follow.

- [ ] **Step 1: Run the skill**

```
/kb-analyse life-graph
```

life-graph is `Owner = own`, so the card goes to `life-graph/docs/knowledge/00-index.md`.

Rich existing material to draw on — but **verify against source, do not just summarise**:
`START_HERE.md`, `KNOWLEDGE.md`, `AGENTS.md`, `CLAUDE.md`, `docs/specs/`.

- [ ] **Step 2: Check the card against the checklist**

Confirm every `_template/CHECKLIST.md` question is answered or marked `n/a`, and that
**Traps** has at least three entries. Good candidates already known:

- Every DB query must filter by `tenant_id` (contextvar, `life_graph/core/tenant.py`) — a
  missing filter leaks across tenants and nothing catches it.
- `metadata` is reserved by SQLAlchemy declarative and can never be a column name.
- Era-8 status/result values are constrained by DB CHECKs (`ck_aa_status`, `ck_aq_status`,
  `ck_al_result`) — invalid values fail only at insert time.

- [ ] **Step 3: Add the pointer to life-graph's CLAUDE.md**

In `D:\DevTools\Projects\life-graph\CLAUDE.md`, in the "Orientation" section, add
`docs/knowledge/00-index.md` to the list of onboarding docs:

```markdown
- **docs/knowledge/00-index.md** — orientation card: 60-second version, architecture sketch,
  and the traps that bite newcomers first. Mirrored to the private `knowledge-base` hub.
```

- [ ] **Step 4: Mirror into the hub**

```bash
mkdir -p /d/DevTools/Projects/knowledge-base/_mirror/life-graph
cp /d/DevTools/Projects/life-graph/docs/knowledge/00-index.md \
   /d/DevTools/Projects/knowledge-base/_mirror/life-graph/00-index.md
```

- [ ] **Step 5: Verify**

```bash
head -1 /d/DevTools/Projects/life-graph/docs/knowledge/00-index.md   # kb: header present
wc -l /d/DevTools/Projects/life-graph/docs/knowledge/00-index.md     # expect ~150-250
cd /d/DevTools/Projects/knowledge-base && bash scripts/kb-stale.sh | grep life-graph
```

Expected: last command prints `life-graph: up to date (<sha>)`.

- [ ] **Step 6: Commit both repos**

```bash
cd /d/DevTools/Projects/life-graph
git add docs/knowledge/00-index.md CLAUDE.md
git commit -m "docs: add knowledge orientation card + CLAUDE.md pointer"

cd /d/DevTools/Projects/knowledge-base
git add _mirror/life-graph README.md
git commit -m "docs: mirror life-graph T1 card; registry -> T1"
git push
```

---

### Task 8: Second T1 card (proves the skill generalises)

**Files:**
- Create: either `<own-repo>/docs/knowledge/00-index.md` + `knowledge-base/_mirror/<app>/00-index.md`, **or** `knowledge-base/<app>/00-index.md` if the chosen repo is client/third-party
- Modify: `knowledge-base/README.md` (that app's row → T1)
- Modify: `<own-repo>/CLAUDE.md` if the repo is own and has one

**Interfaces:**
- Consumes: `/kb-analyse` (Task 6), the registry `Status` column confirmed in Task 4 Step 4.
- Produces: evidence the workflow works on a repo the author has *not* just been working in.

- [ ] **Step 1: Pick the repo**

Choose the highest-value repo marked **active** in the Task 4 registry, other than
life-graph. Default to `uzhavu.race` if it is active (it is the source of the `uzhavu`
design system already used by life-graph's dashboard). Confirm the choice with the
developer before spending a session on it.

- [ ] **Step 2: Run the skill**

```
/kb-analyse <chosen-path>
```

Follow the owner rule: `own` → in-repo + mirror; `client` → hub only.

- [ ] **Step 3: Check against the checklist**

Every question answered or `n/a`; at least three real Traps.

This repo is less familiar than life-graph, so explicitly list what could **not** be
determined rather than guessing.

- [ ] **Step 4: Wire the pointer (own repos only)**

If the repo has a `CLAUDE.md`, add:

```markdown
- **docs/knowledge/00-index.md** — orientation card: architecture, conventions, and the
  traps that bite first.
```

If it has no `CLAUDE.md`, create one containing just that pointer plus a one-line
description of the project.

- [ ] **Step 5: Verify**

```bash
cd /d/DevTools/Projects/knowledge-base
bash scripts/kb-stale.sh
grep -c '| T1 |' README.md
```

Expected: the new app reports `up to date`; `grep -c` returns `2` (life-graph + this one).

- [ ] **Step 6: Commit**

```bash
# in the analysed repo, if own:
git add docs/knowledge/00-index.md CLAUDE.md
git commit -m "docs: add knowledge orientation card + CLAUDE.md pointer"

cd /d/DevTools/Projects/knowledge-base
git add -A
git commit -m "docs: T1 card for <app>"
git push
```

---

### Task 9: Client-repo agent wiring + end-to-end verification

Prime agents inside a client repo **without leaving any trace in the client's git history**.

**Files:**
- Create: `D:\DevTools\Projects\work\fin-tech\CLAUDE.md` (local only — never committed)
- Modify: `D:\DevTools\Projects\work\fin-tech\.git\info\exclude`

**Interfaces:**
- Consumes: hub docs at `knowledge-base/startgold/` (Task 2).
- Produces: the documented pattern for every future client repo.

- [ ] **Step 1: Exclude the file BEFORE creating it**

Order matters — exclude first so the file is never visible to git, not even briefly.

Append to `D:\DevTools\Projects\work\fin-tech\.git\info\exclude`:

```gitignore
# Local-only agent guide pointing at my private knowledge base.
# .git/info/exclude is never committed or pushed — this stays out of the client's repo.
CLAUDE.md
```

- [ ] **Step 2: Create the local agent guide**

Create `D:\DevTools\Projects\work\fin-tech\CLAUDE.md`:

```markdown
# CLAUDE.md — local only, not part of this repository

This file is excluded via `.git/info/exclude`. Do not `git add -f` it.

## Before working here, read the study notes

Detailed notes on this codebase live **outside** this repo, in a private knowledge base:

`D:\DevTools\Projects\knowledge-base\startgold\`

- `00-index.md` — start here: 60-second version, architecture, the three things that bite first
- `02-data-model.md`, `03-core-flows.md`, `04-patterns-and-conventions.md`
- `05-sip-deep-dive.md`, `06-payments-gateway-deep-dive.md`, `07-security-deep-dive.md`
- `08-risks-and-gotchas.md`

Those notes are **a map, not truth** — verify against source before relying on a detail.

## Client-work rules

- This is a **client** repository (`LOGIMAX-CLIENTS/fin-tech`). Never commit personal notes,
  analysis, or this file into it.
- Analysis of this codebase — especially security findings — belongs only in the private
  knowledge base. Never in a public repo, issue, or PR description.
```

- [ ] **Step 3: Verify git cannot see it**

```bash
cd /d/DevTools/Projects/work/fin-tech
git status --porcelain | grep CLAUDE.md; echo "grep exit=$?"
git check-ignore -v CLAUDE.md
```

Expected: `grep exit=1` (no output — git does not see it) and `check-ignore` naming
`.git/info/exclude`.

- [ ] **Step 4: Verify the whole system end-to-end**

Security gates:

```bash
gh repo view raja4lmx/knowledge-base --json isPrivate       # {"isPrivate":true}
cd /d/DevTools/Projects/life-graph
git check-ignore -v knowledge/ ; git log --all --oneline -- knowledge | head -1
```

Expected: hub private; `knowledge/` ignored in life-graph; no commits ever touched it.

Cross-project recall (C) — a real question answered from the hub alone:

```bash
cd /d/DevTools/Projects/knowledge-base
rg -i "webhook" _cross/ _mirror/ startgold/ -l
```

Expected: matches in `_cross/patterns.md` and at least one app doc.

Staleness:

```bash
bash scripts/kb-stale.sh
```

Expected: one line per T1/T2 app; life-graph and the Task 8 app `up to date`.

Agent priming (B) — the real test. In a **fresh** session in `work/fin-tech`, ask:
"What is this codebase and what will bite me first?"

Expected: it answers from `knowledge-base/startgold/00-index.md` — the three traps
(migrations only from `admin_service`; no cross-DB-app JOINs; HTTP status codes rewritten
to 200) — **without** exploring the source tree first.

- [ ] **Step 5: Record the client-wiring pattern in the hub**

Append to `D:\DevTools\Projects\knowledge-base\CLAUDE.md`:

```markdown
## Priming agents inside a client repo

Client repos cannot carry a committed `CLAUDE.md`. The pattern:

1. Append `CLAUDE.md` to the repo's `.git/info/exclude` **first** (never committed, never pushed).
2. Then create a local `CLAUDE.md` pointing at this hub's `<app>/` folder.
3. Verify with `git status --porcelain | grep CLAUDE.md` — it must return nothing.

Applied to: `work/fin-tech`.
```

- [ ] **Step 6: Commit**

```bash
cd /d/DevTools/Projects/knowledge-base
git add CLAUDE.md
git commit -m "docs: record the client-repo agent wiring pattern"
git push
```

---

## Done when

- The hub exists, is **private**, and holds the registry, template, checklist, cross-app
  notes, `startgold/`, and mirrors.
- `life-graph` can no longer stage `knowledge/`, and never did.
- Every project directory has a T0 registry row with a confirmed `Status`.
- Two apps have T1 cards — one via the own-repo path, one proving it generalises.
- `/kb-analyse` exists at user level and produced both cards.
- `bash scripts/kb-stale.sh` reports drift, with a passing test.
- A cold agent session in `work/fin-tech` answers "what will bite me?" from the notes.

## Explicitly out of scope

Remaining T1 cards, **all** T2 deep dives, growing `_cross/patterns.md` beyond its seed,
and ingesting the hub into Life Graph. These are ongoing content work — the system must be
complete and useful with only two T1 cards.
