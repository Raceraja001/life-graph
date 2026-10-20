# 11. Jarvis and its workers

> **Status:** Revised 2026-10-20 (supersedes the first roster of six personas) — for the
> owner's final review before building. | **Date:** 2026-10-20
>
> The owner's direction: one lead, **Jarvis**; everything else is created dynamically, the
> way Grok Heavy and Kimi's agent swarm create agents per task, instead of a fixed roster.

---

## Why this replaces the roster

The first plan consolidated 20 personas into six. The owner's point: most of those roles
should not be fixed at all. Grok Heavy runs several copies of a model, each with a role for
*this* question only; Kimi's swarm lets the model split a task and write each sub-agent's
instructions on the fly. Fixed personas then become guesses about work we have not seen yet.

What must stay fixed is not *roles* but *boundaries* — what a piece of work may touch, which
model may see it, and how far it may act. Those are safety, not convenience: an agent invented
on the fly must not be able to give itself mail access on a cloud model.

## The design

### 1. Jarvis — the only lead

- **The one you talk to:** chat, Telegram, voice. Plans the work, spawns workers, merges
  their results, answers you.
- **Its own model is chosen per request**, by a deterministic sensitivity check (not by
  Jarvis): a request that needs personal data runs Jarvis on the **local** model; anything
  else on a **free cloud** model, with personal details redacted. This is what keeps the GPU
  free for speech most of the day.
- **Standing orders:** the scheduled work is Jarvis's, run as workers — the nightly coding
  queue, topic watching, the daily life-admin sweep, the daily study nudge.

### 2. Envelopes — fixed, enforced by code

Every worker runs inside exactly one envelope. Jarvis picks the envelope; the envelope's
rules are enforced by the system, whatever the brief says.

| Envelope | May see / use | Models | Acts? |
|---|---|---|---|
| **personal** | memories, mail, calendar, contacts, money, documents, study cards | **local only** | reads; may set up page monitors and study cards |
| **research** | the web (search, read pages), public info; briefs are redacted | free cloud, local fallback | reports only |
| **code** | the dev-task pipeline (worktrees, engines, verifiers) | engines: cloud by day, local at night | changes land only through the Tier 1–3 gates |
| **ops** | system health, repos read-only; commands only as proposals you approve | free cloud (no secrets), local fallback | proposes |

Rules the system enforces for every worker:
- tools ⊆ its envelope's tools, and ⊆ what Jarvis itself may use;
- a brief that leaves the machine (research, ops, cloud code) passes the **redaction layer**
  first; personal tools never exist outside the personal envelope;
- content a worker read from the web or mail is marked **untrusted** when it comes back, so
  it can inform Jarvis but never instruct it or another worker;
- a budget (time, tokens, tool calls) per worker, a cap on workers per request, and a
  delegation depth of one (workers do not spawn workers).

### 3. Workers — dynamic, per task

`spawn_worker(envelope, brief, tools, budget)` — Jarvis writes the brief for *this* task:
objective, inputs, output format, boundaries. Workers run in parallel where the work is wide
(several topics, sources or sub-questions), report back, and are gone. No database row.

- **Fan-out:** one worker per topic, source or sub-question; Jarvis merges and checks.
- **Heavy mode:** for a hard or high-stakes question, three workers on *different* models
  answer independently and critique each other once; a deterministic check decides where one
  exists (tests, fetched sources), Jarvis otherwise.
- **Templates:** a brief that keeps recurring and scores well can be saved as a template
  (say, "free-LLM-offer evaluator"), with the owner's approval. Today's personas become the
  first templates: scout (research), admin (life-admin sweep), tutor (study nudge),
  cody (code review), ops (health check).

### 4. Outside the lead

- **support-desk** stays a separate front door for **customers** of the owner's apps. It must
  never be able to reach the owner's data, so it is not a Jarvis worker; it reads one app's docs
  only and runs on local or paid models (customer data never goes to free tiers that train).
- **The coding engines** (code-fixer local / opencode / cloud / claude_code / auto, dependency
  updates) are the code envelope's machinery, not personas you talk to.

## What the database personas become

| Today | Becomes |
|---|---|
| jarvis | **the lead** (prompt and tools rewritten; model per request) |
| assistant, chief, penny, swe-lead, rex, scribe, uzhavu-ops | **retired** — deactivated, not deleted (their conversations stay readable) |
| scout, admin, tutor, cody, ops | **worker templates** (research, personal, personal, code, ops envelopes) |
| support-desk | unchanged, customer front door |
| code-fixer-*, dependency-updater | unchanged, code-envelope engines |

## Free and freemium providers

Unchanged from the agreed rules: one account per provider within its limits (never several
accounts to get round them); local is the base and work waits rather than pays; personal data
stays local and everything else is redacted before it leaves; terms recorded per provider
(trains on prompts? commercial use?); free tiers serve our own work, not the sold product;
per-provider daily quotas in the router; new models found by the research standing order are
adopted only through an approval with benchmark results.

## The jobs (what Jarvis is for)

Built job by job: each job decides which templates and envelopes exist, and is "done" only
when its check passes on real use. Two personas only — **Jarvis** (the owner) and
**support-desk** (customers); everything below is Jarvis creating workers.

| # | Job | Trigger | Envelope | Done when | Blocked by |
|---|---|---|---|---|---|
| 1 | **Free LLM offers**: find new free models/tiers/credits, evaluate the reachable ones, propose adoption | daily catalog diff + news every few hours | research → code (benchmark) | a new free model is found, benchmarked and offered as an approval with no manual step | — |
| 2 | **Night shift report**: what the coding engines did overnight — merged, held and why | every morning | code | one message lists each task with its outcome and links | — |
| 3 | **Morning brief**: calendar, bills and expiries due, study due, night-shift summary | every morning; by voice on request | personal | the brief arrives on the phone and every item is correct against the data | Telegram token |
| 4 | **Reminders**: bills, document expiries, invoice due dates — ahead of time | daily sweep | personal | an item due in N days is reminded once, never missed, never repeated | Telegram token |
| 5 | **Money check-in**: where the money went, what changed vs last month, budget overruns | weekly + on request | personal | figures match the transactions; overruns named | bank CSV / SMS imported |
| 6 | **Research on demand**: "compare X and Y", "what's the latest on Z", with sources | you ask | research | every claim cites a page fetched in that run | — |
| 7 | **App health**: uzhavu/HIS uptime, errors, TLS, backups; deploy checks | hourly + on incident | ops | an outage or failing backup reaches you within the hour | each app's health URL |
| 8 | **Study**: daily nudge, quiz on Telegram, cards from what you are learning | daily + on request | personal | due cards get reviewed; nudge only when something is due | Telegram token |
| 9 | **Capture from the phone**: voice notes, photos, quick text → memories and tasks | you send | personal | a captured item is findable by search the same day | Telegram token |
| 10 | **Tech watch**: open models that fit 16 GB, AI coding agent releases — weekly digest | weekly | research | the digest has only new items, each with a source | — |
| — | **Customer support** for your apps (support-desk, not Jarvis) | a customer asks | customer | answers come only from the app's docs; anything else escalates | an app to deploy it in |

**Order:** 1 (no blockers, proves the research envelope, workers, templates and the approval
flow) → 2 (small, uses what exists) → 6 and 10 (reuse job 1's research pieces) → 3, 4, 8, 9
once the Telegram token is in (prove the personal envelope and the local model) → 5 → 7.

## Build order

Job by job, each a complete slice that is used for real before the next starts; the shared
pieces are built the first time a job needs them, and only as much as it needs.

1. **Job 1, free LLM offers** — builds: the research envelope and its enforcement, the brief
   written from only what the worker needs plus a deterministic scrub as a second layer,
   `spawn_worker` (tool subset, untrusted marking, budget, depth 1), the first templates
   (catalog diff is plain code; "offer reader" and "model evaluator" are templates), the
   adoption approval, per-provider quotas and terms. Eval: a frozen set of catalog snapshots
   and offer pages with known answers.
2. **Job 2, night shift report** — plain code over dev tasks and approvals; Jarvis words it.
3. **Jobs 6 and 10** — reuse job 1's research pieces; heavy mode for important questions.
4. **Jarvis as the lead + retirements** — once the workers it leads exist and are measured.
5. **Jobs 3, 4, 8, 9** (after the Telegram token) — the personal envelope, the local model,
   Jarvis's per-request model choice.
6. **Jobs 5 and 7**, then templates promoted from what proved useful.

Rules for every job: templates first, free-form briefs only for new kinds of work; when Jarvis
runs locally (personal requests) it uses direct tools and templates, and real multi-worker
orchestration runs on the stronger cloud models for non-personal work; hard planning may
escalate to Claude (the claude_code driver) on purpose and rarely; every completed job is
logged with what it was worth, and jobs that are not used are dropped.

## Decisions taken (the owner, 2026-10-20)

- Jarvis is the only lead; workers are dynamic.
- Personal data is handled by the local model; other work may use free cloud APIs that train
  on it; personal details are hidden before anything leaves.
- Free-tier rules as above; adoption of a new model is an approval.
- Kept from the first round: tutor's daily nudge on; support-desk kept.
