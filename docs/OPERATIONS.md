# Operations Runbook — The Lifeline (F0)

> Backups and restore drills for Life Graph. Strategy: `docs/design/07_strategic_direction_2026-07.md` §D7.1 —
> *"Data loss is not an incident; it is the death of the product thesis."*

## What Runs Automatically (production stack)

The `backup` sidecar service in `docker-compose.production.yml` runs:

| Job | Schedule | Script | Audit trail |
|-----|----------|--------|-------------|
| Nightly backup | 02:00 UTC daily | `scripts/backup.sh` | `job_runs` row, `job_name='backup'` |
| Restore drill | Sunday 06:00 UTC | `scripts/verify_restore.sh` | `job_runs` row, `job_name='restore_drill'` |

The sidecar reuses the postgres image (`Dockerfile.postgres`) so `pg_dump`/`pg_restore`
always match the server version (PG16). Dumps land in the `backup_data` volume
(`/backups` inside the container), retained `BACKUP_RETENTION_DAYS` days (default 30).

### What the restore drill verifies

1. Latest dump restores into a scratch database (`life_graph_verify`) on the same server.
2. Row counts for `memories`, `sessions`, `capture_events`, `decisions`, `predictions`,
   `agent_tasks` — restored `memories` count must be ≥ 90% of live (`MIN_ROW_RATIO`).
3. Embedding sample: restored DB must contain non-null embeddings with the right dimensions.
4. Warns if the latest dump is older than 48h (nightly backup broken).
5. Scratch database is dropped afterwards; outcome recorded in `job_runs`.

**Untested backups don't count.** A `restore_drill` failure means your backups may be garbage — treat it as a P0.

## Off-Site (encrypted) Backups

Set in `.env.production`:

```bash
RESTIC_REPOSITORY=sftp:user@backup-host:/srv/restic-life-graph   # or s3:, b2:, rest:
RESTIC_PASSWORD=<strong-passphrase>
```

When set (and `restic` is installed in the image/host), `backup.sh` pushes the dump
directory off-site after each nightly run with retention 7 daily / 4 weekly / 6 monthly.
To include MinIO object data, set `MINIO_DATA_DIR` to a mounted copy of the MinIO volume.

> `restic` is not bundled in `Dockerfile.postgres` by default. Either add
> `apt-get install restic` there, or run restic from the host against the
> `backup_data` volume mount point.

## Manual Operations

```bash
# One-off backup now
docker compose -f docker-compose.production.yml exec backup bash /scripts/backup.sh

# Run the restore drill now
docker compose -f docker-compose.production.yml exec backup bash /scripts/verify_restore.sh

# List backups
docker compose -f docker-compose.production.yml exec backup ls -lh /backups

# Check backup/drill history
docker compose -f docker-compose.production.yml exec postgres \
  psql -U life_graph -c "SELECT job_name, status, started_at, result FROM job_runs \
  WHERE job_name IN ('backup','restore_drill') ORDER BY started_at DESC LIMIT 14;"
```

## Disaster Recovery

```bash
# 1. Provision the stack (postgres up, app down)
docker compose -f docker-compose.production.yml up -d postgres

# 2. Restore the latest dump (interactive confirmation)
docker compose -f docker-compose.production.yml run --rm backup \
  bash /scripts/restore.sh /backups/life_graph_<TIMESTAMP>.dump

# 3. If restoring from off-site: restic restore latest --target /restore first

# 4. Bring the rest up and smoke-test
docker compose -f docker-compose.production.yml up -d
curl -fsS http://localhost/health
```

## Monitoring Checklist (weekly)

- [ ] `job_runs` shows a `backup` success for every night this week
- [ ] `job_runs` shows a `restore_drill` success for Sunday
- [ ] Off-site repo (`restic snapshots`) grew this week
- [ ] Backup volume disk usage under control (`ls -lh /backups`)
