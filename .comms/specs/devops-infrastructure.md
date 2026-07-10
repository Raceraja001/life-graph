# DevOps & Infrastructure — Feature Spec

> **Purpose**: Define the complete self-hosted infrastructure for the uzhavu.race platform — CI/CD pipelines, Docker Compose setup, backup strategy, monitoring stack, and SSL/domain management. Everything runs on a single VPS with no cloud vendor lock-in.
>
> **Context**: Uzhavu is a multi-tenant SaaS monorepo (Turborepo + pnpm) with NestJS API, Next.js frontend, FastAPI AI engine, BullMQ worker, PostgreSQL, and Redis. Deployed on a self-hosted VPS (Ubuntu). The platform supports multiple branded products via different domains (product factory system).
>
> **Architecture ref**: `APP_ARCHITECTURE.md`, `product-factory-implementation.md`
>
> **Developer**: Solo developer, values self-hosted solutions, cost efficiency, no vendor lock-in.

---

## Table of Contents

1. [Requirements](#requirements)
   - [Feature 1: CI/CD Pipeline](#feature-1-cicd-pipeline)
   - [Feature 2: Docker Compose Setup](#feature-2-docker-compose-setup)
   - [Feature 3: Backup Strategy](#feature-3-backup-strategy)
   - [Feature 4: Monitoring Stack](#feature-4-monitoring-stack)
   - [Feature 5: SSL & Domain Management](#feature-5-ssl--domain-management)
2. [Design](#design)
3. [Tasks](#tasks)

---

# Requirements

## Feature 1: CI/CD Pipeline

### Story 1.1: Push-to-Deploy Flow

As a **developer**, I want **code to be automatically tested and deployed when I push to the main branch** so that **I don't have to manually SSH into the server and deploy**.

#### Acceptance Criteria

- GIVEN I push a commit to the `main` branch WHEN GitHub Actions triggers THEN the pipeline runs: lint → test → build → deploy — in that order
- GIVEN the lint step fails WHEN ESLint or Prettier reports errors THEN the pipeline stops, deployment is NOT triggered, and I see the lint errors in the GitHub Actions log
- GIVEN all tests pass WHEN the build step succeeds THEN the pipeline SSHs into the VPS and runs the deploy script
- GIVEN I push to a non-main branch (e.g., `feature/billing`) WHEN GitHub Actions triggers THEN only lint and test steps run — NO deployment
- GIVEN I push to the `staging` branch WHEN GitHub Actions triggers THEN the pipeline deploys to the staging environment (different port/subdomain)
- GIVEN the deploy script runs WHEN the health check passes THEN the GitHub Actions job shows ✅ success and a notification is sent to Discord/Slack

---

### Story 1.2: Per-Service Workflows

As a **developer**, I want **separate CI/CD workflows for each service** so that **changing the API doesn't trigger a full rebuild of the frontend and AI engine**.

#### Acceptance Criteria

- GIVEN I modify files under `apps/api/` WHEN I push to `main` THEN only the `deploy-api.yml` workflow runs — NOT `deploy-web.yml` or `deploy-ai-engine.yml`
- GIVEN I modify files under `apps/web/` WHEN I push to `main` THEN only the `deploy-web.yml` workflow runs
- GIVEN I modify files under `apps/ai-engine/` WHEN I push to `main` THEN only the `deploy-ai-engine.yml` workflow runs
- GIVEN I modify files under `packages/` (shared libraries) WHEN I push to `main` THEN ALL service workflows run (shared code affects everything)
- GIVEN I modify only `.md` files or `docs/` WHEN I push THEN NO workflows run (docs changes are excluded)

---

### Story 1.3: Rollback Mechanism

As a **developer**, I want to **automatically rollback a deployment if the health check fails** so that **a bad deploy doesn't leave the service down**.

#### Acceptance Criteria

- GIVEN a deploy completes WHEN the deploy script runs a health check (`GET /health`) THEN it waits up to 60 seconds for a `200 OK` response
- GIVEN the health check fails after 60 seconds WHEN the timeout expires THEN the deploy script automatically rolls back to the previous Docker image (tagged `previous`) and restarts the service
- GIVEN a rollback occurs WHEN the previous version is restored THEN a ⚠️ warning notification is sent to Discord/Slack with: service name, commit SHA, and error details
- GIVEN I want to manually rollback WHEN I run `./scripts/rollback.sh api` THEN the API service is rolled back to the previous image and restarted

---

### Story 1.4: Staging → Production Promotion

As a **developer**, I want to **deploy to staging first, verify, then promote to production** so that **I can test changes in a production-like environment before going live**.

#### Acceptance Criteria

- GIVEN I push to the `staging` branch WHEN the pipeline completes THEN the service is deployed to the staging environment (e.g., `staging.uzhavu.com`)
- GIVEN staging is verified WHEN I merge `staging` into `main` THEN the production deployment pipeline runs with the same Docker image (no rebuild)
- GIVEN a staging deployment fails WHEN the health check fails THEN staging is rolled back and production is NOT affected
- GIVEN I want to skip staging WHEN I push directly to `main` with tag `[deploy-now]` in the commit message THEN the pipeline deploys directly to production (escape hatch for hotfixes)

---

### Story 1.5: Deployment Notifications

As a **developer**, I want to **receive notifications on Discord/Slack for all deployment events** so that **I always know the state of my deployments**.

#### Acceptance Criteria

- GIVEN a deployment starts WHEN the pipeline begins THEN a 🚀 notification is sent: "Deploying [service] — commit [sha] by [author]"
- GIVEN a deployment succeeds WHEN the health check passes THEN a ✅ notification is sent: "Deployed [service] successfully — took [duration]"
- GIVEN a deployment fails WHEN the build, test, or health check fails THEN a ❌ notification is sent: "Failed to deploy [service] — [error summary] — [link to logs]"
- GIVEN a rollback occurs WHEN the previous version is restored THEN a ⚠️ notification is sent: "Rolled back [service] to previous version"

---

## Feature 2: Docker Compose Setup

### Story 2.1: Local Development Environment

As a **developer**, I want to **start the entire stack locally with one command** so that **I can develop and test without manual setup**.

#### Acceptance Criteria

- GIVEN I clone the repo WHEN I run `docker compose -f docker-compose.dev.yml up` THEN all services start: api (NestJS with hot reload), web (Next.js with hot reload), ai-engine (FastAPI with hot reload), worker (BullMQ), postgres, redis
- GIVEN the dev environment is running WHEN I edit a file in `apps/api/src/` THEN the API service automatically restarts with my changes (hot reload via volume mount)
- GIVEN the dev environment is running WHEN I edit a file in `apps/web/src/` THEN the Next.js dev server picks up the change instantly (HMR)
- GIVEN the dev environment is running WHEN I need to debug THEN the API is accessible on port 3001 with debug port 9229, the web is on port 3000, and the AI engine is on port 8000
- GIVEN I run `docker compose -f docker-compose.dev.yml down -v` WHEN I want a clean slate THEN all containers and volumes are removed

---

### Story 2.2: Production Deployment

As a **developer**, I want to **deploy the production stack with one command** so that **I can get the platform running on the VPS quickly**.

#### Acceptance Criteria

- GIVEN I have a VPS with Docker installed WHEN I run `docker compose -f docker-compose.prod.yml up -d` THEN all services start with production-optimized images, restart policies (`unless-stopped`), and resource limits
- GIVEN the production stack is running WHEN a service crashes THEN Docker automatically restarts it (restart policy)
- GIVEN the production stack is running WHEN I view `docker compose ps` THEN all services show as `healthy` (health checks passing)
- GIVEN I need to update a service WHEN I run `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d` THEN only changed services are recreated (others remain running)

---

### Story 2.3: Service Health & Restart

As a **developer**, I want **all services to have health checks and automatic restart** so that **transient failures are handled without manual intervention**.

#### Acceptance Criteria

- GIVEN the API service is running WHEN the health check (`GET /health`) fails 3 times in a row THEN Docker marks the container as `unhealthy` and restarts it
- GIVEN PostgreSQL is starting WHEN the API tries to connect THEN the API waits (via `depends_on: condition: service_healthy`) until PostgreSQL passes its health check
- GIVEN Redis is running WHEN its health check (`redis-cli ping`) fails THEN Docker restarts the Redis container
- GIVEN a service is restarted WHEN it comes back up THEN it reconnects to PostgreSQL and Redis automatically

---

### Story 2.4: Environment Configuration

As a **developer**, I want **a well-documented `.env.example` file** so that **I can quickly set up environment variables for local and production environments**.

#### Acceptance Criteria

- GIVEN I clone the repo WHEN I copy `.env.example` to `.env` THEN all required variables have sensible defaults for local development (localhost URLs, default passwords)
- GIVEN the `.env.example` file WHEN I read it THEN every variable has a comment explaining its purpose, acceptable values, and whether it's required or optional
- GIVEN I deploy to production WHEN I set the environment variables THEN the `.env.example` clearly marks which variables MUST be changed for production (e.g., database password, secret keys)

---

## Feature 3: Backup Strategy

### Story 3.1: Automated Backup Scheduling

As a **developer**, I want **PostgreSQL backups to run automatically on a schedule** so that **I never lose data even if the VPS fails**.

#### Acceptance Criteria

- GIVEN the backup cron is configured WHEN midnight (UTC) arrives THEN a full `pg_dump` backup runs and saves a compressed `.sql.gz` file to the backup directory
- GIVEN the hourly cron is configured WHEN each hour passes THEN a WAL-based incremental backup captures changes since the last full backup
- GIVEN a backup completes WHEN the script finishes THEN it logs: backup filename, size, duration, and success/failure status to `backup_logs` table
- GIVEN a backup fails WHEN the error occurs THEN a notification is sent via Discord/Slack webhook with the error details

---

### Story 3.2: Backup Storage & Rotation

As a **developer**, I want **backups to be stored externally with automatic rotation** so that **I don't run out of disk space and old backups are cleaned up**.

#### Acceptance Criteria

- GIVEN a daily backup is created WHEN it is saved THEN it is also uploaded to S3-compatible storage (MinIO, Backblaze B2, or Wasabi) or synced to a local NAS
- GIVEN backup rotation is configured WHEN backups accumulate THEN the system keeps: 7 daily backups, 4 weekly backups (Sunday), and 12 monthly backups (1st of month) — older backups are deleted
- GIVEN the local backup directory WHEN disk usage exceeds 80% THEN the oldest local backups are pruned first (remote copies are retained)
- GIVEN the uploads directory (user files) WHEN the backup runs THEN it also syncs the `uploads/` directory to external storage using `rsync` or `rclone`

---

### Story 3.3: Restore Procedures

As a **developer**, I want to **restore from a backup quickly** so that **I can recover from data loss or migrate to a new server**.

#### Acceptance Criteria

- GIVEN I have a backup file WHEN I run `./scripts/restore.sh 2026-07-06-daily.sql.gz` THEN the script: stops the API, drops and recreates the database, restores from the backup, runs any pending Prisma migrations, restarts the API
- GIVEN I need point-in-time recovery WHEN I specify a timestamp THEN the script restores the latest full backup before that timestamp, then replays WAL logs up to the exact time
- GIVEN a restore completes WHEN the API restarts THEN a verification query runs (`SELECT COUNT(*) FROM organizations`) to confirm data is present
- GIVEN I want to restore to a different database WHEN I specify `--target-db=uzhavu_staging` THEN the backup is restored to the staging database without affecting production

---

### Story 3.4: Backup Verification

As a **developer**, I want **backups to be automatically verified monthly** so that **I know my backups are actually restorable**.

#### Acceptance Criteria

- GIVEN the monthly verification cron runs WHEN the 1st of the month arrives THEN the script: downloads the latest daily backup, restores it to a temporary database (`uzhavu_verify`), runs verification queries, drops the temp database, and logs the result
- GIVEN verification passes WHEN all checks succeed THEN the log shows: "Backup verified — [X] tables, [Y] rows, restore took [Z] seconds"
- GIVEN verification fails WHEN the restore or verification queries fail THEN a ⚠️ CRITICAL notification is sent via Discord/Slack: "Backup verification FAILED — [error details]"

---

## Feature 4: Monitoring Stack

### Story 4.1: Infrastructure Metrics

As a **developer**, I want to **monitor VPS resources (CPU, RAM, disk, network)** so that **I can detect capacity issues before they cause downtime**.

#### Acceptance Criteria

- GIVEN Prometheus is running WHEN Node Exporter scrapes metrics THEN CPU usage, memory usage, disk I/O, network traffic, and filesystem space are collected every 15 seconds
- GIVEN I open Grafana WHEN I view the "VPS Overview" dashboard THEN I see real-time gauges for CPU, RAM, disk, and network with 1h/6h/24h/7d time range selectors
- GIVEN disk usage exceeds 80% WHEN Prometheus evaluates alert rules THEN an alert fires and a notification is sent via Discord/Slack: "⚠️ Disk usage at 82% on /dev/sda1"
- GIVEN CPU usage exceeds 90% for 5 minutes WHEN the alert fires THEN a notification includes: which processes are consuming CPU (from `node_exporter`)

---

### Story 4.2: Application Metrics

As a **developer**, I want to **monitor API performance (request count, latency, error rate)** so that **I can track application health and debug performance issues**.

#### Acceptance Criteria

- GIVEN the NestJS API is instrumented WHEN requests are processed THEN Prometheus collects: `http_requests_total` (by method, path, status), `http_request_duration_seconds` (histogram), and `http_response_size_bytes`
- GIVEN the FastAPI AI engine is instrumented WHEN AI calls are processed THEN Prometheus collects: `ai_requests_total`, `ai_request_duration_seconds`, `ai_tokens_used_total`, and `ai_cost_usd_total`
- GIVEN BullMQ worker is running WHEN jobs are processed THEN Prometheus collects: `bullmq_jobs_completed_total`, `bullmq_jobs_failed_total`, `bullmq_queue_depth`, and `bullmq_job_duration_seconds`
- GIVEN the API error rate exceeds 5% over 5 minutes WHEN the alert fires THEN a notification includes: error rate percentage, most common error paths, and sample error messages

---

### Story 4.3: PostgreSQL Metrics

As a **developer**, I want to **monitor PostgreSQL performance** so that **I can detect slow queries, connection exhaustion, and database issues**.

#### Acceptance Criteria

- GIVEN PostgreSQL Exporter is running WHEN it scrapes metrics THEN it collects: active connections, idle connections, max connections, transaction rate, tuple operations (inserts/updates/deletes/selects), cache hit ratio, replication lag, table sizes, and index usage
- GIVEN I view the "PostgreSQL" Grafana dashboard WHEN metrics are loaded THEN I see: connection pool gauge, queries/sec chart, cache hit ratio (should be >99%), largest tables by size, and slow query log
- GIVEN connection count exceeds 80% of `max_connections` WHEN the alert fires THEN a notification includes current connection count and breakdown by application

---

### Story 4.4: Custom Dashboards

As a **developer**, I want **pre-configured Grafana dashboards for key business and technical metrics** so that **I can quickly assess platform health at a glance**.

#### Acceptance Criteria

- GIVEN I open Grafana WHEN I select "API Health" dashboard THEN I see: request rate (req/sec), p50/p95/p99 latency, error rate, top 10 slowest endpoints, and uptime percentage
- GIVEN I open Grafana WHEN I select "AI Engine Costs" dashboard THEN I see: total AI calls today/week/month, estimated cost (USD), tokens consumed, model breakdown (cheap vs expensive), and cost trend
- GIVEN I open Grafana WHEN I select "User Activity" dashboard THEN I see: DAU/WAU/MAU, signups per day, active organizations, most-used features (by API endpoint hits)
- GIVEN I open Grafana WHEN I select "Infrastructure" dashboard THEN I see: VPS overview (CPU/RAM/disk), Docker container status, PostgreSQL health, Redis memory usage, and BullMQ queue depths

---

### Story 4.5: Alerting & Uptime Integration

As a **developer**, I want **alert rules that notify me when something is wrong** and **integration with the existing status page module** so that **I'm alerted immediately and users see real-time status**.

#### Acceptance Criteria

- GIVEN alert rules are configured WHEN any rule fires THEN a notification is sent to Discord/Slack with: alert name, severity (warning/critical), current value, threshold, and suggested action
- GIVEN the existing uptime monitor module in the platform WHEN Prometheus detects a service down THEN it updates the status page module via API call (`POST /api/status/incidents`)
- GIVEN all alerts are resolved WHEN conditions return to normal THEN a ✅ resolved notification is sent and the status page incident is auto-closed
- GIVEN I want to add a new alert WHEN I edit `alert-rules.yml` THEN the change is picked up by Prometheus without restart (via `SIGHUP` or API reload)

| Alert | Condition | Severity |
|:------|:----------|:---------|
| High Disk Usage | `disk_used_percent > 80` for 5m | Warning |
| Critical Disk | `disk_used_percent > 95` for 1m | Critical |
| High CPU | `cpu_usage_percent > 90` for 5m | Warning |
| High Memory | `memory_used_percent > 85` for 5m | Warning |
| API Down | `up{job="api"} == 0` for 1m | Critical |
| AI Engine Down | `up{job="ai-engine"} == 0` for 1m | Critical |
| High Error Rate | `http_error_rate > 0.05` for 5m | Warning |
| High Latency | `http_p99_latency > 5s` for 5m | Warning |
| PostgreSQL Down | `pg_up == 0` for 30s | Critical |
| Connection Exhaustion | `pg_connections / pg_max > 0.8` for 5m | Warning |
| Redis Down | `redis_up == 0` for 30s | Critical |
| Backup Failed | `backup_last_success_age > 25h` | Critical |
| SSL Cert Expiring | `ssl_cert_expiry_days < 14` | Warning |

---

## Feature 5: SSL & Domain Management

### Story 5.1: Automatic SSL Provisioning

As a **developer**, I want **SSL certificates to be automatically provisioned for all domains** so that **every product domain has HTTPS without manual certificate management**.

#### Acceptance Criteria

- GIVEN Caddy is configured as the reverse proxy WHEN a new domain is added to the Caddyfile THEN Caddy automatically requests a Let's Encrypt SSL certificate for that domain
- GIVEN a wildcard domain `*.uzhavu.com` is configured WHEN any subdomain (e.g., `app.uzhavu.com`, `staging.uzhavu.com`) is accessed THEN the wildcard certificate covers it
- GIVEN a certificate is about to expire WHEN 30 days remain THEN Caddy automatically renews it without downtime
- GIVEN certificate provisioning fails WHEN Let's Encrypt rate limits are hit THEN the system falls back to self-signed and logs a warning

---

### Story 5.2: Custom Domain Onboarding

As a **platform admin**, I want **tenants to use their own custom domains** so that **standalone products can run on branded domains like `invoicesimple.in`**.

#### Acceptance Criteria

- GIVEN a tenant wants to use a custom domain WHEN they add it via Admin → Products → Domains THEN the system shows DNS instructions: "Add a CNAME record pointing `yourdomain.com` to `vps.uzhavu.com`"
- GIVEN the tenant has added the CNAME WHEN they click "Verify Domain" THEN the system performs a DNS lookup to confirm the CNAME points to the VPS IP
- GIVEN DNS verification passes WHEN the domain is confirmed THEN Caddy automatically provisions an SSL certificate for the custom domain
- GIVEN multiple domains point to the same product WHEN they are all verified THEN each domain serves the same product with the same branding

---

### Story 5.3: Domain Verification via DNS TXT Record

As the **system**, I want to **verify domain ownership via DNS TXT records** so that **only legitimate domain owners can configure their domains on the platform**.

#### Acceptance Criteria

- GIVEN a tenant adds a custom domain `myapp.com` WHEN the system generates a verification token THEN it displays: "Add a TXT record: `_uzhavu-verify.myapp.com` with value `uzv_verify_abc123def456`"
- GIVEN the tenant adds the TXT record WHEN they click "Verify" THEN the system queries DNS for the TXT record and confirms the value matches
- GIVEN the TXT record is not found WHEN verification fails THEN the system shows: "DNS record not found. It may take up to 48 hours for DNS changes to propagate. Try again later."
- GIVEN a domain was previously verified WHEN the TXT record is removed THEN the domain remains verified (one-time verification, not continuous)

---

### Story 5.4: Domain Management API

As a **developer**, I want to **manage domains programmatically** so that **the product launcher can automatically configure domains when products are published**.

#### Acceptance Criteria

- GIVEN I call `POST /api/admin/domains` with a domain name WHEN the domain is valid THEN it is added to the domain configuration, and Caddy is reloaded to pick up the new domain
- GIVEN I call `DELETE /api/admin/domains/:id` WHEN the domain exists THEN it is removed from the configuration, and Caddy is reloaded
- GIVEN I call `GET /api/admin/domains` WHEN domains are configured THEN I see a list with: domain name, product ID, SSL status (active/pending/failed), verification status, and last checked timestamp
- GIVEN I call `POST /api/admin/domains/:id/verify` WHEN verification is triggered THEN the system checks DNS records and updates the verification status

---

# Design

## VPS Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VPS (Ubuntu 22.04 LTS)                          │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Caddy (Reverse Proxy)                           │ │
│  │  :80 ─── HTTP → HTTPS redirect                                    │ │
│  │  :443 ── HTTPS → route by domain:                                 │ │
│  │         app.uzhavu.com      → localhost:3000 (web)                │ │
│  │         api.uzhavu.com      → localhost:3001 (api)                │ │
│  │         ai.uzhavu.com       → localhost:8000 (ai-engine)          │ │
│  │         invoicesimple.in    → localhost:3000 (web, product route)  │ │
│  │         farmbook.in         → localhost:3000 (web, product route)  │ │
│  │         staging.uzhavu.com  → localhost:4000 (staging web)        │ │
│  │         grafana.uzhavu.com  → localhost:3100 (grafana)            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│  ┌──────────────────────────┐│┌──────────────────────────────────────┐  │
│  │     Application Stack    │││     Monitoring Stack                 │  │
│  │  ┌─────────────────────┐ │││  ┌──────────────────────────────┐   │  │
│  │  │ web       (:3000)   │ │││  │ prometheus    (:9090)         │   │  │
│  │  │ Next.js 16          │ │││  │ node-exporter (:9100)         │   │  │
│  │  ├─────────────────────┤ │││  │ pg-exporter   (:9187)         │   │  │
│  │  │ api       (:3001)   │ │││  │ redis-exporter(:9121)         │   │  │
│  │  │ NestJS 11           │ │││  │ caddy-exporter(:9180)         │   │  │
│  │  ├─────────────────────┤ │││  │ grafana       (:3100)         │   │  │
│  │  │ ai-engine (:8000)   │ │││  └──────────────────────────────┘   │  │
│  │  │ FastAPI             │ │││                                      │  │
│  │  ├─────────────────────┤ │└┘──────────────────────────────────────┘  │
│  │  │ worker              │ │                                           │
│  │  │ BullMQ processor    │ │                                           │
│  │  ├─────────────────────┤ │                                           │
│  │  │ postgres  (:5432)   │ │                                           │
│  │  │ PostgreSQL 16       │ │                                           │
│  │  ├─────────────────────┤ │                                           │
│  │  │ redis     (:6379)   │ │                                           │
│  │  │ Redis 7             │ │                                           │
│  │  └─────────────────────┘ │                                           │
│  └──────────────────────────┘                                           │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                       Backup System                                │ │
│  │  Cron: daily pg_dump → /backups/ → rsync to NAS/S3               │ │
│  │  Cron: hourly WAL archive → /backups/wal/                        │ │
│  │  Cron: daily rsync uploads/ → NAS/S3                             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Files

### CI/CD Pipeline

#### `.github/workflows/deploy-api.yml`

```yaml
name: Deploy API

on:
  push:
    branches: [main, staging]
    paths:
      - 'apps/api/**'
      - 'packages/**'
      - 'prisma/**'
      - '.github/workflows/deploy-api.yml'

concurrency:
  group: deploy-api-${{ github.ref }}
  cancel-in-progress: true

env:
  SERVICE: api
  DOCKER_IMAGE: uzhavu-api
  HEALTH_ENDPOINT: /health
  HEALTH_PORT: 3001

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Lint
        run: pnpm --filter api lint

      - name: Type check
        run: pnpm --filter api type-check

      - name: Run tests
        run: pnpm --filter api test
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/uzhavu_test
          NODE_ENV: test

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: uzhavu_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

  build-and-deploy:
    needs: lint-and-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/staging'
    environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}

    steps:
      - uses: actions/checkout@v4

      - name: Notify deploy start
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "🚀 Deploying API"
          description: "Commit: `${{ github.sha }}` by ${{ github.actor }}"
          color: 0x0099ff

      - name: Build Docker image
        run: |
          docker build -f docker/Dockerfile.api -t ${{ env.DOCKER_IMAGE }}:${{ github.sha }} .
          docker tag ${{ env.DOCKER_IMAGE }}:${{ github.sha }} ${{ env.DOCKER_IMAGE }}:latest
          docker save ${{ env.DOCKER_IMAGE }}:${{ github.sha }} | gzip > /tmp/api-image.tar.gz

      - name: Copy image to VPS
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          source: "/tmp/api-image.tar.gz"
          target: "/tmp/"

      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/uzhavu
            # Load new image
            docker load < /tmp/api-image.tar.gz
            rm /tmp/api-image.tar.gz
            # Tag current as previous (for rollback)
            docker tag ${{ env.DOCKER_IMAGE }}:current ${{ env.DOCKER_IMAGE }}:previous 2>/dev/null || true
            docker tag ${{ env.DOCKER_IMAGE }}:${{ github.sha }} ${{ env.DOCKER_IMAGE }}:current
            # Deploy with health check
            ./scripts/deploy.sh api ${{ github.sha }}

      - name: Notify deploy success
        if: success()
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "✅ API Deployed Successfully"
          description: "Commit: `${{ github.sha }}`"
          color: 0x00ff00

      - name: Notify deploy failure
        if: failure()
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "❌ API Deploy Failed"
          description: "Commit: `${{ github.sha }}` — Check logs"
          color: 0xff0000
          url: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

---

#### `.github/workflows/deploy-web.yml`

```yaml
name: Deploy Web

on:
  push:
    branches: [main, staging]
    paths:
      - 'apps/web/**'
      - 'packages/**'
      - '.github/workflows/deploy-web.yml'

concurrency:
  group: deploy-web-${{ github.ref }}
  cancel-in-progress: true

env:
  SERVICE: web
  DOCKER_IMAGE: uzhavu-web
  HEALTH_ENDPOINT: /api/health
  HEALTH_PORT: 3000

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter web lint
      - run: pnpm --filter web type-check

  build-and-deploy:
    needs: lint-and-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/staging'
    environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}
    steps:
      - uses: actions/checkout@v4
      - name: Notify deploy start
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "🚀 Deploying Web"
          description: "Commit: `${{ github.sha }}` by ${{ github.actor }}"
          color: 0x0099ff
      - name: Build and deploy
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/uzhavu
            git pull origin ${{ github.ref_name }}
            docker compose -f docker-compose.prod.yml build web
            docker tag uzhavu-web:current uzhavu-web:previous 2>/dev/null || true
            docker tag uzhavu-web:latest uzhavu-web:current
            ./scripts/deploy.sh web ${{ github.sha }}
      - name: Notify result
        if: always()
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "${{ job.status == 'success' && '✅' || '❌' }} Web Deploy ${{ job.status }}"
          color: ${{ job.status == 'success' && '0x00ff00' || '0xff0000' }}
```

---

#### `.github/workflows/deploy-ai-engine.yml`

```yaml
name: Deploy AI Engine

on:
  push:
    branches: [main, staging]
    paths:
      - 'apps/ai-engine/**'
      - '.github/workflows/deploy-ai-engine.yml'

concurrency:
  group: deploy-ai-${{ github.ref }}
  cancel-in-progress: true

env:
  SERVICE: ai-engine
  DOCKER_IMAGE: uzhavu-ai
  HEALTH_ENDPOINT: /health
  HEALTH_PORT: 8000

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r apps/ai-engine/requirements.txt
      - run: cd apps/ai-engine && python -m ruff check .
      - run: cd apps/ai-engine && python -m pytest tests/

  build-and-deploy:
    needs: lint-and-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/staging'
    environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}
    steps:
      - uses: actions/checkout@v4
      - name: Notify deploy start
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "🚀 Deploying AI Engine"
          description: "Commit: `${{ github.sha }}` by ${{ github.actor }}"
          color: 0x0099ff
      - name: Build and deploy
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/uzhavu
            git pull origin ${{ github.ref_name }}
            docker compose -f docker-compose.prod.yml build ai-engine
            docker tag uzhavu-ai:current uzhavu-ai:previous 2>/dev/null || true
            docker tag uzhavu-ai:latest uzhavu-ai:current
            ./scripts/deploy.sh ai-engine ${{ github.sha }}
      - name: Notify result
        if: always()
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "${{ job.status == 'success' && '✅' || '❌' }} AI Engine Deploy ${{ job.status }}"
          color: ${{ job.status == 'success' && '0x00ff00' || '0xff0000' }}
```

---

#### `scripts/deploy.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# Deploy a service with health check and rollback
# Usage: ./scripts/deploy.sh <service> <commit_sha>
# Example: ./scripts/deploy.sh api abc123
# ============================================================

set -euo pipefail

SERVICE="${1:?Usage: deploy.sh <service> <commit_sha>}"
COMMIT="${2:?Usage: deploy.sh <service> <commit_sha>}"
COMPOSE_FILE="docker-compose.prod.yml"
HEALTH_TIMEOUT=60
HEALTH_INTERVAL=5
LOG_FILE="/var/log/uzhavu/deploy-${SERVICE}-$(date +%Y%m%d-%H%M%S).log"

# Service health check mapping
declare -A HEALTH_URLS=(
  ["api"]="http://localhost:3001/health"
  ["web"]="http://localhost:3000/api/health"
  ["ai-engine"]="http://localhost:8000/health"
  ["worker"]="http://localhost:3001/health"  # Worker shares API health
)

HEALTH_URL="${HEALTH_URLS[$SERVICE]:-}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

notify_discord() {
  local message="$1"
  local color="${2:-0x0099ff}"
  if [ -n "${DISCORD_WEBHOOK:-}" ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"embeds\":[{\"title\":\"$message\",\"color\":$color}]}" \
      "$DISCORD_WEBHOOK" > /dev/null 2>&1 || true
  fi
}

health_check() {
  local url="$1"
  local timeout="$2"
  local elapsed=0

  log "Running health check: $url (timeout: ${timeout}s)"

  while [ $elapsed -lt "$timeout" ]; do
    if curl -sf "$url" > /dev/null 2>&1; then
      log "Health check PASSED after ${elapsed}s"
      return 0
    fi
    sleep "$HEALTH_INTERVAL"
    elapsed=$((elapsed + HEALTH_INTERVAL))
    log "Health check pending... (${elapsed}s / ${timeout}s)"
  done

  log "Health check FAILED after ${timeout}s"
  return 1
}

rollback() {
  log "⚠️  ROLLING BACK $SERVICE to previous version..."
  notify_discord "⚠️ Rolling back $SERVICE — health check failed for commit $COMMIT" "0xff9900"

  # Stop current container
  docker compose -f "$COMPOSE_FILE" stop "$SERVICE"

  # Restore previous image
  docker tag "uzhavu-${SERVICE}:previous" "uzhavu-${SERVICE}:current" 2>/dev/null || {
    log "ERROR: No previous image found for rollback!"
    notify_discord "❌ ROLLBACK FAILED for $SERVICE — no previous image" "0xff0000"
    exit 1
  }

  # Start with previous image
  docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"

  # Verify rollback
  if health_check "$HEALTH_URL" 30; then
    log "✅ Rollback successful"
    notify_discord "⚠️ Rolled back $SERVICE to previous version" "0xff9900"
  else
    log "❌ CRITICAL: Rollback also failed!"
    notify_discord "❌ CRITICAL: $SERVICE rollback also failed!" "0xff0000"
    exit 1
  fi
}

# ── Main ──────────────────────────────────────────────────

log "═══════════════════════════════════════════"
log "Deploying $SERVICE (commit: $COMMIT)"
log "═══════════════════════════════════════════"

cd /opt/uzhavu

# Run migrations if deploying API
if [ "$SERVICE" = "api" ]; then
  log "Running Prisma migrations..."
  docker compose -f "$COMPOSE_FILE" run --rm api npx prisma migrate deploy 2>&1 | tee -a "$LOG_FILE"
fi

# Restart the service with new image
log "Restarting $SERVICE..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate "$SERVICE"

# Wait for health check
if [ -n "$HEALTH_URL" ]; then
  if health_check "$HEALTH_URL" "$HEALTH_TIMEOUT"; then
    log "✅ Deploy successful: $SERVICE @ $COMMIT"
    notify_discord "✅ Deployed $SERVICE successfully (${COMMIT:0:7})" "0x00ff00"
  else
    rollback
    exit 1
  fi
else
  log "⚠️  No health check URL for $SERVICE — skipping"
  log "✅ Deploy complete (unverified): $SERVICE @ $COMMIT"
fi

# Cleanup old images
log "Cleaning up dangling images..."
docker image prune -f >> "$LOG_FILE" 2>&1

log "═══════════════════════════════════════════"
log "Deploy finished"
log "═══════════════════════════════════════════"
```

---

#### `scripts/rollback.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# Manual rollback script
# Usage: ./scripts/rollback.sh <service>
# Example: ./scripts/rollback.sh api
# ============================================================

set -euo pipefail

SERVICE="${1:?Usage: rollback.sh <service>}"
COMPOSE_FILE="docker-compose.prod.yml"

echo "Rolling back $SERVICE to previous version..."

cd /opt/uzhavu

# Check previous image exists
if ! docker image inspect "uzhavu-${SERVICE}:previous" > /dev/null 2>&1; then
  echo "ERROR: No previous image found for $SERVICE"
  exit 1
fi

# Swap images
docker tag "uzhavu-${SERVICE}:current" "uzhavu-${SERVICE}:rollback-$(date +%s)" 2>/dev/null || true
docker tag "uzhavu-${SERVICE}:previous" "uzhavu-${SERVICE}:current"

# Restart service
docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate "$SERVICE"

echo "✅ Rolled back $SERVICE to previous version"
echo "Run 'docker compose -f $COMPOSE_FILE logs -f $SERVICE' to verify"
```

---

### Docker Compose

#### `docker-compose.dev.yml`

```yaml
# ============================================================
# Development environment — hot reload, debug ports, exposed DBs
# Usage: docker compose -f docker-compose.dev.yml up
# ============================================================

services:
  postgres:
    image: postgres:16-alpine
    container_name: uzhavu-postgres-dev
    environment:
      POSTGRES_USER: ${DB_USER:-uzhavu}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-uzhavu_dev}
      POSTGRES_DB: ${DB_NAME:-uzhavu}
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-uzhavu}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: uzhavu-redis-dev
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
      target: development
    container_name: uzhavu-api-dev
    command: pnpm --filter api dev
    ports:
      - "3001:3001"
      - "9229:9229"     # Node.js debug port
    volumes:
      - ./apps/api:/app/apps/api
      - ./packages:/app/packages
      - ./prisma:/app/prisma
      - /app/node_modules
      - /app/apps/api/node_modules
    environment:
      NODE_ENV: development
      DATABASE_URL: postgresql://${DB_USER:-uzhavu}:${DB_PASSWORD:-uzhavu_dev}@postgres:5432/${DB_NAME:-uzhavu}
      REDIS_URL: redis://redis:6379
      PORT: 3001
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.web
      target: development
    container_name: uzhavu-web-dev
    command: pnpm --filter web dev
    ports:
      - "3000:3000"
    volumes:
      - ./apps/web:/app/apps/web
      - ./packages:/app/packages
      - /app/node_modules
      - /app/apps/web/node_modules
      - /app/apps/web/.next
    environment:
      NODE_ENV: development
      NEXT_PUBLIC_API_URL: http://localhost:3001
      NEXT_PUBLIC_AI_URL: http://localhost:8000
    depends_on:
      - api

  ai-engine:
    build:
      context: .
      dockerfile: docker/Dockerfile.ai-engine
      target: development
    container_name: uzhavu-ai-dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./apps/ai-engine:/app
    environment:
      DATABASE_URL: postgresql://${DB_USER:-uzhavu}:${DB_PASSWORD:-uzhavu_dev}@postgres:5432/${DB_NAME:-uzhavu}
      REDIS_URL: redis://redis:6379
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-sk-dev-key}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
      target: development
    container_name: uzhavu-worker-dev
    command: pnpm --filter api worker:dev
    volumes:
      - ./apps/api:/app/apps/api
      - ./packages:/app/packages
      - /app/node_modules
    environment:
      NODE_ENV: development
      DATABASE_URL: postgresql://${DB_USER:-uzhavu}:${DB_PASSWORD:-uzhavu_dev}@postgres:5432/${DB_NAME:-uzhavu}
      REDIS_URL: redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_dev_data:
```

---

#### `docker-compose.prod.yml`

```yaml
# ============================================================
# Production environment — optimized images, restart policies
# Usage: docker compose -f docker-compose.prod.yml up -d
# ============================================================

services:
  postgres:
    image: postgres:16-alpine
    container_name: uzhavu-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    ports:
      - "127.0.0.1:5432:5432"  # Only accessible from localhost
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups      # For pg_dump access
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M
    shm_size: 256m
    command: >
      postgres
        -c shared_buffers=512MB
        -c effective_cache_size=1536MB
        -c work_mem=16MB
        -c maintenance_work_mem=128MB
        -c max_connections=200
        -c wal_level=replica
        -c archive_mode=on
        -c archive_command='cp %p /backups/wal/%f'
        -c log_min_duration_statement=1000

  redis:
    image: redis:7-alpine
    container_name: uzhavu-redis
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --save 60 1000

  api:
    image: uzhavu-api:current
    container_name: uzhavu-api
    restart: unless-stopped
    ports:
      - "127.0.0.1:3001:3001"
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379
      PORT: 3001
      JWT_SECRET: ${JWT_SECRET}
      RAZORPAY_KEY_ID: ${RAZORPAY_KEY_ID}
      RAZORPAY_KEY_SECRET: ${RAZORPAY_KEY_SECRET}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:3001/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  web:
    image: uzhavu-web:current
    container_name: uzhavu-web
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      NODE_ENV: production
      NEXT_PUBLIC_API_URL: ${API_URL}
      NEXT_PUBLIC_AI_URL: ${AI_URL}
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:3000/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    depends_on:
      - api
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  ai-engine:
    image: uzhavu-ai:current
    container_name: uzhavu-ai
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  worker:
    image: uzhavu-api:current
    container_name: uzhavu-worker
    restart: unless-stopped
    command: node dist/worker.js
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  postgres_data:
  redis_data:
```

---

#### `docker/Dockerfile.api`

```dockerfile
# ============================================================
# NestJS API — Multi-stage build
# ============================================================

# ── Development stage ────────────────────────────────
FROM node:22-alpine AS development
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/api/package.json apps/api/
COPY packages/ packages/
COPY prisma/ prisma/
RUN pnpm install --frozen-lockfile
COPY apps/api/ apps/api/
RUN cd apps/api && npx prisma generate
EXPOSE 3001 9229
CMD ["pnpm", "--filter", "api", "dev"]

# ── Build stage ──────────────────────────────────────
FROM development AS build
RUN pnpm --filter api build

# ── Production stage ─────────────────────────────────
FROM node:22-alpine AS production
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate
ENV NODE_ENV=production

COPY --from=build /app/apps/api/dist ./dist
COPY --from=build /app/apps/api/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/prisma ./prisma
COPY --from=build /app/apps/api/node_modules/.prisma ./node_modules/.prisma

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nestjs -u 1001 && \
    chown -R nestjs:nodejs /app
USER nestjs

EXPOSE 3001
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -sf http://localhost:3001/health || exit 1

CMD ["node", "dist/main.js"]
```

---

#### `docker/Dockerfile.web`

```dockerfile
# ============================================================
# Next.js Frontend — Multi-stage build
# ============================================================

# ── Development stage ────────────────────────────────
FROM node:22-alpine AS development
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/
COPY packages/ packages/
RUN pnpm install --frozen-lockfile
COPY apps/web/ apps/web/
EXPOSE 3000
CMD ["pnpm", "--filter", "web", "dev"]

# ── Build stage ──────────────────────────────────────
FROM development AS build
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter web build

# ── Production stage ─────────────────────────────────
FROM node:22-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./.next/static
COPY --from=build /app/apps/web/public ./public

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001 && \
    chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -sf http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
```

---

#### `docker/Dockerfile.ai-engine`

```dockerfile
# ============================================================
# FastAPI AI Engine
# ============================================================

# ── Development stage ────────────────────────────────
FROM python:3.12-slim AS development
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY apps/ai-engine/requirements.txt .
RUN uv pip install --system -r requirements.txt
COPY apps/ai-engine/ .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production stage ─────────────────────────────────
FROM python:3.12-slim AS production
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv
COPY apps/ai-engine/requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY apps/ai-engine/ .

RUN addgroup --gid 1001 appgroup && \
    adduser --uid 1001 --gid 1001 --disabled-password appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

#### `.env.example`

```bash
# ============================================================
# Uzhavu Environment Variables
# Copy to .env and fill in values
# Variables marked [REQUIRED] must be set for production
# Variables marked [DEV-DEFAULT] have sensible dev defaults
# ============================================================

# ── Database ─────────────────────────────────────────
DB_USER=uzhavu                          # [DEV-DEFAULT] PostgreSQL username
DB_PASSWORD=uzhavu_dev                  # [REQUIRED] Change for production!
DB_NAME=uzhavu                          # [DEV-DEFAULT] Database name
DATABASE_URL=postgresql://uzhavu:uzhavu_dev@localhost:5432/uzhavu  # [REQUIRED] Full connection string

# ── Redis ────────────────────────────────────────────
REDIS_URL=redis://localhost:6379         # [DEV-DEFAULT] Redis connection

# ── API ──────────────────────────────────────────────
PORT=3001                                # [DEV-DEFAULT] API port
NODE_ENV=development                     # [DEV-DEFAULT] development | production
JWT_SECRET=change-me-in-production       # [REQUIRED] JWT signing secret (min 32 chars)
ENCRYPTION_KEY=change-me-32-char-key     # [REQUIRED] AES-256 encryption key for sensitive data

# ── Frontend ────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:3001 # [DEV-DEFAULT] API URL for frontend
NEXT_PUBLIC_AI_URL=http://localhost:8000  # [DEV-DEFAULT] AI engine URL
NEXT_PUBLIC_APP_NAME=Uzhavu              # [DEV-DEFAULT] App display name

# ── AI Engine ───────────────────────────────────────
LITELLM_MASTER_KEY=sk-dev-key           # [REQUIRED] LiteLLM master key
OPENAI_API_KEY=                          # [OPTIONAL] OpenAI API key
GOOGLE_API_KEY=                          # [OPTIONAL] Google AI API key
ANTHROPIC_API_KEY=                       # [OPTIONAL] Anthropic API key

# ── Razorpay ────────────────────────────────────────
RAZORPAY_KEY_ID=                         # [OPTIONAL] Razorpay Key ID (rzp_test_* for testing)
RAZORPAY_KEY_SECRET=                     # [OPTIONAL] Razorpay Key Secret

# ── WhatsApp ────────────────────────────────────────
WHATSAPP_API_TOKEN=                      # [OPTIONAL] WhatsApp Business API token
WHATSAPP_PHONE_NUMBER_ID=               # [OPTIONAL] WhatsApp phone number ID

# ── Notifications ───────────────────────────────────
DISCORD_WEBHOOK=                         # [OPTIONAL] Discord webhook URL for deploy notifications
SMTP_HOST=                               # [OPTIONAL] SMTP server for emails
SMTP_PORT=587                            # [DEV-DEFAULT]
SMTP_USER=                               # [OPTIONAL]
SMTP_PASSWORD=                           # [OPTIONAL]
SMTP_FROM=noreply@uzhavu.com            # [DEV-DEFAULT]

# ── Monitoring ──────────────────────────────────────
GRAFANA_ADMIN_PASSWORD=admin             # [REQUIRED] Change for production!

# ── Backup ──────────────────────────────────────────
BACKUP_S3_ENDPOINT=                      # [OPTIONAL] S3-compatible endpoint (e.g., Backblaze B2)
BACKUP_S3_BUCKET=                        # [OPTIONAL] Bucket name
BACKUP_S3_ACCESS_KEY=                    # [OPTIONAL] S3 access key
BACKUP_S3_SECRET_KEY=                    # [OPTIONAL] S3 secret key
BACKUP_DISCORD_WEBHOOK=                  # [OPTIONAL] Separate webhook for backup notifications

# ── Domain ──────────────────────────────────────────
PRIMARY_DOMAIN=uzhavu.com               # [REQUIRED] Primary domain
VPS_IP=                                  # [REQUIRED] VPS public IP address
```

---

### Backup Scripts

#### `scripts/backup.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# PostgreSQL Backup Script with Rotation
# Usage: ./scripts/backup.sh [daily|hourly]
# Crontab:
#   0 0 * * * /opt/uzhavu/scripts/backup.sh daily
#   0 * * * * /opt/uzhavu/scripts/backup.sh hourly
# ============================================================

set -euo pipefail

BACKUP_TYPE="${1:-daily}"
BACKUP_DIR="/opt/uzhavu/backups"
DAILY_DIR="$BACKUP_DIR/daily"
HOURLY_DIR="$BACKUP_DIR/hourly"
WEEKLY_DIR="$BACKUP_DIR/weekly"
MONTHLY_DIR="$BACKUP_DIR/monthly"
WAL_DIR="$BACKUP_DIR/wal"
UPLOADS_DIR="/opt/uzhavu/uploads"
LOG_FILE="/var/log/uzhavu/backup.log"
DATE=$(date +%Y-%m-%d)
DATETIME=$(date +%Y-%m-%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday
DAY_OF_MONTH=$(date +%d)

# Load env
source /opt/uzhavu/.env

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [BACKUP] $*" | tee -a "$LOG_FILE"
}

notify() {
  local message="$1"
  local webhook="${BACKUP_DISCORD_WEBHOOK:-$DISCORD_WEBHOOK}"
  if [ -n "${webhook:-}" ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"content\":\"$message\"}" \
      "$webhook" > /dev/null 2>&1 || true
  fi
}

# Create directories
mkdir -p "$DAILY_DIR" "$HOURLY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR" "$WAL_DIR"

if [ "$BACKUP_TYPE" = "daily" ]; then
  FILENAME="uzhavu-${DATE}-daily.sql.gz"
  FILEPATH="$DAILY_DIR/$FILENAME"

  log "Starting daily backup..."
  START_TIME=$(date +%s)

  # Full pg_dump
  docker exec uzhavu-postgres pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=custom \
    --compress=9 \
    --verbose \
    2>> "$LOG_FILE" | gzip > "$FILEPATH"

  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))
  SIZE=$(du -h "$FILEPATH" | cut -f1)

  log "Daily backup complete: $FILENAME ($SIZE) in ${DURATION}s"

  # ── Rotation ───────────────────────────────────────

  # Copy to weekly (Sundays)
  if [ "$DAY_OF_WEEK" = "7" ]; then
    cp "$FILEPATH" "$WEEKLY_DIR/uzhavu-${DATE}-weekly.sql.gz"
    log "Weekly backup created"
  fi

  # Copy to monthly (1st of month)
  if [ "$DAY_OF_MONTH" = "01" ]; then
    cp "$FILEPATH" "$MONTHLY_DIR/uzhavu-${DATE}-monthly.sql.gz"
    log "Monthly backup created"
  fi

  # Rotate: keep 7 daily, 4 weekly, 12 monthly
  find "$DAILY_DIR" -name "*.sql.gz" -mtime +7 -delete 2>/dev/null
  find "$WEEKLY_DIR" -name "*.sql.gz" -mtime +28 -delete 2>/dev/null
  find "$MONTHLY_DIR" -name "*.sql.gz" -mtime +365 -delete 2>/dev/null

  log "Rotation complete"

  # ── Upload to S3 ───────────────────────────────────

  if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
    log "Uploading to S3..."
    rclone copy "$FILEPATH" "s3remote:${BACKUP_S3_BUCKET}/daily/" \
      --config /opt/uzhavu/rclone.conf \
      2>> "$LOG_FILE" || {
        log "ERROR: S3 upload failed!"
        notify "❌ Backup S3 upload failed: $FILENAME"
      }
    log "S3 upload complete"
  fi

  # ── Backup uploads directory ───────────────────────

  if [ -d "$UPLOADS_DIR" ]; then
    log "Syncing uploads directory..."
    if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
      rclone sync "$UPLOADS_DIR" "s3remote:${BACKUP_S3_BUCKET}/uploads/" \
        --config /opt/uzhavu/rclone.conf \
        2>> "$LOG_FILE" || log "WARNING: Uploads sync failed"
    fi
  fi

  notify "✅ Daily backup complete: $FILENAME ($SIZE) in ${DURATION}s"

elif [ "$BACKUP_TYPE" = "hourly" ]; then
  # Archive WAL files (incremental)
  FILENAME="wal-${DATETIME}.tar.gz"
  FILEPATH="$HOURLY_DIR/$FILENAME"

  if [ "$(ls -A $WAL_DIR 2>/dev/null)" ]; then
    tar -czf "$FILEPATH" -C "$WAL_DIR" . 2>> "$LOG_FILE"
    rm -f "$WAL_DIR"/* 2>/dev/null
    SIZE=$(du -h "$FILEPATH" | cut -f1)
    log "Hourly WAL backup: $FILENAME ($SIZE)"
  else
    log "No WAL files to archive"
  fi

  # Rotate hourly: keep 24 hours
  find "$HOURLY_DIR" -name "wal-*.tar.gz" -mmin +1440 -delete 2>/dev/null
fi
```

---

#### `scripts/restore.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# PostgreSQL Restore Script
# Usage: ./scripts/restore.sh <backup_file> [--target-db=<db_name>]
# Example: ./scripts/restore.sh /opt/uzhavu/backups/daily/uzhavu-2026-07-06-daily.sql.gz
# ============================================================

set -euo pipefail

BACKUP_FILE="${1:?Usage: restore.sh <backup_file> [--target-db=<db_name>]}"
TARGET_DB=""

# Parse optional arguments
for arg in "$@"; do
  case $arg in
    --target-db=*) TARGET_DB="${arg#*=}" ;;
  esac
done

source /opt/uzhavu/.env
TARGET_DB="${TARGET_DB:-$DB_NAME}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [RESTORE] $*"
}

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "═══════════════════════════════════════════"
echo "RESTORE DATABASE"
echo "  Backup: $BACKUP_FILE"
echo "  Target: $TARGET_DB"
echo "═══════════════════════════════════════════"
echo ""
echo "⚠️  WARNING: This will DROP and RECREATE the database '$TARGET_DB'!"
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

# Stop API and worker if restoring production DB
if [ "$TARGET_DB" = "$DB_NAME" ]; then
  log "Stopping API and worker..."
  cd /opt/uzhavu
  docker compose -f docker-compose.prod.yml stop api worker web ai-engine 2>/dev/null || true
fi

log "Dropping and recreating database '$TARGET_DB'..."
docker exec uzhavu-postgres psql -U "$DB_USER" -c "
  SELECT pg_terminate_backend(pg_stat_activity.pid)
  FROM pg_stat_activity
  WHERE pg_stat_activity.datname = '$TARGET_DB' AND pid <> pg_backend_pid();
" 2>/dev/null || true

docker exec uzhavu-postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS \"$TARGET_DB\";"
docker exec uzhavu-postgres psql -U "$DB_USER" -c "CREATE DATABASE \"$TARGET_DB\";"

log "Restoring from backup..."
START_TIME=$(date +%s)

if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" | docker exec -i uzhavu-postgres pg_restore \
    -U "$DB_USER" \
    -d "$TARGET_DB" \
    --no-owner \
    --no-privileges \
    --verbose 2>&1 | tail -5
else
  docker exec -i uzhavu-postgres pg_restore \
    -U "$DB_USER" \
    -d "$TARGET_DB" \
    --no-owner \
    --no-privileges \
    --verbose < "$BACKUP_FILE" 2>&1 | tail -5
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log "Restore complete in ${DURATION}s"

# Run migrations
if [ "$TARGET_DB" = "$DB_NAME" ]; then
  log "Running Prisma migrations..."
  docker compose -f docker-compose.prod.yml run --rm api npx prisma migrate deploy 2>&1 | tail -5

  # Verification
  log "Verifying restore..."
  ORGS=$(docker exec uzhavu-postgres psql -U "$DB_USER" -d "$TARGET_DB" -t -c "SELECT COUNT(*) FROM organizations;" 2>/dev/null | tr -d ' ')
  log "Organizations found: ${ORGS:-0}"

  log "Restarting services..."
  docker compose -f docker-compose.prod.yml up -d api worker web ai-engine
fi

log "✅ Restore complete"
```

---

#### `scripts/backup-verify.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# Monthly Backup Verification
# Crontab: 0 3 1 * * /opt/uzhavu/scripts/backup-verify.sh
# ============================================================

set -euo pipefail

source /opt/uzhavu/.env
VERIFY_DB="uzhavu_verify"
LOG_FILE="/var/log/uzhavu/backup-verify.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [VERIFY] $*" | tee -a "$LOG_FILE"
}

notify() {
  local message="$1"
  local webhook="${BACKUP_DISCORD_WEBHOOK:-$DISCORD_WEBHOOK}"
  if [ -n "${webhook:-}" ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"content\":\"$message\"}" \
      "$webhook" > /dev/null 2>&1 || true
  fi
}

# Find latest daily backup
LATEST_BACKUP=$(ls -t /opt/uzhavu/backups/daily/*.sql.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
  log "ERROR: No backup files found!"
  notify "❌ CRITICAL: Backup verification failed — no backup files found!"
  exit 1
fi

log "Verifying backup: $LATEST_BACKUP"
START_TIME=$(date +%s)

# Create temporary database
docker exec uzhavu-postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $VERIFY_DB;" 2>/dev/null
docker exec uzhavu-postgres psql -U "$DB_USER" -c "CREATE DATABASE $VERIFY_DB;"

# Restore to temp database
gunzip -c "$LATEST_BACKUP" | docker exec -i uzhavu-postgres pg_restore \
  -U "$DB_USER" \
  -d "$VERIFY_DB" \
  --no-owner \
  --no-privileges 2>> "$LOG_FILE"

RESTORE_STATUS=$?

if [ $RESTORE_STATUS -ne 0 ]; then
  log "ERROR: Restore failed with status $RESTORE_STATUS"
  notify "❌ CRITICAL: Backup verification FAILED — restore error!"
  docker exec uzhavu-postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $VERIFY_DB;" 2>/dev/null
  exit 1
fi

# Run verification queries
TABLES=$(docker exec uzhavu-postgres psql -U "$DB_USER" -d "$VERIFY_DB" -t -c \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')

ORGS=$(docker exec uzhavu-postgres psql -U "$DB_USER" -d "$VERIFY_DB" -t -c \
  "SELECT COUNT(*) FROM organizations;" 2>/dev/null | tr -d ' ' || echo "0")

USERS=$(docker exec uzhavu-postgres psql -U "$DB_USER" -d "$VERIFY_DB" -t -c \
  "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' ' || echo "0")

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Cleanup
docker exec uzhavu-postgres psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $VERIFY_DB;"

log "Verification PASSED:"
log "  Tables: $TABLES"
log "  Organizations: $ORGS"
log "  Users: $USERS"
log "  Restore duration: ${DURATION}s"

notify "✅ Monthly backup verification PASSED — $TABLES tables, $ORGS orgs, $USERS users — restore took ${DURATION}s"
```

---

### Monitoring Stack

#### `monitoring/docker-compose.monitoring.yml`

```yaml
# ============================================================
# Monitoring Stack — Prometheus + Grafana + Exporters
# Usage: docker compose -f monitoring/docker-compose.monitoring.yml up -d
# ============================================================

services:
  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: uzhavu-prometheus
    restart: unless-stopped
    ports:
      - "127.0.0.1:9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
      - '--storage.tsdb.retention.size=5GB'
      - '--web.enable-lifecycle'    # Enable config reload via API
    deploy:
      resources:
        limits:
          memory: 512M

  grafana:
    image: grafana/grafana:11.1.0
    container_name: uzhavu-grafana
    restart: unless-stopped
    ports:
      - "127.0.0.1:3100:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_SERVER_ROOT_URL: https://grafana.${PRIMARY_DOMAIN:-uzhavu.com}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    depends_on:
      - prometheus
    deploy:
      resources:
        limits:
          memory: 256M

  node-exporter:
    image: prom/node-exporter:v1.8.1
    container_name: uzhavu-node-exporter
    restart: unless-stopped
    ports:
      - "127.0.0.1:9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--path.rootfs=/rootfs'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    pid: host

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    container_name: uzhavu-pg-exporter
    restart: unless-stopped
    ports:
      - "127.0.0.1:9187:9187"
    environment:
      DATA_SOURCE_NAME: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}?sslmode=disable
    depends_on:
      - prometheus

  redis-exporter:
    image: oliver006/redis_exporter:v1.61.0
    container_name: uzhavu-redis-exporter
    restart: unless-stopped
    ports:
      - "127.0.0.1:9121:9121"
    environment:
      REDIS_ADDR: redis://redis:6379
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

---

#### `monitoring/prometheus/prometheus.yml`

```yaml
# ============================================================
# Prometheus Configuration
# ============================================================

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

rule_files:
  - alert-rules.yml

alerting:
  alertmanagers: []
  # TODO: Add Alertmanager when needed
  # For now, alerts are evaluated and exposed via Grafana

scrape_configs:
  # ── VPS Metrics ────────────────────────────────────
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'vps'

  # ── PostgreSQL ─────────────────────────────────────
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # ── Redis ──────────────────────────────────────────
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # ── NestJS API ─────────────────────────────────────
  - job_name: 'api'
    metrics_path: /metrics
    static_configs:
      - targets: ['api:3001']

  # ── FastAPI AI Engine ──────────────────────────────
  - job_name: 'ai-engine'
    metrics_path: /metrics
    static_configs:
      - targets: ['ai-engine:8000']

  # ── Caddy ─────────────────────────────────────────
  - job_name: 'caddy'
    static_configs:
      - targets: ['host.docker.internal:2019']
    # Caddy exposes metrics on admin port :2019/metrics

  # ── Prometheus Self ────────────────────────────────
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

---

#### `monitoring/prometheus/alert-rules.yml`

```yaml
# ============================================================
# Prometheus Alert Rules
# ============================================================

groups:
  - name: infrastructure
    interval: 30s
    rules:
      # ── Disk ───────────────────────────────────────
      - alert: HighDiskUsage
        expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100 > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Disk usage above 80%"
          description: "Disk usage is {{ $value | printf \"%.1f\" }}% on {{ $labels.instance }}"

      - alert: CriticalDiskUsage
        expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100 > 95
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL: Disk usage above 95%"
          description: "Disk usage is {{ $value | printf \"%.1f\" }}% — immediate action required"

      # ── CPU ────────────────────────────────────────
      - alert: HighCPU
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CPU usage above 90%"
          description: "CPU usage is {{ $value | printf \"%.1f\" }}% on {{ $labels.instance }}"

      # ── Memory ─────────────────────────────────────
      - alert: HighMemory
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage above 85%"
          description: "Memory usage is {{ $value | printf \"%.1f\" }}% on {{ $labels.instance }}"

  - name: application
    interval: 30s
    rules:
      # ── Service Up/Down ────────────────────────────
      - alert: APIDown
        expr: up{job="api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API service is DOWN"
          description: "NestJS API has been unreachable for 1 minute"

      - alert: AIEngineDown
        expr: up{job="ai-engine"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AI Engine is DOWN"
          description: "FastAPI AI engine has been unreachable for 1 minute"

      # ── Error Rate ─────────────────────────────────
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API error rate above 5%"
          description: "HTTP 5xx error rate is {{ $value | printf \"%.2f\" }} ({{ $value | printf \"%.0f\" }}%)"

      # ── Latency ────────────────────────────────────
      - alert: HighLatency
        expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="api"}[5m])) by (le)) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API p99 latency above 5 seconds"
          description: "p99 latency is {{ $value | printf \"%.2f\" }}s"

  - name: database
    interval: 30s
    rules:
      # ── PostgreSQL ─────────────────────────────────
      - alert: PostgreSQLDown
        expr: pg_up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL is DOWN"
          description: "PostgreSQL database server is unreachable"

      - alert: PostgreSQLHighConnections
        expr: pg_stat_activity_count / pg_settings_max_connections > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL connection usage above 80%"
          description: "{{ $value | printf \"%.0f\" }}% of max connections in use"

      - alert: PostgreSQLLowCacheHitRatio
        expr: pg_stat_database_blks_hit / (pg_stat_database_blks_hit + pg_stat_database_blks_read) < 0.99
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL cache hit ratio below 99%"
          description: "Cache hit ratio: {{ $value | printf \"%.4f\" }}"

      # ── Redis ──────────────────────────────────────
      - alert: RedisDown
        expr: redis_up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Redis is DOWN"
          description: "Redis server is unreachable"

  - name: backup
    interval: 60s
    rules:
      - alert: BackupOverdue
        expr: time() - backup_last_success_timestamp > 90000  # 25 hours
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Daily backup is overdue"
          description: "Last successful backup was more than 25 hours ago"

  - name: ssl
    interval: 3600s  # Check hourly
    rules:
      - alert: SSLCertExpiringSoon
        expr: ssl_cert_not_after - time() < 14 * 24 * 3600  # 14 days
        labels:
          severity: warning
        annotations:
          summary: "SSL certificate expiring within 14 days"
          description: "Certificate for {{ $labels.domain }} expires in {{ $value | humanizeDuration }}"
```

---

### SSL & Domain Management

#### `Caddyfile`

```caddyfile
# ============================================================
# Caddy Reverse Proxy Configuration
# Automatic HTTPS for all domains via Let's Encrypt
# ============================================================

{
    # Global options
    email admin@uzhavu.com
    acme_ca https://acme-v02.api.letsencrypt.org/directory

    # Admin API (for programmatic config changes)
    admin localhost:2019

    # Metrics endpoint for Prometheus
    servers {
        metrics
    }
}

# ── Primary Platform ─────────────────────────────────

app.uzhavu.com {
    reverse_proxy localhost:3000
    encode gzip zstd
    header {
        X-Frame-Options DENY
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }
}

api.uzhavu.com {
    reverse_proxy localhost:3001
    encode gzip zstd
    header {
        Access-Control-Allow-Origin *
        Access-Control-Allow-Methods "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Authorization, Content-Type, X-Api-Key, X-Product-Id"
    }
}

ai.uzhavu.com {
    reverse_proxy localhost:8000
    encode gzip zstd
}

# ── Staging ──────────────────────────────────────────

staging.uzhavu.com {
    reverse_proxy localhost:4000
}

staging-api.uzhavu.com {
    reverse_proxy localhost:4001
}

# ── Monitoring ───────────────────────────────────────

grafana.uzhavu.com {
    reverse_proxy localhost:3100
    basicauth {
        admin $2a$14$... # bcrypt hash — replace with actual
    }
}

# ── Standalone Products ──────────────────────────────
# Each product domain proxies to the same Next.js app
# The middleware detects the domain and applies product branding

invoicesimple.in, www.invoicesimple.in {
    reverse_proxy localhost:3000
    encode gzip zstd
    header {
        X-Frame-Options DENY
        X-Content-Type-Options nosniff
        Strict-Transport-Security "max-age=31536000"
    }
}

farmbook.in, www.farmbook.in {
    reverse_proxy localhost:3000
    encode gzip zstd
}

gymtrack.in, www.gymtrack.in {
    reverse_proxy localhost:3000
    encode gzip zstd
}

# ── Wildcard for dynamic subdomains ──────────────────
# Requires DNS-01 challenge (Cloudflare DNS plugin)
# *.uzhavu.com {
#     tls {
#         dns cloudflare {env.CLOUDFLARE_API_TOKEN}
#     }
#     reverse_proxy localhost:3000
# }

# ── Import block for dynamic domains ─────────────────
# Managed domains are stored in /etc/caddy/domains/*.caddy
# and imported here for auto-SSL
import /etc/caddy/domains/*.caddy
```

---

#### `scripts/add-domain.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# Add a custom domain to Caddy configuration
# Usage: ./scripts/add-domain.sh <domain> [product_id]
# Example: ./scripts/add-domain.sh myapp.com invoice-simple
# ============================================================

set -euo pipefail

DOMAIN="${1:?Usage: add-domain.sh <domain> [product_id]}"
PRODUCT_ID="${2:-}"
DOMAINS_DIR="/etc/caddy/domains"

mkdir -p "$DOMAINS_DIR"

# Generate Caddy config for this domain
cat > "$DOMAINS_DIR/${DOMAIN}.caddy" <<EOF
${DOMAIN}, www.${DOMAIN} {
    reverse_proxy localhost:3000
    encode gzip zstd
    header {
        X-Frame-Options DENY
        X-Content-Type-Options nosniff
        Strict-Transport-Security "max-age=31536000"
    }
}
EOF

echo "Domain config created: $DOMAINS_DIR/${DOMAIN}.caddy"

# Reload Caddy to pick up new domain
echo "Reloading Caddy..."
caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || \
  docker exec uzhavu-caddy caddy reload --config /etc/caddy/Caddyfile

echo "✅ Domain $DOMAIN added and SSL will be provisioned automatically"
echo "Ensure DNS is pointing to this server: $(curl -s ifconfig.me)"
```

---

#### `scripts/verify-domain.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# Verify domain ownership via DNS TXT record
# Usage: ./scripts/verify-domain.sh <domain> <expected_value>
# Example: ./scripts/verify-domain.sh myapp.com uzv_verify_abc123
# ============================================================

set -euo pipefail

DOMAIN="${1:?Usage: verify-domain.sh <domain> <expected_value>}"
EXPECTED="${2:?Usage: verify-domain.sh <domain> <expected_value>}"
TXT_HOST="_uzhavu-verify.${DOMAIN}"

echo "Checking DNS TXT record: $TXT_HOST"

# Query DNS
RESULT=$(dig +short TXT "$TXT_HOST" 2>/dev/null | tr -d '"' | head -1)

if [ -z "$RESULT" ]; then
  echo "❌ No TXT record found for $TXT_HOST"
  echo "   Please add: TXT _uzhavu-verify.${DOMAIN} → ${EXPECTED}"
  echo "   DNS may take up to 48 hours to propagate."
  exit 1
fi

if [ "$RESULT" = "$EXPECTED" ]; then
  echo "✅ Domain verified: $DOMAIN"
  exit 0
else
  echo "❌ TXT record value mismatch"
  echo "   Expected: $EXPECTED"
  echo "   Got:      $RESULT"
  exit 1
fi
```

---

## SQL Schemas (Domain Management)

```sql
-- ============================================================
-- Domain Configurations (managed domains for SSL/routing)
-- ============================================================
CREATE TABLE domain_configs (
  id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  domain              TEXT NOT NULL UNIQUE,             -- 'invoicesimple.in'
  product_id          TEXT,                              -- FK to SaasProduct
  domain_type         TEXT NOT NULL DEFAULT 'custom',   -- 'primary', 'alias', 'custom', 'subdomain'
  verification_status TEXT NOT NULL DEFAULT 'pending',  -- pending|verified|failed
  verification_token  TEXT NOT NULL,                    -- uzv_verify_abc123
  verified_at         TIMESTAMPTZ,
  ssl_status          TEXT NOT NULL DEFAULT 'pending',  -- pending|active|failed|expired
  ssl_issued_at       TIMESTAMPTZ,
  ssl_expires_at      TIMESTAMPTZ,
  caddy_config_path   TEXT,                              -- /etc/caddy/domains/domain.caddy
  dns_target          TEXT,                              -- Expected CNAME target
  last_checked_at     TIMESTAMPTZ,
  is_active           BOOLEAN NOT NULL DEFAULT true,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dc_domain ON domain_configs(domain);
CREATE INDEX idx_dc_product ON domain_configs(product_id) WHERE product_id IS NOT NULL;
CREATE INDEX idx_dc_ssl ON domain_configs(ssl_status) WHERE ssl_status != 'active';

-- ============================================================
-- Backup Logs (tracking backup success/failure)
-- ============================================================
CREATE TABLE backup_logs (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  backup_type     TEXT NOT NULL,                    -- 'daily', 'hourly', 'weekly', 'monthly'
  file_name       TEXT NOT NULL,
  file_size_bytes BIGINT,
  file_path       TEXT NOT NULL,
  remote_path     TEXT,                              -- S3 path if uploaded
  status          TEXT NOT NULL DEFAULT 'success',  -- success|failed
  duration_secs   INT,
  tables_count    INT,
  rows_count      BIGINT,
  error_message   TEXT,
  verified_at     TIMESTAMPTZ,                       -- Last verification date
  verification_status TEXT,                          -- passed|failed
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bl_type ON backup_logs(backup_type, created_at DESC);
CREATE INDEX idx_bl_status ON backup_logs(status) WHERE status = 'failed';
```

---

## API Endpoints (Domain Management)

### Add Domain

```
POST /api/admin/domains
Authorization: Bearer <admin_token>
```

**Request:**
```json
{
  "domain": "invoicesimple.in",
  "productId": "invoice-simple",
  "domainType": "custom"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "dom_001",
    "domain": "invoicesimple.in",
    "verificationStatus": "pending",
    "verificationToken": "uzv_verify_a1b2c3d4e5f6",
    "dnsInstructions": {
      "type": "CNAME",
      "host": "invoicesimple.in",
      "target": "vps.uzhavu.com",
      "txtRecord": {
        "host": "_uzhavu-verify.invoicesimple.in",
        "value": "uzv_verify_a1b2c3d4e5f6"
      }
    },
    "sslStatus": "pending"
  }
}
```

### Verify Domain

```
POST /api/admin/domains/:id/verify
Authorization: Bearer <admin_token>
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "domain": "invoicesimple.in",
    "verificationStatus": "verified",
    "verifiedAt": "2026-07-06T00:30:00Z",
    "sslStatus": "active",
    "sslIssuedAt": "2026-07-06T00:30:15Z",
    "sslExpiresAt": "2026-10-04T00:30:15Z"
  }
}
```

### List Domains

```
GET /api/admin/domains
Authorization: Bearer <admin_token>
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "dom_001",
      "domain": "app.uzhavu.com",
      "productId": "uzhavu",
      "domainType": "primary",
      "verificationStatus": "verified",
      "sslStatus": "active",
      "sslExpiresAt": "2026-10-04T00:00:00Z",
      "isActive": true
    },
    {
      "id": "dom_002",
      "domain": "invoicesimple.in",
      "productId": "invoice-simple",
      "domainType": "custom",
      "verificationStatus": "verified",
      "sslStatus": "active",
      "sslExpiresAt": "2026-10-04T00:30:15Z",
      "isActive": true
    }
  ]
}
```

### Remove Domain

```
DELETE /api/admin/domains/:id
Authorization: Bearer <admin_token>
```

**Response (200):**
```json
{
  "success": true,
  "message": "Domain invoicesimple.in removed. SSL certificate revoked."
}
```

---

## Deployment Flow Diagrams

### CI/CD Pipeline Flow

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant GH as GitHub
    participant GA as GitHub Actions
    participant VPS as VPS Server
    participant DC as Discord

    Dev->>GH: git push main (apps/api/*)
    GH->>GA: Trigger deploy-api.yml
    GA->>DC: 🚀 "Deploying API..."

    GA->>GA: Install dependencies
    GA->>GA: Run lint (ESLint)
    GA->>GA: Run type-check
    GA->>GA: Run tests

    alt Tests pass
        GA->>GA: Build Docker image
        GA->>VPS: SCP image.tar.gz
        GA->>VPS: SSH: load image + deploy.sh

        VPS->>VPS: Tag current → previous
        VPS->>VPS: Tag new → current
        VPS->>VPS: Run Prisma migrations
        VPS->>VPS: Restart API container
        VPS->>VPS: Health check (60s timeout)

        alt Health check passes
            VPS-->>GA: Deploy success
            GA->>DC: ✅ "API deployed successfully"
        else Health check fails
            VPS->>VPS: Rollback: tag previous → current
            VPS->>VPS: Restart with previous image
            VPS-->>GA: Deploy failed (rolled back)
            GA->>DC: ⚠️ "API rolled back to previous version"
        end

    else Tests fail
        GA->>DC: ❌ "API deploy failed — tests failed"
    end
```

### Backup & Restore Flow

```mermaid
sequenceDiagram
    participant Cron as Cron Job
    participant Script as backup.sh
    participant PG as PostgreSQL
    participant Disk as Local Disk
    participant S3 as S3/NAS
    participant DC as Discord

    Note over Cron: Daily at midnight UTC
    Cron->>Script: Run daily backup

    Script->>PG: pg_dump --format=custom --compress=9
    PG-->>Script: Database dump
    Script->>Disk: Save to /backups/daily/

    alt Sunday
        Script->>Disk: Copy to /backups/weekly/
    end

    alt 1st of month
        Script->>Disk: Copy to /backups/monthly/
    end

    Script->>Script: Rotate: delete daily>7, weekly>28, monthly>365

    alt S3 configured
        Script->>S3: rclone copy to S3 bucket
    end

    Script->>Disk: rsync uploads/ to S3/NAS
    Script->>DC: ✅ "Backup complete: X MB in Ys"

    Note over Cron: Monthly verification (1st, 3am)
    Cron->>Script: Run backup-verify.sh
    Script->>Disk: Get latest daily backup
    Script->>PG: Restore to uzhavu_verify DB
    Script->>PG: Run verification queries
    Script->>PG: DROP uzhavu_verify
    Script->>DC: ✅ "Backup verified: X tables, Y rows"
```

---

## Error Handling & Edge Cases

| Scenario | Handling |
|:---------|:---------|
| Deploy health check fails | Auto-rollback to `previous` image; notify Discord; exit with error |
| No `previous` image for rollback | Log critical error; notify Discord; leave service down for manual fix |
| Docker build OOM during CI | Set `--memory` limit on build; retry once; fail with clear error |
| GitHub Actions SSH timeout | Set 10-minute timeout; retry once; notify on failure |
| Concurrent deploys to same service | Use GitHub Actions `concurrency` group; cancel in-progress |
| pg_dump fails (disk full) | Check disk space before backup; alert if < 5GB free; abort backup |
| Backup S3 upload fails | Log warning; retain local copy; retry on next run; alert after 2 failures |
| Backup restore fails | Show error; don't drop production DB until restore verified; manual intervention |
| Prometheus scrape target unreachable | Alert "target down" after 1 minute; don't remove from config |
| Grafana data source connection lost | Auto-retry every 30s; show "No Data" on dashboards |
| SSL cert provisioning fails (rate limit) | Log warning; retry in 1 hour; Let's Encrypt allows 50 certs/week |
| Custom domain DNS not propagated | Show "DNS pending" status; retry verification every hour for 48 hours |
| Domain verification TXT record wrong | Show mismatch details; allow retry; don't provision SSL until verified |
| Caddy reload fails (bad config) | Caddy validates before reload; reject invalid configs; keep previous config |
| Wildcard SSL requires DNS challenge | Document Cloudflare DNS plugin setup; fall back to per-domain certs |
| Docker volume corruption | Use named volumes with regular backup; document recovery procedure |
| Redis OOM | Configure `maxmemory-policy allkeys-lru`; monitor memory usage; alert at 80% |
| PostgreSQL max_connections reached | Alert at 80%; configure PgBouncer as connection pooler for production |
| VPS reboots unexpectedly | All services have `restart: unless-stopped`; Caddy auto-starts via systemd |

---

## NestJS Module Structure (Domain Management)

```
apps/api/src/modules/domains/
├── domains.module.ts
├── domains.controller.ts           # Admin REST endpoints
├── domains.service.ts              # Domain CRUD + verification logic
├── domains.caddy.service.ts        # Generate Caddy config + reload
├── domains.dns.service.ts          # DNS verification (TXT record lookup)
├── domains.cron.service.ts         # Periodic verification + SSL checks
├── dto/
│   ├── create-domain.dto.ts
│   └── verify-domain.dto.ts
└── domains.service.spec.ts
```

---

# Tasks

## Phase 1: Docker Compose Setup (~2 days)

- [ ] Create `docker/Dockerfile.api` — multi-stage build with dev and prod targets (~2h)
- [ ] Create `docker/Dockerfile.web` — multi-stage build with standalone Next.js output (~2h)
- [ ] Create `docker/Dockerfile.ai-engine` — FastAPI with uv for fast pip installs (~1h)
- [ ] Create `docker-compose.dev.yml` — all 6 services with hot reload, volume mounts, health checks (~3h)
- [ ] Create `docker-compose.prod.yml` — production-optimized with resource limits, restart policies, logging config (~3h)
- [ ] Create `.env.example` with all variables documented (~1h)
- [ ] Create `.dockerignore` files for each app (~0.5h)
- [ ] Test full dev environment: `docker compose -f docker-compose.dev.yml up` — verify all services start, hot reload works, ports accessible (~2h)
- [ ] Test prod build: build all images, verify sizes are reasonable (<500MB each) (~1h)

## Phase 2: CI/CD Pipeline (~3 days)

- [ ] Create `.github/workflows/deploy-api.yml` — lint → test → build → deploy with Discord notifications (~3h)
- [ ] Create `.github/workflows/deploy-web.yml` — same pattern, path-filtered to `apps/web/**` (~2h)
- [ ] Create `.github/workflows/deploy-ai-engine.yml` — Python lint (ruff) → test (pytest) → deploy (~2h)
- [ ] Create `.github/workflows/deploy-worker.yml` — reuses API image, separate deploy (~1h)
- [ ] Create `scripts/deploy.sh` — deploy with health check, rollback, and Discord notification (~3h)
- [ ] Create `scripts/rollback.sh` — manual rollback script (~1h)
- [ ] Set up GitHub repository secrets: VPS_HOST, VPS_USER, VPS_SSH_KEY, DISCORD_WEBHOOK (~1h)
- [ ] Set up GitHub environments: `staging` and `production` with protection rules (~1h)
- [ ] Test full pipeline: push to staging → verify deploy → merge to main → verify production deploy (~3h)
- [ ] Create `.github/workflows/lint-only.yml` — runs on PRs, no deploy (~1h)
- [ ] Set up SSH key pair for GitHub Actions → VPS deployment (~1h)

## Phase 3: SSL & Domain Management (~2 days)

- [ ] Install and configure Caddy on VPS as systemd service (~1h)
- [ ] Create `Caddyfile` with all current domains, security headers, gzip encoding (~2h)
- [ ] Create Prisma schema for `domain_configs` table (~1h)
- [ ] Implement `DomainsService` — CRUD with verification token generation (~2h)
- [ ] Implement `DomainsCaddyService` — generate per-domain Caddy configs, reload via API (~2h)
- [ ] Implement `DomainsDnsService` — DNS TXT record verification via `dig` or DNS library (~2h)
- [ ] Implement `DomainsController` — REST endpoints for domain management (~1.5h)
- [ ] Create `scripts/add-domain.sh` and `scripts/verify-domain.sh` (~1h)
- [ ] Implement `DomainsCronService` — periodic SSL expiry check, auto-renew verification (~1.5h)
- [ ] Test end-to-end: add domain → verify DNS → SSL provisioned → domain serves content (~2h)

## Phase 4: Backup Strategy (~2 days)

- [ ] Create `scripts/backup.sh` — full pg_dump with rotation (7 daily, 4 weekly, 12 monthly) (~3h)
- [ ] Create `scripts/restore.sh` — interactive restore with safety checks (~2h)
- [ ] Create `scripts/backup-verify.sh` — monthly verification via temp database restore (~2h)
- [ ] Set up rclone configuration for S3-compatible backup storage (~1h)
- [ ] Create Prisma schema for `backup_logs` table (~0.5h)
- [ ] Add backup logging — write success/failure records to `backup_logs` after each run (~1h)
- [ ] Configure crontab: daily full at midnight, hourly WAL, monthly verify on 1st (~1h)
- [ ] Configure PostgreSQL WAL archiving in `docker-compose.prod.yml` (~1h)
- [ ] Test full cycle: create backup → corrupt data → restore → verify data integrity (~2h)
- [ ] Create backup Prometheus metric (custom exporter or pushgateway) for `backup_last_success_timestamp` (~1.5h)

## Phase 5: Monitoring Stack (~3 days)

- [ ] Create `monitoring/docker-compose.monitoring.yml` — Prometheus, Grafana, Node Exporter, PG Exporter, Redis Exporter (~2h)
- [ ] Create `monitoring/prometheus/prometheus.yml` — scrape configs for all services (~1h)
- [ ] Create `monitoring/prometheus/alert-rules.yml` — all alert rules (infra, app, DB, backup, SSL) (~2h)
- [ ] Add Prometheus metrics instrumentation to NestJS API (`prom-client` or `nestjs-prometheus`) (~3h)
- [ ] Add Prometheus metrics instrumentation to FastAPI AI engine (`prometheus-fastapi-instrumentator`) (~1.5h)
- [ ] Create Grafana provisioning configs — auto-configure Prometheus data source (~1h)
- [ ] Create "VPS Overview" Grafana dashboard — CPU, RAM, disk, network gauges (~2h)
- [ ] Create "API Health" Grafana dashboard — request rate, latency percentiles, error rate, top endpoints (~3h)
- [ ] Create "PostgreSQL" Grafana dashboard — connections, queries/sec, cache hit ratio, table sizes (~2h)
- [ ] Create "AI Engine Costs" Grafana dashboard — AI calls, tokens, estimated cost, model breakdown (~2h)
- [ ] Set up Grafana alerting — Discord/Slack notification channel for all alerts (~1h)
- [ ] Integrate with existing status page module — API endpoint to create incidents from alerts (~2h)
- [ ] Configure Caddy to expose metrics endpoint for Prometheus scraping (~0.5h)

## Phase 6: Integration Testing & Hardening (~2 days)

- [ ] End-to-end test: git push → CI/CD → deploy → health check → rollback scenario (~3h)
- [ ] End-to-end test: backup → restore → verify — across dev and prod environments (~2h)
- [ ] End-to-end test: add custom domain → verify DNS → SSL provisioned → product serves correctly (~2h)
- [ ] Load test: verify monitoring catches high CPU/memory during load (~1h)
- [ ] Verify all alert rules fire correctly — simulate failures for each alert (~2h)
- [ ] Document runbooks: deploy, rollback, restore, domain add, monitoring troubleshooting (~3h)
- [ ] Security audit: verify all admin ports are localhost-only, SSH keys are secure, secrets are encrypted (~2h)
- [ ] Create `DEPLOYMENT.md` — comprehensive deployment guide for the VPS (~2h)

---

**Total Estimated Effort: ~14 days (1 developer)**

**Priority Order**: Phase 1 → Phase 2 → Phase 4 → Phase 3 → Phase 5 → Phase 6

Docker Compose is the foundation — everything else depends on it. CI/CD is next for automated deployments. Backups are prioritized over monitoring because data loss is worse than temporary lack of observability. SSL/domains enable the product factory. Monitoring is last because the platform can run without it (but shouldn't for long).

---

*Generated: 06 Jul 2026*
*For: uzhavu.race monorepo*
*Architecture ref: APP_ARCHITECTURE.md, product-factory-implementation.md*
