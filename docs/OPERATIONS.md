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

# 2. Restore the latest dump (interactive confirmation)
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

- [ ] `job_runs` shows a `backup` success for every night this week
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

In case of abnormal browser agent activity or compromise:

### 1. Instant Revocation of All Pending Capabilities

To immediately cancel all unspent capabilities across all tenants:
```bash
docker compose -f docker-compose.production.yml exec postgres \
  psql -U life_graph -c "UPDATE authorization_capabilities SET revoked_at = NOW() WHERE spent_at IS NULL;"
```

To revoke capabilities for a specific tenant:
```bash
docker compose -f docker-compose.production.yml exec postgres \
  psql -U life_graph -c "UPDATE authorization_capabilities SET revoked_at = NOW() WHERE tenant_id = '<tenant_id>' AND spent_at IS NULL;"
```

### 2. Autonomous Browser Shutdown

To instantly halt all running browser errands and kill the browser driver:
```bash
# Stop the sandbox browser container
docker compose -f compose.sandbox.yaml stop browser

# Alternatively, stop the egress proxy container (all web requests immediately drop)
docker compose -f compose.sandbox.yaml stop egress
```

### 3. Application-Level Kill Switch

Set in `.env.production` or runtime environment:
```bash
LIFE_GRAPH_BROWSER_ENABLED=false
```
Then restart the API and workers (`./dev.sh restart`). When disabled, all browser errand requests are rejected fail-closed with `BrowserDisabledError`.

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
| `local` | in the API process | `run_command`: `TOOL_SHELL_MODE=allowlist` (read-only programs) | `shell_allowlist.child_env()` |
| verifiers | `VERIFIER_SANDBOX=docker`: `--network none` container. `=none`: code-executing checks are **inconclusive** unless `VERIFIER_ALLOW_HOST_EXECUTION=true` | — | — |

### Enable the task runtime

```bash
docker build -t life-graph-sandbox-egress:dev -f Dockerfile.egress .   # the proxy
bash docker/claude-driver/build.sh                                       # life-graph-claude-driver:latest
docker build -t life-graph-verifier:py3.12 docker/verifier              # verifier (and -node/-jvm if used)
# .env
LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX=task
LIFE_GRAPH_VERIFIER_SANDBOX=docker
```

Restart the API. Check it with `python scripts/runtime_security_probe.py --image
life-graph-claude-driver:latest`: it should report no host paths, no LIFE_GRAPH_* variables,
unreachable direct network, and 403 from the proxy for unlisted hosts. A missing image makes
dispatches fail with `exit_status=sandbox_unavailable`. They never fall back to the host.

### Inspect and clean up

- Running runtimes: `docker ps --filter label=life-graph.runtime=1`. The task id is in the
  `life-graph.runtime.task` label, and the run's metadata is in `task.result.metadata.runtime`.
- Leftovers from a crash are removed at the next API start (`dev_task_runtime_sweep`
  startup step, runner-lock holder only). By hand:
  `docker rm -f $(docker ps -aq --filter label=life-graph.runtime=1)`, plus `docker network
  prune --filter label=life-graph.runtime=1`. Never remove the shared `lg-rt-outbound`
  network while a task is running.

### Rollback

Set `LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX=docker` (previous container behaviour) and restart.
There is no schema change.
