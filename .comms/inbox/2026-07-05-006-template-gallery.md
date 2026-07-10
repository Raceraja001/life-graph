---
id: 2026-07-05-006
from: hardware-research-chat (7277501b)
to: uzhavu-dev-chat
priority: medium
status: pending
created: 2026-07-05T18:07:00+05:30
claimed_by:
completed:
---

# Build Template Gallery

## Context

Pre-built business configurations that let new users pick a ready-made setup instead of starting from scratch. Shown during onboarding and in settings.

## Spec

`.comms/specs/template-gallery.md`
- 8 user stories, 4 SQL tables, ~13.5 days effort
- 7 template definitions: School, Gym, Clinic, Restaurant, Farm, Retail, Freelancer
- Custom fields system, one-click apply, versioning, community templates (future)

## Key Files to Read First
1. The spec file above
2. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\APP_ARCHITECTURE.md`
3. `.comms/specs/product-factory-implementation.md`
4. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\.agents\AGENTS.md`

## Acceptance Criteria
- [ ] Template gallery browsable with search and industry filter
- [ ] Template preview showing full breakdown
- [ ] One-click apply creates all categories, custom fields, sample data
- [ ] Applying twice doesn't duplicate data (idempotent)
- [ ] Custom fields editable after template apply
- [ ] Plan-based gating (free=3 templates, starter=all, pro=custom fields builder)
- [ ] All 7 templates seeded
- [ ] Tests passing, `pnpm build` passes

## Output
Write completion report to `d:\DevTools\Projects\agents\.comms\outbox\2026-07-05-006-templates-done.md`
