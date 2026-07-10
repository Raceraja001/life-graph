---
id: 2026-07-05-001
from: hardware-research-chat (7277501b)
to: uzhavu-dev-chat
priority: high
status: pending
created: 2026-07-05T09:03:00+05:30
claimed_by:
completed:
---

# Implement Product Factory — Frontend Layer Only

## ⚠️ Backend Already Exists

The `SaasProduct` Prisma model and `saas-products` NestJS module are **already built**. The model has: slug, domain, aliasDomains, apps[], logo, primaryColor, favicon, footerText, AI feature flags, marketing text, plans JSON.

**Only the FRONTEND integration needs building.**

## What's Done
- ✅ `SaasProduct` Prisma model (full schema)
- ✅ `saas-products` NestJS CRUD module
- ✅ All dev service modules exist (status page, uptime, cron, etc.)

## What Needs Building
1. Domain routing middleware (`middleware.ts`) — detect hostname → set product
2. Frontend product registry — read `SaasProduct` from API instead of static files
3. Product-aware sidebar/branding — filter apps, show product logo/name
4. Product-aware layout — CSS custom properties from product branding
5. Product-aware landing page — dynamic hero/features/pricing from product config
6. Product-aware AI — system prompt override from product config

## Key Difference from Original Spec
The original spec at `.comms/specs/product-factory-implementation.md` describes static TypeScript config files. **Instead, use the existing `SaasProduct` database model** — products are managed via the admin panel, not code files. The middleware should fetch the product by domain from the API (with caching).

## Spec
`.comms/specs/product-factory-implementation.md` (adapt to use existing DB model)

## Read First
1. `.comms/context/uzhavu-audit.md` — see "Product Factory" section
2. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\APP_ARCHITECTURE.md`

## Acceptance Criteria
- [ ] Visiting different domains shows different products
- [ ] Sidebar shows only apps listed in product's `apps[]` array
- [ ] Branding (logo, color, name) comes from product config
- [ ] Landing page shows product-specific marketing content
- [ ] `SaasProduct` records managed via admin panel (already working)
- [ ] Full uzhavu platform still works as default
- [ ] `pnpm build` passes

## Output
Write completion report to `.comms/outbox/2026-07-05-001-product-factory-done.md`
