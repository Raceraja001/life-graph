# Jobs 6 and 10 — Research on Demand, Tech Watch: Feature Spec

> **Status: Built** (2026-10-20). Jobs 6 and 10 of
> [Jarvis and its workers](../design/11_persona_roster_plan.md). Both reuse Job 1's research
> pieces ([free-llm-offers.md](free-llm-offers.md)): search and fetch in plain code, a worker in
> the research envelope that only reads what it is handed, validated output.

## Job 6 — research on demand

The owner asks a question ("compare Groq and Cerebras free tiers", "what's new in OpenCode")
and gets a short answer in which **every claim cites a page fetched in that run**.

- **AC-6.1** GIVEN a question WHEN research runs THEN plain code searches (SearXNG), reads up to
  `research_max_pages` (5) result pages, and the `researcher` worker (research envelope, no tools,
  reasoning off) answers from them only. *(test)*
- **AC-6.2** The answer's sources are the URLs it cites; a cited URL that was not fetched in the
  run is removed, and a claim left with no source is dropped. If nothing survives, the answer is
  "I could not find this in the pages I read" with the pages listed. *(test)*
- **AC-6.3** The question passes the scrub before it leaves the machine (personal details
  hidden). *(test)*
- **AC-6.4** `POST /api/v1/research {question}` → `{question, answer, sources: [{url, title}],
  claims: [{text, sources}], pages_read: [{url, title}], model}`. *(integration test)*
- **AC-6.5** Eval: 6 questions over frozen pages with known facts; pass = every claim's source is
  a page that states it, ≥ 5/6 questions answered. *(eval script)*

## Job 10 — tech watch

A weekly digest of what is genuinely new on the owner's topics, each item with its source.
First topics: **open models that fit 16 GB** (Ollama-ready), **AI coding agents** (new tools and
releases).

- **AC-10.1** Topics are settings: `tech_watch_topics` (JSON: name → queries; `{month}` in a
  query becomes the current month). Runs for `tech_watch_tenants`. *(test)*
- **AC-10.2** Daily, per topic: SearXNG queries → unread result pages (seen set per topic) → the
  `topic_reader` worker returns findings `{title, summary, source, published_on}` that are about
  the topic and new; findings without a fetched source, or without a date in the last 45 days,
  are dropped. *(test)*
- **AC-10.3** Findings are stored once per item (normalised source URL + title) per topic
  (`topic_findings`). *(integration test)*
- **AC-10.4** Weekly (Monday's brief) a "Tech watch" section lists up to 6 findings per topic not
  yet sent, with their source; they are then marked sent. Nothing new → no section. *(test)*
- **AC-10.5** `GET /api/v1/tech-watch?topic=` lists findings. *(integration test)*

### Feature watch: ideas for Jarvis (2026-10-27)

The owner: "always search for new features in mega apps and bring them here". A topic with
`"ideas": true` is a feature-watch topic.

- **AC-10.6** Feature-watch topics take search results one query at a time, at most 2 pages per
  site (`web_pages.candidates(spread=True)`): the first run let one tracker and the ChatGPT query
  fill all six pages. *(unit test)*
- **AC-10.7** Every finding's source is rated `official` (the vendor's site or GitHub
  organisation), `suspicious` (a GitHub repo named after a watched app outside its organisation —
  the first run reported a copycat "open-webui-2026" repo as a release) or `unknown`
  (`services/source_trust.py`). Suspicious findings are never offered as ideas nor sent in the
  brief. *(unit test)*
- **AC-10.8** After each run, the topic's unassessed findings are judged against
  `docs/feature-watch/capabilities.md`: feature or not (pricing, payment methods and news are
  not), app, `have` / `part` / `new`, one suggestion. The worker has no tools; its reply is
  stored as text. *(unit test on validation)*
- **AC-10.9** `GET /tech-watch/ideas?status=open|considering|decided|flagged|all` lists them;
  `POST /tech-watch/{id}/decision` `{"decision": "consider"|"not_for_us"|"dismiss"|"reset"}`
  records the owner's choice. "Consider" only marks it: it starts no task, because the text came
  from a web page. *(integration test)*
- **AC-10.10** The brief leaves out findings ruled out, dismissed, suspicious or judged not a
  feature, and shows an assessed one's fit and suggestion. *(integration test)*
- **AC-10.11** Pricing never reaches the model: a title or summary about tiers, plans,
  subscriptions or payment methods is `is_feature = false` in code
  (`feature_ideas.is_pricing`) — the first run judged "Pro 500 tier" a feature. Each feature
  is rated `worth` `high` / `medium` / `low` with a reason; ideas list most worth first.
  `assess(..., redo=True)` judges the undecided ones again after the capability list changes.
  *(unit + integration test)*
- **AC-10.12** The same feature from two sites is one idea: the assessor names `same_as` (a
  finding of the batch or a known idea); the repeat is stored with `duplicate_of`, left out of
  the list and the brief, and its link shows under the first one's `also_from`.
  *(integration test)*

## Data

```sql
CREATE TABLE topic_findings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    topic       TEXT NOT NULL,
    dedup_key   TEXT NOT NULL,         -- normalised source URL + '#' + title slug
    title       TEXT NOT NULL,
    summary     TEXT,
    source_url  TEXT NOT NULL,
    published_on DATE,
    found_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ,           -- when it went out in a digest
    UNIQUE (tenant_id, topic, dedup_key)
);
```

## Design (as built)

- `services/web_pages.py`: `candidates(queries, limit, skip)` → `Hit(url, title)`, `read(urls)`,
  `seen`/`mark_seen` (Redis sets), `as_inputs`. Job 1's `candidate_pages`/`read_pages` now use it.
- `services/web_research.py`: `research(question, tenant_id)` for Job 6; `scan_topic`,
  `tech_watch`, `digest_lines`, `dated_queries`, `finding_key` for Job 10.
- Templates in `worker_templates.py`: `RESEARCHER` (claims JSON, `validate_claims`) and
  `topic_reader(topic, today)` (findings JSON, `validate_finding`), both `reasoning=False`.
- `api/web_research.py`: `POST /research`, `GET /tech-watch` (the preference research engine
  keeps `/research/runs` and `/research/trigger` in `api/research.py`).
- ARQ: `run_tech_watch` daily 22:00 UTC; the digest is built in the brief on Mondays.
- Migration 051.
- Eval: `evals/research/` (6 made-up pages, 6 questions) and `scripts/eval_researcher.py`.

## Changed while building

- **Seen sets never matched in Job 1.** `candidate_pages` compared a normalised key against
  the raw URLs stored in the seen set, so pages already read were read again. `web_pages`
  normalises both sides.
- **A preferred model for reading.** The free cloud list is ordered for coding; on the researcher
  eval cohere/north-mini-code scored 4/6 → 5/6 after brief fixes (it cited an off-topic page, and
  concluded "won't fit 16 GB" from the 16-bit figure alone), Nemotron 3 Super 6/6.
  `research_models` reorders the research envelope's models (it can only reorder the free list,
  never add to it); set to Nemotron 3 Super.
- **One row per item, not per page.** A blog index holds many releases (16 valid on
  ollama.com/blog in the first live scan); keyed by page alone, 11 were lost.
- **Undated means not news.** The first live scan's undated findings were model-library
  listings ("Qwen3.5 released"). A finding now needs a date within 45 days; the reader is told
  today's date and the cut-off.
- **`{month}` in queries.** Undated queries returned evergreen "best of" lists whose items were
  months old (all dropped by the date rule).

- **Topic rules in code** (after the reader eval, below). Both free models kept a 250 GB model
  under "fits 16 GB" and a runtime release under a models topic whatever the brief said. A
  topic may now declare `kind` ("model" / "tool") and `max_memory_gb`; the reader reports each
  finding's kind and stated memory, and `validate_finding` drops what breaks the rules. When a
  page gives no memory figure, it is estimated from the parameter count in the name (0.6 GB
  per billion at 4-bit; the reader reported null for "needs about 250 GB").

## Reader eval

`scripts/eval_topic_reader.py` over `evals/tech_watch/` (six made-up pages: a blog index, a
model card, a "best of" guide, release notes, a comparison, a tutorial; today fixed at
2026-10-20; the topics' real rules from settings). Pass = every new release found, nothing
forbidden kept (old releases, oversize models, off-kind items, the guides themselves). Before
the rules: both models FAIL (kept Heron 480B and a runtime). After: Nemotron 3 Super and
cohere north-mini PASS, twice each.

## Known gaps

- Live pages are messier than the eval: an item from a guide may still be dated by the page
  rather than its release.
- The same release under different titles on two pages is two rows (same title in one run is
  one).
- A blog index is skipped for 30 days once read, though it is the page that changes.
