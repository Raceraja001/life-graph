# Bills & Renewals from Mail — Feature Spec

> **Status: Built (2026-09-19).** `connectors/bills.py`, summariser fields,
> brief section **Bills & renewals**, Overview → Today *Bills* block (Remind me
> / Paid / Dismiss), tool `bills_due`, bill questions in jarvis's chat context,
> Settings → mail account → *Find bills in past mail*. Verified end to end with
> the real local model (qwen3:14b) on realistic Indian bill emails; unit tests in
> `tests/unit/test_bills.py`. Approved as proposed: cloud models see payee, type
> and due date (never amounts); the one-time 60-day re-scan is included.
>
> **Where the build differs from the text below:**
> - **A deterministic scam check** (`bills.looks_like_scam`): link shorteners,
>   "disconnected tonight", "call our officer" and throwaway domains (`.xyz`, …)
>   (a free-mail sender alone is not a sign: landlords bill from Gmail). In the
>   first end-to-end run qwen3 did **not** flag a BESCOM disconnection scam as
>   suspicious. The check drops such a "bill" and
>   marks the mail suspicious whatever the model says. The prompt now also
>   describes these signs, and the summariser sees the sender's address.
> - Newsletter-category mail is not excluded outright: renewal notices are often
>   classed as notifications. The model's `bill_kind` decides, and the prompt
>   says offers and marketing are `none`.
> - New mail is summarised newest first, so a payment confirmation can be read
>   before its bill. A new bill therefore also checks for a later confirmation
>   (`bills.paid_since`).
> - The re-scan runs as a background task in the API process (like *Sync now*),
>   not as a worker job.
> - The counts-only switch is the setting `LIFE_GRAPH_CONNECTOR_BILLS_CLOUD`
>   (`details` / `counts`). There is no dashboard toggle yet.
> - The end-to-end test feeds the email texts straight to the runtime's
>   summariser rather than through GreenMail. The mail path itself is covered by
>   PR #35's tests.
>
> **Purpose**: Bring the bills and renewals already sitting in the user's inbox
> into the brief, with a due date:
> - card statements, electricity, water, gas, phone and broadband bills, rent,
>   school and loan payments;
> - renewals and expiries: insurance, domains, subscriptions, licences, passport
>   and vehicle documents.
>
> Each one can be turned into a reminder or marked paid with one click, and a
> payment-confirmation email closes the matching bill by itself.
>
> **Shape**: no new connector and no new data source. The local mail summariser
> (`connectors/summarize.py`) already reads every message once; it gains a few
> bill fields. The dates and amounts are then worked out by code, not by the
> model. Everything stays inside the connector runtime and its exposure rules.
>
> **Depends on**: PR #35 (mail). Stacked after #37 so the branches stay linear.
> It needs no migration.

---

## Decisions

| Question | Proposal | Why |
|---|---|---|
| Where it comes from | The existing per-message summary call gets 5 more JSON fields | One local-model call per email, as today. No second pass over the inbox. |
| Who works out the date | The model copies the due or expiry words as written ("Due date: 25-09-2026", "renews on 3 Oct"); code parses them. Indian `DD-MM-YYYY` is read day-first. | The same fix as promises: qwen3 got date arithmetic wrong. |
| Amounts | Copied as written, normalised by code (`₹2,345.00` → 2345.00 INR) | Deterministic and testable. |
| Phishing | Suspicious mail (already flagged) never becomes a bill. Neither does mail the user sent, or marketing. | "Your bill is overdue, pay here" is a classic scam. |
| Same bill, several emails | Grouped by payee and due date: a statement plus two reminders show as one line | Less noise. |
| Paid | Three ways: a later **payment-confirmation** email from the same payee within 45 days, **Mark paid**, or **Dismiss**. **Remind me** creates a reminder, as for promises. | Closes itself when the confirmation arrives. |
| Autopay | Bills that say auto-debit or auto-renew show as "autopay" and never as overdue | Keeps these as information, not tasks. |
| What cloud models see | **Payee, type and due date; never the amount** ("HDFC credit card bill due Fri"). A global switch reduces this to counts ("2 bills due this week"). | Amounts and account numbers are the sensitive part. The payee is usually harmless and makes the line useful. |
| Existing mail | A one-time **re-scan** of the last 60 days of transactional and sensitive mail, in the background on the local model | Mail summarised before this change has no bill fields. |

---

## Requirements

### Story 1 — Extraction (inbound mail only, not suspicious)

- **New summary fields:**

  | Field | Holds |
  |---|---|
  | `bill_kind` | `none`, `bill` (payment due), `renewal` (something expires or renews), `payment_done` (confirms a payment) |
  | `bill_payee` | Who is paid or what renews, under 6 words ("BESCOM electricity", "HDFC credit card", "example.com domain") |
  | `bill_amount` | As written, or `""` |
  | `bill_due` | The due or expiry date words as written, or `""` |
  | `bill_autopay` | true when auto-debit or auto-renew is stated |

- **Stored** in the email item's `flags.bill`: `kind`, `payee`, `amount`, `currency`, `due` (ISO date), `autopay`, `state` (`open` / `paid` / `dismissed` / `reminded`).
- **When there is no bill:** a bill or renewal without a parseable date is kept, but isn't listed as due. `payment_done` closes the newest open bill whose payee matches, issued within the previous 45 days.

### Story 2 — Use it

- **Brief section "Bills & renewals"**, only when non-empty:
  ```
  ## Bills & renewals
  - Overdue: BESCOM electricity (due Wed 17 Sep)
  - HDFC credit card — due Fri 26 Sep
  - Airtel broadband — due Mon 29 Sep (autopay)
  - example.com domain — renews Sat 4 Oct
  ```
  - **Window:** bills overdue up to 7 days or due in the next 7 days; renewals in the next 14 days.
  - **Amounts:** shown in the dashboard version only.
- **Today card:** a *Bills* block with the amount, **Remind me**, **Paid** and **Dismiss**.
- **Tool `bills_due`** for `admin` and `jarvis`, filtered by audience.
- **Chat context** for jarvis: bill, due, pay, renewal, expire, subscription.
- **API:**
  - `POST /connectors/items/{id}/bill` with `{action: paid|dismiss|remind}`.
  - `POST /connectors/bills/rescan`: background, returns at once, with progress in the logs.

### Story 3 — Exposure

| Field | LOCAL | CLOUD (default) | CLOUD, "bills as counts" |
|---|---|---|---|
| Payee, type, due date, autopay | yes | yes (redacted) | count only |
| Amount, currency | yes | **never** | never |
| `local_only` mail account | yes | count only | count only |

A bill in mail the classifier marked **sensitive** (for example a credit card statement) still shows payee and due date to the cloud, as above. The email itself stays hidden: subject, summary and sender detail as today.

---

## Design

- **`summarize.py`:**
  - Five fields added to the schema and prompt; `Summary.bill`.
  - Only filled for received mail that isn't suspicious and isn't a newsletter.
- **`bills.py` (new):**
  - `parse_due(words, received_at)`: explicit dates in the forms `DD-MM-YYYY`, `DD/MM/YY`, `25 Sep 2026`, `Sep 25`, `25th September` and ISO, falling back to `parse_horizon`. A date without a year takes the next occurrence after the email date.
  - `parse_amount`.
  - `payee_key` (normalised tokens for grouping and matching).
  - `close_paid(session, account, payee, when)`.
  - `bills_due(session, tenant, today)`, grouped.
- **`runtime._summarize_pending`:** stores `flags.bill` and calls `close_paid` for `payment_done`.
- **Other changes:**
  - `exposure._bill_view`.
  - `brief` section.
  - `tools.bills_due`.
  - `chat_context` intent.
  - API endpoints.
  - Today card block.
  - Settings switch: "Bills in cloud chat: payee and date / counts only". It is stored in `settings` (`connector_bills_cloud`), not per account.
- **Re-scan:** a worker task walks the tenant's inbound transactional and sensitive mail from the last 60 days. It re-fetches each body (read-only), re-summarises it with the local model, and updates the flags. Local-model time: a few seconds per message.

## Testing

- **Unit:**
  - `parse_due`: day-first Indian formats, month names, no year, "within 15 days", garbage.
  - `parse_amount`: ₹, Rs., INR, USD.
  - Payee matching.
  - Grouping.
  - The exposure table (no amount to the cloud; the counts switch).
  - Brief rendering.
  - Suspicious mail → no bill.
- **End to end,** with the **real local model** on realistic Indian bills sent through the test mail server (GreenMail):
  - BESCOM, an HDFC statement, Airtel autopay, a GoDaddy renewal.
  - A phishing "overdue" mail.
  - A payment confirmation.
  - Checks: fields extracted, dates correct, confirmation closes the bill, phishing ignored, no amounts off the machine, re-scan.
  - On a copy of the live DB.
