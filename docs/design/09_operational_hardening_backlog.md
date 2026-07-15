# 09 — Operational Hardening Backlog

> **Date:** 2026-07-15
> **Status:** Active — execute one track at a time, each preceded by a brainstorming pass.
> **Extends:** `07_strategic_direction_2026-07.md` §D7 (operational foundations rank *ahead* of capability work) and §D6 (modernization).
> **Discipline:** No new capability features while any track below is open. Feature sprawl is the identified risk (see D10 kill criteria).

This backlog was produced from a **verified code audit** on 2026-07-15 (not the docs). It records the
real state of the D7 operational foundations and the order in which we will close the gaps. Each track
is built **test-first, one at a time, after a brainstorming pass** — do not batch them.

---

## Verified audit (2026-07-15)

| Foundation | State | Evidence |
|---|---|---|
| **D7.1 Lifeline** — backups + restore drills | ✅ **Done** | `scripts/backup_cron.sh` wired into `docker-compose.production.yml:164`; weekly Sun 06:00 UTC restore drill via `scripts/verify_restore.sh`, outcome logged to `job_runs`. |
| **D7.2 Immune System** — trust tiers, egress, injection defense | ❌ **Largely missing** | No `trust_tier`/untrusted/hostile tagging anywhere. No egress allowlist on driver subprocesses. `autonomy/audit/service.py` is append-only but **not** hash-chained/tamper-evident. |
| **D7.3 Governor** — one budget kernel over all spenders | ⚠️ **Fragmented** | Only scattered caps: `config.research_monthly_budget_usd=0.60`, `drivers/dispatcher.py:DEFAULT_COST_CAP_USD=2.0` per task. No unified monthly cap, allocation, or cross-spender throttling. |
| **D7.4 Shadow Mode** — dry-run rung on the autonomy ladder | ❌ **Missing** | Only unrelated bulk-delete `dry_run` in `api/admin.py`. No "would-have-done" track for new pipelines/personas. |
| **D6 Embeddings** — modern local embedder | ⚠️ **Dated** | `config.embedding_model = all-mpnet-base-v2`, 768-dim (2021-era). Versioned, so migration is mechanical. |

**Why this is urgent now:** the desktop capture agent (`clients/desktop/`) and `claude_code` drivers
mean external, untrusted content now flows *capture → context packet → agent that executes*, with no
trust labeling and no egress control. That is a live prompt-injection surface — the exact thing D7.2
calls a first-class subsystem.

---

## Execution order

Each track: **brainstorm → write plan → TDD build → verify → integrate.** Check off only when the
brainstorming, the tests, and a real-behavior verification are all green.

- [x] **Track 1 — Immune System foundation (trust tiers).** Add `trust_tier` at the capture-spine
      ingress (`self < verified < external < hostile-possible`), classify by surface, thread the tier
      through context packets, and enforce "untrusted content is data, never instructions." First
      increment only; egress allowlist and hash-chained audit are later increments of this same track.
      *Rationale: closes the live injection surface opened by drivers + desktop capture.*
      **Code-complete 2026-07-15** (migration `022`, `core/trust.py`, enforcement in
      `drivers/context.py` + `claude_code.py`, 42 unit tests). ⚠️ Migration not yet applied to a live
      DB (no Postgres/Docker in the build env) — run `alembic upgrade head` once infra is up. Next
      Track-1 increments: egress allowlist on driver subprocesses; hash-chained audit; wiring
      untrusted memory-creation callers (multimodal/transcript ingest) to pass the tier.
- [ ] **Track 2 — The Governor.** Unify the scattered cost caps into one budget kernel over all
      spenders (research, drivers, mining, challenges): monthly cap, per-pipeline allocation,
      automatic throttling, ROI ranking in verified-tasks-per-₹. Extends `tenant_usage` metering.
- [ ] **Track 3 — Shadow Mode.** New pipelines/personas run 2 weeks in dry-run, emitting
      "would-have-done" reports graded with one tap; grades feed the trust calculator (Era-8 ladder).
- [ ] **Track 4 — Embedding modernization (D6).** Swap `all-mpnet-base-v2` → bge-m3-class local
      embedder; versioned re-embed job, verify recall/dedup quality vs. old. Needs a running
      Postgres+pgvector. Lowest risk to defer; highest infra requirement.

## Cross-cutting discipline (not a track — runs in parallel)

- **Dogfooding + kill criteria (D10).** Route the two real daily workflows (morning project check;
  decision capture from coding sessions) so the Judgment loop accumulates data, and instrument which
  Era features are actually invoked. Unused features get removed, not accumulated. This gates whether
  Tracks 2–4 are even worth their build cost.

---

## Log

- **2026-07-15** — Backlog created from verified audit. Lifeline confirmed done. Starting Track 1
  (Immune System) with a brainstorming pass.
