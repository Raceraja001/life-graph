# Jarvis Roadmap — Reality Check & Path Forward (2026-08-05)

> **Why this doc exists.** `START_HERE.md` (July 12) and `KNOWLEDGE.md` are **stale** and under-report
> reality: START_HERE's "Remaining Gaps — ALL CLOSED" is the G/H/I list and predates the Jarvis work;
> KNOWLEDGE's "What's Next" still lists items as unchecked that are in fact shipped. Neither mentions the
> Jarvis persona layer, voice, or real-world integrations. This doc is the current, code-verified snapshot
> and the prioritized path to an actual "Jarvis-like always-on personal assistant." Supersedes the roadmap
> view in START_HERE until those are refreshed (see §5).

> **⚠️ CORRECTION (2026-08-05, verified live).** An earlier draft of this doc said the Jarvis persona
> layer was "unmerged / ~40% built." **That was wrong** — it was based on stale local git refs (local
> `master` was 91 commits behind `origin/master`). Verified against origin/master and by testing the live
> VM: **all 5 personas (`jarvis, tutor, scout, admin, swe-lead`) + `delegate_to_persona` + the router
> `target_agent` override are merged, deployed, and working.** A live test had Jarvis delegate to `tutor`,
> get real answers, and synthesize a final result (~4 min). The real gap is **surfacing** it in a chat UI,
> now spec'd as `docs/superpowers/specs/2026-08-05-jarvis-streaming-chat-design.md` (Sub-project A) with UI
> mockup `docs/design/mockups/jarvis-streaming-chat.html`. Sections below are corrected accordingly.

## 0. The mental model

A Jarvis-style assistant is five layers. Life Graph has an unusually complete backend for all five; the
gaps are in **closing loops** and **reach into the real world**, not in core plumbing.

| Layer | Means | Status |
|-------|-------|--------|
| **Brain** — memory | pgvector + Apache AGE graph, dedup, decay, consolidation | ✅ built & running; now being fed by transcript distillation |
| **Mind** — reasoning/judgment | judgment engine, calibration, multi-model advisor, self-improvement | ✅ built |
| **Senses** — ambient input | hourly watchers, capture spine, desktop capture client | ✅ built & running |
| **Hands** — action-taking | autonomy levels, sandboxed executor, agent drivers | 🔶 built but **default-gated off** (L0 + shadow-mode) |
| **Face** — interface | dashboard PWA; chat bar; (no voice) | 🔶 PWA yes; **conversational chat not wired**; no voice |

## 1. Built AND running (on `master`)

- **Memory OS** — pgvector + Apache AGE graph, dedup, decay, nightly consolidation. Fed by the
  transcript-distillation pipeline shipped 2026-08-05 (conversation-aware extractor, `master @ 6bee0fa`).
- **Ambient loop (genuinely always-on)** — a separate ARQ `worker` service runs real cron:
  `run_watchers` **hourly** → **auto-creates kernel tasks** via `TaskOriginationService`
  (`workers/tasks.py:319`), a **daily brief** (08:00), daily digest, nightly consolidation/merge/decay/
  self-heal (03:00–04:00), monthly failure-pattern mining. Registered in `workers/settings.py`.
- **Autonomy + drivers (safety-gated)** — sandboxed `CommandExecutor`, a `claude_code` driver that shells
  to the Claude CLI, verifier chains, WIP-limited dispatcher. Operational personas (`uzhavu-ops`,
  `dependency-updater`) can run unattended. Defaults: `autonomy_default_level=L0` ("ask about everything"),
  `shadow_mode_enabled=True` (14-day / 5-sample / 80%-good graduation), `$10/mo` budget, blast-radius ≤3.
- **Surfaces** — dashboard PWA (memories/tasks/decisions/calibration/drivers/activity + mobile route group),
  a desktop capture tray client (`clients/desktop/`), outbound email/webhook notifications, web search/browse
  tools, MCP server, and a multi-model **advisor endpoint** (`api/advisor.py`) that returns real answers.
- **Deployed** — live at `https://brain.raceraja001.in` on a GCP VM behind Cloudflare Access, free
  OpenRouter models with failover, backups + restore drills.

## 2. Built but NOT usable / partial

1. **Jarvis multi-persona layer — MERGED, DEPLOYED, WORKING (was wrongly listed here as unmerged).**
   The 5 personas + `delegate_to_persona` + `ChiefRouter.route(target_agent=...)` override are on
   origin/master and live on the VM; a live test confirmed end-to-end delegation + synthesis. The only
   thing missing is the **chat surface** to see/use it — that's Sub-project A (spec'd 2026-08-05). Ambient
   scout/admin *scheduling* (Story 4 of `personal-roles.md`) is the remaining unbuilt piece → Sub-project B.
2. **Chat is a router, not a conversation.** `dashboard/components/chat-bar.tsx` calls `POST /kernel/route`
   and renders `JSON.stringify(response)` — but `ChiefRouter.route()` returns only routing metadata
   (`{classified_intent, routed_to, task_id, task_status:"queued"}`), no assistant text. It fires a
   background task and never fetches its answer. The `api/advisor.py` endpoint *does* return real replies,
   but no chat surface consumes it. (An "ask your memories" chat exists only as plan/branch `feat/memory-chat`.)
3. **Autonomy** — real machinery, deliberately off by default (see §1).

## 3. Truly missing for a Jarvis

- **Real-world integrations** — no calendar, no email *reading*, no messaging (Slack/WhatsApp/Telegram).
  `config.py` has `google_credentials_json` / `google_delegated_user` placeholders "for Gmail/Calendar
  tools" but **no tool files exist**. SMTP is outbound-notify only. WhatsApp/Razorpay are specs, not code.
  This is the biggest *new* build and the thing that makes an assistant useful for life-admin.
- **Voice** — none (no STT/TTS anywhere).
- **Streaming conversational reply in the shipped UI** — nothing polls/streams a task's answer back.
- **Server-side push delivery** — client-side service-worker push handlers exist; server-side VAPID/webpush
  delivery is unconfirmed (needs the pending phone E2E to verify end-to-end).

## 4. The path to Jarvis, by leverage

Ordered by (payoff ÷ effort). Each is a separate brainstorm → spec → plan → build cycle.

1. **Build the streaming Jarvis chat surface (Sub-project A).** The persona layer already works and is
   deployed — the highest-ROI move is *surfacing* it: SSE token streaming + a persona picker + collapsible
   delegation steps, plus a small Jarvis coordination-prompt tune-up. This also closes the chat→reply loop
   (the chat consumes the persona's streamed reply instead of routing JSON). Spec:
   `docs/superpowers/specs/2026-08-05-jarvis-streaming-chat-design.md`.
2. **Ambient roles (Sub-project B).** Create `ScheduledJob`s for `scout`/`admin` so they run daily and post
   `Notification`s (Story 4 of `personal-roles.md`) — the remaining unbuilt piece of the persona layer.
3. **Confirm ambient roles + push reach the phone.** Verify the pending E2Es: web push + daily brief,
   reactive capture, distill button, model-health card. Then schedule `scout`/`admin` jobs so they surface
   things proactively.
4. **Add read-only real-world senses.** Calendar + email *reading* first (Google creds are already stubbed
   in `config.py`), before any action-taking. This is where Jarvis starts being useful outside dev work.
5. **Then** enable action-taking one rung up (L0→L1) through the existing trust/approval pipeline, and add
   messaging (WhatsApp/Telegram) as an interaction channel.
6. **Voice** — STT/TTS as the natural interface, once the above make it worth talking to.

**Continuous, in parallel:** keep feeding the brain — finish the transcript backfill (6 monster sessions
deferred, see the transcript-distillation work) so Jarvis reasons over real history.

## 5. Doc hygiene (do this soon)

- Refresh `START_HERE.md` — its "ALL CLOSED" gap section and July-12 date mislead; add the Jarvis layer,
  the deployed state, and the real remaining gaps (§2–§3 here).
- Refresh `KNOWLEDGE.md` "What's Next" — several listed `[ ]` items are shipped (watcher→task origination,
  seed personas, failure mining, big-decision detection).
- Note the **branch sprawl**: active-but-unmerged work lives across `feat/memory-chat`,
  `feat/chat-distillation`, `feat/multimodal-capture`, `feat/reactive-ui`, `worktree-personal-roles`,
  `batch-merge`. Decide what merges and what's abandoned before building more.
