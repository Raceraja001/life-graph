# 03: Scrub UPI ids, vehicle numbers, passport and voter ids

| | |
|---|---|
| Theme | B. Privacy and routing |
| Engine | `code-fixer-local`, `spec_first=True` |
| Depends on | none |
| Review | **Claude**: this is the privacy net for everything sent to free cloud models |
| Size | ~15 lines in `scrub.py`, one new test file |

## Why

`services/scrub.py::scrub` is the deterministic second layer that hides personal details before
a brief leaves the machine (CHARTER invariant 7). `lead.is_personal` also uses it to decide that
a message is personal. On 6459f6b it misses common Indian identifiers:

```
"pay raja@okhdfcbank now"  -> unchanged       (UPI id: not an email, no TLD)
"upi 9876543210@ybl"       -> "upi «HIDDEN:phone»@ybl"   (the handle is left)
"my car TN 09 AB 1234"     -> unchanged
"passport Z1234567"        -> unchanged
"voter id ABC1234567"      -> unchanged
```

## Instruction

<!-- instruction:start -->
Scrub: hide UPI ids, Indian vehicle numbers, passport numbers and voter ids

Read first:
- life_graph/services/scrub.py: _PATTERNS and scrub (the whole file is 49 lines).
- tests/unit/test_workers_and_offers.py: test_scrub_hides_personal_details and test_scrub_keeps_ordinary_text_and_hides_secrets (must keep passing unchanged).

Change (life_graph/services/scrub.py, the _PATTERNS list only):
Add four entries. Order matters, because each pattern runs on the output of the previous one:
1. ("upi", ...) directly AFTER "email" and BEFORE "card". A UPI id is 2 to 64 characters from [A-Za-z0-9._-], then "@", then a known payment handle as a whole word, case-insensitive. Handles: any "ok" + letters (okaxis, oksbi, okhdfcbank, okicici), ybl, ibl, axl, apl, yapl, upi, paytm, any "pt" + letters, any "wa" + letters, icici, sbi, hdfcbank, axisbank, kotak, idfcbank, aubank, fbl, freecharge, airtel, jio, barodampay, unionbank, pnb, cnrb, indus, federal, rbl, yesbank, dbs, hsbc, citi, boi, mahb, kbl, abfspay, ikwik, naviaxis, jupiteraxis, slc, superyes, timecosmos. A known-handle list, not "anything@word", keeps "create-next-app@latest" and "python@3.12" untouched.
2. ("vehicle", r"\b[A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{4}\b"), ("passport", r"\b[A-Z][1-9]\d{6}\b") and ("voter_id", r"\b[A-Z]{3}\d{7}\b"), all three AFTER "ifsc" and BEFORE the first "phone". They are case-sensitive: the ids are upper case.
Update the module docstring's list of shapes to name the new ones.

Cases (copy exactly). scrub(text) contains "«HIDDEN:<kind>»" and no digit is left inside the last placeholder's text:
- "pay raja@okhdfcbank now" -> exactly "pay «HIDDEN:upi» now"
- "upi 9876543210@ybl" -> exactly "upi «HIDDEN:upi»"
- "send to raja.k@oksbi." -> kind upi
- "my car TN 09 AB 1234" -> kind vehicle
- "TN09AB1234" -> kind vehicle
- "KA-01-MX-4321" -> kind vehicle
- "passport Z1234567" -> kind passport
- "voter id ABC1234567" -> kind voter_id
scrub(text) == text (unchanged) for each of:
- "npx create-next-app@latest my-app"
- "brew install python@3.12"
- "RTX 4090 vs RTX 3090"
- "qwen3:14b runs on 16 GB"
- "ISO 8601 dates"
- "meet at 10:30 in room B2"
- "@raja please review"
- "GPT-4o and Claude 3.5"
- "version v2.1.0 released 2026-10-01"
- "OpenRouter gives 1000 free requests a day for 50 models until 2026-12-31."
The existing kinds (email, phone, pan, aadhaar, card, ifsc, account) still hide what they hid before.

Files you may touch:
- life_graph/services/scrub.py
- tests/unit/test_scrub_more_shapes.py (new)

Do NOT:
- edit life_graph/services/redaction.py (protected) or any caller of scrub;
- remove or reorder the existing patterns;
- edit tests/unit/test_workers_and_offers.py or any other existing test;
- make any pattern case-insensitive except the UPI one.

## Spec
**Requirements:**
AC-1: UPI ids with a known payment handle are hidden as «HIDDEN:upi», including phone-number ids — test: tests/unit/test_scrub_more_shapes.py::test_upi_ids_are_hidden
AC-2: Indian vehicle numbers, passport numbers and voter ids are hidden — test: tests/unit/test_scrub_more_shapes.py::test_vehicle_passport_and_voter_ids_are_hidden
AC-3: Ordinary technical text is left unchanged — test: tests/unit/test_scrub_more_shapes.py::test_ordinary_text_is_unchanged
AC-4: The existing kinds are still hidden — test: tests/unit/test_workers_and_offers.py::test_scrub_hides_personal_details
**Design:** Four new (kind, pattern) entries placed so the UPI id is replaced before the phone rule can eat its digits, and the id shapes run before phone/account.
**Tasks:**
1. Add the upi pattern after email, with tests (AC-1, AC-3, AC-4)
2. Add the vehicle, passport and voter_id patterns after ifsc, update the docstring, with tests (AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes (Claude)

- Run the new patterns over a sample of real research briefs and Jarvis general-route
  messages, and look for false positives. The cost of a false positive is a hidden
  token in a cloud brief. The cost of a miss is a personal id sent to a provider that trains on
  prompts.
- `is_personal()` calls `scrub()`, so a message carrying a vehicle or passport number now
  routes to the local model. That is intended.
