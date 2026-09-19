# Contacts Connector — Feature Spec

> **Status: Built (2026-09-19).** Plugin `plugins/contacts/`, migration 040,
> Settings → *Calendar, email & contacts* (import, cloud visibility), birthdays
> in the brief and on Overview → *Today*, meeting-prep "Who" lines, tool
> `contact_lookup`, contact questions in jarvis's chat context. Verified end to
> end on a copy of the live DB against a fake People API and real vCard text;
> unit tests in `tests/unit/test_connector_contacts.py`.
>
> Approved with two changes from the first draft: cloud visibility is
> **configurable per account**, field by field, and Google's "Other contacts"
> are included.
>
> **Where the build differs from the text below:**
> - No `vobject` dependency: a small vCard reader (`plugins/contacts/vcard.py`,
>   2.1/3.0/4.0, folding, quoted-printable) covers what exports contain.
> - The import method is a new auth method, `file`; the vCard text is posted
>   as JSON (read in the browser), not multipart.
> - A contact's flags are replaced on each sync (other kinds merge), so a
>   birthday or company removed at the source is removed here.
> - An expired sync token on either Google list re-lists both, as a complete
>   set, rather than tracking the two lists' deletions separately.
> - A suspicious (possibly spoofed) sender never borrows a contact's name.
> - Meeting prep's recent mail shows your own messages as "You".
> - Store functions are `people_by_address`, `search_contacts`,
>   `birthdays_between` and `mail_with` (the design names differ).
> - Not verified: whether Google's CardDAV would take an app password. It was
>   not needed: the vCard import covers accounts without OAuth.
>
> **Purpose**: Know *who* people are. Today Life Graph sees addresses, not people:
> a calendar invite lists `a.kumar@vendor.in`, and meeting prep looks for related
> mail by guessing a first name from the address. With the user's contacts:
> - Senders and attendees are shown by name.
> - Meeting prep says who each attendee is and finds their mail by exact address.
> - Birthdays reach the brief.
> - Agents can answer "who is Arun?" and "what's Priya's number?".
>
> **Shape**: a third connector plugin, `plugins/contacts/`, on the runtime built
> in [connectors.md](connectors.md). No new services. The runtime already owns
> credentials, sync, exposure and retention.
>
> **Depends on**: PR #35 (connectors runtime, migration 039).

---

## Decisions

| Question | Decision | Why |
|---|---|---|
| Sources | **Google OAuth** (People API) and **vCard file import** | The two ways the user can get their contacts. As far as we know, Google's CardDAV accepts only OAuth, so an app password cannot read Google contacts. To confirm before building. |
| Which Google contacts | Saved contacts **and** "Other contacts" (addresses Google auto-saves from mail) | Most senders are never saved by hand. Other contacts carry only name + address. |
| Scopes | `contacts.readonly`, `contacts.other.readonly` | Read-only, like mail and calendar. No directory scope: the work domain's directory needs an admin-approved app. |
| Work account | vCard export only, or skip | The user does not administer the Workspace domain. |
| Storage | `connector_items`, kind `contact`, plus one `emails` column | Reuses the store, exposure, account deletion and dashboard. The column is needed for lookup by address; it also changes the kind check constraint to allow `contact`. |
| Retention | Not time-bounded; mirrors the source | A contact is not old or new. Deleted at the source → deleted here. |
| Cloud visibility | **The user picks, per account**, which field groups cloud models may see. Default: name, organisation and job title, email addresses, birthday (day and month) | Enough for "meeting with Arun (Acme, CFO)" out of the box. The user can widen or narrow it. |
| Off by default | Phone numbers, postal addresses, notes (redacted when shared) | Other people's personal data. Shared only when the user switches it on for that account. |
| Never to cloud | Birth year, relations | Nothing in chat needs them. |
| Addresses on every item | The new `emails` column holds the people an item involves: a contact's addresses, an event's attendees, a mail's sender and recipients (not the user) | Lets meeting prep find mail by exact address and count history. |

---

## Requirements

### Story 1 — Sync contacts

- **Google OAuth account** (connector `contacts`, auth `oauth`):
  - `people.connections.list` and `otherContacts.list`, with sync tokens.
  - An expired sync token (after 7 days, HTTP 410) triggers a full re-sync, not an error.
  - A revoked grant → **Reconnect needed**, as for mail.
  - Default interval: 6 hours.
- **vCard import** (connector `contacts`, auth `file`, new):
  - Settings → *Calendar & email* → the account's **Import vCard** button sends a `.vcf` file of up to 5 MB (read in the browser, posted as text).
  - Each import replaces the account's contacts (a complete set).
  - The file itself is not kept.
- **Item mapping:**

  | Item field | Holds |
  |---|---|
  | `external_id` | Google `resourceName`, or vCard `UID` (fallback: a hash of name and emails) |
  | `direction` | `own` for saved contacts, `inbound` for other contacts |
  | `title` | Display name |
  | `emails` (new column) | Lower-cased addresses |
  | `flags` | `org`, `job_title`, `birthday` (`MM-DD`), `starred`, `groups` |
  | `local_detail` | Phones, addresses, notes, relations, birth year (JSON). Never cloud-bound. |

- **Trust:** names and organisations are not safe instructions. Other contacts are named by whoever sent the mail, so they are `hostile_possible` like inbound mail. Rendering already treats every connector field as data.

### Story 2 — Use it

- **Names everywhere:**
  - Brief and Today: attendee lists show names.
  - Waiting on you: a sender with no display name shows the contact's name.
  - Resolution happens at read time (`store.names_for(session, tenant, addresses)`), so fixing a contact fixes every view.
- **Meeting prep:**
  - For each attendee, a "Who" line, for example: `Arun Kumar — Acme, CFO · 14 emails in 90 days, last Tue`.
  - Mail found by the attendee's **exact addresses** instead of a first-name guess.
  - A mail count of 0 or no contact at all reads "no history", so the user knows before walking in.
- **Birthdays:**
  - A brief line for birthdays today and in the next 3 days, and on the Today card.
  - Saved contacts only; other contacts have no birthdays.
- **Agent tool `contact_lookup(query)`:**
  - Matches name, address or organisation.
  - A LOCAL caller gets everything. A CLOUD caller gets the cloud fields.
  - Given to `admin` and `jarvis`, like the other connector tools.
- **Chat context for jarvis:** "who is X" / "X's number/email" builds the cloud view of matching contacts. The number itself only reaches a local model; the cloud answer says so.

### Story 3 — Exposure

Account setting `cloud_fields` (Settings → the account → *Cloud visibility*):

| Field group | LOCAL | CLOUD by default | Configurable | `local_only` account, CLOUD |
|---|---|---|---|---|
| `name` | yes | yes | yes; off → each contact counts as withheld | count only |
| `org` (company, job title) | yes | yes | yes | count only |
| `emails` | yes | yes | yes | count only |
| `birthday` (day and month) | yes | yes | yes | count only |
| `phones` | yes | no | yes | count only |
| `addresses` (postal) | yes | no | yes | count only |
| `notes` | yes | no | yes; redacted when shared | count only |
| Birth year, relations | yes | never | no | count only |

- **Names in other views:** name resolution for *other* views follows that view's audience. A local-only account's names never appear in a cloud view of a mail from that person, where the mail header name is used instead.

---

## Design

### Contract changes

- `base.py`:
  - Add `KIND_CONTACT`.
  - Add `emails: list[str]` to `Item`.
- `google_oauth.SCOPES["contacts"]`: the two read-only scopes.
- `scopes_for` is keyed on connector name instead of a `"calendar" in name` check.

### Migration 040

```sql
ALTER TABLE life_graph.connector_items ADD COLUMN emails text[] NOT NULL DEFAULT '{}';
CREATE INDEX ix_connector_items_emails ON life_graph.connector_items USING gin (emails);
```

- **Retention:** `purge_expired` skips kind `contact`.
- **Deletions:** the sync token reports deleted people; a vCard import is `complete=True`.

### Plugin `plugins/contacts/`

| File | Role |
|---|---|
| `connector.py` | `ContactsConnector`: auth `oauth` or `file`; `sync` dispatches to Google or returns nothing for vCard (import is a separate call) |
| `google_source.py` | People API paging, sync tokens, 410 → full sync, mapping |
| `vcard.py` | `parse_vcards(text) -> list[Item]` via `vobject` |

- **Import path:** `POST /connectors/accounts/{id}/import` (JSON `{"vcard": "..."}`). The runtime parses the file and upserts the items with `complete=True`.

### Core additions

- `store.names_for(session, tenant, addrs, audience)`, and `store.contacts_search(session, tenant, query, limit)`.
- `exposure._contact_view`.
- `tools.contact_lookup`.
- `brief` birthdays section.
- `assist.prepare_meetings` uses `emails`.

### New dependency

None (planned: `vobject`; see the status note — a small built-in reader is used instead).

---

## Testing

- **Unit:**
  - vCard parsing: v2.1, v3 and v4, folded lines, a UTF-8 name, a missing UID.
  - People API mapping, and a 410 → full sync.
  - The exposure table (a phone number never in a CLOUD view).
  - Name resolution across a local-only account.
  - Birthdays around a month or year end.
  - Tenant scoping.
- **End to end,** on a copy of the live DB:
  - A fake People API served locally: full sync, incremental sync with one deletion, expired token.
  - A real `.vcf` exported from Google Contacts.
  - Brief, meeting prep and the tool output checked for each audience.
- **Real account:** checked after deploy, when the user connects Google. A real OAuth grant cannot be tested before then.

## Phases

1. **Plugin and store:** contract change, migration 040, Google and vCard sources, import API, Settings UI.
2. **Use:** names, meeting prep, birthdays, tool, chat context.
3. **Verify:** end to end, spec status, STATE.md, then a PR.

## What the user sets up

- **Google (OAuth):** Settings → Add account → *Contacts* → Connect with Google (the OAuth client from #35 is reused).
- **Without OAuth:** export from contacts.google.com → Export → vCard, then Settings → Add account → *Contacts (file)* → Import.
