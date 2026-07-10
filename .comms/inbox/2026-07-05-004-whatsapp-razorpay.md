---
id: 2026-07-05-004
from: hardware-research-chat (7277501b)
to: uzhavu-dev-chat
priority: high
status: pending
created: 2026-07-05T18:07:00+05:30
claimed_by:
completed:
---

# Build WhatsApp Bot + Razorpay UPI Integration

## Context

Two critical integration modules for the uzhavu platform that enable businesses to communicate with customers and collect payments.

## Specs

1. **WhatsApp Bot**: `.comms/specs/whatsapp-bot.md`
   - 7 user stories, 5 SQL tables, 48 tasks (~19 days)
   - AI assistant on WhatsApp, invoice sharing, payment reminders, two-way chat

2. **Razorpay UPI**: `.comms/specs/razorpay-upi.md`
   - 7 user stories, 7 SQL tables, 55 tasks (~24 days)
   - Payment links, auto-reconciliation, QR codes, refunds, subscriptions

## Key Files to Read First
1. The spec files above (full schemas, endpoints, diagrams)
2. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\APP_ARCHITECTURE.md`
3. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\.agents\AGENTS.md`

## Acceptance Criteria
- [ ] All SQL tables created and migrated
- [ ] NestJS modules with service + controller + spec for both
- [ ] Webhook endpoints receiving and processing events
- [ ] Frontend manifests, pages, and module configs
- [ ] Multi-tenant scoping on all queries
- [ ] Plan-based gating working
- [ ] Tests passing, `pnpm build` passes

## Output
Write completion report to `d:\DevTools\Projects\agents\.comms\outbox\2026-07-05-004-integrations-done.md`
