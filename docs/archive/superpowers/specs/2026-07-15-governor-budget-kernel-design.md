# The Governor — Unified Budget Kernel (Track 2, Increment 1)

> **Date:** 2026-07-15
> **Status:** Approved — ready for implementation planning
> **Backlog:** `docs/design/09_operational_hardening_backlog.md` Track 2
> **Strategic basis:** `docs/design/07_strategic_direction_2026-07.md` §D7.3 (the Governor)

## Problem

Spend is scattered and unenforced, so unattended autonomous operation is not
financially safe by construction:

- LLM calls happen at **6+ independent call sites** (`agents/orchestrator.py`,
  `extraction/llm.py`, `jobs/consolidation.py`, `services/multi_model_advisor.py`,
  `services/research_engine.py`, `watchers/dependency_watcher.py`) — no single gateway.
- The only "cost cap" is **toothless**: `drivers/dispatcher.py` checks
  `if result.cost_usd > cost_cap_usd:` and merely **logs a warning after the money is
  already spent**.
- `tenant_usage.llm_cost_usd` exists (hourly, per-tenant) but is **dormant** — not
  incremented at runtime.
- Budgets are scattered magic numbers: `config.research_monthly_budget_usd = 0.60`,
  `config.llm_daily_budget_usd = 1.0`, `dispatcher.DEFAULT_COST_CAP_USD = 2.0`.

## Goal

One budget kernel — the **Governor** — that every autonomous spender must consult
**before** spending. A spender is refused or throttled when the budget is exhausted;
the user's own interactive requests are never blocked. Makes unattended operation
financially safe by construction.

**Decisions locked in brainstorming:**
- **Coarse gating**: spenders consult the Governor at their entry-points (not a per-call
  LLM gateway — that is a later increment).
- **Exhaustion posture**: throttle autonomous spend, never block interactive.

## Design

### 1. Pure policy — `life_graph/core/budget.py` (single source of truth)

No DB / no I/O (mirrors `core/trust.py`):

- `class BudgetCategory(str, Enum)`: `DRIVER`, `ADVISOR`, `RESEARCH`, `FAILURE_MINING`,
  `WATCHER`. Each maps to a priority via `_CATEGORY_PRIORITY` (`high` / `low`):
  - **high**: `DRIVER`, `ADVISOR` (act on the user's live tasks / decisions).
  - **low**: `RESEARCH`, `FAILURE_MINING`, `WATCHER` (background maintenance).
- `class BudgetPriority(str, Enum)`: `HIGH`, `LOW`.
- `@dataclass BudgetDecision`: `allowed: bool`, `throttled: bool`, `reason: str`,
  `spent_usd: float`, `cap_usd: float`, `remaining_usd: float`.
- **`decide(spent, cap, priority, *, interactive, soft_threshold=0.8) -> BudgetDecision`** —
  the entire posture as one pure function:

  | Condition | Result |
  |---|---|
  | `interactive` | **allowed** always (`throttled=True` + reason if `spent ≥ cap`) |
  | autonomous, `spent < soft*cap` | allowed |
  | autonomous, `soft*cap ≤ spent < cap`, `priority == HIGH` | allowed |
  | autonomous, `soft*cap ≤ spent < cap`, `priority == LOW` | denied (`throttled=True`) |
  | autonomous, `spent ≥ cap` | denied |

  `remaining_usd = max(0.0, cap - spent)`. A non-positive `cap` disables gating
  (allowed) — a safety default so a misconfig never freezes the system.

### 2. Service — `life_graph/services/governor.py`

- `authorize(tenant_id, category, estimated_usd, *, interactive=False) -> BudgetDecision`:
  reads month-to-date spend for the tenant (sum across categories), calls `decide(...)`
  with the category's priority and the configured cap/threshold. **Fail-open with a loud
  `logger.error` + notification** if the check itself raises — a DB hiccup must not freeze
  all autonomous work; overspend risk is covered by the alert (consistent with the repo's
  degrade-gracefully pattern).
- `record(tenant_id, category, actual_usd)`: upsert month-to-date spend for
  `(tenant_id, period_month, category)`.
- `status(tenant_id) -> BudgetStatus`: month-to-date spent, cap, remaining, per-category
  breakdown — for the daily brief and a future dashboard tile.

`period_month` is the first day of the current UTC month (date).

### 3. Data model — migration `023_budget_spend`

New table `budget_spend` (default/public schema, matching `memories`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | String(64) | |
| `period_month` | Date | first-of-month UTC |
| `category` | String(32) | `BudgetCategory` value |
| `spent_usd` | Numeric(10,6) | rolling aggregate |
| `updated_at` | timestamptz | |

Unique constraint on `(tenant_id, period_month, category)`; index on
`(tenant_id, period_month)` for fast `authorize()` sum reads.

### 4. Config

- `monthly_budget_usd: float = 10.0` (`LIFE_GRAPH_MONTHLY_BUDGET_USD`) — the one global cap.
- `budget_soft_threshold: float = 0.8` (`LIFE_GRAPH_BUDGET_SOFT_THRESHOLD`).
- `research_monthly_budget_usd` and `dispatcher.DEFAULT_COST_CAP_USD` remain as the
  per-run/per-task *estimate* inputs but enforcement moves to the Governor. (The dispatcher
  per-task cap stays as a secondary guard; the primary gate is `authorize`.)

### 5. Wiring — increment 1 (coarse entry-points)

Identical 3-step pattern (`authorize → work → record`) at:

1. **`drivers/dispatcher.py`** — `authorize(DRIVER, est=driver.cost_per_task(), interactive=?)`
   **before** `driver.dispatch(...)`; if denied, short-circuit with a throttled result and
   no LLM call. `record(DRIVER, result.cost_usd)` after. Replaces the post-hoc warning.
2. **`services/research_engine.py`** — `authorize(RESEARCH)` before a research run.
3. **`services/failure_mining.py`** — `authorize(FAILURE_MINING)` before the monthly LLM pass.

Advisor / watcher / second-opinion spenders use the same pattern and are wired in this
increment where the entry-point is clean; the spec's completion note will list exactly
which landed vs. deferred (no silent partial coverage).

The `interactive` flag: driver dispatches originating from a user command pass
`interactive=True`; cron/watcher/scheduled origins pass `interactive=False` (default).

### 6. Testing (TDD, unit-level; no DB — matches conftest)

`tests/unit/test_budget.py` (pure `decide`):
1. Below soft threshold → all allowed.
2. Soft band → high-priority allowed, low-priority denied+throttled.
3. At/over cap → autonomous denied.
4. **Interactive always allowed**, even over cap (throttled flag set, reason present).
5. Non-positive cap disables gating.
6. `remaining_usd` math and boundary values (exactly soft, exactly cap).

`tests/unit/test_governor.py` (service, fake session):
7. `authorize` sums month-to-date and returns the right decision.
8. `record` upserts (insert then increment same `(tenant, month, category)`).
9. `authorize` fails open (allowed) and logs when the session raises.

`tests/unit/test_dispatcher_budget.py`:
10. A denied `authorize` short-circuits dispatch — the driver's `dispatch` is never called.

## Files touched (estimate)

- New: `life_graph/core/budget.py`, `life_graph/services/governor.py`,
  `alembic/versions/023_budget_spend.py`, 3 test files.
- Edited: `models/db.py` (BudgetSpend model), `config.py` (2 settings),
  `drivers/dispatcher.py`, `services/research_engine.py`, `services/failure_mining.py`.

## Out of scope (later increments / other tracks)

ROI ranking (verified-tasks-per-₹ — needs a verification-outcomes join; least
safety-critical), per-call LLM-gateway gating, per-category **hard** sub-caps (the
table + priority model supports adding them later; not configured now), dashboard UI.
