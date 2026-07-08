# Life Graph Dashboard — Kiro-Style Spec (v2)

> **Identity:** Chat + Canvas SaaS dashboard (you = client #1)
> **Tech:** Next.js 15 PWA | `@uzhavu/ui` product factory | webhooks for real-time
> **Repo location:** `d:\DevTools\Projects\agents\dashboard\`
> **Backend:** `https://brain.uzhavu.co.in/api/v1/` (55+ endpoints)

---

## Architecture

```
Uzhavu Product Factory
├── @uzhavu/ui (91 components + 10-dimension tokens)  ← SHARED
├── Uzhavu SaaS app                                    ← Product 1
└── Life Graph Dashboard                               ← Product 2
    ├── Next.js 15 (App Router)
    ├── Auth (JWT + tenant isolation)
    ├── Full Uzhavu component library
    ├── Webhooks (HMAC-signed EventBus → dashboard)
    └── Life Graph-specific pages
```

---

## User Stories

### US-1: Chat + Capture (THE CORE)
**As a** user, **I want to** type thoughts, decisions, and questions into a chat bar
**So that** Life Graph captures everything and responds intelligently.

**Acceptance Criteria:**
- GIVEN I see the persistent chat bar at bottom, WHEN I type "I decided to use PostgreSQL", THEN it fires `POST /capture/` and shows confirmation
- GIVEN I type a question, WHEN I submit, THEN it routes via `POST /kernel/route` and streams a response
- GIVEN I press `Ctrl+K`, WHEN the CommandPalette opens, THEN I see grouped commands: Search, Capture, Decide, Challenge, Navigate
- GIVEN a capture event has yielded a DECISION_CANDIDATE, WHEN the event arrives via webhook, THEN the decision appears in the response

### US-2: Overview Dashboard
**As a** user, **I want to** see a summary of my system at a glance
**So that** I know the health of my memory, decisions, and agents.

**Acceptance Criteria:**
- GIVEN I open the dashboard, WHEN data loads, THEN I see StatsCards for: total memories, active decisions, Brier score
- GIVEN I see the calibration mini-chart, WHEN data loads via `GET /judgment/calibration/curve`, THEN I see 5 confidence buckets
- GIVEN I see recent activity, WHEN captures arrive, THEN I see the last 5 events with type badges

### US-3: Calibration Dashboard (FLAGSHIP)
**As a** user, **I want to** see my prediction calibration curve improving over time
**So that** I can demonstrate I'm getting better at predicting outcomes.

**Acceptance Criteria:**
- GIVEN I open Calibration, WHEN data loads, THEN I see predicted vs actual chart with 5 buckets
- GIVEN ≥20 resolved predictions, WHEN page renders, THEN I see Brier score, multiplier, bias findings
- GIVEN <20 resolved, WHEN page renders, THEN I see "Keep making predictions!" with progress bar (N/20)

### US-4: Memory Browser
**As a** user, **I want to** search, browse, and filter my memories
**So that** I can find and manage stored knowledge.

**Acceptance Criteria:**
- GIVEN I open Memories, WHEN data loads, THEN I see DataTable with content, importance, tags, created_at
- GIVEN I search, WHEN I submit, THEN semantic search via `POST /search/` replaces the table
- GIVEN I click a row, WHEN detail panel opens, THEN I see full content, importance, source, linked sessions

### US-5: Decision Tracker
**As a** user, **I want to** see decisions with predictions and outcomes
**So that** I can track what I decided and how accurate I was.

**Acceptance Criteria:**
- GIVEN I open Decisions, WHEN data loads, THEN I see Timeline with status badges
- GIVEN I click a decision, WHEN detail opens, THEN I see reasoning, predictions with confidence bars, resolution

### US-6: Task Board
**As a** user, **I want to** see agent tasks in a kanban board
**So that** I can monitor dispatch and approval status.

**Acceptance Criteria:**
- GIVEN I open Tasks, WHEN data loads via `GET /kernel/tasks`, THEN I see Kanban: Queued → Running → Verifying → Landed / Failed
- GIVEN a task needs_human, WHEN it appears, THEN I can approve/reject inline

### US-7: Driver Stats
**As a** user, **I want to** see agent driver performance
**So that** I can evaluate verified tasks landed per rupee.

**Acceptance Criteria:**
- GIVEN I open Drivers, WHEN stats load, THEN I see StatsCards per driver: dispatched, landed, failed, ₹/task
- GIVEN I view cost chart, WHEN data renders, THEN I see weekly cost trend

---

## Design System

### Theme: `supabase` preset
```ts
{
  base: "zinc", accent: "emerald", scheme: "dark",
  density: "default", radius: "md", shadow: "md",
  border: "thin", font: "inter", style: "default", sidebar: "dark"
}
```

### Layout
```
┌──────────────────────────────────────────────────────┐
│ Topbar [breadcrumb] [🔍 Ctrl+K] [🔔 notifs] [avatar]│
├────────┬─────────────────────────────────────────────┤
│        │                                             │
│ Side-  │         CANVAS                              │
│ bar    │   (page content changes per route)          │
│        │                                             │
│ 🏠 Home│                                             │
│ 🧠 Mem │                                             │
│ ⚖️ Dec │                                             │
│ 📊 Cal │                                             │
│ 📋 Task│                                             │
│ 🤖 Drv │                                             │
│ ───    │                                             │
│ ⚙️ Set ├─────────────────────────────────────────────┤
│        │ 💬 Chat Bar (persistent, always visible)    │
│        │ ┌─────────────────────────────────┐  ⌘K ↵  │
│        │ │ Type a thought, question, or... │         │
│        │ └─────────────────────────────────┘         │
└────────┴─────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Choice | Rationale |
|:------|:-------|:----------|
| Framework | Next.js 15 (App Router) | SaaS: SSR, middleware auth, SEO |
| UI Library | `@uzhavu/ui` (full copy) | Product factory: shared design system |
| Charts | Recharts | Lightweight, ChartCard integration |
| State | React Query (TanStack) | Server state caching, auto-refetch |
| Real-time | Webhooks (HMAC-signed) | Already built in EventBus, no new backend |
| Auth | JWT + `X-Tenant-ID` | SaaS multi-tenant |
| PWA | `@serwist/next` | Installability for SaaS customers |
| CSS | Uzhavu design tokens | 10-dimension system |
| Font | Inter (Google Fonts) | Matches preset |

---

## Real-Time via Webhooks

The backend already supports HMAC-signed webhooks. Dashboard registers a webhook endpoint:

```
POST /api/v1/webhooks/register
{
  "url": "https://dashboard.lifegraph.ai/api/webhooks",
  "events": ["capture:received", "decision:recorded", "prediction:resolved"],
  "secret": "hmac-secret"
}
```

Dashboard receives events → React Query `invalidateQueries()` → UI auto-refreshes.

For local dev: poll `GET /capture/?since=...` every 5s as fallback.

---

## API Client

```typescript
// lib/api.ts
const API = process.env.NEXT_PUBLIC_API_URL;

export const api = {
  memories: {
    list: (p) => GET("/memories/", p),
    get: (id) => GET(`/memories/${id}`),
    search: (q) => POST("/search/", { query: q }),
  },
  judgment: {
    decisions:   { list: (p) => GET("/judgment/decisions", p), get: (id) => GET(`/judgment/decisions/${id}`), create: (d) => POST("/judgment/decisions", d) },
    predictions: { list: (p) => GET("/judgment/predictions", p), create: (d) => POST("/judgment/predictions", d), resolve: (id, d) => POST(`/judgment/predictions/${id}/resolve`, d) },
    calibration: () => GET("/judgment/calibration"),
    curve:       (domain?) => GET("/judgment/calibration/curve", { domain }),
    stats:       () => GET("/judgment/stats"),
    challenge:   (proposal) => POST("/judgment/challenge", { proposal }),
  },
  capture: {
    ingest: (d) => POST("/capture/", d),
    list:   (p) => GET("/capture/", p),
  },
  kernel: {
    tasks:         { list: (p) => GET("/kernel/tasks", p) },
    drivers:       { list: () => GET("/kernel/drivers"), stats: (w?) => GET("/kernel/drivers/stats", { window: w }) },
    notifications: { list: () => GET("/kernel/notifications") },
    route:         (msg) => POST("/kernel/route", { message: msg }),
  },
};
```

---

## Build Phases (Chat-First Order)

### Phase 1: Scaffold + Shell + Chat Bar (~2 days)
- [ ] `npx -y create-next-app@latest ./` in `dashboard/`
- [ ] Copy `@uzhavu/ui` components + tokens from Uzhavu repo
- [ ] Apply `supabase` preset (dark theme, Inter font)
- [ ] Build shell: `PageLayout` + `Sidebar` + `Topbar`
- [ ] Set up API client (`lib/api.ts`) + React Query provider
- [ ] **Chat bar (persistent)** — `ComposeBox` variant at bottom
- [ ] Wire `CommandPalette` to `Ctrl+K` with command groups
- [ ] Chat → `POST /capture/` + `POST /kernel/route`
- [ ] Backend: add CORS middleware for dashboard origin

### Phase 2: Overview + Calibration (~2 days)
- [ ] Overview page: 3× `StatsCard` + calibration mini-chart + recent activity `Timeline`
- [ ] **Calibration page** (flagship): Recharts bar chart (predicted vs actual), Brier `StatsCard`, bias alerts
- [ ] Empty state for insufficient data (progress bar N/20)
- [ ] Webhook receiver endpoint (`/api/webhooks`) → invalidate queries

### Phase 3: Memory Browser + Decision Tracker (~2 days)
- [ ] Memory browser: `DataTable` + search bar + `Sheet` detail panel
- [ ] Cursor pagination for memories
- [ ] Semantic search via `/search/`
- [ ] Decision tracker: `Timeline` + detail `Modal` + create form
- [ ] Prediction confidence bars + resolve action

### Phase 4: Tasks + Drivers + Polish (~2 days)
- [ ] Task board: `Kanban` grouped by status
- [ ] Approval flow: `ConfirmDialog` for needs_human tasks
- [ ] Driver stats: `StatsCard` per driver + cost trend `ChartCard`
- [ ] Auth flow: login page + JWT + tenant header
- [ ] PWA manifest + service worker
- [ ] Responsive design + Lighthouse audit
- [ ] Deploy alongside API on VPS

**Total: ~8 days**

---

## File Structure

```
dashboard/
├── app/
│   ├── layout.tsx              ← Root: Sidebar + Topbar + ChatBar + QueryProvider
│   ├── page.tsx                ← Overview
│   ├── memories/page.tsx       ← Memory browser
│   ├── decisions/page.tsx      ← Decision tracker
│   ├── calibration/page.tsx    ← Calibration curve (flagship)
│   ├── tasks/page.tsx          ← Task kanban
│   ├── drivers/page.tsx        ← Driver stats
│   ├── settings/page.tsx       ← Settings
│   ├── login/page.tsx          ← Auth
│   └── api/webhooks/route.ts   ← Webhook receiver
├── components/
│   ├── ui/                     ← Full @uzhavu/ui copy
│   │   ├── primitives/
│   │   ├── composites/
│   │   ├── patterns/
│   │   ├── layouts/
│   │   └── tokens/
│   ├── chat-bar.tsx            ← Persistent chat input + response
│   ├── app-sidebar.tsx         ← Navigation
│   ├── app-topbar.tsx          ← Top bar with Ctrl+K
│   ├── calibration-chart.tsx   ← Recharts calibration curve
│   └── command-bar.tsx         ← Wired CommandPalette
├── lib/
│   ├── api.ts                  ← Typed API client
│   ├── hooks.ts                ← React Query hooks
│   ├── auth.ts                 ← JWT auth utilities
│   └── webhooks.ts             ← Webhook handler
├── public/
│   ├── manifest.json
│   └── icons/
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

## Verification Plan

### Manual Testing
- Type a thought in chat bar → verify capture event created
- Search memories → verify semantic search results
- Create a decision → verify it appears in timeline
- View calibration → verify chart or empty state
- Press Ctrl+K → verify command palette
- Login → verify tenant isolation

### Lighthouse
```bash
npx lighthouse http://localhost:3000 --view
```
Target: 90+ Performance, 100 Accessibility, 90+ Best Practices
