# Feature survey: the `jarvis-ai` ecosystem

**Date:** 2026-09-06
**Source:** [github.com/topics/jarvis-ai](https://github.com/topics/jarvis-ai) — 197 public repos.
**Sample:** the 6 substantive ones, read in full. The other ~190 are variations on a single
Python voice-command wrapper (speech-to-text → keyword match → shell out); their union adds
nothing this document doesn't already contain.

The point of this file is not to catalogue what other people built. It is to answer one
question: **of everything the ecosystem has converged on, what should Life Graph build, and
what should it deliberately refuse?** Sections 3 and 4 are the answer; sections 1–2 are the
evidence.

---

## 1. What was read

| Repo | Stars | What it actually is |
|---|---|---|
| [IRISX-AI/IRIS-AI](https://github.com/IRISX-AI/IRIS-AI) | 185 | Electron desktop agent. LanceDB vector memory, LangGraph orchestration. **Open-core** — the agent logic ships as compiled V8 bytecode. Widest feature surface by far. |
| [aerele/jarvis](https://github.com/aerele/jarvis) | 87 | AI teammate *inside* ERPNext. AGPL, ~3,000 commits. The only one with a serious opinion about permissions and approvals. |
| [GauravSingh9356/J.A.R.V.I.S](https://github.com/GauravSingh9356/J.A.R.V.I.S) | 1.3k | The archetype the other 190 copy. Stateless voice commands. |
| [akshayaggarwal99/jarvis-ai-assistant](https://github.com/akshayaggarwal99/jarvis-ai-assistant) | 622 | Mac voice dictation. Narrow but well-executed; local-first. |
| [gia-guar/JARVIS-ChatGPT](https://github.com/gia-guar/JARVIS-ChatGPT) | 459 | Voice + LangChain agent with an academic research mode. |
| [Avinashb722/jarvis-ai-assistant](https://github.com/Avinashb722/jarvis-ai-assistant) | 88 | Voice + biometrics + Android control via ADB. |

Two observations before the feature lists.

**Star count does not track engineering.** The 1.3k-star project is a stateless `if/elif`
chain. The 87-star project has 3,000 commits and a coherent permission model. Rank by commits
and README specificity, not by stars.

**The one with the best architecture won't show it.** IRIS-AI publishes its UI and framework
under MIT while the voice orchestration, tool execution, and automation internals are shipped
as bytecode. Its feature list is trustworthy as a statement of *ambition*; it is not
verifiable as a statement of *implementation*, and none of it is readable as reference code.

---

## 2. The combined capability list

Deduplicated union across all six, normalised into capability names. The **LG** column is the
honest current state, checked against `docs/STATE.md` (247 operations, 66 tables, 13 tools,
15 cron jobs) rather than from memory.

Legend: **✅ have** · **◐ partial** · **○ missing** · **✕ deliberately refused** (see §4)

### Memory & knowledge

| Capability | Seen in | LG |
|---|---|---|
| Persistent long-term memory across sessions | IRIS, gia-guar | ✅ core |
| Vector/semantic retrieval | IRIS | ✅ pgvector + hybrid graph search |
| Named, starred, searchable conversations | aerele, gia-guar | ✅ `conversations` |
| Explicit "core memory ingestion" — user pins a fact permanently | IRIS | ✅ capture spine |
| **"Wiki" — show what the system knows about X, its sources, its scope, and let you correct it** | aerele | ◐ `evidence` + `memory-links` exist; no single view |
| **Suggested learnings reviewed before they become rules** | aerele | ◐ shadow log + judgment engine grade actions, not learnings |
| Local file/folder semantic indexing | IRIS | ○ |
| Codebase RAG / repo oracle | IRIS | ○ (FORGE's job, not this one) |

### Autonomy & background work

| Capability | Seen in | LG |
|---|---|---|
| Background agents that monitor and report | aerele, IRIS | ✅ watchers + ambient roles |
| Scheduled multi-step sequences (daily/weekly/monthly) | aerele | ✅ 15 cron jobs + `tick_scheduled_jobs` |
| Triggers — start work when a record changes | aerele | ✅ EventBus (77 event types) |
| **Irreversible actions always wait for a person** | aerele | ✅ fail-closed autonomy — *convergent, see §3* |
| Saved business rules applied consistently | aerele | ◐ personas + procedures; not user-authored rules |
| Daily brief / digest | — | ✅ `run_daily_brief`, `run_daily_digest` |
| Proactive recommendations from usage patterns | Avinash | ✅ advisor + `failure_pattern_mining` |

### Input surfaces

| Capability | Seen in | LG |
|---|---|---|
| Wake-word / hands-free activation | IRIS, gia-guar, Avinash | ○ |
| Voice dictation with filler removal + grammar fix | akshay | ○ |
| Local speech-to-text (Whisper/Parakeet) | akshay, gia-guar | ○ |
| Text-to-speech on **all** replies, not just voice-originated | all | ◐ known charter gap |
| Image / PDF / spreadsheet attachments in chat | aerele | ◐ `multi-modal` (4 ops) |
| **Screen-region OCR capture** | IRIS | ○ |
| Telegram | — | ✅ shipped (migration 037) |
| WhatsApp | IRIS, Avinash | ○ |

### Documents & output

| Capability | Seen in | LG |
|---|---|---|
| **"File Box" — drop a bill/statement/price list, it reads it and prepares the work** | aerele | ○ |
| **Surfaces uncertainty instead of assuming silently** | aerele | ◐ judgment engine scores confidence; not surfaced this way |
| Approval board with the source conversation attached | aerele | ◐ approvals exist; provenance link is weaker |
| Spreadsheet import with preview before commit | aerele | ○ |
| Generate PDF / Excel / PowerPoint | IRIS | ○ |
| Export records and reports | aerele | ◐ NDJSON export only |
| **Turn a question into a saved, shareable dashboard** | aerele | ○ (18 fixed dashboard pages) |

### Integrations

| Capability | Seen in | LG |
|---|---|---|
| **Email reading** (Gmail) | IRIS | ○ **#1 charter gap** |
| Email drafting and send | IRIS, Gaurav | ○ |
| **Calendar** | — *(nobody had it)* | ○ **#1 charter gap** |
| Web browse / scrape / fill forms | IRIS, gia-guar | ◐ `browse_web` reads; no JS, no forms |
| Web search | IRIS | ✅ `web_search` |
| Deep multi-step research | IRIS, gia-guar | ✅ `run_all_research` weekly |
| Academic paper search + download | gia-guar | ○ |
| Terminal / shell execution | IRIS | ✅ `run_command` |
| Git operations | — | ✅ 4 git tools |
| Localhost tunnels | IRIS | ○ |

### Refused outright — see §4

Face-recognition login · fingerprint auth via ADB · Android touch/swipe injection · APK
deployment · window management · ghost keyboard injection · AI wallpaper engine · live CSS
mutation of websites · Spotify/media control · stock tickers · weather · "tell me the time" ·
YouTube download · Iron Man voice cloning · F.R.I.D.A.Y. persona toggle · team plans, billing,
seat management

---

## 3. The one finding that matters

**aerele/jarvis independently arrived at Life Graph's autonomy invariant.**

Their README: *"Reading and explanations happen directly; important or irreversible actions
require approval."* That is, near-verbatim, the fail-closed rule in `CHARTER.md` — an action
that cannot be matched to a safe pattern is classified dangerous and queued rather than run.

Two projects with no shared lineage, one built inside an ERP and one built as a memory OS,
converging on the same rule is meaningful evidence. It suggests the rule is a property of the
problem, not a stylistic preference — and that the pressure to relax it (L0 → L1) should be
resisted until shadow mode produces graduation data, exactly as the charter already says.

Their **permission model** is the part worth copying. Jarvis-in-ERPNext does not maintain its
own access rules; it inherits each user's existing Frappe permissions, so the assistant
provably cannot see more than the person operating it. Life Graph's equivalent is
`tenant_id` scoping, which is isolation between tenants but not *delegation within* one. If
the system ever reads a real inbox or a real ERP on someone's behalf, "the agent sees exactly
what you see, by construction" is the property that makes it defensible.

---

## 4. What to refuse, and why

Most of the ecosystem's feature surface is disqualified by charter, not by difficulty. Writing
that down is the point of this document — otherwise a long feature table reads as a backlog.

**Non-goal 6 — "Not a wrapper."** Roughly 60% of the union is voice-triggered shell commands:
open a website, play music, tell the time, fetch the weather, download a YouTube video. These
are `if/elif` chains with a microphone. They inflate a feature list and add nothing a memory
system can reason over.

**Non-goal 7 — "Not a team product."** aerele's plan management, seat limits, usage review and
billing are load-bearing for a commercial ERP add-on and irrelevant to a self-hosted system
with one user.

**Not in the problem statement.** IRIS's desktop-manipulation layer — window teleporting,
keyboard injection, wallpaper generation, live CSS mutation, remote Android touch control, APK
deployment — is an enormous attack surface and maintenance burden in service of a demo. Every
one of those is a way for an autonomous agent to do something irreversible to a machine.

**Biometrics as theatre.** Face and fingerprint auth appear in several projects as an Iron Man
flourish. A self-hosted single-user system already behind an auth layer gains nothing.

---

## 5. Shortlist

Ordered by value per unit of work, filtered through §4.

1. **Email reading, then calendar.** Already the charter's top gap; the survey confirms
   nobody in this space has solved calendar at all, and email only shallowly. Credential
   stubs already exist in `config.py`.
2. **A "File Box" ingestion workflow.** Drop a PDF, statement or spreadsheet; the system reads
   it, prepares the resulting memories or actions, and **surfaces what it is unsure about**
   rather than guessing. This composes with the existing approval queue and multi-modal
   ingest, and it is the single most-praised feature in the one repo that has real users.
3. **Spreadsheet/document import with a preview step.** The natural first slice of (2), and
   cheap.
4. **A "what do you know about X" view** — the claim, its evidence, its scope, and a
   correction affordance. Life Graph already stores all three; it has no page that shows them
   together. High trust value for low build cost.
5. **Document generation — PDF and spreadsheet.** Export today is NDJSON, which serves
   portability but not life-admin. Skip PowerPoint.
6. **Command palette across memories, conversations, dashboards and records.** Small, and it
   is how a system with 247 endpoints becomes navigable.
7. **TTS on every reply.** Already a known gap; the survey shows it is table stakes.
8. **Wake word.** Only after 7. Meaningful for hands-free capture, which serves the
   "no capture friction" non-goal directly.

Deliberately *not* on this list: web form-filling (real automation value, but it is the
autonomy-risk surface the charter is most careful about — revisit after L1), and codebase RAG
(FORGE's territory).

---

## 6. Corrections to make elsewhere

- **`CHARTER.md` is stale on messaging.** It lists WhatsApp/Telegram as *"Specs exist, no
  code."* Telegram shipped — migration `037_telegram_bridge`, 4 endpoints, a
  `purge_telegram_pairing_codes` cron. Only WhatsApp remains unbuilt.
- **Naming.** 197 repos carry this topic, essentially all of them Iron Man fan projects of
  wide quality variance. "Jarvis" is fine as an internal layer name and actively harmful as an
  external one — it places the project next to `JARVIS-MARK5` rather than next to anything
  serious. Worth a deliberate decision if the project ever faces outward.
