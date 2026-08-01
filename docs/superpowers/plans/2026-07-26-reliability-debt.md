# Reliability Debt — 3 Quick Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix three real reliability bugs: silently-dead ARQ jobs (webhooks, consolidation, bulk-embeddings never run), the worker container's false "unhealthy", and the PWA needing a hard-refresh after every deploy.

**Architecture:** Three independent, mechanical fixes. No behavior *design* — these restore intended behavior. A regression test guards the ARQ-name class of bug so it can't silently recur.

**Tech Stack:** FastAPI + ARQ, Docker Compose, Next.js service worker.

## Global Constraints

- Python: async, double quotes, ruff line-length 100. Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- ARQ registers `WorkerSettings.functions` entries by the FULL dotted string; `enqueue_job("<name>")` must use that exact string or the job silently never runs.
- Windows: verify with `python -m py_compile` + pytest from the worktree ROOT (`python -m pytest tests/unit/ -v`). `dashboard/`: `npm run build` passes, lint zero new.
- Worktree: `<scratchpad>/hotfix-wt`, branch `fix/reliability-debt` (off master).
- **Deploy is BATCHED** — Task 4 opens the PR; the VM deploy runs when the user calls a batch deploy.

## Key facts (verified)

- `WorkerSettings.functions` (workers/settings.py:48-68) uses full dotted names, e.g. `"life_graph.workers.tasks.run_tenant_consolidation"`, `"life_graph.workers.embeddings.generate_embeddings_batch"`, `"life_graph.integrations.webhook.deliver_webhook"`.
- Broken `enqueue_job` bare-name calls:
  - `api/admin.py:713-717` → `"generate_bulk_embeddings", tenant_id, [ids]` — **wrong name AND wrong arg order**. Real job: `generate_embeddings_batch(ctx, memory_ids: list[str], tenant_id: str)` (embeddings.py:31) — memory_ids FIRST.
  - `api/admin.py:851` → `"run_tenant_consolidation", tenant_id`
  - `api/admin.py:853` → `"run_all_consolidations"`
  - `workers/tasks.py:147` → `"run_tenant_consolidation", tid` (internal cron fan-out)
  - `integrations/webhook.py:266` → `"deliver_webhook", str(webhook.id), ...` (webhook delivery — silently dead)
  - Correct example: `services/multimodal.py:103` uses `INGEST_CAPTURE_JOB_NAME` (full dotted).
- Dockerfile:55 `HEALTHCHECK ... urlopen('http://localhost:8000/health')` — inherited by BOTH app and worker containers; the ARQ worker doesn't serve :8000 → false "unhealthy". Compose worker service (docker-compose.production.yml:70-98) has no `healthcheck:` override. `arq <WorkerSettings> --check` is the arq-native health probe.
- `dashboard/public/sw.js` install→`skipWaiting()`, activate→`clients.claim()` (so a new SW takes control), but `dashboard/app/layout.tsx:60-70` registration is fire-and-forget — no `controllerchange` reload, so open tabs keep old code until manual refresh.
- No existing admin/job tests.

---

### Task 1: Fix broken ARQ enqueues + regression guard

**Files:**
- Modify: `life_graph/api/admin.py` (3 enqueues), `life_graph/workers/tasks.py` (1), `life_graph/integrations/webhook.py` (1)
- Test: `tests/unit/test_arq_enqueue_names.py` (new)

**Interfaces:** every `pool.enqueue_job("<name>", ...)` uses a name that appears verbatim in `WorkerSettings.functions`.

- [ ] **Step 1: Write the failing regression test** `tests/unit/test_arq_enqueue_names.py` — scan the repo source for `enqueue_job("<literal>"` calls and assert each literal name is in `WorkerSettings.functions`:

```python
"""Every enqueue_job() name must be a registered ARQ function (full dotted path),
or the worker silently never runs the job."""

import re
from pathlib import Path

from life_graph.workers.settings import WorkerSettings

_ROOT = Path(__file__).resolve().parents[2] / "life_graph"
_CALL = re.compile(r'enqueue_job\(\s*"([^"]+)"')


def _registered_names() -> set[str]:
    return {f if isinstance(f, str) else getattr(f, "__qualname__", str(f))
            for f in WorkerSettings.functions}


def test_all_enqueue_names_are_registered():
    registered = _registered_names()
    offenders = []
    for py in _ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in _CALL.finditer(text):
            name = m.group(1)
            if name not in registered:
                offenders.append(f"{py.relative_to(_ROOT.parent)}: enqueue_job(\"{name}\")")
    assert not offenders, "Unregistered enqueue_job names:\n" + "\n".join(offenders)
```

(Note: this catches only string-literal calls; the `INGEST_CAPTURE_JOB_NAME` constant call is already correct and not a literal, so it won't be scanned — acceptable, it's verified elsewhere.)

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/unit/test_arq_enqueue_names.py -v` → FAIL listing the 5 offenders (generate_bulk_embeddings, run_tenant_consolidation ×2, run_all_consolidations, deliver_webhook).

- [ ] **Step 3: Fix each enqueue**

`api/admin.py:713-717` — correct name AND arg order (memory_ids first):

```python
    job = await pool.enqueue_job(
        "life_graph.workers.embeddings.generate_embeddings_batch",
        [str(mid) for mid in memory_ids],
        tenant_id,
    )
```

`api/admin.py:851,853`:

```python
        job = await pool.enqueue_job("life_graph.workers.tasks.run_tenant_consolidation", tenant_id)
    else:
        job = await pool.enqueue_job("life_graph.workers.tasks.run_all_consolidations")
```

`workers/tasks.py:147`:

```python
        await pool.enqueue_job("life_graph.workers.tasks.run_tenant_consolidation", tid)
```

`integrations/webhook.py:266` — change the bare `"deliver_webhook"` to `"life_graph.integrations.webhook.deliver_webhook"` (keep the remaining args).

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_arq_enqueue_names.py tests/unit/ -v` → green (the regression test now passes; full suite unaffected). `python -m py_compile` the 3 changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/api/admin.py life_graph/workers/tasks.py life_graph/integrations/webhook.py tests/unit/test_arq_enqueue_names.py
git commit -m "fix(arq): enqueue jobs by full dotted name so they actually run (+ regression test)"
```

---

### Task 2: Worker container healthcheck

**Files:**
- Modify: `docker-compose.production.yml` (worker service)

- [ ] **Step 1: Add a worker healthcheck** overriding the inherited Dockerfile one. In the `worker:` service block, after `restart: unless-stopped` and before `deploy:` (preserve `command`, `depends_on`, `restart`):

```yaml
    healthcheck:
      test: ["CMD", "arq", "life_graph.workers.settings.WorkerSettings", "--check"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

- [ ] **Step 2: Verify** — `python -c "import yaml; yaml.safe_load(open('docker-compose.production.yml'))"` parses cleanly (no unit test; the real check is on deploy — `docker inspect life_graph_worker` should read `healthy` once running). Confirm the app service's healthcheck and all other worker keys are unchanged (git diff shows only the added block).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.production.yml
git commit -m "fix(ops): give the worker its own arq --check healthcheck (was inheriting the app's :8000 probe)"
```

---

### Task 3: PWA auto-update on new deploy

**Files:**
- Modify: `dashboard/app/layout.tsx` (SW registration script)

- [ ] **Step 1: Add controllerchange reload** — replace the registration `<script>` body so that when a new service worker takes control, the page reloads once (guarded against reload loops):

```jsx
      if ('serviceWorker' in navigator) {
        let refreshing = false;
        navigator.serviceWorker.addEventListener('controllerchange', () => {
          if (refreshing) return;
          refreshing = true;
          window.location.reload();
        });
        window.addEventListener('load', () => {
          navigator.serviceWorker.register('/sw.js').then((reg) => {
            reg.addEventListener('updatefound', () => {
              const nw = reg.installing;
              if (nw) nw.addEventListener('statechange', () => {
                // new SW installed while an old one controls the page → it will
                // skipWaiting + claim, firing controllerchange above → reload.
              });
            });
            // Poll for updates when the tab regains focus.
            document.addEventListener('visibilitychange', () => {
              if (document.visibilityState === 'visible') reg.update();
            });
          });
        });
      }
```

(The core mechanism is the `controllerchange` → reload with the `refreshing` guard; `sw.js` already does `skipWaiting()`+`clients.claim()`, so a freshly-deployed SW claims the page and fires `controllerchange`. The `visibilitychange` → `reg.update()` makes an already-open PWA notice a new deploy when the user returns to it.)

- [ ] **Step 2: Verify** — from `dashboard/`: `npm run build` passes; lint zero new. (No reload loop: the guard + the fact that `controllerchange` fires once per new SW activation prevents it.)

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/layout.tsx
git commit -m "fix(pwa): reload on new service-worker activation so deploys apply without a hard refresh"
```

---

### Task 4: PR (deploy batched)

**Files:** none.

- [ ] **Step 1: PR**

```bash
gh pr create --repo Raceraja001/life-graph --base master --head fix/reliability-debt \
  --title "fix: reliability debt — dead ARQ jobs, worker healthcheck, PWA auto-update" \
  --body "Three real fixes: (1) webhook delivery / consolidation / bulk-embedding ARQ jobs were enqueued by bare name and silently never ran — now full dotted names + a regression test; (2) the worker container showed 'unhealthy' because it inherited the app's :8000 probe — now has its own arq --check; (3) the PWA needed a hard refresh after each deploy — now reloads on new SW activation. Deploy batched."
```

- [ ] **Step 2: Batch-deploy verification** (when the user calls a deploy): after deploy, confirm `docker inspect life_graph_worker` → `healthy`; trigger `POST /admin/jobs/consolidate` → the job actually runs in the worker logs (not "'run_tenant_consolidation' not found"); a webhook fires and delivers; a fresh deploy auto-reloads the open PWA.

---

## Self-review notes

- Coverage: dead ARQ enqueues + guard (T1), worker healthcheck (T2), PWA auto-update (T3), PR (T4). ✅
- The regression test (T1) is the durable win — it fails CI if anyone re-introduces a bare-name enqueue. ✅
- Judgment call: `generate_embeddings_batch` arg order corrected (memory_ids, tenant_id) — verified against the job signature. `deliver_webhook`'s other args unchanged. Deploy batched per the user's workflow.
