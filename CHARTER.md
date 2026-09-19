# Life Graph — Charter

> **This file is intent.** Why the project exists, what it is trying to become, and the
> rules that must not be broken. It deliberately contains **no counts** — how many
> endpoints, tables, or events exist today is generated into
> [docs/STATE.md](docs/STATE.md) by `scripts/gen_state.py`.
>
> Intent drifts slowly. State drifts fast. Keeping them in one file is what rotted the
> documentation this charter replaces.

---

## What Life Graph is

**A brain-inspired memory system that grew an operating system on top of it.**

The base is a multi-tenant memory service: it takes in the raw exhaust of a life —
conversations, transcripts, documents, tool output, voice — extracts durable facts,
scores them, links them into a graph, and surfaces the right ones at the right moment
without being asked. On top of that sits an agent OS: a kernel that runs personas as
processes, watchers that notice things unprompted, drivers that let agents actually
change code, and a judgment layer that records decisions and grades its own predictions
against what really happened.

The distinction that matters: this is not a chatbot with a database attached. Memory is
the substrate, and everything else is built to feed it or act on it.

## The problem it solves

Every AI conversation starts from zero. You re-explain your stack, your constraints, your
preferences, the decision you already made last month and the reason you made it. The
context you built up evaporates when the session ends.

Worse, the obvious fix — "just save everything" — fails in its own way. An undifferentiated
pile of saved chats is a collector's fallacy: it grows without becoming more useful, and
the cost of finding anything in it rises faster than the value of what's stored.

Life Graph's bet is that useful memory needs the same machinery a brain uses: selective
encoding (most of what happens is not worth keeping), consolidation (periodically
reorganise and compress), decay (let unimportant things fade), and proactive recall (surface
the memory *before* it is asked for, because the moment you know to search is the moment
you already remembered).

---

## Design invariants

These five rules are load-bearing. Changing one is an architectural decision, not an
implementation detail.

### 1. LLM as advisor, not authority

The overwhelming majority of operations are deterministic code. Fact extraction runs a
three-tier pipeline — regex patterns, then spaCy NER and dependency parsing, and only if
those score below threshold does an LLM get consulted. Importance scoring, tagging, query
routing, dedup, and decay never call an LLM at all.

This is a cost decision *and* a correctness decision. Deterministic code is debuggable,
testable, free, and does not hallucinate. The LLM is reserved for genuinely ambiguous
judgment calls, and its output is treated as a suggestion to be validated — never as
ground truth.

### 2. Schema-less core

Facts live in a JSONB `properties` column with dynamic tag arrays. There are no hardcoded
type or domain enums anywhere in the memory core.

The reason is that a life does not have a fixed schema. The same system has to hold a
health decision, a career note, a debugging lesson, and a preference about coffee. Every
enum added to the core is a future domain excluded from it.

### 3. Event-driven

Cross-cutting behaviour is wired by firing an event and subscribing to it, not by calling
a service directly. Events bridge to Redis for cross-instance fan-out, then to HMAC-signed
webhook delivery and WebSocket relay.

When adding a feature that needs to react to something, subscribe. Do not reach into the
producing service and add a call — that is how a decoupled system quietly becomes a
monolith.

### 4. Tenant-scoped, always

Every database query filters by `tenant_id`. Middleware reads the `X-Tenant-ID` header into
a contextvar; every model carries the column. A query that forgets the filter is a data
leak across tenants, not a bug to fix later.

### 5. Fail-closed autonomy

An action with no matching safety rule is classified `DANGEROUS` and queued for approval —
never executed on the assumption that unknown means harmless. Low trust *upgrades* an
action's risk tier rather than lowering the bar. Verifiers treat "could not check" as a
distinct third state, not as a pass.

The whole autonomy ladder is built so that the failure mode of any missing configuration is
*asking the human*, not acting.

---

## The layer model

```
                        ┌─────────────────────────────┐
                        │   Jarvis / chat surface     │  streaming, voice, delegation
                        └──────────────┬──────────────┘
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
┌───────▼────────┐            ┌────────▼────────┐            ┌────────▼────────┐
│  Ambient       │            │  Judgment       │            │  Drivers        │
│  watchers,     │            │  decisions,     │            │  worktree-      │
│  self-improve  │            │  calibration    │            │  isolated exec  │
└───────┬────────┘            └────────┬────────┘            └────────┬────────┘
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       │
                        ┌──────────────▼──────────────┐
                        │   Autonomy  levels · risk   │  fail-closed gate
                        │   trust · shadow · approval │
                        └──────────────┬──────────────┘
                        ┌──────────────▼──────────────┐
                        │   Kernel  processes,        │  zero-LLM routing
                        │   personas, scheduler       │
                        └──────────────┬──────────────┘
                        ┌──────────────▼──────────────┐
                        │   Memory core               │  the substrate
                        │   extract · score · link    │
                        │   consolidate · decay       │
                        └─────────────────────────────┘
```

**Memory core** — ingestion, three-tier extraction, dedup, hybrid retrieval (vector + BM25 +
graph), contradiction detection, proactive recall.

**Kernel** — personas as processes, regex intent routing, a hand-written cron scheduler, a
project registry, notifications. Deliberately LLM-free.

**Autonomy** — the gate everything with side effects passes through. A four-level ladder
crossed with a three-tier risk classifier, plus trust scoring, shadow-mode graduation, an
approval queue, an append-only audit log, and a kill switch.

**Drivers** — how a proposal becomes a real code change: dispatch into an isolated git
worktree, run tools, pass a verifier chain, optionally face a dissenting second-opinion
model, then land.

**Judgment** — decisions recorded with predictions attached, resolved against outcomes,
scored with Brier scores and bucket analysis so the system learns how overconfident it is.

**Ambient** — watchers that notice things unprompted and turn findings into tasks;
self-improvement that evaluates and optimises its own prompts.

**Jarvis** — the human surface: streaming chat, voice in and out, persona delegation.

---

## Brain-inspired cycles

The mapping is not decoration — each of these is an actual implemented behaviour.

| Brain process | Life Graph equivalent |
|---|---|
| Sleep consolidation | Nightly pipeline: cluster → dedup → distill |
| Forgetting curve | Exponential decay — `importance × access^0.3 × e^(−λ·days)` |
| Priming | Proactive recall at session start |
| Reconsolidation | Memories update importance and tags on each access |
| Prospective memory | Intentions with time, event, and context triggers |
| Metacognition | Tracking what the system *doesn't* know as knowledge gaps |

---

## Non-goals

What this project deliberately does not do. Each of these is a decision, not an oversight.

1. **No maintenance tax.** The system organises itself. The user never manually files,
   tags, or sorts anything. A memory system that needs tending is a second job.
2. **No collector's fallacy.** Store decisions and lessons, not bookmarks. Volume is not
   the goal; retrievability is.
3. **No capture friction.** Observe work as it happens. Never interrupt to ask the user to
   categorise something.
4. **No proprietary lock-in.** PostgreSQL and standard APIs, fully exportable as NDJSON.
   Own the toolchain end to end.
5. **No hardcoded schemas.** See invariant 2.
6. **Not a wrapper.** If a capability can be implemented as deterministic local code, it is
   not an LLM prompt.
7. **Not a team product.** Multi-tenancy exists for isolation and self-hosting, not because
   this is being built as a collaboration tool.

---

## Current frontier

What is genuinely unfinished, in priority order. Everything else that used to be listed as
pending has shipped — check [docs/STATE.md](docs/STATE.md) for what actually exists rather
than trusting any prose, including this paragraph.

- [x] **Calendar and email reading** — built as connector plugins (`plugins/calendar`,
      `plugins/mail`, runtime `life_graph/connectors/`, spec `docs/specs/connectors.md`):
      read-only, several accounts, app password or Google OAuth, brief sections, agent
      tools, meeting prep. Mail bodies never reach a cloud model. Contacts too
      (`plugins/contacts`, Google or a vCard export, per-account cloud visibility,
      spec `docs/specs/connector-contacts.md`): names on addresses, birthdays, "who"
      lines in meeting prep. GitHub too (`plugins/github`, read-only fine-grained token,
      spec `docs/specs/connector-github.md`): review requests, your PRs' CI and review
      state, assigned issues in the brief; private repos are counts for cloud chat.
      Bills & renewals from mail too (spec `docs/specs/bills-from-mail.md`): due dates
      and amounts parsed by code, confirmations close bills, amounts never leave.
- [ ] **Messaging channels** — WhatsApp/Telegram as an interaction surface. Specs exist,
      no code.
- [ ] **Text-to-speech coverage and quality** — replies are spoken only for voice-originated
      turns, so typed turns stay silent. It uses the browser's native `speechSynthesis`
      rather than a higher-quality voice.
- [ ] **Raising autonomy trust (L0 → L1)** — a policy decision to make once shadow mode has
      graduated real personas, not a build task. The system currently defaults to asking
      about everything.
- [ ] **SDK documentation** — Python and TypeScript SDK usage examples.

---

## Where to look next

| You want... | Read |
|---|---|
| The exact current inventory | [docs/STATE.md](docs/STATE.md) — generated, never hand-edited |
| A browsable version of the same | [docs/feature-inventory.html](docs/feature-inventory.html) |
| How to run it, conventions, workflow | [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md) |
| Public overview and quickstart | [README.md](README.md), [docs/QUICKSTART.md](docs/QUICKSTART.md) |
| Architecture in depth | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Why the strategy is what it is | [docs/design/07_strategic_direction_2026-07.md](docs/design/07_strategic_direction_2026-07.md) |
| Per-feature specs | [docs/specs/](docs/specs/) — see the spec-status table in `docs/STATE.md` |
| Operations, backup, restore drills | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Historical build records | [docs/archive/](docs/archive/) — non-authoritative |

### Keeping this accurate

`CHARTER.md` is hand-written and should change rarely — when direction changes, not when
code does. `docs/STATE.md` is generated:

```bash
python scripts/gen_state.py          # refresh docs/STATE.md
python scripts/gen_state.py --html   # also refresh the browsable HTML view
python scripts/gen_state.py --check  # exit 1 if STATE.md is stale
```

If a number anywhere in the documentation disagrees with `docs/STATE.md`, `docs/STATE.md`
is right and the other file is stale.
