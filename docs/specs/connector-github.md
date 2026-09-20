# GitHub Connector — Feature Spec

> **Status: Built (2026-09-19).** Plugin `plugins/github/`, migration 041, auth
> method `token`, brief section **Code**, Overview → Today *Code* block, tool
> `code_inbox`, GitHub questions in jarvis's chat context, Settings → *Connected
> accounts*. Verified end to end on a copy of the live DB against a fake GitHub;
> unit tests in `tests/unit/test_connector_github.py`. Approved as proposed:
> private repo titles are counts only for cloud models by default (switchable
> per account); @mentions are not included.
>
> **Where the build differs from the text below:**
> - The read-only check runs on **every** request, not only when the token is
>   added: a token that starts reporting write scopes stops syncing.
> - A code item's flags are replaced on each sync, so a cleared CI state or
>   review decision does not linger.
> - PRs with a merge conflict are ranked after failing CI ("merge conflict").
> - The login GitHub reports becomes the account's `username` in Settings.
>
> **Purpose**: Show what is waiting on the user in code, next to mail and the
> calendar:
> - pull requests where their review is requested;
> - their own open pull requests: CI failing, changes requested, or approved and
>   ready to merge;
> - issues assigned to them.
>
> It goes into the daily brief, the Today card and chat ("anything waiting on me
> on GitHub?").
>
> **Shape**: a fourth connector plugin, `plugins/github/`, on the connector
> runtime ([connectors.md](connectors.md)). Read-only. Several accounts: the user
> has more than one GitHub identity (`Raceraja001`, `raja4lmx`).
>
> **Depends on**: PR #36 (contacts, migration 040), which depends on #35.

---

## Decisions

| Question | Proposal | Why |
|---|---|---|
| Credential | A **fine-grained personal access token**, read-only, one per account | The only GitHub credential that can be read-only. Classic tokens and OAuth apps need the `repo` scope for private repos, which also allows writing. |
| Reuse the `gh` login? | **No** | Its token can push and merge (the dev-agent pipeline needs that). A connector must not hold write access. |
| Classic tokens | **Refused** when GitHub reports write scopes (`repo`, `public_repo`, `workflow`, …) | Keeps the read-only guarantee checkable. Fine-grained tokens report no scopes, so their permissions rest on the setup steps. The form lists them. |
| Several owners | One account per token | A fine-grained token covers one owner (the user, or one organisation). Work and personal stay separate, and each can be local-only. |
| What is fetched | Titles and status only: never code, diffs, descriptions or comment bodies | Enough for "what's waiting". Descriptions and comments are written by others and are the injection risk. |
| How | One GraphQL query per sync, every 15 minutes; each sync is the complete open set | Closed or merged items disappear on the next sync. No webhooks needed. |
| Private repos, cloud view | **Counts by default** ("2 reviews waiting in private repos"); a per-account switch shares their titles | Private repo names and PR titles can be confidential work. Public ones are public anyway. |
| Retention | Only open items are kept | Nothing historical to bound. |

---

## Requirements

### Story 1 — Sync

- **Account** (connector `github`, new auth method `token`):
  - Settings: paste the token.
  - Optional: a GitHub Enterprise API URL.
  - Creation checks the token with `GET /user`, which gives the login, and refuses a classic token with write scopes.
- **Every 15 minutes**, one GraphQL request with three searches:

  | Search | Item |
  |---|---|
  | `is:open is:pr review-requested:@me archived:false` | `pr_review`: repo, number, title, author, age, draft |
  | `is:open is:pr author:@me archived:false` | `pr_mine`: plus the CI rollup (`SUCCESS` / `FAILURE` / `PENDING`), review decision, mergeable |
  | `is:open is:issue assignee:@me archived:false` | `issue`: repo, number, title, labels, age |

  - Up to 50 of each.
  - The result is the complete set (`complete=True`).
- **Errors:**
  - 401 (revoked or expired token) → **Reconnect needed**.
  - Rate limit → back off.
  - A fine-grained token past its expiry date → Reconnect, with the date shown.

### Story 2 — Use it

- **Brief section "Code"** (only when non-empty):
  ```
  ## Code
  - Review requested (2): life-graph#36 Contacts connector (Raceraja001, 1d); …
  - Your PRs: life-graph#35 — CI failing · life-graph#34 — approved, ready to merge
  - Assigned issues (1): pulse#12 Login loop
  ```
  - A PR where you've been asked for changes shows first, then failing CI, then ready to merge.
  - Drafts are skipped in "Review requested".
- **Today card:** a "Code" block under "Waiting on you". Rows link to GitHub.
- **Tool `code_inbox`:** returns the same view to agents (`admin`, `jarvis`), filtered by audience.
- **Chat context for jarvis:** triggered by "github", "PR", "pull request", "review", "CI", "build failing", "issue".
- **Dev-agent overlap:** PRs opened by Life Graph's own dev agent (`lg/task-*` branches) are marked "(dev agent)". Their approve and merge steps stay on the Approvals page. This connector only reports.

### Story 3 — Exposure

| Field | LOCAL | CLOUD, public repo | CLOUD, private repo |
|---|---|---|---|
| Repo, number, title, author | yes | yes (title redacted) | count only, unless the account shares private titles |
| CI state, review decision, age | yes | yes | count only, unless shared |
| URL | yes | yes | no |
| Any `local_only` account | yes | count only | count only |

---

## Design

- **`base.py`:** `KIND_CODE = "code"` and `AUTH_TOKEN = "token"`.
- **Migration 041:** allows kind `code` in the kind check constraint.
- **Item mapping:**

  | Item field | Holds |
  |---|---|
  | `external_id` | `pr:owner/repo#12` / `issue:owner/repo#7` |
  | `title` | The PR or issue title |
  | `direction` | `inbound` (others' PRs and issues) or `own` (your PRs) |
  | `occurred_at` | Last update |
  | `flags` | `sub` (`pr_review` / `pr_mine` / `issue`), `repo`, `number`, `private`, `ci`, `review`, `mergeable`, `draft`, `author`, `labels`, `url`, `dev_agent` |

- **Plugin `plugins/github/`:**
  - `connector.py`: validates settings and the token (the scope check) and syncs.
  - `graphql.py`: the query, paging and mapping.
- **Core:**
  - `store.code_items(session, tenant)`.
  - `exposure._code_view` with the private-repo rule.
  - `brief` "Code" section.
  - `tools.code_inbox`.
  - `chat_context` intent.
  - Today card block.
- **No new dependency:** plain `httpx` against `https://api.github.com/graphql`.

## Testing

- **Unit:**
  - Query-result mapping: CI rollup, review decision, drafts, dev-agent branches.
  - Refusing a classic token with write scopes.
  - Private-repo exposure.
  - Brief ordering.
  - 401 → reauth.
- **End to end,** on a copy of the live DB, with a fake GraphQL endpoint: sync, close an item → it disappears, a private repo in the cloud brief, local-only.
- **Real check** after deploy: the user's own token, read-only. It can't be tested before then without a token.

## What the user sets up (per GitHub identity, ~3 minutes)

github.com → Settings → Developer settings → **Fine-grained tokens** → Generate:
- **Resource owner:** you (or an organisation). **Repository access:** All repositories.
- **Permissions, all read-only:**
  - Pull requests
  - Issues
  - Commit statuses
  - Checks
  - Metadata (added automatically)
- **Expiry:** up to a year. Life Graph shows **Reconnect needed** when it lapses.
- Paste the token in Settings → Add account → *GitHub*.
