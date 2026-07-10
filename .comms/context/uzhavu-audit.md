# Uzhavu Platform — Complete Audit Report

> **Generated:** 05 Jul 2026
> **Source:** Full codebase scan of `uzhavu.race` monorepo

---

## 🚨 Critical Discovery

**Many modules we spec'd as "new" are ALREADY BUILT.** The platform is far more complete than initially understood.

| Module We Spec'd | Already Exists? | Evidence |
|:-----------------|:----------------|:---------|
| Status Page | ✅ **YES** | 6 Prisma models + NestJS module + dashboard page |
| Uptime Monitor | ✅ **YES** | 3 Prisma models + NestJS module + dashboard page |
| Log Explorer | ✅ **YES** | Prisma model + NestJS module + dashboard page |
| Cron Manager | ✅ **YES** | 2 Prisma models + NestJS module + dashboard page |
| Env Manager | ✅ **YES** | 3 Prisma models + NestJS module + dashboard page |
| Feedback Widget | ✅ **YES** | 3 Prisma models + NestJS module + dashboard page |
| API Key Management | ✅ **YES** | 2 Prisma models + NestJS module + dashboard page |
| Release Notes | ✅ **YES** | 3 Prisma models + NestJS module + dashboard page |
| Product Factory (SaasProduct) | ✅ **PARTIAL** | Prisma model exists, NestJS module exists |
| AI Conversations | ✅ **YES** | 5 Prisma models + FastAPI stores |
| Payment System | ✅ **PARTIAL** | Payment model exists, Razorpay field in Subscription |

> **8 of the 8 "new" devtools modules already exist in the codebase.**
> The product factory model (`SaasProduct`) already exists with domain, branding, apps, plans.

---

## Platform Scale

| Metric | Count |
|:-------|:------|
| Prisma models | **~110** |
| NestJS API modules | **62** |
| Dashboard pages | **34** |
| Dev dashboard pages | **21** |
| School admin pages | **16** |
| Community pages | **8** |
| Server actions files | **39** |
| Frontend module configs | **11** |
| AI engine API routers | **13** |
| AI agent tools | **6** |
| UI components | **77** |
| Theme presets | **19** |

---

## What's Actually Built — By Domain

### 1. 🏢 Business SaaS (Multi-tenant)
| Feature | Models | Module | Dashboard | Status |
|:--------|:-------|:-------|:----------|:-------|
| Contacts/CRM | Contact | contacts | ✅ | **Done** |
| Products/Catalog | Product | products | ✅ | **Done** |
| Orders | Order, OrderItem | orders | ✅ | **Done** |
| Invoicing | Invoice | invoices | ✅ | **Done** |
| Payments | Payment | payments | ✅ | **Done** |
| Expenses | Expense | expenses | ✅ | **Done** |
| Appointments | Appointment | appointments | ✅ | **Done** |
| Files/Uploads | File | files | ✅ | **Done** |
| RBAC (Roles) | Role, StaffMembership | roles | ✅ | **Done** |
| Billing/Plans | Plan, Subscription | — | ✅ | **Done** |
| Webhooks | Webhook, WebhookDelivery | webhooks | ✅ | **Done** |
| Feedback | Feedback | feedback | ✅ | **Done** |
| Audit Logs | AuditLog | audit | ✅ | **Done** |
| Calendar | — | calendar | ✅ | **Done** |
| Notifications | Notification, NotificationLog | notifications | ✅ | **Done** |

### 2. 🏫 School Management (Full Vertical)
| Feature | Models | Status |
|:--------|:-------|:-------|
| Academic Years | AcademicYear, SchoolSettings | **Done** |
| Classes & Sections | ClassSection | **Done** |
| Students | Student (with full metadata) | **Done** |
| Fee Management | FeeStructure, FeeAssignment, FeePayment | **Done** |
| Attendance | AttendanceRecord | **Done** |
| Exams & Results | Exam, ExamResult, Subject | **Done** |
| Report Cards | — (generation module) | **Done** |
| Timetable | Period, TimetableSlot | **Done** |
| Homework | Assignment, AssignmentSubmission | **Done** |
| Library | Book, BookIssue | **Done** |
| Transport | BusRoute, BusStop, StudentTransport | **Done** |
| Hostel | Hostel, HostelRoom, HostelAllocation | **Done** |
| Staff | SchoolStaff, StaffSubjectAssignment | **Done** |
| Transfer Certificates | TransferCertificate | **Done** |
| Promotion | PromotionLog | **Done** |
| Parent Portal | — (separate routes) | **Done** |
| School Events | SchoolEvent | **Done** |

### 3. 🌐 Community/Social Platform
| Feature | Models | Status |
|:--------|:-------|:-------|
| Communities | Community, CommunityMembership | **Done** |
| Posts & Feed | Post (text, poll, repost, GIF, video) | **Done** |
| Likes (6 types) | Like (like/love/haha/wow/sad/angry) | **Done** |
| Comments/Replies | Post (self-referencing parentId) | **Done** |
| Polls | Poll, PollOption, PollVote | **Done** |
| Follow/Unfollow | Follow | **Done** |
| Block | Block | **Done** |
| Groups | Group, GroupMember (public/private) | **Done** |
| Saved Posts | SavedPost | **Done** |
| Moderation | Report (reason, status, action) | **Done** |
| Notifications | Notification (like/reply/follow) | **Done** |
| Business Directory | Business (public listings) | **Done** |

### 4. 🤖 AI Engine
| Feature | Implementation | Status |
|:--------|:--------------|:-------|
| Chat (SSE streaming) | AgentOrchestrator + LiteLLM | **Done** |
| Conversations (persistent) | AiConversation, AiChatMessage + asyncpg store | **Done** |
| Voice Chat | Deepgram STT + ElevenLabs TTS | **Done** |
| Knowledge Base / RAG | AiKnowledgeDocument + pgvector embeddings | **Done** |
| User Preferences | AiUserPreference (auto-inferred) | **Done** |
| Agent Actions | AiAgentAction (tool call logging) | **Done** |
| Custom Personas | PersonaStore + asyncpg | **Done** |
| Usage/Token Tracking | UsageStore + asyncpg | **Done** |
| Prompt Templates | Templates router | **Done** |
| Conversation Sharing | Share router | **Done** |
| Web Search | Tavily integration | **Done** |
| Gmail Integration | Google API tool | **Done** |
| Calendar Integration | Google API tool | **Done** |
| Calculator | Built-in tool | **Done** |
| Life Graph | Brain router (integration point) | **Partial** |

### 5. 🛠️ Dev Services
| Feature | Models | Module | Dashboard | Status |
|:--------|:-------|:-------|:----------|:-------|
| Error Tracking | ErrorLog | error-tracking | `/dev/errors` | **Done** |
| API Analytics | ApiRequestLog | api-analytics | `/dev/api-analytics` | **Done** |
| Health Dashboard | — | health | `/dev/health` | **Done** |
| Feature Flags | FeatureFlag | feature-flags | `/dev/feature-flags` | **Done** |
| Webhooks | Webhook, WebhookDelivery | webhooks | `/dev/webhooks` | **Done** |
| Job Dashboard | — (in-memory) | job-dashboard | `/dev/jobs` | **Done** |
| Tenant Admin | — (queries Business) | tenant-admin | `/dev/tenants` | **Done** |
| Database Studio | — (information_schema) | db-studio | `/dev/database` | **Done** |
| Audit Dashboard | AuditLog | audit | `/dev/audit` | **Done** |
| Performance | ApiRequestLog (p95) | performance | `/dev/performance` | **Done** |
| Status Page | 6 models | status-page | `/dev/status-page` | **Done** |
| Uptime Monitor | 3 models | uptime-monitor | `/dev/uptime` | **Done** |
| Log Explorer | AppLog | log-explorer | `/dev/logs` | **Done** |
| Cron Manager | CronJob, CronExecution | cron-manager | `/dev/cron` | **Done** |
| Env Manager | EnvProject, EnvVariable, EnvHistory | env-manager | `/dev/env` | **Done** |
| Feedback Widget | FeedbackItem, FeedbackVote, FeedbackComment | dev-feedback | `/dev/feedback` | **Done** |
| API Keys | DevApiKey, DevApiKeyUsage | api-key-manager | `/dev/api-keys` | **Done** |
| Release Notes | Release, ReleaseItem, ChangelogSubscriber | release-notes | `/dev/releases` | **Done** |
| Notification Center | DevNotification, NotificationRule | notification-center | `/dev/notifications` | **Done** |
| Dev Projects | DevProject | dev-projects | `/dev/projects` | **Done** |
| Deployments | Deployment | deployments | — | **Partial** |
| Canary Tests | CanaryTest, CanaryResult | canary | — | **Partial** |

### 6. 🏭 Product Factory
| Feature | Implementation | Status |
|:--------|:--------------|:-------|
| SaasProduct model | Full Prisma model (slug, domain, aliasDomains, apps[], branding, plans JSON, features, marketing text) | **Done** |
| saas-products module | NestJS CRUD module | **Done** |
| Domain → product middleware | — | **Not done** |
| Frontend product filtering | — | **Not done** |
| Product-aware sidebar/branding | — | **Not done** |

---

## What's NOT Built Yet

### Needs Building (genuinely new)
| Feature | Spec Exists? |
|:--------|:-------------|
| Domain-based routing middleware | ✅ `.comms/specs/product-factory-implementation.md` |
| Frontend product filtering (sidebar, branding, landing) | ✅ Same spec |
| WhatsApp Bot | ✅ `.comms/specs/whatsapp-bot.md` |
| Razorpay integration (payment links, QR, auto-reconciliation) | ✅ `.comms/specs/razorpay-upi.md` |
| PWA (installable, offline, push) | ✅ `.comms/specs/pwa-mobile.md` |
| Natural Language Queries | ✅ `.comms/specs/natural-language-queries.md` |
| Template Gallery (pre-built business configs) | ✅ `.comms/specs/template-gallery.md` |
| Eval Harness | ✅ `.comms/specs/eval-harness.md` |
| LLM Trace Viewer | ✅ `.comms/specs/llm-trace-viewer.md` |
| Prompt Registry | ✅ `.comms/specs/prompt-registry.md` |
| MCP Tool Server | ✅ `.comms/specs/mcp-tool-server.md` |
| AI Agent System (personal agents) | ❌ Needs spec |

### Needs Finishing (partially built)
| Feature | What's Missing |
|:--------|:--------------|
| Product Factory | Domain routing, frontend filtering, branding (backend model done) |
| Worker | Only OTP queue placeholder — needs fee reminders, bulk imports |
| Canary/Synthetic Monitoring | Module exists but no scheduler/runner |
| Deployment Dashboard | Model exists, no dashboard |
| Developer CLI | Module exists, no implementation |
| Alert Channels | Health alerts don't push to Slack/Discord/Telegram yet |

### Architecture Migration Pending
| From | To | Status |
|:-----|:---|:-------|
| Flat `/modules/` structure | Nested `/apps/` manifests | **Not started** |
| Plan gating via code | Plan gating via manifest + DB features | **Not started** |
| CRM app | — | **Planned** |
| HR & Payroll app | — | **Planned** |
| Advanced Reports app | — | **Planned** |

---

## Tech Stack Summary

| Layer | Technology |
|:------|:-----------|
| Monorepo | pnpm + Turborepo |
| Frontend | Next.js 16 + React 19 + next-auth v5 beta |
| Backend API | NestJS 11 + Express 5 + Prisma |
| AI Engine | FastAPI + LiteLLM + asyncpg + pgvector |
| Worker | BullMQ + IORedis |
| Database | PostgreSQL (Neon serverless) |
| Cache/Queue | Redis |
| Real-time | Socket.IO |
| Design System | 77 custom components, OKLCH tokens, 19 themes |
| CSS | Tailwind v4 (layout) + CSS Modules |
| Testing | Vitest + Playwright |
| i18n | next-intl |
| External | Razorpay, Deepgram, ElevenLabs, Gemini, Tavily, Google APIs |

---

*This audit represents the complete state of the uzhavu.race codebase as of 05 Jul 2026.*
