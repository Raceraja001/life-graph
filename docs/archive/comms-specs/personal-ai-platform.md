# Personal AI Platform — Personal AI Platform

> Personal AI Platform � knows you, improves itself, watches your back.
> **Status:** ACTIVE — This is the ONLY thing we're building from scratch.
> **Date:** 06 Jul 2026

---

## Vision

Three products that don't exist yet. Each solves a real limitation in current AI:

| Product | What It Is | Current Limitation It Solves |
|:--------|:-----------|:----------------------------|
| **Core (Knowledge Engine)** | Knowledge Engine — AI that knows YOU and challenges your assumptions | AI is generic, doesn't remember your context or preferences |
| **Learn (Self-Optimizer)** | Self-Optimizing Agent — AI that fixes its own mistakes automatically | Agents repeat the same errors, humans must manually fix prompts |
| **Watch (Ambient AI)** | Ambient AI — AI that proactively helps without being asked | AI is reactive (you ask → it answers), never proactive |

Combined: **a personal AI platform that knows you, improves itself, and watches your back.**

---

# Product 1: Core (Knowledge Engine) (Knowledge Engine)

## Problem Statement

You have opinions: "FastAPI for backend", "PostgreSQL only", "self-hosted over cloud". But you formed these opinions months or years ago. The tech world changes weekly. **Nobody is checking if your opinions still hold.**

Current tools:
- ChatGPT → generic, doesn't know your context, forgets everything
- Perplexity → search engine, no memory of your preferences
- Obsidian → passive notes, YOU have to organize and update

**What's missing:** An AI that stores your preferences, actively researches alternatives, and tells you when you should reconsider — with evidence.

## User Stories

### US-1: Capture a Preference
**As a** developer
**I want to** record my technical preferences with context
**So that** my AI advisor knows my baseline opinions

**GIVEN** I have a preference about a technology choice
**WHEN** I tell my AI "I prefer FastAPI for backend because I know Python well"
**THEN** the system stores:
- Topic: `backend_framework`
- Choice: `FastAPI`
- Reason: `Python expertise, async support`
- Context: `solo developer, 16GB RAM, SaaS apps`
- Confidence: `0.9` (explicitly stated)
- Date: `2026-07-06`

### US-2: Get a Multi-Model Opinion
**As a** developer
**I want to** ask a question and get perspectives from multiple AI models
**So that** I get a balanced view, not a single model's bias

**GIVEN** I ask "Should I use Go instead of FastAPI for a webhook processor?"
**WHEN** the system processes my question
**THEN** it:
1. Queries 3 models in parallel (GPT-4o-mini, DeepSeek, Groq/Llama)
2. Injects MY context (solo dev, Python expert, existing FastAPI codebase)
3. Returns structured comparison:
   - Per-model recommendation + reasoning
   - Consensus score (3/3 agree = high, 2/3 = medium, split = low)
   - Evidence links
   - Final suggestion weighted by MY context

### US-3: Automated Research Challenge
**As a** developer
**I want** the system to periodically research whether my preferences still hold
**So that** I don't get stuck with outdated opinions

**GIVEN** I have a stored preference (e.g., "FastAPI for backend")
**WHEN** the weekly research cron runs
**THEN** the system:
1. Uses browser-use to scrape: benchmarks, HN discussions, Reddit threads, GitHub trending
2. Queries multiple models: "Given these new findings, is FastAPI still the best choice for [MY CONTEXT]?"
3. Updates the knowledge graph with new evidence
4. If confidence drops below 0.7 → sends me a proactive notification:
   "⚠️ Your preference for FastAPI may need review. Go 1.23 introduced X which solves your main objection. Evidence: [3 links]"

### US-4: Evidence-Based Suggestion
**As a** developer
**I want** to get suggestions when starting a new project
**So that** I make decisions based on evidence, not habit

**GIVEN** I start a new project and specify requirements: `high throughput, webhook processing, 50K req/sec`
**WHEN** I ask "What tech stack should I use?"
**THEN** the system:
1. Searches my knowledge graph for relevant preferences and evidence
2. Scores each option against the specific requirements
3. Returns: "FastAPI scores 72/100 (your expertise is high but throughput ceiling is 8K/sec). Go scores 88/100 (learning curve but handles 50K/sec natively). Evidence: [benchmarks]"
4. If suggestion differs from my preference → explains WHY with evidence

### US-5: Knowledge Graph Navigation
**As a** developer
**I want** to see my knowledge as a visual graph
**So that** I can explore connections between my decisions

**GIVEN** I have 50+ preferences and 200+ evidence entries
**WHEN** I open the knowledge graph view
**THEN** I see:
- Nodes: my preferences (FastAPI, PostgreSQL, self-hosted, etc.)
- Edges: relationships (FastAPI → Python → my expertise)
- Color: confidence level (green=high, yellow=medium, red=needs review)
- Click a node → see all evidence, history of changes, related preferences

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Core (Knowledge Engine)                              │
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Preference   │  │ Multi-Model │  │ Research         │  │
│  │ Store        │  │ Advisor     │  │ Engine           │  │
│  │              │  │             │  │                  │  │
│  │ POST /pref   │  │ POST /ask   │  │ Cron: weekly     │  │
│  │ GET /prefs   │  │ → 3 models  │  │ → browser-use    │  │
│  │ PUT /pref    │  │ → merge     │  │ → scrape sources │  │
│  │              │  │ → score     │  │ → update graph   │  │
│  └──────┬───────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                 │                   │           │
│  ┌──────▼─────────────────▼───────────────────▼────────┐  │
│  │              KNOWLEDGE GRAPH                         │  │
│  │         PostgreSQL + pgvector + Apache AGE           │  │
│  │                                                      │  │
│  │  Nodes: preferences, technologies, evidence          │  │
│  │  Edges: supports, contradicts, related_to            │  │
│  │  Vectors: semantic search on evidence                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              EXTERNAL INTEGRATIONS                    │  │
│  │  ├── LiteLLM (GPT-4o-mini, DeepSeek, Groq)          │  │
│  │  ├── browser-use (web scraping)                       │  │
│  │  ├── Mem0 (memory pipeline)                           │  │
│  │  └── Antigravity transcripts (learn from sessions)    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Data Model

```sql
-- Core tables

CREATE TABLE preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic VARCHAR(200) NOT NULL,          -- 'backend_framework'
    choice VARCHAR(200) NOT NULL,          -- 'FastAPI'
    reason TEXT,                            -- 'Python expertise, async'
    context JSONB DEFAULT '{}',            -- {"role": "solo_dev", "ram": "16GB"}
    confidence FLOAT DEFAULT 0.5,          -- 0.0 to 1.0
    source VARCHAR(50) NOT NULL,           -- 'explicit', 'inferred', 'research'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_validated TIMESTAMPTZ,            -- when was this last research-checked?
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preference_id UUID REFERENCES preferences(id),
    content TEXT NOT NULL,                  -- the finding
    source_url TEXT,                        -- where it came from
    source_type VARCHAR(50),               -- 'benchmark', 'article', 'reddit', 'ai_opinion'
    model_source VARCHAR(100),             -- 'gpt-4o-mini', 'deepseek', 'groq/llama'
    supports BOOLEAN,                      -- true=supports preference, false=contradicts
    strength FLOAT DEFAULT 0.5,            -- how strong is this evidence?
    embedding VECTOR(384),                 -- for semantic search
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE advisor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    models_queried TEXT[] NOT NULL,        -- ['gpt-4o-mini', 'deepseek', 'groq/llama']
    responses JSONB NOT NULL,             -- per-model responses
    consensus_score FLOAT,                -- 0.0 (split) to 1.0 (unanimous)
    final_recommendation TEXT,
    cost_usd FLOAT,                       -- total API cost
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE research_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preference_id UUID REFERENCES preferences(id),
    trigger VARCHAR(50) NOT NULL,          -- 'scheduled', 'manual', 'confidence_drop'
    sources_scraped TEXT[],               -- URLs visited
    findings_count INT DEFAULT 0,
    confidence_before FLOAT,
    confidence_after FLOAT,
    recommendation TEXT,                   -- 'maintain', 'review', 'change'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Apache AGE graph (for relationships)
-- SELECT * FROM cypher('Platform', $$ 
--   CREATE (f:Tech {name: 'FastAPI', type: 'framework'})
--          -[:BUILT_WITH]->
--          (p:Tech {name: 'Python', type: 'language'})
-- $$) AS (result agtype);
```

## API Endpoints

```
POST   /api/preferences              — Store a new preference
GET    /api/preferences              — List all preferences (with filters)
GET    /api/preferences/:id          — Get preference with all evidence
PUT    /api/preferences/:id          — Update preference
DELETE /api/preferences/:id          — Soft-delete preference

POST   /api/ask                      — Multi-model advisor query
GET    /api/ask/history              — Past advisor sessions

POST   /api/research/run             — Trigger manual research for a preference
GET    /api/research/runs             — List research runs with results

GET    /api/graph                    — Knowledge graph data (for visualization)
GET    /api/graph/explore/:node_id   — Explore connections from a node

POST   /api/ingest/transcript        — Ingest Antigravity transcript for preference extraction
POST   /api/ingest/bookmark          — Save a URL with auto-tagging
```

## Key Implementation Details

### Multi-Model Advisor (the core function)
```python
async def ask(question: str, context: dict) -> AdvisorResponse:
    """Ask 3 models the same question, merge insights"""
    
    # 1. Enrich with stored preferences
    relevant_prefs = await search_preferences(question)
    
    # 2. Build context-aware prompt
    prompt = f"""About me:
    - Solo developer, Python expert, Windows + ARM
    - My existing preferences: {format_prefs(relevant_prefs)}
    - My specific context: {json.dumps(context)}
    
    Question: {question}
    
    Respond with JSON:
    {{
        "recommendation": "...",
        "confidence": 0.0-1.0,
        "pros": ["..."],
        "cons": ["..."],
        "evidence": ["..."],
        "compared_to": [{{"option": "...", "score": 0-100, "reason": "..."}}]
    }}"""
    
    # 3. Query 3 models in parallel
    results = await asyncio.gather(
        litellm.acompletion(model="gpt-4o-mini", messages=[...]),
        litellm.acompletion(model="deepseek/deepseek-chat", messages=[...]),
        litellm.acompletion(model="groq/llama-3.3-70b-versatile", messages=[...]),
    )
    # Cost: ~₹0.15 per question
    
    # 4. Merge: consensus scoring
    parsed = [parse_json(r) for r in results]
    consensus = calculate_consensus(parsed)
    
    # 5. Store session + update evidence
    await store_session(question, parsed, consensus)
    await update_evidence_from_responses(parsed, relevant_prefs)
    
    return AdvisorResponse(
        models=parsed,
        consensus=consensus,
        cost=sum_costs(results)
    )
```

### Research Cron (weekly autonomous research)
```python
# Runs every Sunday at 2 AM
@scheduler.cron("0 2 * * 0")
async def weekly_research():
    # Get preferences that haven't been validated in 30+ days
    stale = await get_stale_preferences(days=30)
    
    for pref in stale:
        # 1. Browser-use scrapes relevant sources
        findings = await browser_research(
            query=f"{pref.choice} vs alternatives {pref.topic} 2026",
            sources=["techcrunch", "hackernews", "reddit", "github"]
        )
        
        # 2. Multi-model evaluation of findings
        evaluation = await ask(
            f"Given these new findings about {pref.topic}, "
            f"is {pref.choice} still the best option? "
            f"Findings: {findings}",
            context=pref.context
        )
        
        # 3. Update confidence
        new_confidence = evaluation.consensus.confidence
        await update_preference_confidence(pref.id, new_confidence)
        
        # 4. Alert if confidence dropped
        if new_confidence < 0.7 and pref.confidence >= 0.7:
            await notify(
                f"⚠️ Your preference for {pref.choice} ({pref.topic}) "
                f"may need review. Confidence dropped from "
                f"{pref.confidence:.0%} to {new_confidence:.0%}."
            )
```

## Effort

| Task | Days |
|:-----|:-----|
| FastAPI project setup + data models | 1 |
| Preference CRUD API | 1 |
| Multi-model advisor | 2 |
| browser-use research integration | 2 |
| Knowledge graph (Apache AGE) | 2 |
| Transcript ingestion | 1 |
| Simple frontend (Next.js or HTML) | 2 |
| **Total** | **~11 days** |

---

# Product 2: Learn (Self-Optimizer) (Self-Optimizing Agent)

## Problem Statement

Every AI agent today makes mistakes and repeats them. When an agent fails to parse a date, extract an entity, or generate correct SQL — **a human has to manually fix the prompt.** There's no feedback loop.

DSPy proved that prompts can be auto-optimized. promptfoo proved that agents can be systematically tested. **Nobody has combined them into a product that fixes itself.**

## User Stories

### US-1: Auto-Detect Weakness
**As a** developer
**I want** my agent to automatically detect what it's bad at
**So that** I don't have to manually review every failure

**GIVEN** my agent has processed 100 tasks this week
**WHEN** the nightly eval cron runs
**THEN** the system:
1. Runs promptfoo eval suite against recent outputs
2. Groups failures by category (date parsing, SQL generation, entity extraction)
3. Identifies: "Date parsing fails 30% of the time with Indian date formats (DD-MM-YYYY)"
4. Logs this as a weakness with examples

### US-2: Auto-Fix Prompts
**As a** developer
**I want** the system to automatically improve prompts based on detected weaknesses
**So that** agent quality improves without my intervention

**GIVEN** a weakness is detected (date parsing, 30% failure rate)
**WHEN** the auto-optimization runs
**THEN** the system:
1. Collects failing examples: `{"input": "05-07-2026", "expected": "2026-07-05", "got": "2026-05-07"}`
2. Runs DSPy BootstrapFewShot to find better prompt + few-shot examples
3. Runs the new prompt against the FULL eval suite (not just failing cases)
4. If new prompt scores higher overall → auto-deploys
5. If new prompt regresses on other cases → flags for human review
6. Logs: "Prompt v12 → v13: date parsing improved 30% → 95%, no regressions"

### US-3: Continuous Improvement Dashboard
**As a** developer
**I want** to see how my agent's quality changes over time
**So that** I know if self-optimization is working

**GIVEN** the system has been running for 4 weeks
**WHEN** I check the dashboard
**THEN** I see:
- Quality score over time (line chart)
- Per-task-type accuracy (bar chart)
- Auto-fixes applied this week (table)
- Prompts pending human review (action items)
- Cost per task over time (is it getting cheaper?)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Learn (Self-Optimizer)                         │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ EVAL      │  │ OPTIMIZE     │  │ DEPLOY         │  │
│  │           │  │              │  │                │  │
│  │ promptfoo │  │ DSPy         │  │ Hot-swap       │  │
│  │ nightly   │→│ Bootstrap    │→│ prompt if      │  │
│  │ test suite│  │ FewShot      │  │ no regression  │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
│       ↑                                    │         │
│       └────────── feedback loop ───────────┘         │
│                                                      │
│  Storage:                                            │
│  ├── eval_results (PostgreSQL)                       │
│  ├── prompt_versions (PostgreSQL)                    │
│  ├── optimization_runs (PostgreSQL)                  │
│  └── few_shot_examples (pgvector for retrieval)      │
└─────────────────────────────────────────────────────┘
```

## Data Model

```sql
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(100) NOT NULL,        -- 'date_parsing', 'sql_generation'
    version INT NOT NULL,
    prompt_text TEXT NOT NULL,
    few_shot_examples JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT FALSE,
    eval_score FLOAT,                       -- overall score when deployed
    created_by VARCHAR(50),                 -- 'human', 'auto_optimize'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE eval_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_version_id UUID REFERENCES prompt_versions(id),
    task_type VARCHAR(100) NOT NULL,
    total_cases INT NOT NULL,
    passed INT NOT NULL,
    failed INT NOT NULL,
    accuracy FLOAT NOT NULL,
    failures JSONB DEFAULT '[]',            -- [{input, expected, got, error}]
    cost_usd FLOAT,
    run_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE optimization_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(100) NOT NULL,
    trigger VARCHAR(50),                    -- 'scheduled', 'accuracy_drop', 'manual'
    weakness_detected TEXT,                 -- 'Indian date formats DD-MM-YYYY'
    old_version_id UUID REFERENCES prompt_versions(id),
    new_version_id UUID REFERENCES prompt_versions(id),
    old_accuracy FLOAT,
    new_accuracy FLOAT,
    auto_deployed BOOLEAN DEFAULT FALSE,
    human_review_needed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## The Self-Healing Loop
```python
# Nightly cron at 3 AM
@scheduler.cron("0 3 * * *")
async def nightly_optimization():
    for task_type in get_all_task_types():
        # 1. Run evals
        active_prompt = get_active_prompt(task_type)
        results = await run_promptfoo_eval(active_prompt, task_type)
        
        # 2. Check if optimization needed
        if results.accuracy < 0.9:  # Below 90% threshold
            weakness = analyze_failures(results.failures)
            
            # 3. Auto-optimize with DSPy
            optimizer = dspy.BootstrapFewShot(
                metric=task_metric(task_type),
                max_bootstrapped_demos=4
            )
            optimized = optimizer.compile(
                student=PromptModule(active_prompt),
                trainset=results.failures + results.passes  # Learn from both
            )
            
            # 4. Eval the new prompt on FULL test suite
            new_results = await run_promptfoo_eval(optimized.prompt, task_type)
            
            # 5. Deploy or flag
            if new_results.accuracy > results.accuracy and no_regressions(results, new_results):
                await deploy_prompt(optimized, task_type)
                await log(f"Auto-deployed: {task_type} accuracy {results.accuracy:.0%} → {new_results.accuracy:.0%}")
            else:
                await flag_for_review(optimized, task_type, reason="Regression detected")
```

## Effort

| Task | Days |
|:-----|:-----|
| promptfoo eval pipeline setup | 1 |
| Prompt version management | 1 |
| DSPy optimization integration | 2 |
| Auto-deploy with regression check | 1 |
| Dashboard (simple HTML) | 1 |
| Nightly cron orchestration | 1 |
| **Total** | **~7 days** |

---

# Product 3: Watch (Ambient AI) (Ambient AI)

## Problem Statement

Every AI tool today is **reactive** — you open it, type a question, get an answer. But the most valuable assistant is one that **comes to you** with important information before you ask.

Your server could be running out of disk. A dependency could have a CVE. A library you use could have released a breaking update. **You won't know until something breaks.**

## User Stories

### US-1: Dependency Watch
**As a** developer
**I want** my AI to monitor my project dependencies for updates and security issues
**So that** I don't get surprised by breaking changes or vulnerabilities

**GIVEN** my project uses FastAPI 0.115.0 and Pydantic 2.10
**WHEN** the daily dependency check runs
**THEN** the system:
1. Checks PyPI/npm for new versions
2. Reads release notes using browser-use
3. Classifies: security fix, breaking change, feature, patch
4. If security fix → immediate notification: "⚠️ Pydantic 2.10.1 fixes CVE-2026-XXXX — affects your User model validation"
5. If breaking change → notification with impact analysis: "FastAPI 0.116 changes X — affects 3 of your endpoints"
6. If patch → weekly digest

### US-2: Server Health Watch
**As a** developer
**I want** my AI to monitor my VPS and alert me proactively
**So that** I prevent outages instead of reacting to them

**GIVEN** my VPS is running PostgreSQL, Redis, and my services
**WHEN** the hourly health check runs
**THEN** the system:
1. Checks: disk usage, CPU, RAM, service status, response times
2. Predicts: "At current log growth rate, disk will be full in 5 days"
3. Suggests: "Run `journalctl --vacuum-size=500M` to free 2GB"
4. Auto-executes safe actions (with permission): log rotation, cache clearing
5. Alerts on anomalies: "API response time increased 3x in the last hour"

### US-3: Tech Radar Watch
**As a** developer
**I want** my AI to monitor the tech landscape for things relevant to MY stack
**So that** I stay current without spending hours reading HN/Reddit

**GIVEN** my tech profile: Python, FastAPI, Next.js, PostgreSQL, AI/ML, self-hosted
**WHEN** the daily tech scan runs
**THEN** the system:
1. Scrapes: HN front page, Reddit r/python r/selfhosted, GitHub trending
2. Filters by MY interests (not generic tech news)
3. Scores relevance (0-100) against my preferences and projects
4. Daily digest: "3 things relevant to you today:
   - PostgreSQL 17.1 released with 20% faster JSON queries
   - New FastAPI alternative 'Litestar' hit 5K stars (you should know, not switch)
   - Article: 'Self-hosting LLMs on ARM in 2026' — directly relevant to your setup"

### US-4: Code Quality Watch
**As a** developer
**I want** my AI to analyze my coding patterns and suggest improvements
**So that** I grow as a developer, not just ship features

**GIVEN** I've made 50 commits this month
**WHEN** the weekly code analysis runs
**THEN** the system:
1. Analyzes git history: file churn, test coverage trends, commit patterns
2. Identifies patterns: "You write tests for API endpoints but not for services"
3. Suggests: "Your services/ directory has 0% test coverage. Here are 3 service functions that would benefit most from tests"
4. Tracks improvement: "Test coverage: 45% → 52% this month 📈"

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Watch (Ambient AI)                            │
│                                                           │
│  WATCHERS (background crons):                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐│
│  │Dependency │ │ Server   │ │ Tech     │ │ Code Quality ││
│  │Watch      │ │ Health   │ │ Radar    │ │ Watch        ││
│  │           │ │          │ │          │ │              ││
│  │Daily 6AM  │ │Hourly    │ │Daily 8AM │ │Weekly Sun    ││
│  │PyPI/npm   │ │SSH/API   │ │HN/Reddit │ │git log       ││
│  │check      │ │health    │ │browser-  │ │analysis      ││
│  │           │ │check     │ │use scrape│ │              ││
│  └─────┬─────┘ └─────┬────┘ └─────┬────┘ └──────┬──────┘│
│        │              │            │              │       │
│  ┌─────▼──────────────▼────────────▼──────────────▼─────┐│
│  │              NOTIFICATION ENGINE                      ││
│  │                                                       ││
│  │  Priority routing:                                    ││
│  │  🔴 Critical (CVE, disk full)  → Immediate push      ││
│  │  🟡 Important (breaking change) → Same-day digest     ││
│  │  🟢 Informational (new release) → Weekly digest       ││
│  │                                                       ││
│  │  Channels: Terminal, Email, WhatsApp (future)         ││
│  └───────────────────────────────────────────────────────┘│
│                                                           │
│  Storage:                                                 │
│  ├── watch_events (all detected events)                   │
│  ├── watch_configs (what to monitor, thresholds)          │
│  ├── notifications (sent notifications + read status)     │
│  └── tech_radar (scraped articles, scored by relevance)   │
└──────────────────────────────────────────────────────────┘
```

## Data Model

```sql
CREATE TABLE watch_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watcher_type VARCHAR(50) NOT NULL,     -- 'dependency', 'server', 'tech_radar', 'code_quality'
    config JSONB NOT NULL,                  -- watcher-specific config
    schedule VARCHAR(50) NOT NULL,          -- cron expression
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Example configs:
-- dependency: {"projects": ["/path/to/project"], "check_security": true}
-- server: {"host": "vps.example.com", "ssh_key": "...", "thresholds": {"disk": 80, "cpu": 90}}
-- tech_radar: {"interests": ["python", "fastapi", "self-hosted"], "sources": ["hn", "reddit", "github"]}
-- code_quality: {"repos": ["/path/to/repo"], "min_coverage": 60}

CREATE TABLE watch_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watcher_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,          -- 'critical', 'important', 'info'
    title VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',            -- watcher-specific data
    action_taken TEXT,                      -- what auto-action was performed
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tech_radar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    url TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,            -- 'hackernews', 'reddit', 'github'
    summary TEXT,                            -- AI-generated summary
    relevance_score FLOAT,                  -- 0-100 based on user's interests
    tags TEXT[],
    embedding VECTOR(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Key Implementation

### Dependency Watcher
```python
@scheduler.cron("0 6 * * *")  # Daily at 6 AM
async def check_dependencies():
    for project in get_watched_projects():
        # Parse requirements.txt / package.json
        deps = parse_dependencies(project.path)
        
        for dep in deps:
            latest = await check_pypi(dep.name)  # or npm registry
            
            if latest.version != dep.version:
                # Use browser-use to read release notes
                notes = await browser_agent.run(
                    f"Go to {latest.release_url} and extract: "
                    f"breaking changes, security fixes, new features"
                )
                
                # Classify severity
                severity = await classify_update(dep, latest, notes)
                
                await create_event(
                    watcher_type="dependency",
                    severity=severity,
                    title=f"{dep.name} {dep.version} → {latest.version}",
                    body=notes.summary,
                    metadata={"breaking_changes": notes.breaking, "cves": notes.cves}
                )
```

### Tech Radar Scanner
```python
@scheduler.cron("0 8 * * *")  # Daily at 8 AM
async def scan_tech_radar():
    interests = get_user_interests()  # ['python', 'fastapi', 'self-hosted', ...]
    
    # 1. Scrape sources
    articles = []
    articles += await scrape_hn_frontpage()
    articles += await scrape_reddit(["r/python", "r/selfhosted", "r/nextjs"])
    articles += await scrape_github_trending(language="python")
    
    # 2. Score relevance using cheap model
    for article in articles:
        score = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Rate 0-100 how relevant this is to someone "
                           f"interested in {interests}: {article.title}\n{article.summary}"
            }]
        )
        article.relevance_score = parse_score(score)
    
    # 3. Store high-relevance articles
    relevant = [a for a in articles if a.relevance_score > 60]
    await store_articles(relevant)
    
    # 4. Generate digest if enough relevant articles
    if len(relevant) >= 3:
        digest = await generate_digest(relevant[:5])
        await notify(severity="info", title="Your Daily Tech Radar", body=digest)
```

## Effort

| Task | Days |
|:-----|:-----|
| Watcher framework (cron + event + notify) | 2 |
| Dependency watcher | 1.5 |
| Server health watcher | 1.5 |
| Tech radar scanner | 2 |
| Code quality analyzer | 1.5 |
| Notification engine (terminal + email) | 1 |
| Dashboard (events + digest view) | 1.5 |
| **Total** | **~11 days** |

---

# Implementation Roadmap

## Phase 0: Foundation (Days 1-2)
```
├── Docker compose: PostgreSQL (pgvector + AGE) + Redis
├── FastAPI project scaffold with async SQLAlchemy
├── pip install: browser-use, litellm, mem0ai, dspy
├── Basic project structure:
│   Platform/
│   ├── core/           # shared: db, config, litellm client
│   ├── knowledge/      # Core (Knowledge Engine)
│   ├── optimize/       # Learn (Self-Optimizer)
│   ├── watch/          # Watch (Ambient AI)
│   └── api/            # FastAPI routes
└── Alembic migrations for all tables
```

## Phase 1: Core (Knowledge Engine) MVP (Days 3-8)
```
├── Preference CRUD
├── Multi-model advisor (the ₹0.15 query)
├── Knowledge graph basics (Apache AGE)
├── browser-use research integration
├── Simple CLI: `Platform ask "Should I use Go?"`
└── Transcript ingestion (extract prefs from Antigravity sessions)
```

## Phase 2: Watch (Ambient AI) MVP (Days 9-14)
```
├── Watcher framework + notification engine
├── Dependency watcher
├── Tech radar scanner
├── Server health check (basic)
└── Daily digest generation
```

## Phase 3: Learn (Self-Optimizer) MVP (Days 15-19)
```
├── promptfoo eval pipeline
├── Prompt version management
├── DSPy auto-optimization
├── Auto-deploy with regression check
└── Nightly self-healing cron
```

## Phase 4: Polish + UI (Days 20-24)
```
├── Web dashboard (Next.js or simple HTML)
│   ├── Knowledge graph visualization (D3.js)
│   ├── Watch events feed
│   ├── Optimization history
│   └── Preference management
├── Weekly research cron
├── Code quality watcher
└── Documentation + open-source prep
```

**Total: ~24 days to full platform.**
**MVP (just Core (Knowledge Engine)): ~8 days.**

---

# Cost Estimates

| Component | Monthly Cost |
|:----------|:------------|
| Multi-model queries (100 questions/month) | ~₹15 ($0.18) |
| Research scraping (4 prefs × 4 weeks) | ~₹50 ($0.60) |
| Tech radar scanning (30 days) | ~₹25 ($0.30) |
| Dependency checking | Free (API calls) |
| Server health | Free (SSH) |
| DSPy optimization (weekly) | ~₹40 ($0.48) |
| **Total** | **~₹130/month ($1.56)** |

Self-hosted on your existing VPS. No vendor fees. No subscriptions. **Your AI platform for the cost of a cup of chai per month.**

---

# Open Source Strategy

| Milestone | Action |
|:----------|:-------|
| Day 8 (Core MVP done) | Push to GitHub, write README |
| Day 14 (Watch added) | Product Hunt launch, HN "Show HN" |
| Day 24 (Full platform) | Documentation site, Discord community |
| Month 3 | Plugin system — others build watchers |
| Month 6 | Hosted version for non-technical users (revenue) |

**Name:** Platform (நிலா)
**Tagline:** "Personal AI that knows you, improves itself, and watches your back."
**Repo:** `github.com/raceraja/Platform`
