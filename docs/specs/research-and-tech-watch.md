# Jobs 6 and 10 — Research on Demand, Tech Watch: Feature Spec

> **Status: Spec'd, building** (2026-10-20). Jobs 6 and 10 of
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
- **AC-6.4** `POST /api/v1/research {question}` → `{answer, sources: [{url, title}], claims: [{text,
  sources}], pages_read, model}`. *(integration test)*
- **AC-6.5** Eval: 6 questions over frozen pages with known facts; pass = every claim's source is
  a page that states it, ≥ 5/6 questions answered. *(eval script)*

## Job 10 — tech watch

A weekly digest of what is genuinely new on the owner's topics, each item with its source.
First topics: **open models that fit 16 GB** (Ollama-ready), **AI coding agents** (new tools and
releases).

- **AC-10.1** Topics are settings: `tech_watch_topics` (JSON: name → queries). *(test)*
- **AC-10.2** Daily, per topic: SearXNG queries → unread result pages (seen set per topic) → the
  `topic_reader` worker returns findings `{title, summary, source, published_on?}` that are about
  the topic and new; findings without a fetched source are dropped. *(test)*
- **AC-10.3** Findings are stored once per normalised source URL per topic (`topic_findings`).
  *(integration test)*
- **AC-10.4** Weekly (Monday's brief) a "Tech watch" section lists up to 6 findings per topic not
  yet sent, with their source; they are then marked sent. Nothing new → no section. *(test)*
- **AC-10.5** `GET /api/v1/tech-watch?topic=` lists findings. *(integration test)*

## Data

```sql
CREATE TABLE topic_findings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    topic       TEXT NOT NULL,
    dedup_key   TEXT NOT NULL,         -- normalised source URL
    title       TEXT NOT NULL,
    summary     TEXT,
    source_url  TEXT NOT NULL,
    published_on DATE,
    found_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ,           -- when it went out in a digest
    UNIQUE (tenant_id, topic, dedup_key)
);
```

## Design

- `services/research.py`: `research(question, tenant_id)` for Job 6; `scan_topic(...)`,
  `digest_lines(...)` for Job 10. Shares `llm_offers.read_pages` (moved to a common
  `services/web_pages.py`: search → unread URLs → fetched text).
- Templates in `worker_templates.py`: `researcher` (answer + claims JSON) and `topic_reader`
  (findings JSON), both `reasoning=False`, both validated like `offer_reader`.
- ARQ: `run_tech_watch` daily 22:00 UTC; the digest is built in the brief on Mondays.
- Migration 051.

## Tasks

1. `services/web_pages.py` (search → candidates → read), used by Job 1 too. S
2. `researcher` template + `research()` + citation validation; eval with frozen pages. M
3. `POST /research`. S
4. Migration 051 `topic_findings`; `topic_reader` template; `scan_topic`; ARQ job. M
5. Monday digest section; `GET /tech-watch`. S
6. Tests; live run; STATE.md. S
