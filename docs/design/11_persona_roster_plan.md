# 11. Persona Roster Plan

> **Status:** Agreed 2026-10-20 — building in the order below. | **Date:** 2026-10-20
>
> One plan per persona before building: what it is for, what triggers it, what it may
> touch, which model runs it, how far it may act alone, and how we will know it works.
> Facts in "Today" are from the live database (tenant `raja`, last 30 days) and the
> 2026-10-12 survey.

---

## The problems across the roster

1. **Too many overlapping roles.** 20 personas; three "front doors" (chief, jarvis,
   assistant), three coordinators (chief, jarvis, swe-lead), two infra roles (ops,
   uzhavu-ops), and a conversational coder (cody) beside five code-fixer engines.
2. **Most run on a model that does not call tools.** 15 personas use `qwen3:14b`. Scout's
   last three runs answered in one token with no search at all; the driver benchmark had
   qwen3:14b refuse 41 of 60 edits. `gpt-oss:20b` scored 11/12 and calls tools reliably.
3. **Tools that do not exist here.** `run_command` is disabled on this machine, yet it is
   the *only* tool of `ops` and most of `penny`'s — those personas cannot do their job.
4. **No way to know a persona works.** The coding engines have a benchmark with hidden
   tests; no other persona has any measure, so regressions are invisible.
5. **Ambient jobs run for the wrong tenant.** scout/admin run daily for `default`, not
   `raja`, with an empty watch-list.

## The shape I propose

Every persona gets five things written down (and enforced where code can enforce it):

| Field | Meaning |
|---|---|
| **Job** | One sentence; if two personas share it, one goes. |
| **Trigger** | You (chat/Telegram/voice), a schedule, or another persona. |
| **Autonomy** | `answer` (talks only) · `report` (read-only, scheduled) · `propose` (files approvals) · `act` (changes things, behind the quality gates). |
| **Model** | Local by default; the engine for tool-using roles is `gpt-oss:20b`. Personal data never goes to a cloud model (CHARTER invariant 7). |
| **Eval** | 5–10 golden tasks with a deterministic check, run like the driver benchmark — before and after every change to the persona. |

---

## Front door — the one you talk to

### `assistant` → **your front door** (keep, make primary)
- **Today:** 20 tools (memory, calendar, mail, contacts, bills, money, documents, monitors,
  study, invoices, web). 2 runs. On qwen3:14b.
- **Job:** answer anything about your life and work from your own data and the web; hand
  off to a specialist when the request needs one.
- **Trigger:** chat, Telegram, voice (tamil-ai). **Autonomy:** `answer`, plus `propose`
  for anything that writes (a page monitor, study cards).
- **Model:** gpt-oss:20b (tool calls). Tamil/Tanglish quality to be checked in its eval;
  if gpt-oss is weak in Tamil, voice turns stay on tamil-ai's gemma3 and only tool calls
  route here.
- **Eval:** 10 questions with known answers from your data ("what bills are due this
  week", "when does my car insurance expire", one Tamil question) + one web question.
- **Changes:** model switch; add `delegate_to_persona` so it can hand off to the specialists
  below; make it the persona Telegram and voice use.

### `chief` → **retire as a persona; keep as code**
- **Today:** no tools, 0 runs. Routes chat by intent tags (the `get_by_intent` lookup).
- **Plan:** routing stays deterministic code (CHARTER invariant 1); no LLM persona needed.

### `jarvis` → **merge into `assistant`** (decision needed)
- **Today:** 35 tools — everything — on `claude-cli`, which has no tool access and needs
  your Claude login. 8 runs.
- **Plan:** `assistant` + `delegate_to_persona` covers it. Keep jarvis only if you want a
  "Claude-powered" mode for hard questions while the subscription bridge lasts.

### `swe-lead` → **merge into `cody`**
- **Today:** delegates and runs shell; 2 runs. Its job (coordinate engineering work) is
  what cody + the dev-task plans already do.

---

## Research & knowledge

### `scout` → **topic watcher** (keep, rebuild — the feature you asked for)
- **Today:** runs daily for `default`, empty topics, last runs fetched nothing.
- **Job:** watch your topics on the internet and report what is genuinely new.
- **Trigger:** schedule — news every 2–3 h, model catalogs daily. **Autonomy:** `report`.
- **How:** code gathers (SearXNG news, HN, Reddit, GitHub, feeds, OpenRouter/NVIDIA
  catalog diffs) and de-duplicates; scout judges relevance, extracts facts, writes findings
  with verified sources. First topics: free LLM offers, local/open models, AI coding
  agents. Evaluation of a promising model is a separate job → an approval for you.
- **Model:** gpt-oss:20b. **Eval:** a frozen set of 30 crawled items with labelled
  "relevant / not / duplicate" — precision and recall, plus "every finding cites a fetched URL".

### `rex` → **on-demand researcher** (keep)
- **Today:** 27 completed runs — the most-used non-coding persona. web_search + memory.
- **Job:** answer a research question now, with sources. **Autonomy:** `answer`.
- **Changes:** model switch; add `browse_web` (it can search but not read pages);
  same source-verification as scout. **Eval:** 8 questions with checkable facts.

### `tutor` → **study coach** (keep, opt-in)
- **Today:** off; web + memory + due cards.
- **Job:** your study plan: what is due, quiz you, make cards from what you are learning.
- **Changes:** add `make_study_cards`; turn on its daily nudge only if you want it.
- **Eval:** given notes, the cards it makes pass a "front/back answerable" check.

### `scribe` → **docs writer** (keep)
- **Today:** the one persona that worked in the 2026-10-12 survey. file read/write + memory.
- **Changes:** run through the dev-task pipeline (worktree, checks, PR) instead of writing
  files directly — docs-only changes already earn their own trust (change_policy `docs`).

---

## Life admin & business

### `admin` → **daily life-admin sweep** (keep)
- **Today:** works — 19 completed runs, 13 read-only tools (calendar, mail, bills, tasks).
  Runs for `default`, not you.
- **Changes:** run for `raja`; model switch; report into the daily brief. **Eval:** a fixed
  inbox/calendar fixture with 5 known follow-ups it must surface.

### `penny` → **money & data analyst** (repurpose)
- **Today:** "analyzes data, queries databases" with only `run_command` (disabled) and file
  tools — cannot work.
- **Plan:** give it the money tools (spending summary, budgets, transactions) and read-only
  memory; job: "where does my money go, what changed this month, what to cut". `answer`.

### `support-desk` → **customer support for your apps** (keep, commercial)
- **Today:** reads one project's docs; 0 runs.
- **Plan:** keep for the product goal (uzhavu customers). **Eval:** 10 support questions
  per app with answers in its docs; must refuse what the docs do not cover.

---

## Engineering

### The code-fixer engines (keep; they are engines, not chat personas)
| Engine | Role | Keep? |
|---|---|---|
| `code-fixer-local` (gpt-oss:20b) | default nightly/queue engine | yes |
| `code-fixer-opencode` (qwen3-coder:30b) | escalation for harder tasks | yes — but its persona row says qwen3:14b; OpenCode uses `driver_opencode_model`, so fix the row to avoid confusion |
| `code-fixer-cloud` (free models) | daytime, when the GPU is yours | yes |
| `code-fixer` (claude_code) | paid bridge for hard tasks | yes, until fully local (LLM transition plan) |
| `code-fixer-auto` | picks an engine per project by record | yes |

All behind Tier 1–3 gates (trust per kind, protected paths, proof checks).

### `cody` → **your coding partner in chat** (keep, absorbs swe-lead)
- **Today:** file/shell/git tools; shell is disabled; relative paths rejected.
- **Job:** discuss code, read it (code_read/search), and turn decisions into dev tasks or
  plans for the engines — it does not edit files itself. **Autonomy:** `propose`.
- **Eval:** 6 "where is X / why does Y" questions on life-graph with checkable answers.

### `ops` + `uzhavu-ops` → **one `ops`** (merge)
- **Today:** ops has only the disabled shell; uzhavu-ops is uzhavu-specific on claude_code, 0 runs.
- **Plan:** one ops persona with project context (any registered project), read-only health
  tools (`inspect_system`, the uptime/server-health watchers' data); deploys stay human-approved
  (`driver_deploy`, never auto). **Autonomy:** `report` + `propose`.

### `dependency-updater` → **move to the free engines** (keep)
- **Today:** claude_code (paid), 0 runs.
- **Plan:** run on code-fixer-local/opencode from dependency-watcher findings; dependency
  files are protected paths, so every upgrade waits for you anyway.

---

## Result

| | Today | Proposed |
|---|---|---|
| Personas you talk to | assistant, chief, jarvis, cody, rex, penny, scribe, tutor, ops, swe-lead | **assistant** (front door) + specialists it hands off to: rex, cody, penny, tutor, scribe, ops |
| Scheduled | scout, admin (wrong tenant), tutor/ops/cody (off) | **scout** (topics), **admin** (daily), tutor (opt-in) |
| Engines | 5 code-fixers + dependency-updater | same, all gated |
| Retired / merged | — | chief (→ code), jarvis (→ assistant, decision), swe-lead (→ cody), uzhavu-ops (→ ops) |
| Measured | coding engines only | every persona has an eval |

## How the team coordinates

A small team that organises itself — not a swarm of hundreds. One 16 GB GPU runs one large
model at a time and free cloud tiers allow ~20 requests a minute, so the team is 3–8 agents
working in parallel where parallel work pays, and in sequence otherwise.

What we take from the systems that do this (researched 2026-10-20):

| Source | Idea we adopt |
|---|---|
| Grok 4 Heavy / 4.20 (xAI): parallel copies of one model debate one problem | **Heavy mode** for hard decisions — but with *different* models, which disagree more usefully than copies |
| Kimi Agent Swarm (Moonshot): up to 100–300 parallel sub-agents on wide tasks | **Fan-out only for wide work** (many topics, sources, sub-questions), merged and checked |
| Anthropic's research system: lead agent writes precise briefs; ~15× tokens for ~90% better wide research | **Leads write briefs** (goal, output format, tools, boundaries); parallelism only where it is worth the cost |
| Blackboard systems: agents read a shared board and volunteer for work | **A team board** with claims, so agents self-select and never duplicate work |

### The pieces

1. **Team board.** Built on what exists: the memory graph (shared knowledge), `agent_tasks`
   (work items), the event bus (notifications) and approvals (decisions that are yours).
   A posted item states what is needed and what "done" means; an agent **claims** it before
   starting (an atomic claim, so two agents never take the same item — the lesson of the
   979 duplicate tasks); results are posted back as findings or artifacts.
2. **Teams with leads.**
   - **Life:** `assistant` leads `admin`, `penny`, `tutor`.
   - **Research:** `rex` leads; `scout` workers fan out per topic/source.
   - **Engineering:** `cody` leads the code-fixer engines and a reviewer.
   Leads talk to each other through the board. You see approvals, not chatter.
3. **Briefs.** Every hand-off is a typed brief: objective, inputs, output format, tools
   allowed, boundaries, budget. A worker that cannot meet the brief says so instead of guessing.
4. **Fan-out / fan-in.** For wide work only: one worker per topic, source or sub-question,
   run in parallel on free cloud models (or one GPU slot each at night), then merged by the
   lead and checked (sources fetched, tests pass, findings de-duplicated).
5. **Heavy mode.** For a hard or high-stakes question: three different models answer
   independently, critique each other once, and the answer is decided by a deterministic
   check where one exists (tests, verified sources) and by the lead otherwise. Used for code
   review, important research answers, and judging a promising offer — not for everyday chat.
6. **Who is good at what.** Persona evals and the trust records feed routing: a lead sends
   work to the agent with the best record for that kind of task, and that record changes as
   results come in.
7. **Guardrails.** A time/token budget per task and per run; a maximum delegation depth
   (the process manager already caps it at 5); every step recorded (trajectories); code
   still passes the Tier 1–3 quality gates; the compute router decides where each worker
   runs; personal data never reaches a cloud model.

### Free and freemium providers

Free cloud capacity makes the team affordable in the daytime; it is not what the team stands
on. Rules:

- **One account per provider, within that provider's limits.** Rotating across *different*
  providers is how failover already works (resilient_llm benches a rate-limited model and
  tries the next). Multiple accounts or keys on one provider to get around its limits is
  out: it breaks most terms of service and gets accounts banned.
- **Local is the base.** Free tiers come and go (Qwen3 Coder left OpenRouter's free list in
  July 2026). When none is available, work waits for the GPU — never a paid fallback.
- **Code only, never personal data** (CHARTER invariant 7).
- **Terms recorded per provider** when it is evaluated: does it train on prompts, is
  commercial/production use allowed. Free tiers serve our own development and research; a
  product sold to customers runs on local models or paid APIs.
- **Router additions:** per-provider daily quotas tracked so load is spread before limits hit;
  a provider that fails re-evaluation or changes its terms drops out of the list.
- **Discovery** is scout's free-LLM-offers topic; **adoption** is an approval for you with the
  benchmark results attached.

## Build order (after this plan is agreed)

1. **Persona evals** — the harness first, so every later change is measured (including
   whether a team beats a single agent).
2. **Model switch** for tool-using personas (gpt-oss:20b), measured by step 1.
3. **Team board + briefs + claims** — the coordination layer every team uses.
4. **scout topic watches** as the first fan-out team (research lead + topic workers), with
   the model-evaluation job and provider quotas/terms in the router.
5. **assistant as front door** (Life team lead; delegation, Telegram/voice routing).
6. **Heavy mode** for review and high-stakes answers.
7. Merges/retirements (chief, swe-lead, uzhavu-ops; jarvis per your decision), penny repurpose.
8. admin/scout to tenant `raja`, daily brief wiring.

## Decisions (the owner, 2026-10-20)

1. **jarvis:** merged into `assistant`, which becomes the single front door.
2. **chief** retired (routing stays code); **swe-lead** merged into `cody`; **uzhavu-ops**
   merged into one `ops` for all projects.
3. **penny:** money analyst (read-only money tools).
4. **tutor:** daily nudge on.
5. **support-desk:** kept, for the product goal.

Free-tier rules as above: one account per provider within its limits, local as the base,
code only, terms recorded per provider. Adoption of a newly found model is an approval.
