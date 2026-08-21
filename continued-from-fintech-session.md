# Continuation notes: Claude usage tracking / sleep-safety work

This is a handoff from a long tangent in a different Claude Code session (working
directory: `d:\DevTools\Projects\work\fin-tech\.claude\worktrees\PM-S-STG-0378.5-source-account-mapping`,
a work project unrelated to life-graph). None of this touches life-graph's own
codebase — it's tooling that happens to live on this machine. Delete this file once
you've absorbed the context, or keep it as a reference; it's not part of life-graph itself.

## 1. Sleep-safety daemon (`D:\devtools\sleep-safety`)

Built to solve: system should never sleep/lock while Claude is running, but should
warn (not auto-sleep) if battery drops critically low or CPU overheats.

- `watcher.ps1` — polls battery (via .NET `SystemInformation.PowerStatus`, no WMI
  needed) and CPU temp (via LibreHardwareMonitor's HTTP JSON endpoint — its WMI
  provider was removed in 0.9.5+, .NET dropped support). On trigger, shows a
  Yes/No `MessageBox` dialog ("sleep now?") — **never sleeps automatically**, only
  if the user clicks Yes.
- `install.ps1` / `uninstall.ps1` — download/configure LibreHardwareMonitor,
  register two Scheduled Tasks (`LibreHardwareMonitor`, `SleepSafetyWatcher`),
  both set `AllowStartIfOnBatteries` (Task Scheduler's default blocks running on
  battery, which defeats the whole point — this was a real bug we hit and fixed).
- **Known gap**: both tasks trigger on `AtLogOn` only. If the machine sleeps/locks
  without a full logoff+logon, they silently stop and don't restart. Had to
  manually restart both mid-session today. If you want resilience here, consider
  adding a periodic self-check or a `AtStartup`-style trigger too.
- Also built `D:\devtools\docs\sleep-guard.html` / `guard-on.bat` / `guard-off.bat`
  — an earlier, simpler `powercfg`-based approach (no-sleep power plan settings).
  Superseded in spirit by the daemon above but still there/functional.

## 2. Claude usage tracking (`D:\devtools\claude-usage`)

Goal: monitor usage/quota across 4 Claude Pro/Max subscriptions (work + personal +
family). Landed on a layered approach after ruling out riskier options:

- **Declined approaches** (for the record, so they don't get re-proposed): scraping
  claude.ai's authenticated web session (ToS risk), reverse-engineering the private
  endpoint behind the "Account & usage" panel, extracting OAuth tokens to
  rotate/pool requests across multiple subscriptions to dodge rate limits (ToS
  circumvention, account-suspension risk — declined even for legitimate family use).
- **What's real and used**: Claude Code's official `statusLine` hook
  (`settings.json` → `statusLine.command`) delivers `rate_limits.five_hour` /
  `.seven_day` (real server-side quota, used_percentage + resets_at) via stdin —
  documented at code.claude.com/docs/en/statusline.md. This is the only legitimate
  source of the *real* pending/remaining quota; local logs can only ever estimate
  "used," never "remaining."
  - **Caveat**: `statusLine` is terminal-only — the VS Code extension does NOT
    invoke it (open GitHub issues #20207, #55643, unresolved). Fix: either use a
    plain terminal `claude` session, or set `"claudeCode.useTerminal": true` in VS
    Code user settings (applied already on this machine, but only affects *new*
    sessions, not ones already running).
- `capture-statusline.cjs` — the actual hook script. Reads stdin JSON, logs
  locally to `quota-log.jsonl`, prints a short status line, and — if this device
  has already been onboarded to `ai-usage-tracker` (see below) — forwards the
  quota reading as normalized rows to that collector's `/ingest` endpoint. Handles
  two identity cases:
  - Fixed device tag (`OTEL_RESOURCE_ATTRIBUTES` has `enduser.id=...`) → fast path.
  - No fixed tag (shared device, "whoever logs in") → falls back to `claude auth
    status` (async, after the visible line is already printed, so it never delays
    what you see).
- `server.mjs` + `dashboard.html` — a small local live dashboard (port 4319,
  `http://localhost:4319/`), read-only, re-reads real data on every request (no
  caching). Two tabs: **By Account** (used cost/tokens per subscription email,
  plus real pending quota once captured, else a manual "check claude.ai" link) and
  **By Person**. Currently running as a background process — may need restarting
  if the machine slept (same `AtLogOn`-fragility issue as above).
- `profile-map.json` — maps `CLAUDE_CONFIG_DIR` values to account emails (for
  multi-profile setups on one machine, tested with a real second login).

## 3. `ai-usage-tracker` (`C:\xampp\htdocs\ai-usage-tracker`) — pre-existing team tool, extended

This is a **real, already-deployed internal tool** (not built this session) — Node
collector + static dashboard, ingests real OpenTelemetry metrics from Claude Code
across the team, tracks cost/tokens/sessions per person. Has a store-and-forward
`agent.exe` for offline/remote devices, PIN-based self-serve onboarding
(`onboard.bat`), and is exposed via a Cloudflare tunnel (`ai.usage.website`) for
remote access — though the tunnel process itself doesn't survive reboot (needs
manual `cloudflared tunnel run ai-usage`, was down mid-session, restarted).

**Extended today** (uncommitted — diff is sitting in that repo, review before
committing):
- `assets/js/usage.js`: added `latestQuotaByPerson()` and `nearQuotaLimit()` —
  reads the new `quota.fiveHourUsedPct`/`quota.sevenDayUsedPct` metric rows
  (point-in-time readings, correctly takes latest value, not sum/max like the
  existing cost/token metrics).
- `assets/js/usage.test.js`: 2 new tests. Full suite: **61/61 passing**.
- `assets/js/pages/dashboard.js`: red alert banner when anyone's ≥80% on either
  quota window.
- No changes to the collector itself — quota rows flow through its existing,
  unmodified `/ingest` endpoint.

## 4. Family device plan (not yet built)

Context: 4 subscriptions used by the user + spouse + two kids, each on their own
separate physical device. Goal: monitor usage + restrict which models are
available (not usage caps — confirmed Claude Code has no per-device spend cap for
Pro/Max subscriptions, only Console/Team-org plans support that).

Plan agreed but **not yet executed**:
1. **Model restriction**: `managed-settings.json` at the OS-protected path
   (Windows: `C:\Program Files\ClaudeCode\managed-settings.json`), using the
   `availableModels` allowlist key — takes precedence over user settings, can't be
   overridden locally, requires admin access on that device (which the parent has).
   Not yet built — was about to build a template + per-device deployment
   instructions when the session ended.
2. **Onboarding the 4 devices to `ai-usage-tracker`**: reuse their *existing*
   agent/onboarding flow, not new infrastructure. Important nuance surfaced late
   in the session: since these devices may be shared ("anyone logs into their own
   account"), **do NOT set a static `enduser.id` device tag** via
   `enable-telemetry.bat` — Claude Code's OTel export auto-populates the real
   logged-in account's `user.email` on every metric when using OAuth login, so
   skipping the tag lets identity follow the actual account, not the device. This
   was verified against official docs, not assumed.
3. Not yet built: the actual deployment package/instructions to hand to each
   device.

## Where to pick this up

If continuing this exact thread of work, the natural next steps are (1) and (3)
above — the `managed-settings.json` template and the device deployment package.
Everything is real, tested code as of this handoff; nothing here is speculative.
