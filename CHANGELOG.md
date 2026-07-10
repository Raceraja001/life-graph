# Changelog

All notable changes to Life Graph will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] — 2026-07-05

### Added

#### Webhooks (F1)
- Per-tenant webhook registration via `POST /admin/webhooks`
- HMAC-SHA256 signed payload delivery
- Circuit breaker: auto-deactivates after 10 consecutive failures
- Test ping endpoint: `POST /admin/webhooks/{id}/test`
- Full CRUD: create, list, delete

#### Memory Decay & TTL (F2)
- Exponential decay formula: `importance × e^(-decay_rate × days_since_activity)`
- Nightly cron sweep at 04:00 UTC
- Unarchive endpoint: `POST /memories/{id}/unarchive`
- Grace period via `COALESCE(last_accessed, created_at)`

#### Cursor Pagination (F3)
- Keyset pagination on `(created_at, id)` for `/memories/` and `/sessions/`
- `cursor`, `include_total` query parameters
- `next_cursor` and `has_more` in response envelope

#### Tenant Lifecycle (F4)
- Provision: `POST /admin/tenants/provision`
- Summary: `GET /admin/tenants/{id}` (counts, usage stats, plan)
- Two-phase deletion: deactivate → delete (409 if still active)
- Middleware blocks writes for deactivated tenants (403)
- Reactivate: `POST /admin/tenants/{id}/reactivate`

#### Bulk Operations (F5)
- Bulk delete: `POST /admin/bulk/delete` with dry-run mode
- Bulk import: `POST /admin/bulk/import` (max 500 memories)
- Background embedding generation via ARQ

#### Search Filters (F6)
- `created_after`, `created_before`, `source_type`, `status` on search
- Default `status="active"` excludes archived memories

#### Memory Deduplication (F7)
- Content hash (SHA-256) for O(1) exact duplicate detection
- Vector similarity (pgvector cosine, threshold=0.92) for near-duplicates
- Merge rules: `max(importance)`, `union(tags)`, `{**old, **new}` properties
- `skip_dedup=true` on `MemoryCreate` to bypass

### Improved
- `/health` now returns per-dependency latency and HTTP 503 when Postgres is down
- `/admin/export` streams NDJSON instead of loading all memories into RAM
- `create_webhook` and `provision_tenant` use Pydantic schemas (422 on bad input)
- `X-API-Version: 1.0` header on every response
- Per-tenant `cold_start_config` JSONB field for custom onboarding
- Structured `extra={}` logging with `tenant_id`, `request_id`, `method`, `path`, `status`, `duration_ms`

### Fixed
- `list_memories()` return type: callers in `recall.py`, `hybrid.py` updated for tuple
- `protocol.py` signature matches new `tuple[list[Memory], bool]` return
- Webhook ARQ pool wired in `main.py` startup

### Database Migrations
- `004`: TenantConfig, TenantWebhook tables + content_hash column
- `005`: cold_start_config JSONB column on tenant_configs

---

## API Versioning Policy

- Current version: **1.0**
- All responses include `X-API-Version: 1.0`
- Breaking changes will increment to 2.0 and mount under `/api/v2/`
- Deprecated endpoints will include `Sunset: <date>` header
- v1 will remain active for minimum 6 months after v2 launch
