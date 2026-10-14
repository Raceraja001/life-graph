# Assistant Capabilities Beyond Development — Roadmap Spec

> **Status: Built (2026-10-14), Phases A–H.** The user handed this over to plan and
> build without waiting ("plan for them and do them without waiting for me").
>
> **Where each piece lives:**
>
> | Phase | Code |
> |---|---|
> | A | `tools/web_search.py`, `services/safe_fetch.py`, `services/sources.py`, `services/persona_context.py`, `tools/shell_allowlist.py`, `docker/searxng/` |
> | B | `services/documents.py` (migration 045) |
> | C | `services/money.py` (046) |
> | D | `services/page_monitors.py` with `watchers/page_monitor_watcher.py` (047) |
> | E | `watchers/app_uptime_watcher.py` |
> | F | `services/assistant_chat.py`, the Telegram router, the `assistant` persona |
> | G | `services/study.py` (048) |
> | H | `services/invoices.py` (049), the `support-desk` persona |
>
> Shared pieces: `api/assistant.py`, `tools/assistant.py`, `services/assistant_daily.py` (daily sweep and the brief's "Coming up") and `watchers/provision.py`.
>
> **Stubbed, behind settings:**
>
> | What | How it is stubbed | Setting that switches it on |
> |---|---|---|
> | TTS | Replies are text only | `tts_base_url` |
> | Bank feeds | Statements by CSV, alerts pasted or sent with `/txn` | — |
> | PDF statements | Unsupported | — |
> | Invoice sending | Returns the email as a draft for the user to send | — |
> | Customer-facing support endpoint | Not built; the persona works from chat and the kernel API | — |
>
> **Where the build differs from the text below:**
> - **Scout findings arrays** are checked per finding, in place. Each finding is marked `unverified` when its `source` was not fetched in the run. An appended note would break findings_bridge's JSON contract.
> - **Every tool-using persona** now gets the current date. A live run showed qwen3 calling a two-week-old release "a future date".
> - **Support-desk is not source-checked**, because it cites file paths rather than URLs. Instead its file tools are *confined* to the project's README and docs/ at run time, so a prompt rule is not the only boundary.
> - **Startup reconciles built-in personas for every tenant that has personas**, not only `default`. Before this, new personas and prompt fixes never reached the user's tenant.
> - **Fixed along the way:** the project register and PATCH request models silently dropped the settings added by the autonomous-development roadmap (base_branch, smoke and rollback commands, the sandbox and deploy settings). They are now declared.
> - **Budget alerts are a sweep, not a watcher.** They run with the other daily reminders an hour before the brief, so they are held for it.
> - **No `/doc` command:** the `/doc` caption is read on the photo itself, and media is now routed before commands.

## Goal

Life Graph is a personal assistant; software development is one kind of work
it does. This roadmap fills the other kinds, building on what already works
rather than beside it.

**Already built and reused here** (not rebuilt):
- connectors: mail, calendar, contacts, Google Tasks and GitHub (`plugins/`);
- bills and renewals from mail, plus promises the user made in sent mail;
- the daily brief and the digest;
- the watcher framework (hourly cron, events, notification routing);
- the Telegram bridge (capture of text, photos with OCR and voice notes with
  transcription, plus outbound notifications);
- the capture spine and the memory graph;
- the production-findings fix loop from autonomous-app-development.md.

**Gaps found on 2026-10-12/14** (see the agent survey):
- web search needs a paid Tavily key, so the research personas cannot search;
- `browse_web` fetches any URL, including private network addresses;
- the research persona invented a finding with no source;
- personas with code tools are not told which projects exist;
- shell execution is either off or an unrestricted shell string;
- Telegram is capture-only: the user cannot *ask* the assistant anything there;
- documents, money, page monitoring, app uptime, study and invoicing are absent.

## Constraints kept

- **Local-first and $0.** Personal data stays on the local model (qwen3 on
  Ollama). Nothing here spends the user's money or adds a paid dependency.
- **Third parties are stubbed behind settings**, for example a hosted search
  API, a TTS server, a bank feed or an email sender for invoices. The code
  paths are real and tested with fakes, and switching them on is configuration.
- **Read-only by default.** Nothing sends mail, pays a bill or moves money.
  Anything outward-facing is a draft, or goes through an approval.
- **Tenant isolation.** Every row is scoped by `tenant_id`, as everywhere else.
- **Record everything.** Agent runs keep flowing into the trajectory and
  observability tables, so these capabilities can be studied as well.

## Phases

### Phase A — Foundations the other agents need
1. **Free web search.** `web_search` gains providers: SearXNG (self-hosted,
   no key), Tavily (when a key is set) and a keyless DuckDuckGo HTML fallback.
   The provider is chosen by `web_search_provider` (default `auto`, which
   tries SearXNG, then Tavily, then DuckDuckGo).
2. **Safe fetching.** `browse_web` and every monitor fetch refuse private,
   loopback and link-local addresses, unless the host is on an allowlist
   (`fetch_allow_hosts`). Each redirect hop is checked as well.
3. **Sourced answers.** Research personas (`require_sources`) must cite URLs
   that a tool actually returned in this run. An answer that cites nothing it
   fetched gets a visible "unverified" note, and the run records
   `sources_checked` and `unsourced_urls`.
4. **Project context.** Personas holding code, file or git tools get a
   "Projects you can work on" block (name, path, base branch) in their system
   prompt.
5. **Allowlisted shell.** `tool_shell_mode=allowlist` runs commands with exec
   and no shell, accepts only allowlisted read-only programs, and rejects shell
   metacharacters. This makes `ops` useful without granting an arbitrary shell.
   `full` keeps the old behaviour, and `off` is unchanged.

### Phase B — Documents vault
- A `documents` table holds the kind (passport, licence, insurance, warranty,
  contract, ID, receipt, other), title, issuer, the last 4 characters of the
  number only, issue and expiry dates, and the source capture.
- **Extraction** from OCR or text uses the local model. Dates are parsed
  deterministically and never taken from the model's arithmetic.
- **Expiry reminders** at 60, 30, 7 and 1 days before, through the
  notification engine, plus a brief section **Documents expiring**.
- **Interfaces:**
  - API: `POST /documents` (text, or an image through the existing OCR) and
    `GET`/`DELETE`;
  - tool: `documents_expiring`;
  - Telegram: a photo captioned `/doc` is filed as a document.

### Phase C — Money
- **Transactions:**
  - CSV statement import with column detection (date, description, debit and
    credit, or amount), deduplicated by a hash;
  - a parser for Indian bank SMS or alert text (debited or credited, amount,
    merchant, the last 4 digits of the account). The user forwards the text or
    pastes it in;
  - a PDF statement is a stub for now; it is an unsupported type until a
    parser exists.
- **Categories:** deterministic merchant rules first, then the local model,
  with the user's correction stored as a rule.
- **Budgets** per category per month. A `budget` watcher alerts at 80% and
  100% of a budget.
- **Interfaces:** the tool `spending_summary`, the API
  `/money/{transactions,import,budgets,summary}`, and a brief line on
  spending.

### Phase D — Page monitors
- `page_monitors` hold the URL, an optional CSS-like selector or regex, a mode
  (`change`, `price_below` or `contains`), a threshold, the last hash and the
  last value.
- **Behaviour:**
  - the `page_monitor` watcher checks the tenant's monitors on their interval
    through the safe fetcher;
  - a change, a price under the threshold or a text appearing emits an event
    with the before and after values;
  - a monitor that fails 5 times in a row is paused.
- **Interfaces:**
  - API CRUD;
  - the tool `watch_page`, so the scout can set one up when asked ("tell me
    when this drops under ₹20,000").

### Phase E — Ops for the apps it builds
- The `app_uptime` watcher runs for every project that has `health_url` set.
  It records the HTTP status, latency and days until TLS certificate expiry.
- **When a check fails:**
  - two consecutive failures emit an event and call
    `production_findings.file_fix_task`, deduplicated as it already is;
  - a certificate under 14 days emits a warning.
- **Backups:** the project key `backup_check_command` runs nightly; a failure
  or a missing backup emits an event. This is a stub until a project defines
  one.

### Phase F — Talk to it on Telegram, with voice
- **Asking:** `/ask <question>` answers through the assistant persona
  (setting `telegram_assistant_persona`, default `admin`, the persona with
  tools) via the process manager. `/chat` switches the chat into conversation
  mode, so that plain messages are questions until `/capture` switches back.
- **Voice in conversation mode:** a voice note is transcribed and answered.
  When `tts_base_url` is set, the reply is spoken as well, using an
  OpenAI-compatible `/v1/audio/speech` endpoint (speaches on :8010 locally).
  Without it, the reply is text only; that is the stub.
- **Unchanged:** replies are redacted on the bridge's single outbound path, as
  now.

### Phase G — Learning
- `review_cards` hold the front, the back, the source memory and the
  scheduling fields (ease, interval, repetitions, due), using SM-2.
- **Generation:** the local model writes cards from memories matching a topic,
  or from pasted notes. Duplicates are skipped.
- **Interfaces:**
  - API: `due`, `grade` and `generate`;
  - Telegram: `/review` sends the next due card and accepts `again`, `hard`,
    `good` or `easy`;
  - a brief line with the count of cards due.

### Phase H — Business operations (commercial)
- **Invoices:**
  - an `invoices` table (client, line items, currency, tax, status, issue and
    due dates) with numbering per tenant;
  - HTML rendering;
  - an `invoices_overdue` watcher that drafts reminder text.
  - **Sending is a stub:** a draft goes through an approval, and mail sending
    is not wired up.
- **Support desk:** the `support-desk` persona answers customer questions
  about an app from that project's docs and README. It uses read-only code
  tools, must cite sources, and escalates when the docs have no answer.

## Order and verification

The phases run in order A → H, and each is committed with:
- unit tests for its pure logic;
- integration tests against the database for its storage and API;
- for watchers, a run through `BaseWatcher.run()` with fake fetches.

CI must stay green.
