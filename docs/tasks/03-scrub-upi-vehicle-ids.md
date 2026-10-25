# 03: Scrub UPI ids, vehicle numbers, passport and voter ids

| | |
|---|---|
| Theme | B. Privacy and routing |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
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

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_scrub_more_shapes.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_scrub_more_shapes.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_scrub_more_shapes.py =====
import pytest

from life_graph.services.scrub import scrub


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pay raja@okhdfcbank now", "pay «HIDDEN:upi» now"),
        ("upi 9876543210@ybl", "upi «HIDDEN:upi»"),
        ("send to raja.k@oksbi.", "send to «HIDDEN:upi»."),
    ],
)
def test_upi_ids_are_hidden(text, expected):
    assert scrub(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my car TN 09 AB 1234", "my car «HIDDEN:vehicle»"),
        ("TN09AB1234", "«HIDDEN:vehicle»"),
        ("KA-01-MX-4321", "«HIDDEN:vehicle»"),
        ("passport Z1234567", "passport «HIDDEN:passport»"),
        ("voter id ABC1234567", "voter id «HIDDEN:voter_id»"),
    ],
)
def test_vehicle_passport_and_voter_ids_are_hidden(text, expected):
    assert scrub(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "npx create-next-app@latest my-app",
        "brew install python@3.12",
        "RTX 4090 vs RTX 3090",
        "qwen3:14b runs on 16 GB",
        "ISO 8601 dates",
        "meet at 10:30 in room B2",
        "@raja please review",
        "GPT-4o and Claude 3.5",
        "version v2.1.0 released 2026-10-01",
        "OpenRouter gives 1000 free requests a day for 50 models until 2026-12-31.",
    ],
)
def test_ordinary_text_is_unchanged(text):
    assert scrub(text) == text
===== end of tests/unit/test_scrub_more_shapes.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_scrub_more_shapes.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/scrub.py (_PATTERNS) that makes those cases pass. Read the code first.
Add four entries to _PATTERNS. Order matters: each pattern runs on the output of the previous one.
1. ("upi", ...) directly AFTER "email" and BEFORE "card": 2 to 64 characters from [A-Za-z0-9._-], then "@", then a known payment handle as a whole word, case-insensitive (re.I). Handles: ok[a-z]+, ybl, ibl, axl, apl, yapl, upi, paytm, pt[a-z]+, wa[a-z]+, icici, sbi, hdfcbank, axisbank, kotak, idfcbank, aubank, fbl, freecharge, airtel, jio, barodampay, unionbank, pnb, cnrb, indus, federal, rbl, yesbank, dbs, hsbc, citi, boi, mahb, kbl, abfspay, ikwik, naviaxis, jupiteraxis, slc, superyes, timecosmos. A known-handle list, not "anything@word", keeps "create-next-app@latest" and "python@3.12" untouched.
2. ("vehicle", re.compile(r"\b[A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{4}\b")), ("passport", re.compile(r"\b[A-Z][1-9]\d{6}\b")) and ("voter_id", re.compile(r"\b[A-Z]{3}\d{7}\b")), all three AFTER "ifsc" and BEFORE the first "phone". Case-sensitive: the ids are upper case.
Also name the new shapes in the module docstring's list (that edit is allowed).

STEP 4. Run run_tests with paths ["tests/unit/test_scrub_more_shapes.py", "tests/unit/test_workers_and_offers.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_scrub_more_shapes.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what _PATTERNS did before, in your words>
Change: <what you changed in _PATTERNS (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_scrub_more_shapes.py or tests/unit/test_workers_and_offers.py shows it does not>

Files you may touch:
- life_graph/services/scrub.py (_PATTERNS)
- tests/unit/test_scrub_more_shapes.py (new; created in STEP 1)

Do NOT:
- edit life_graph/services/redaction.py (protected) or any caller of scrub;
- remove or reorder the existing patterns;
- make any pattern case-insensitive except the UPI one;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: UPI ids with a known payment handle are hidden as «HIDDEN:upi», including phone-number ids — test: tests/unit/test_scrub_more_shapes.py::test_upi_ids_are_hidden
AC-2: Indian vehicle numbers, passport numbers and voter ids are hidden — test: tests/unit/test_scrub_more_shapes.py::test_vehicle_passport_and_voter_ids_are_hidden
AC-3: Ordinary technical text is left unchanged — test: tests/unit/test_scrub_more_shapes.py::test_ordinary_text_is_unchanged
AC-4: The existing kinds are still hidden — test: tests/unit/test_workers_and_offers.py::test_scrub_hides_personal_details
**Design:** Four new (kind, pattern) entries placed so the UPI id is replaced before the phone rule can eat its digits, and the id shapes run before phone/account.
**Tasks:**
1. Create tests/unit/test_scrub_more_shapes.py exactly as given, then add the upi pattern after email and the vehicle, passport and voter_id patterns after ifsc, and update the docstring, until it and the existing scrub tests pass (AC-1, AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes (Claude)

- Run the new patterns over a sample of real research briefs and Jarvis general-route
  messages, and look for false positives. The cost of a false positive is a hidden
  token in a cloud brief. The cost of a miss is a personal id sent to a provider that trains on
  prompts.
- `is_personal()` calls `scrub()`, so a message carrying a vehicle or passport number now
  routes to the local model. That is intended.
