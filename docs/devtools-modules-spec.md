# DevTools Modules — Feature Spec & Plan Matrix

> **Purpose**: New developer-focused modules to add to the uzhavu platform library. Each module follows existing patterns (manifest, CRUD config, NestJS service + controller). Combined with the product factory system, these modules can be assembled into any developer tool product via config.
>
> **Architecture ref**: `APP_ARCHITECTURE.md` — all modules follow the same app manifest + module config pattern
>
> **Existing dev modules** (already built, need to be converted to proper apps with manifests):
> - Error Tracking, API Analytics, Health Dashboard, Feature Flags, Webhook System, Background Jobs, Tenant Admin, Database Studio, Audit Logs, Performance Profiling

---

## Phase 0: Convert Existing Dev Services to App Manifests

The 10 existing dev services live under `apps/api/src/modules/` as NestJS modules with dashboards at `/dashboard/dev/*`. They need to be restructured as proper pluggable apps so they can be included/excluded via product configs.

### What to do:

1. Create `apps/web/src/apps/devtools/manifest.ts`:
   ```typescript
   export const manifest: AppManifest = {
     id: 'devtools',
     name: 'Developer Tools',
     description: 'Error tracking, API analytics, performance monitoring, and more',
     icon: 'terminal',
     version: '1.0.0',
     plans: ['starter', 'pro', 'enterprise'],
     dependencies: [],
     models: ['ErrorLog', 'ApiRequestLog', 'FeatureFlag', 'Webhook', 'WebhookDelivery'],
     nav: { section: 'devtools', order: 1 },
     routes: [
       { path: '/dev/errors', label: 'Errors', icon: 'bug' },
       { path: '/dev/api-analytics', label: 'API Analytics', icon: 'activity' },
       { path: '/dev/performance', label: 'Performance', icon: 'gauge' },
       { path: '/dev/health', label: 'Health', icon: 'heart-pulse' },
       { path: '/dev/feature-flags', label: 'Feature Flags', icon: 'flag' },
       { path: '/dev/webhooks', label: 'Webhooks', icon: 'webhook' },
       { path: '/dev/jobs', label: 'Jobs', icon: 'clock' },
       { path: '/dev/database', label: 'Database', icon: 'database' },
       { path: '/dev/audit', label: 'Audit Log', icon: 'scroll-text' },
       { path: '/dev/tenants', label: 'Tenants', icon: 'building-2' },
     ],
   };
   ```

2. Move existing dev dashboard pages from hardcoded routes to the manifest-driven system

3. Make dev services multi-tenant — currently they're internal-only. Each tenant should see only their own errors, logs, analytics. The data models already have `orgId` where needed, but verify scoping on all queries.

4. Backend: Add plan-based guards to dev service endpoints so they can be gated by product config.

**Effort**: 2-3 days (restructuring, no new features)

---

## Phase 1: New Modules — High Value, Low Effort

### Module 1: Status Page

Public-facing status page showing service health and incident history.

**What it does:**
- Public page (no login required) showing current status of services
- Service list with status: operational, degraded, partial outage, major outage
- Incident timeline with updates
- Scheduled maintenance announcements
- Uptime percentage (30/90 day)
- Subscribable — visitors get email/webhook notifications on incidents
- Customizable branding (logo, colors, custom domain)

**Database schema:**
```sql
CREATE TABLE status_services (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,           -- "API", "Web App", "Database"
  description TEXT,
  current_status TEXT DEFAULT 'operational',  -- operational|degraded|partial_outage|major_outage
  display_order INT DEFAULT 0,
  is_visible BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE status_incidents (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT DEFAULT 'investigating',  -- investigating|identified|monitoring|resolved
  impact TEXT DEFAULT 'minor',          -- none|minor|major|critical
  started_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE status_incident_updates (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  incident_id TEXT NOT NULL REFERENCES status_incidents(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE status_incident_services (
  incident_id TEXT NOT NULL REFERENCES status_incidents(id) ON DELETE CASCADE,
  service_id TEXT NOT NULL REFERENCES status_services(id) ON DELETE CASCADE,
  PRIMARY KEY (incident_id, service_id)
);

CREATE TABLE status_subscribers (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  email TEXT NOT NULL,
  confirmed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, email)
);

CREATE TABLE status_maintenance (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  scheduled_start TIMESTAMPTZ NOT NULL,
  scheduled_end TIMESTAMPTZ NOT NULL,
  status TEXT DEFAULT 'scheduled',  -- scheduled|in_progress|completed
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Backend (NestJS):**
```
apps/api/src/modules/status-page/
├── status-page.module.ts
├── status-page.service.ts
├── status-page.controller.ts        -- Admin CRUD (requires auth)
├── status-page.public.controller.ts  -- Public endpoints (no auth)
└── status-page.service.spec.ts
```

Endpoints:
- `GET /status/:orgSlug` — public status page data (no auth)
- `GET /status/:orgSlug/history` — public incident history
- `POST /status/:orgSlug/subscribe` — email subscription
- `POST /business/:orgId/status/services` — CRUD services (auth)
- `POST /business/:orgId/status/incidents` — create/update incidents (auth)
- `POST /business/:orgId/status/maintenance` — schedule maintenance (auth)

**Frontend:**
```
apps/web/src/apps/status-page/
├── manifest.ts
├── modules/
│   ├── services.ts       -- Service CRUD config
│   ├── incidents.ts      -- Incident CRUD config
│   └── maintenance.ts    -- Maintenance CRUD config
├── pages/
│   ├── StatusAdminPage.tsx    -- Admin dashboard
│   └── StatusPublicPage.tsx   -- Public status page (standalone route)
└── actions/
    └── status.ts
```

**Plan gating:**
```typescript
plans: ['starter', 'pro', 'enterprise']
// free: no status page
// starter: 5 services, 1 subscriber (just the owner)
// pro: 20 services, unlimited subscribers, custom domain
// enterprise: unlimited everything
```

**Effort:** 3-4 days

---

### Module 2: Uptime Monitor

Automated endpoint monitoring with alerting.

**What it does:**
- Monitor HTTP endpoints (GET/POST) at configurable intervals (1/5/10/15 min)
- Check response status code, response time, SSL certificate expiry
- Alert via email, webhook, or Telegram on failure
- Uptime percentage calculation (24h, 7d, 30d, 90d)
- Response time graphs
- Integration with Status Page — auto-update service status on failure

**Database schema:**
```sql
CREATE TABLE uptime_monitors (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  method TEXT DEFAULT 'GET',
  headers JSONB DEFAULT '{}',
  body TEXT,
  expected_status INT DEFAULT 200,
  interval_seconds INT DEFAULT 300,      -- 5 min default
  timeout_ms INT DEFAULT 10000,          -- 10s
  regions TEXT[] DEFAULT '{"default"}',
  is_active BOOLEAN DEFAULT true,
  status_page_service_id TEXT,           -- Link to status page service
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE uptime_checks (
  id BIGSERIAL PRIMARY KEY,
  monitor_id TEXT NOT NULL REFERENCES uptime_monitors(id) ON DELETE CASCADE,
  status TEXT NOT NULL,         -- up|down|degraded
  response_time_ms INT,
  status_code INT,
  error TEXT,
  region TEXT DEFAULT 'default',
  checked_at TIMESTAMPTZ DEFAULT NOW()
);
-- Partition by month for performance:
CREATE INDEX idx_checks_monitor_time ON uptime_checks(monitor_id, checked_at DESC);

CREATE TABLE uptime_alerts (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  monitor_id TEXT NOT NULL REFERENCES uptime_monitors(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,        -- email|webhook|telegram
  target TEXT NOT NULL,         -- email address, webhook URL, or telegram chat ID
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE uptime_incidents_auto (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  monitor_id TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ,
  duration_seconds INT,
  cause TEXT
);
```

**Implementation notes:**
- The actual checking runs in `apps/worker/` (background worker process)
- Worker uses a cron schedule: every 1 minute, check all monitors due
- Use `fetch` / `undici` for HTTP checks
- Calculate uptime: `(total_checks - down_checks) / total_checks * 100`
- Data retention: keep raw checks for 90 days, aggregate to hourly after that
- Alert deduplication: don't alert on every failed check, wait for 2-3 consecutive failures

**Plan gating:**
```typescript
// free: 3 monitors, 10-min interval, email alerts only
// starter: 10 monitors, 5-min interval, email + webhook
// pro: 50 monitors, 1-min interval, all alert channels, multi-region
// enterprise: unlimited
```

**Effort:** 4-5 days

---

### Module 3: Log Explorer

Structured log search, filtering, and real-time tail.

**What it does:**
- Ingest structured logs via HTTP API or SDK
- Search by level (info, warn, error), service, message content, time range
- Real-time log tail (WebSocket)
- Log retention policies (7/30/90 days per plan)
- Saved filters and alerts on log patterns
- JSON log expansion (click to see full payload)

**Database schema:**
```sql
CREATE TABLE app_logs (
  id BIGSERIAL PRIMARY KEY,
  org_id TEXT NOT NULL,
  service TEXT NOT NULL,          -- "api", "web", "worker", "ai-engine"
  level TEXT NOT NULL,            -- debug|info|warn|error|fatal
  message TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',   -- Any structured data
  trace_id TEXT,                  -- For request tracing
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_logs_org_time ON app_logs(org_id, timestamp DESC);
CREATE INDEX idx_logs_level ON app_logs(org_id, level, timestamp DESC);
CREATE INDEX idx_logs_service ON app_logs(org_id, service, timestamp DESC);
CREATE INDEX idx_logs_trace ON app_logs(trace_id) WHERE trace_id IS NOT NULL;

-- GIN index for full-text search on message
CREATE INDEX idx_logs_message_search ON app_logs USING gin(to_tsvector('english', message));
```

**Endpoints:**
- `POST /v1/logs/ingest` — batch log ingestion (accepts array of log entries)
- `GET /business/:orgId/logs` — search logs with filters
- `GET /business/:orgId/logs/stats` — log volume stats, error rate
- `WS /business/:orgId/logs/tail` — real-time log stream
- `POST /business/:orgId/logs/alerts` — alert on log patterns

**Client SDK** (npm package for easy integration):
```typescript
// @uzhavu/log-sdk (publish later)
import { Logger } from '@uzhavu/log-sdk';

const log = new Logger({
  endpoint: 'https://app.example.com/v1/logs/ingest',
  apiKey: 'key_xxx',
  service: 'my-api',
});

log.info('User logged in', { userId: '123' });
log.error('Payment failed', { orderId: '456', error: err.message });
```

**Plan gating:**
```typescript
// free: 1,000 logs/day, 7-day retention, no real-time tail
// starter: 50,000 logs/day, 30-day retention, real-time tail
// pro: 500,000 logs/day, 90-day retention, alerts, saved filters
// enterprise: unlimited, 1-year retention, custom retention
```

**Effort:** 4-5 days

---

### Module 4: Cron Job Manager

Schedule, monitor, and get alerts on recurring jobs.

**What it does:**
- Define cron jobs with schedule expressions
- Monitor execution: started, completed, failed, duration
- Alert on: job didn't run (dead man's switch), job failed, job took too long
- Manual trigger ("Run Now" button)
- Execution history with logs
- Lock mechanism (prevent overlapping runs)

**Database schema:**
```sql
CREATE TABLE cron_jobs (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  schedule TEXT NOT NULL,          -- Cron expression: "0 */6 * * *"
  endpoint TEXT,                   -- HTTP endpoint to call (webhook-style)
  method TEXT DEFAULT 'POST',
  headers JSONB DEFAULT '{}',
  body TEXT,
  timeout_seconds INT DEFAULT 300,
  grace_period_seconds INT DEFAULT 600,  -- How long before "missed" alert
  is_active BOOLEAN DEFAULT true,
  last_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE cron_executions (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  job_id TEXT NOT NULL REFERENCES cron_jobs(id) ON DELETE CASCADE,
  status TEXT NOT NULL,            -- started|completed|failed|timed_out
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  duration_ms INT,
  output TEXT,                     -- Response body or error message
  status_code INT,
  triggered_by TEXT DEFAULT 'schedule',  -- schedule|manual
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cron_exec_job ON cron_executions(job_id, created_at DESC);
```

**How it works:**
- Worker process checks every minute: "which jobs are due?"
- Calls the configured HTTP endpoint (like a webhook)
- Records execution result
- If a job doesn't report completion within `grace_period_seconds`, alert
- Dead man's switch pattern: job pings us, if we don't hear back → alert

**Plan gating:**
```typescript
// free: 3 jobs, 15-min minimum interval, email alerts
// starter: 20 jobs, 1-min minimum interval, webhook alerts
// pro: 100 jobs, all intervals, all alert channels, execution logs 90d
// enterprise: unlimited
```

**Effort:** 3 days

---

### Module 5: Environment Manager

Securely manage environment variables across projects and environments.

**What it does:**
- Store env vars per project, per environment (dev/staging/prod)
- Encrypted at rest (AES-256)
- Version history — see what changed and when
- Compare environments side-by-side
- Pull env vars via CLI or API
- Shared secrets across projects
- Access control — who can see/edit prod secrets

**Database schema:**
```sql
CREATE TABLE env_projects (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  environments TEXT[] DEFAULT '{"development","staging","production"}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE env_variables (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  project_id TEXT NOT NULL REFERENCES env_projects(id) ON DELETE CASCADE,
  environment TEXT NOT NULL,
  key TEXT NOT NULL,
  value_encrypted TEXT NOT NULL,  -- AES-256 encrypted
  is_secret BOOLEAN DEFAULT false,  -- Mask in UI
  comment TEXT,
  updated_by TEXT,
  version INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, environment, key)
);

CREATE TABLE env_history (
  id BIGSERIAL PRIMARY KEY,
  variable_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  environment TEXT NOT NULL,
  key TEXT NOT NULL,
  old_value_encrypted TEXT,
  new_value_encrypted TEXT,
  action TEXT NOT NULL,   -- created|updated|deleted
  changed_by TEXT,
  changed_at TIMESTAMPTZ DEFAULT NOW()
);
```

**CLI tool** (for pulling env vars):
```bash
# Developer pulls env vars for local development
npx uzhavu-env pull --project=my-api --env=development > .env

# Or pipe directly
eval $(npx uzhavu-env export --project=my-api --env=production)
```

**Plan gating:**
```typescript
// free: 1 project, 2 environments, 20 variables
// starter: 5 projects, 4 environments, 200 variables
// pro: 25 projects, unlimited environments, unlimited variables, version history
// enterprise: unlimited, SSO, audit trail
```

**Effort:** 3-4 days

---

### Module 6: Feedback & Bug Reports

Embeddable widget for collecting user feedback and bug reports.

**What it does:**
- JavaScript widget (embed with one `<script>` tag)
- Screenshot capture (html2canvas)
- Console log attachment
- Browser/OS metadata auto-capture
- Feedback board — users vote on features
- Status tracking: new → triaged → in progress → done
- Integration with Tasks module (auto-create task from feedback)

**Database schema:**
```sql
CREATE TABLE feedback_items (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  type TEXT NOT NULL,              -- bug|feature|improvement|question
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'new',       -- new|triaged|planned|in_progress|done|closed
  priority TEXT DEFAULT 'medium',  -- low|medium|high|critical
  votes INT DEFAULT 0,
  reporter_email TEXT,
  reporter_name TEXT,
  screenshot_url TEXT,
  metadata JSONB DEFAULT '{}',     -- Browser, OS, URL, console logs
  task_id TEXT,                    -- Link to tasks module
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE feedback_votes (
  feedback_id TEXT NOT NULL REFERENCES feedback_items(id) ON DELETE CASCADE,
  voter_email TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (feedback_id, voter_email)
);

CREATE TABLE feedback_comments (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  feedback_id TEXT NOT NULL REFERENCES feedback_items(id) ON DELETE CASCADE,
  author TEXT NOT NULL,
  content TEXT NOT NULL,
  is_internal BOOLEAN DEFAULT false,  -- Internal notes vs public reply
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Embed widget:**
```html
<!-- One line to add to any website -->
<script src="https://app.example.com/widget.js" data-org="org_xxx"></script>
```

**Plan gating:**
```typescript
// free: 50 feedback items/month, no screenshot, no voting board
// starter: 500/month, screenshots, public voting board
// pro: unlimited, console logs, task integration, custom branding on widget
// enterprise: unlimited, SSO, API access
```

**Effort:** 4-5 days

---

### Module 7: API Key Management

Issue, revoke, and rate-limit API keys for your product.

**What it does:**
- Generate API keys with prefix (e.g., `sk_live_xxx`, `sk_test_xxx`)
- Per-key rate limiting (requests/minute, requests/day)
- Per-key scoping (which endpoints are allowed)
- Key rotation (create new, deprecate old with grace period)
- Usage analytics per key
- Temporary keys with expiry

**Database schema:**
```sql
CREATE TABLE api_keys (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE,   -- SHA-256 of the key (never store raw)
  key_prefix TEXT NOT NULL,        -- First 8 chars for identification: "sk_live_"
  scopes TEXT[] DEFAULT '{}',      -- ["read:products", "write:orders"]
  rate_limit_rpm INT,              -- Requests per minute (NULL = unlimited)
  rate_limit_rpd INT,              -- Requests per day
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT true,
  environment TEXT DEFAULT 'live', -- live|test
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE api_key_usage (
  id BIGSERIAL PRIMARY KEY,
  key_id TEXT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
  endpoint TEXT NOT NULL,
  method TEXT NOT NULL,
  status_code INT,
  response_time_ms INT,
  ip_address TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_key_usage_time ON api_key_usage(key_id, timestamp DESC);
```

**Implementation:**
- Middleware validates API key on every request
- Key is hashed and compared (never stored raw)
- Rate limiting via in-memory counter (or Redis if available)
- The full key is shown ONCE on creation, then only the prefix

**Plan gating:**
```typescript
// free: 2 keys, 100 rpm, no scoping
// starter: 10 keys, 1000 rpm, scoping
// pro: 50 keys, 10000 rpm, usage analytics, key rotation
// enterprise: unlimited, SSO-generated keys
```

**Effort:** 3 days

---

### Module 8: Release Notes & Changelog

Auto-generate and publish changelogs.

**What it does:**
- Manual changelog entries (title, description, category, date)
- Categories: feature, improvement, fix, breaking change
- Public changelog page (standalone route, no auth)
- Email notification to subscribers on new releases
- Markdown support in descriptions
- Version tagging

**Database schema:**
```sql
CREATE TABLE releases (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  version TEXT NOT NULL,
  title TEXT NOT NULL,
  published_at TIMESTAMPTZ,
  is_published BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE release_items (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  release_id TEXT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
  category TEXT NOT NULL,  -- feature|improvement|fix|breaking
  title TEXT NOT NULL,
  description TEXT,
  display_order INT DEFAULT 0
);

CREATE TABLE changelog_subscribers (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id TEXT NOT NULL,
  email TEXT NOT NULL,
  confirmed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, email)
);
```

**Plan gating:**
```typescript
// free: 5 releases, no subscriber notifications
// starter: unlimited releases, email notifications, custom domain
// pro: API access, widget embed, subscriber analytics
```

**Effort:** 2-3 days

---

## Plan Matrix — All Modules

| Module | Free | Starter (₹499) | Pro (₹1,499) | Enterprise (₹4,999) |
|:-------|:-----|:---------------|:-------------|:--------------------|
| **Error Tracking** | 100 errors/day | 10K/day | 100K/day | Unlimited |
| **API Analytics** | 7-day retention | 30-day | 90-day | 1 year |
| **Performance** | Basic metrics | p95, trends | Alerts, profiling | Custom |
| **Health** | 3 checks | 10 checks | Unlimited, alerts | Multi-region |
| **Feature Flags** | 5 flags | 50 flags | Unlimited, % rollout | A/B testing |
| **Webhooks** | 3 endpoints | 20 endpoints | Unlimited, retry | Transforms |
| **Jobs Dashboard** | View only | 10 jobs | Unlimited, retry | Priority queues |
| **Database Studio** | Read-only | Read-only | Query runner | Full access |
| **Audit Logs** | 7-day | 30-day | 90-day, export | 1 year |
| **Status Page** | — | 5 services | 20 services, subs | Custom domain |
| **Uptime Monitor** | — | 10 monitors, 5min | 50 monitors, 1min | Multi-region |
| **Log Explorer** | — | 50K/day, 30d | 500K/day, 90d | Unlimited |
| **Cron Manager** | — | 20 jobs | 100 jobs | Unlimited |
| **Env Manager** | — | 5 projects | 25 projects | SSO, audit |
| **Feedback Widget** | — | 500/month | Unlimited | Custom brand |
| **API Keys** | — | 10 keys | 50 keys, analytics | Unlimited |
| **Release Notes** | — | Unlimited | Subscribers, API | Widget embed |

---

## Implementation Order

| Priority | Module | Effort | Why |
|:---------|:-------|:-------|:----|
| **1** | Phase 0: Convert existing dev services to manifests | 2-3 days | Foundation — makes everything else possible |
| **2** | Status Page | 3-4 days | High demand, visible, attracts users |
| **3** | Uptime Monitor | 4-5 days | Pairs with status page, natural upsell |
| **4** | Feedback Widget | 4-5 days | Embeddable = viral growth |
| **5** | Cron Manager | 3 days | Common need, quick build |
| **6** | Log Explorer | 4-5 days | Core devtool, high retention |
| **7** | API Key Management | 3 days | Needed for external API access |
| **8** | Env Manager | 3-4 days | Developer workflow tool |
| **9** | Release Notes | 2-3 days | Nice to have, public page |

**Total effort for all new modules: ~30-35 days**

Build one module per week alongside other work. In 2 months, you have a complete devtools platform.

---

## Backend Patterns to Follow

All new modules MUST follow existing uzhavu patterns:

1. **NestJS module structure**: `module.ts` + `service.ts` + `controller.ts` + `spec.ts`
2. **Multi-tenant scoping**: Every query includes `orgId`
3. **Response format**: `success(data)`, `paginated(items, page, limit, total)`, `fail(code, msg)`
4. **Auth**: `@UseGuards(AuthGuard)` on all controllers
5. **Events**: Emit events via `EventBusService` for cross-module hooks
6. **Tests**: Every service gets a `.spec.ts` file, never skip

## Frontend Patterns to Follow

1. **App manifest**: Every new app gets a `manifest.ts`
2. **Module configs**: CRUD screens use module config (columns, forms, filters)
3. **Server actions**: Data layer via `actions/` files with `withAction()` wrapper
4. **CSS Modules**: No Tailwind — use CSS Modules + vanilla CSS
5. **UI components**: Import from `@uzhavu/ui`

---

*Generated: 05 Jul 2026*
*Ref: DEV-SERVICES-ROADMAP.md, APP_ARCHITECTURE.md*
