# 07 — Strategic Direction (July 2026)

> **Date:** 2026-07-08
> **Status:** Accepted by developer (Raja)
> **Extends:** `.comms/context/strategic-decision.md` (the "don't build what exists" rule — still in force)
> **Supersedes:** the "memory microservice" framing in README.md §intro where it conflicts with D1 below

This document records the strategic decisions made during the July 2026 direction review, with rationale and consequences. Future agents: read this before proposing new product directions — these questions have been decided.

---

## D1. Identity: Life Graph is a personal Agent OS, not a memory service

**Decision.** Life Graph's product identity is **an agent system that works for the user across all work** — coding, testing, reviewing, content, learning, operations. Memory is the substrate, not the product.

**Why.** Raw memory-as-a-service is commoditizing: Mem0/Zep/Letta sell it, and model providers are bundling memory natively. Meanwhile execution via agents is also commoditizing. The durable value sits in the layer between: context, dispatch, verification, judgment, and learning — the *management layer* — which requires accumulated personal data nobody else has.

**Consequences.**
- Positioning language: "the private, self-hosted brain + workforce your agents plug into," not "memory API."
- Multi-tenant SaaS plumbing stays (it serves our own products and a future open-core play) but SaaS billing/plans are **not** the near-term focus (see D5).

---

## D2. Agent strategy: rent the muscle, own the nervous system

**Decision.** Life Graph **hires** best-in-class external agents as workers and does not build custom *executors* for commodity skills.

| Layer | Approach | Examples |
|---|---|---|
| **Executors (muscle)** | RENT — wrap as drivers | Claude Code headless, Codex CLI, browser-use |
| **Management (nervous system)** | OWN — already largely built | kernel, ProcessManager, ChiefRouter, autonomy/trust, watchers, memory, context assembly |
| **Custom agents** | BUILD as **configuration**, not codebases | persona row = prompt + tools + driver + verifier chain + context profile |

**The line for custom agents:** build custom where **our data** is the differentiator (verifiers checking against our standards, the adversarial advisor, watcher agents, Uzhavu ops agent, content agents tuned by correction history, cheap local-model task agents, privacy-sensitive tasks via LM Studio). Do NOT build custom where **capability** is the differentiator (general coding, browsing) — frontier labs ship a better version quarterly and homegrown loops depreciate at the same rate.

**Why.** A solo developer cannot out-execute frontier coding agents, but nobody can out-*context* the owner of the substrate. The unfair advantage is the context packet (memories + preferences + procedures + project map + calibration profile) attached to every dispatch, and the verification/trust gate on every result.

**Consequences.**
- New spec: `docs/specs/agent-drivers.md` (AgentDriver protocol, context packets, verifier framework).
- The existing `AgentOrchestrator` is retained as the **local driver** for cheap/small/private tasks — it is not the swarm.
- Anti-pattern, recorded: no persona-chain pipelines (Architect→Planner→Backend→…→Release). Start with orchestrator–worker–verifier; add a persona only when a repeated, observed failure demands it.
- The swarm's success metric is **verified tasks landed per rupee per week** — not tasks attempted, not tokens spent.

---

## D3. Differentiator track: the Judgment Engine (with the Capture Spine as its input layer)

**Decision.** The flagship intelligence bet is the closed judgment loop: **Decide → Predict → Act → Observe → Recalibrate**. Specs written: `docs/specs/capture-spine.md` (universal input: ambient observation, conversation-as-capture, system-initiated interviews, daily brief) and `docs/specs/judgment-engine.md` (decision records, predictions, automatic outcome resolution, calibration curves, adversarial advisor with citations).

**Why.** As agents commoditize execution, human judgment becomes the bottleneck; no product today measurably improves it. The loop requires persistent memory + belief tracking + evidence + watchers + agent execution — a substrate combination only this system has. The moat is the accumulated, outcome-resolved history itself; it cannot be shipped retroactively by a competitor.

**Follow-on concepts, decided direction but not yet specced** (in likely build order): the **Time Machine** (point-in-time knowledge reconstruction, "what did I know when I decided X"), the **Apprentice** (procedure learning from observed trajectories with progressive autonomy — capture spine already emits `PROCEDURE_CANDIDATE`), the **Life Compiler** (goals compiled into scheduled jobs/watchers/tasks with drift detection), the **Delegate** (a queryable representative of the user with disclosure policies).

**Hard rules carried from KNOWLEDGE.md anti-patterns:** zero capture friction (the chat is the form; the user never does data entry), interview budget max 3 questions/day with anti-nag decay, receipts-or-it-didn't-happen (every advisor claim cites row ids), never fake calibration under n=20.

---

## D4. Frontend: one Next.js PWA core, many thin surfaces, built on Uzhavu's design system

**Decision.**
1. Extract Uzhavu's `packages/ui` (74 components + 10-dimension token system) into a **shared package** consumed by both projects (private registry, e.g. self-hosted Verdaccio, or shared git workspace).
2. Build the Life Graph dashboard as **its own Next.js PWA in this repo** — NOT as a pluggable app inside Uzhavu (wrong ownership boundary; the personal OS must not be chained to a product's release cycle).
3. UX model is **chat + canvas**, not a 45-page CRUD admin: a command bar routed through ChiefRouter/orchestrator, generated panels, and fixed pages only for the approval queue, notification inbox/brief, settings, and the graph view.
4. The full surface set is: PWA (screen) + WhatsApp/Telegram bot (everywhere-input, spec exists) + MCP server (agent surface, built) + CLI (built) + WebSocket push (built). No Electron, no React Native, no Flutter — one UI codebase.

**Component mapping (assembly, not construction):** CommandPalette → command bar; Timeline → identity/belief timeline; DataTable + module configs → memory browser; Kanban → kernel task queue; ChartCard/StatsCard → calibration + watcher dashboards; ConfirmDialog/Stepper → approval queue; Tour → onboarding. Net-new builds only: force-directed graph view, streaming chat surface, live event feed.

**Build order:** memory browser + search → live activity feed → chat bar → calibration screen (the flagship demo: *your calibration curve improving*) → graph view → approval queue.

---

## D5. Business: products first, open-core later, no infrastructure-SaaS knife fight

**Decision.** Sequence, don't choose:
1. **Now:** Life Graph serves our own work and products (Uzhavu is its first production tenant). Sell outcomes through vertical products, not memory infrastructure.
2. **When the dashboard makes it demoable:** open-source the core; the differentiators (provenance/audit layer, watchers, judgment engine, dashboard, hosted option) are the paid tier — Plausible/Supabase-style open-core.
3. **If inbound pull appears:** white-label memory/agent backend for agencies building client agents (few, technical, higher-value customers — fits solo-dev support economics).

**Why.** Raw memory-API SaaS means competing with funded free tiers below and platform bundling above, plus SLA/support load no solo dev should carry at $29/month price points. The already-built SaaS plumbing (tenancy, rate limits, webhooks, metering) is what makes the open-core → hosted path cheap to exercise later; it is an option, not the strategy.

**Consequence for Uzhavu:** its ai-engine's own `memory/` + `knowledge/` folders are a second, weaker brain — it should delegate memory to Life Graph over the existing HTTP client. One brain, many products.

---

## D6. Modernization notes (accepted, low ceremony)

- **Embeddings:** `all-mpnet-base-v2` (2021-era) to be replaced with a modern local embedder (bge-m3 class) before the corpus grows large; embeddings are versioned so migration is mechanical.
- **Extraction tiers:** the regex+spaCy tiers may be progressively replaced by small local models (1–4B on the Snapdragon X NPU via ONNX/QNN) — keeps the zero-API-cost principle with better quality. Not urgent; do when a quality ceiling is actually hit.
- **Memory portability:** long-term bet on a signed, selectively-disclosable export format ("memory passport"); NDJSON export + MCP already point this direction. Design when the Delegate is specced.

---

## D7. Operational foundations: the system must be survivable before it gets smarter

**Decision.** Four operational additions are accepted and rank **ahead of further capability work** (the moat is the accumulated data; the risk profile changes as agents gain execution power):

1. **The Lifeline** — nightly encrypted off-site backups (Postgres + MinIO via restic/borgmatic), **weekly automated restore-verification** into a scratch container (row counts + embedding samples — untested backups don't count), and provenance/integrity checks in consolidation. *Data loss is not an incident; it is the death of the product thesis.*
2. **The Immune System** — trust-tier tags on every capture and packet section (`self < verified < external < hostile-possible`); the hard rule that untrusted content is **data, never instructions**; egress allowlists for driver subprocesses; hash-chained append-only audit. Prompt-injection defense is a first-class subsystem, not a prompt disclaimer.
3. **The Governor** — one budget kernel over all spenders (research, challenges, drivers, pipelines, mining): monthly cap, per-pipeline allocation, automatic throttling, ROI ranking in verified-tasks-per-₹. Extends `tenant_usage` metering; makes unattended operation financially safe by construction.
4. **Shadow Mode** — the missing rung on the Era-8 autonomy ladder: new pipelines/personas run 2 weeks in dry-run, producing "would-have-done" reports graded with one tap; grades feed the trust calculator. Nothing acts for real without a shadow track record.

## D8. The People Graph: model people as a first-class domain

**Decision.** Add person entities built **from ambient capture** (never manual CRM upkeep): what each person cares about, last interaction, commitments made to them and by them, communication preferences. Integrations: commitments feed the Judgment Engine (promises are predictions), person-importance feeds the attention firewall, client context feeds Uzhavu ops. Rationale: every manual personal-CRM product stalls on data entry; the capture spine removes that failure mode, and a solo founder acquiring customers needs this before scale, not after.

## D9. The Spoken Brief (small, accepted)

**Decision.** TTS pass over the daily brief (a ~3-minute private morning podcast), voice answers back through the existing Whisper path. Half a day on top of the brief composer; its purpose is adoption — daily habitual use is what feeds every upstream flywheel.

## D10. Operating discipline: planning is closed — these four govern execution

1. **Dogfooding protocol.** Adoption is deliberate: route exactly two real daily workflows through the system first (morning project check; decision capture from coding sessions). No third workflow until the first two feel indispensable. Every feature earns its place in the developer's actual day before the next ships.
2. **Operating rhythm + kill criteria.** Monthly 15-minute self-review, prepared by the system from its own data (usage, cost, value). Kill criteria are pre-committed at ship time — e.g. interview engine: answer rate <30% after 60 days → redesign or remove. Unused features are removed, not accumulated.
3. **Personal/client data boundary.** Before Uzhavu's ai-engine delegates memory here: client-tenant data is hermetically separated across storage, backups, logs, and embeddings; it **never enters personal context packets**; it is deletable on customer request without touching personal history. Prerequisite for the D5 business path.
4. **Open-source trigger (decided, not scheduled).** Launch when ALL of: calibration screen works end-to-end, quickstart runs clean on a fresh machine, Lifeline restore-drill green. Minimal launch kit: outsider-facing README, demo GIF, dependency license check.

**Planning status: CLOSED as of 2026-07-08.** New concepts go to the Horizon appendix as one paragraph, or nowhere. Execution starts at START_HERE.md roadmap F0.

---

## Priority order

**The canonical build order lives in `START_HERE.md` §Roadmap — one source of truth, maintained there only.** This document records *why*; that table records *what and when*.

**What we are explicitly NOT doing now:** SaaS billing pages and plan tiers; persona-chain agent pipelines; a second UI codebase; a standalone learning platform (Growth Engine concepts fold into Life Graph later, right-sized); multi-device CRDT sync (VPS + thin clients suffices for years); Rewind-style screen recording (storage/privacy cost ≫ signal vs. tool exhaust already captured); building eval/tracing/workflow tools that exist as OSS (see `.comms/context/strategic-decision.md`).

---

## Appendix: Horizon (5–10 years) — directional, NOT committed

> These are recorded so the long arc is visible, not to be built now. Every one of them requires no new invention — only the substrate (capture, provenance, resolved outcomes, procedures, trust) having run for years. Ship the foundations; these become sequencing questions, not research problems. Do not start any of these while items 0–7 of the priority table are unfinished.

**H1. The Council — advisors with track records.** Evolve multi-model dissent into persistent advisor personas (Skeptic, Architect, Accountant, …), each with a multi-year calibration record scored against actual outcomes. The system learns whose advice works for which domain *for this user* and weights accordingly. A personal board of directors whose composition is evolved by evidence. Endgame of the Judgment Engine; the track records are the moat and take years to accumulate.

**H2. The World Feed — a personal intelligence agency.** Invert the watchers: monitor the world through the lens of the user's graph. News/releases/regulations/papers scored by impact on the user's specific projects, beliefs, commitments, and stack — delivered as implication briefs ("this affects your Delegate spec; suggested change attached"), not headlines. Seed exists in the tech-radar watcher. The last defensible filter in a world of infinite generated content: "only what changes *my* decisions."

**H3. Counterfactual Replay — backtesting life policies.** With thick Time Machine + calibration data, replay alternate policies against personal history the way quants backtest strategies ("had you applied the 2.8× multiplier for two years, here is the delivery-date delta"; "had you followed the advisor's 'reconsider' verdicts, here is what you'd have skipped and saved"). Policy changes become adopted-with-evidence instead of resolutions. The dataset is being accumulated incidentally by G/H/I.

**H4. The Body as a Watcher — physiology in the judgment loop.** Wearable streams (sleep, HRV, activity) ingested as one more watcher, local-first. Retrospective correlations ("worst-calibrated estimates cluster after <6h sleep") then prospective guards (attention firewall avoids scheduling big decisions on bad mornings; adversarial advisor cites "deciding this tired"). Decision quality × physiological state is an unclaimed product space; architecture cost is ~one migration + one watcher.

**H5. The Procedure Economy — an app store for learned skills.** Apprentice-distilled procedures with success-rate provenance become portable, signed packages ("deploy-FastAPI-to-VPS, 47 runs, 94%") — shareable in the open-source community, sellable in a marketplace later. The memory-passport idea applied to skills. When execution is commodity, curated battle-tested *how-we-do-things* is what's left to trade; this is how the open-core grows a network moat.

**H6. The Continuity Layer — memory that outlives the user.** Life Graph as estate: succession policies (who may query what, when), a posthumous Delegate under strict disclosure rules, and the nearer-term version — descendants querying actual decision records with reasoning and evidence. Digital-legacy demand and regulation are coming; provenance-grade personal records are the prerequisite nobody else will have.
