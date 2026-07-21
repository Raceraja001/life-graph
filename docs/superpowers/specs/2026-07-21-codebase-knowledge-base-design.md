# Codebase Knowledge Base — Many Personal Apps as One Knowledge Base

> **Date:** 2026-07-21
> **Status:** Approved — ready for implementation planning
> **Scope:** Cross-repo. Creates a new private `knowledge-base` repo; touches `life-graph` and other own repos.
> **Proven prototype:** `life-graph/knowledge/startgold/` (9 docs, ~2,450 lines, written 2026-07-21)

## Problem

There are ~13 project directories under `D:\DevTools\Projects\` (`work/fin-tech`, `work/SIP`,
`uzhavu.race`, `lr_saas`, `lr_cls`, `lca`, `life-graph`, `study-planner`, `agentic`, `my_apps`,
`app`, `csharp-extension`, …). Knowledge about each lives only in the developer's head or in
per-repo generated doc sets that drift. Two costs follow:

1. **Re-onboarding tax.** Returning to a project after months means re-deriving its architecture,
   conventions, and traps from source.
2. **No cross-project recall.** "Where did I implement HMAC webhooks / payment retries / an offline
   queue?" cannot be answered without opening several repos.

A working prototype already exists for one app: `knowledge/startgold/` — numbered docs
(`00-index` → `08-risks-and-gotchas`), pinned to a commit (`3d98b9bc`), front-loaded with a
"60-second version" and "three things that will bite you first". The problem is scaling that from
one app to many **without** it becoming a second job or rotting into fiction.

## Goal

A knowledge base that (a) primes agents to be immediately productive in any repo, and (b) answers
cross-project questions — written in human, narrative prose.

**Decisions locked in brainstorming:**

- **Purpose: B + C, in A's format.** Optimize for agent consumption (B) and cross-project recall (C),
  but written in the narrative, opinionated voice of the startgold notes (A) — prose a human enjoys,
  with exact file paths an agent can act on.
- **Hub is its own repo, and private.** Not a tenant of `life-graph` (which is one app among many,
  and is a **public** repo — see Security constraint).
- **Split by ownership.** Own repos carry their knowledge in-repo (co-versioned, anti-rot). Client
  and third-party repos are documented in the hub, pinned to a SHA.
- **Tiered depth.** Not every repo earns 2,450 lines.
- **Generation is a repeatable skill**, not a remembered ritual.

## Non-goals

- No embeddings, vector index, or search server. `ripgrep` over markdown is sufficient at this scale
  (YAGNI). The docs are plain markdown, so ingestion into Life Graph remains possible later.
- No attempt to auto-generate knowledge from source without review. Generated docs drift; every doc
  is agent-drafted, human-reviewed.
- No changes to client repositories' tracked contents.

## Security constraint (drove the topology decision)

`life-graph` is a **public** GitHub repo. `knowledge/startgold/` is candid analysis of a **client's**
production fintech platform (`LOGIMAX-CLIENTS/fin-tech`), including `07-security-deep-dive.md`
("auth, encryption, throttling, audit, and **the gaps**") and `08-risks-and-gotchas.md`.

At the time of writing, `knowledge/` is **untracked but not gitignored** — one `git add -A` from
being published to a public repo, permanently (git history, forks, GitHub cache). Verified never
committed: `git log --all -- knowledge` is empty.

**Therefore:** client material must live in a private repo, structurally — not behind a `.gitignore`
rule that one `git add -f` defeats. This is the reason the hub is separate and private, and it is
Step 0 of implementation.

## Architecture

```
D:\DevTools\Projects\
├─ knowledge-base/                  ← NEW, its own PRIVATE git repo
│  ├─ README.md                     ← the registry: every app, one row (Tier 0)
│  ├─ CLAUDE.md                     ← tells an agent how to use the hub
│  ├─ _template/                    ← standardized skeleton (from startgold)
│  │  ├─ 00-index.md
│  │  └─ CHECKLIST.md               ← what a Tier-1 analysis must answer
│  ├─ _cross/
│  │  ├─ patterns.md                ← "how I do X" across all apps  ← the payoff for (C)
│  │  └─ stack-decisions.md         ← recurring tech choices + why
│  ├─ startgold/                    ← client apps, pinned to SHA (moved out of life-graph)
│  ├─ sip/
│  └─ _mirror/                      ← generated read-only copies of own-repo docs
│     └─ <app>/                     ← so one `rg` over the hub searches everything
│
├─ life-graph/docs/knowledge/       ← own repos: canonical, co-versioned with the code
├─ uzhavu.race/docs/knowledge/
└─ work/fin-tech/                   ← client repo: tracked contents untouched
```

**Why split by ownership.** Knowledge co-versioned with the code it describes is the only anti-rot
mechanism that reliably works — you update the note in the same commit as the change. That is
available for own repos and impossible for client repos (can't commit personal study notes, and
shouldn't put candid security-gap analysis in a client's history). The hub covers the second case
and unifies search over both via `_mirror/`.

## Components

### 1. Registry (`knowledge-base/README.md`)

One row per project directory, including dormant ones. This is the map, and Tier 0 for every repo.

| App | What it is | Stack | Path | Owner | Status | Depth | Analysed |
|---|---|---|---|---|---|---|---|
| startgold | Digital gold/silver savings platform | Django monorepo, MySQL | `work/fin-tech` | client | active | T2 | 2026-07-21 `3d98b9bc` |
| life-graph | Brain-inspired memory + agent OS | FastAPI, Next.js | `life-graph` | own | active | T1 | — |

`Owner` ∈ {own, client, third-party} — determines where the doc lives. `Depth` ∈ {T0, T1, T2}.

### 2. Tiering

| Tier | Contents | Applies to | Cost |
|---|---|---|---|
| **T0 — Registry row** | The row above. Nothing else. | **Every** repo, including dead ones | ~5 min |
| **T1 — Orientation card** | ~150–250 lines: 60-second version, architecture sketch, "three things that will bite you first", data model sketch, conventions, "where to look for X" | **Active** repos (see below) | ~1 session |
| **T2 — Deep dive** | One subsystem per doc (the startgold `05`/`06`/`07` pattern) | **Lazily** — only when about to work in that area, or it just caused pain | on demand |

T2 is never written pre-emptively. For startgold, `00`–`04` are T1 and `05`–`07` were correctly
earned T2.

**"Active" is decided by the developer during Step 3**, when the T0 sweep produces the real list —
not inferred from commit dates. A repo is active if work is expected in it in the foreseeable
future; everything else stays T0.

### 3. Template (`_template/`)

Standardizes what the startgold prototype proved. Mandatory sections:

- **Header block** — source repo path, commit SHA, branch, date analysed, related repos
- **60-second version** — what the product is, one paragraph
- **ASCII architecture sketch**
- **Three things that will bite you first** — the highest-value section; mandatory
- **Where the project's own docs live** — plus the "map, not truth" caveat
- Then numbered sections as the app warrants

Machine-readable header so tooling can compute staleness:

```markdown
<!-- kb:source=work/fin-tech kb:sha=3d98b9bc kb:branch=main kb:analysed=2026-07-21 -->
```

### 4. Cross-project recall (`_cross/patterns.md`)

The artifact that does not exist today and is the entire point of (C). One entry per recurring
concern, naming which app does what, with file pointers:

> **Webhook auth** — life-graph: HMAC-SHA256 signed delivery (`core/events.py`).
> fin-tech: provider-specific, no shared verifier (`06-payments-gateway-deep-dive.md`).
>
> **Offline queue** — life-graph mobile: IndexedDB + service worker (`dashboard/lib/offline-queue.ts`).
> Others: none.

Search is `rg` over `knowledge-base/` — `_mirror/` makes own-repo docs part of the same corpus.

### 5. Agent wiring (B)

- **Own repos:** each `CLAUDE.md` points at `docs/knowledge/00-index.md`. This generalizes a pattern
  life-graph already uses (its `CLAUDE.md` opens by directing readers to `START_HERE.md` /
  `KNOWLEDGE.md` / `AGENTS.md`).
- **Client repos:** place a `CLAUDE.md` in the working copy pointing at the hub, and add it to
  `.git/info/exclude` — a **local-only** ignore that is never committed and never pushed. This
  primes agents inside a client repo with zero footprint in the client's history.
- **Hub:** its own `CLAUDE.md` explains the registry, tiers, and how to pick the right doc.

### 6. Freshness / anti-rot

- Every doc carries the machine-readable `kb:sha` header.
- A staleness check reports drift per doc: `git -C <repo> rev-list --count <sha>..HEAD` →
  "startgold: 47 commits behind". Flag past a threshold.
- Policy, kept verbatim from the prototype: docs are **"a map, not truth — verify against source
  before relying on a detail."**
- Own repos additionally get co-versioning: update `docs/knowledge/` in the same commit as the change.

### 7. Generation workflow

A Claude Code skill makes N repos tractable and consistent:

- **`/kb-analyse <path>`** — reads the repo, walks `_template/CHECKLIST.md`, emits a T1 card in the
  template's shape, adds/updates the registry row. Human reviews before commit.
- **`/kb-refresh <app>`** — re-analyses an existing doc, updates content, bumps `kb:sha`, and for an
  own repo re-syncs its `docs/knowledge/` into `_mirror/<app>/`.
- **`/kb-stale`** — reports drift across all registered apps.

`_mirror/` is populated only by `/kb-analyse` and `/kb-refresh`; it is generated output and is never
edited by hand (the canonical copy is the own repo's `docs/knowledge/`).

Consistency comes from the checklist, not from memory.

## Rollout

1. **Step 0 (safety):** create the private hub; move `life-graph/knowledge/startgold/` into it; add
   `knowledge/` to life-graph's `.gitignore`.
2. Seed `_template/` from the startgold structure; write the hub `README.md` + `CLAUDE.md`.
3. T0 registry rows for **all** project directories (including dormant/unknown ones — a row saying
   "unknown, dormant" is still useful).
4. T1 cards for active repos, generated via `/kb-analyse`, highest-value first.
5. Seed `_cross/patterns.md` from what T1 surfaces.
6. Add `CLAUDE.md` pointers (own repos committed; client repos via `.git/info/exclude`).

**Scope boundary for the first implementation plan:** steps 0–3 and 6 (the *system*: hub, safety
move, template, full T0 registry, agent wiring) plus **T1 for two repos only** — `life-graph` and one
other — to prove the `/kb-analyse` skill end-to-end. Remaining T1 cards, all T2 deep dives, and
`_cross/patterns.md` growth are **ongoing content work**, not part of the initial plan. The system
must be complete and useful at the end of the plan even if only two T1 cards exist.

## Verification

- **Security:** `git check-ignore -v knowledge/` in life-graph returns a match; hub repo reports
  `"isPrivate": true`; `git log --all -- knowledge` in life-graph remains empty.
- **(B) works:** open a cold agent session in an own repo and in a client repo; it should answer
  "what is this and what will bite me?" from the knowledge doc without exploring source.
- **(C) works:** a single `rg` over the hub answers a genuine cross-project question (e.g. "which
  apps verify webhook signatures, and how?").
- **Freshness works:** `/kb-stale` correctly reports a known-stale doc after commits land upstream.

## Open questions / future

- **Life Graph ingestion.** The hub is plain markdown, so it can later be ingested as real memories —
  dogfooding the product on actual work. Explicitly out of scope now; the format keeps the door open.
- **Mirror sync trigger.** Manual (`/kb-refresh`) to start. A git hook is possible later if manual
  proves unreliable.
- **Dormant repo policy.** T0 rows for everything initially; revisit whether truly dead projects
  should be archived out of the registry once the real count is known.
