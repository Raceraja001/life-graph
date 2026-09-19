# Operations Runbook — The Lifeline (F0)

> Backups and restore drills for Life Graph. Strategy: `docs/design/07_strategic_direction_2026-07.md` §D7.1 —
> *"Data loss is not an incident; it is the death of the product thesis."*

## What Runs Automatically (production stack)

The `backup` sidecar service in `docker-compose.production.yml` runs:

| Job | Schedule | Script | Audit trail |
|-----|----------|--------|-------------|
| Nightly backup | 02:00 UTC daily | `scripts/backup.sh` | `job_runs` row, `job_name='backup'` |
| Restore drill | Sunday 06:00 UTC | `scripts/verify_restore.sh` | `job_runs` row, `job_name='restore_drill'` |
| Backup retry | every 15 min after a failure (`BACKUP_RETRY_MINUTES`) | `scripts/backup.sh` | `job_name='backup'` |
| Off-site catch-up | hourly while `.offsite_pending` exists (`OFFSITE_RETRY_MINUTES`) | `scripts/backup.sh --offsite-only` | `job_name='backup_offsite'` |

Every run first waits for the database (`pg_isready`, up to `DB_WAIT_SECONDS`, default 600).
Docker's restart policy starts the sidecar at boot independently of compose's
`depends_on`, so without this wait the backup at container start ran before Postgres
was up — or before the compose network resolved its hostname — and was lost. A backup
at container start that falls inside `BACKUP_HOUR` counts as that day's backup.

Dumps and MinIO archives are written as `*.partial` and renamed only on success, so a
failed run leaves no empty file behind; the restore drill also verifies the newest
*non-empty* dump.

The sidecar reuses the postgres image (`Dockerfile.postgres`) so `pg_dump`/`pg_restore`
always match the server version (PG16). Dumps land in the `backup_data` volume
(`/backups` inside the container), retained `BACKUP_RETENTION_DAYS` days (default 30).

When `MINIO_DATA_DIR` points at a mount of the MinIO volume, each run also writes
`minio_<timestamp>.tar.gz` next to the dump, with the same retention. Mount the volume
read-only into the sidecar (e.g. `minio_data:/minio-data:ro`). Without it, uploaded
originals (voice notes, images, documents) have no backup — only the memories
extracted from them do.

### What the restore drill verifies

1. Latest dump restores into a scratch database (`life_graph_verify`) on the same server.
2. Row counts for `memories`, `sessions`, `capture_events`, `decisions`, `predictions`,
   `agent_tasks` — restored `memories` count must be ≥ 90% of live (`MIN_ROW_RATIO`).
   Each table is looked up in whichever schema holds it (`public` or `life_graph`);
   the drill log and `job_runs` result name tables schema-qualified.
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
With `MINIO_DATA_DIR` set, restic backs up the raw MinIO directory (which deduplicates
between runs) and skips the local `minio_*.tar.gz`, which would re-upload in full nightly.

The off-site step is **best-effort**: the local dump has already succeeded, so an
unreachable repository is recorded in `job_runs` (`offsite: false`, `offsite_error`)
instead of failing the job. `backup.sh` probes the repository first
(`RESTIC_PROBE_TIMEOUT`, default 60s), because restic otherwise retries an offline
backend for about 15 minutes. Check for a run of `offsite: false` in the weekly review.

| Variable | Purpose |
|---|---|
| `RESTIC_REPOSITORY_FILE` | Read the repository URL from a file, keeping credentials embedded in a `rest:` URL out of compose files and `docker inspect` |
| `RESTIC_PASSWORD_FILE` | Same, for the encryption password (restic native) |
| `RESTIC_FORGET=0` | Skip forget/prune — required for an append-only repository |
| `RESTIC_PROBE_TIMEOUT` | Seconds to wait for the repository before skipping (default 60) |

**Append-only target (recommended for a second machine you own):** run
[`rest-server`](https://github.com/restic/rest-server) there with `--append-only`, bound
to a private address (e.g. its Tailscale IP), with a bcrypt `.htpasswd` entry —
rest-server 0.14 rejects `$6$` SHA-512 hashes. The backup host can then add snapshots
but never delete them, so a compromised backup host cannot erase history. Pruning must
run on the repository host itself (e.g. a weekly `restic forget ... --prune` timer),
and the backup side sets `RESTIC_FORGET=0`.

**Keep the encryption password somewhere other than the backed-up machine.** If that
machine is lost, a password stored only on it makes every off-site snapshot unreadable.

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

## Connectors: Calendar, Email, Contacts, GitHub

Read-only; set up in the dashboard under **Settings → Connected accounts**
(specs: `docs/specs/connectors.md`, `docs/specs/connector-contacts.md`,
`docs/specs/connector-github.md`). Each
account picks its method; the form suggests one.

| Method | Setup | Notes |
|---|---|---|
| App password (mail) | Google Account → Security → 2-Step Verification → App passwords | Missing page = the Workspace admin disabled it |
| Calendar link | Google Calendar → Settings → the calendar → *Secret address in iCal format* | The link is a credential; Google refreshes it with a lag |
| Google sign-in (OAuth) | Once: Google Cloud project, enable Gmail, Calendar and **People** APIs, OAuth client type **Desktop app**, paste its JSON in the form | Read-only scopes; sign in from the machine running the API (loopback redirect). Contacts without the People API enabled fail with a message saying so |
| vCard file (contacts) | contacts.google.com → Export → vCard, then **Import vCard** on the account | No credential. Import a newer export to update; each import replaces that account's contacts |
| Access token (GitHub) | github.com → Settings → Developer settings → **Fine-grained tokens**: all repositories; read-only Pull requests, Issues, Commit statuses, Checks | One per GitHub account or organisation. A classic token that can write is refused. Expiry → **Reconnect needed** |

- Contacts: saved contacts and Google's "Other contacts" (addresses kept from
  mail), synced every 6 h. **Cloud visibility** on each contacts account picks
  which fields cloud chat may see (default: names, company and title, email
  addresses, birthdays; phones, postal addresses and notes are off). Contacts are
  not time-limited: they mirror the source.
- GitHub: review requests, your open PRs (CI, review decision, conflicts) and
  assigned issues, every 15 min; titles and status only. Private repos are counts
  for cloud chat unless the account shares private titles.
- Bills & renewals: read from mail by the local summariser (card statements,
  utilities, broadband, insurance, domains). Brief section and Today card; a
  payment-confirmation email closes its bill. Amounts never leave the machine;
  `LIFE_GRAPH_CONNECTOR_BILLS_CLOUD=counts` reduces the rest to counts. Older mail:
  Settings → the mail account → **Find bills in past mail** (60 days, local model).

- Credentials: `~/.config/life-graph/connectors/<tenant>/<account-id>.json` (0600).
  They are **not** in the database backups — keep your passwords in a password
  manager; reconnecting is two minutes.
- Sync: every 15 min per account (worker job `sync_connectors`, runs every 5 min);
  failures back off up to 6 h; a refused credential sets **Reconnect needed** and
  stops retrying. Retention: mail 90 days, events −90/+365 days (nightly purge).
- What the cloud sees: see the exposure table in the spec. Mark employer or other
  sensitive accounts **Local only** (Settings) — cloud chat and Telegram/push then
  get counts only.
- Checks: `GET /api/v1/connectors` (status, last error, item counts per account).

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
