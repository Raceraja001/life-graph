# 04: Jarvis routing, money questions are personal

| | |
|---|---|
| Theme | B. Privacy and routing |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | 03 (soft: run it after 03 if both are queued; it passes either way) |
| Review | **Claude**: this check decides which requests may go to a cloud model |
| Size | ~10 lines of regex in `lead.py`, one new test file |

## Why

`services/lead.py::is_personal` decides, deterministically, whether a request to Jarvis needs
personal data. If it does, Jarvis runs on the local model with the personal tools. If not, the
request goes to a free cloud model, scrubbed, without them. A personal question routed as general
cannot see the owner's data and gets a useless answer, so the docstring says to err towards
personal. On 6459f6b these money questions are routed as general:

```
"show last week's transactions"  -> None
"list my upi payments"           -> None
"when is the EMI due"            -> None
"what's due this week"           -> None
"how much do I owe"              -> None
"my portfolio is down?"          -> None
```

## Instruction

<!-- instruction:start -->
Jarvis routing: is_personal must treat money questions (transactions, payments, EMIs, dues, investments) as personal

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_lead_money_words.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_lead_money_words.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_lead_money_words.py =====
import pytest

from life_graph.services.lead import is_personal


@pytest.mark.parametrize(
    "text",
    [
        "show last week's transactions",
        "list my upi payments",
        "when is the EMI due",
        "what's due this week",
        "how much do I owe",
        "how is my mutual fund doing",
        "my portfolio is down?",
        "I paid the plumber 500, note it",
        "check my cibil score",
        "recent payments please",
        "what's my net worth",
    ],
)
def test_money_questions_are_personal(text):
    assert is_personal(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "What is the capital of France?",
        "how do I reverse a list in Python",
        "explain how UPI works in India",
        "write a function that sums transactions",
        "what is a SIP in investing",
        "compare mutual funds and ETFs",
        "explain transformers",
        "how do payments gateways work",
    ],
)
def test_general_money_questions_stay_general(text):
    assert is_personal(text) is None
===== end of tests/unit/test_lead_money_words.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_lead_money_words.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/lead.py (_DOMAIN and _PERSONAL) that makes those cases pass. Read the code first.
1. Add to the _DOMAIN alternation (words that are personal after "my/our/mine"): transactions?, txns?, payments?, upi, emis?, dues, portfolio, investments?, savings, stocks, shares, mutual funds?, sips?, rent, net worth, credit score, cibil.
2. Add these alternatives to _PERSONAL (personal without "my"), each as one more r"|..." line before the closing ",":
   \b(?:last|this|past|recent)\s+(?:\S+\s+)?(?:transactions?|txns?|payments?|spending|expenses)\b
   \bemis?\s+(?:due|of|for|this|next)\b and \bnext\s+emi\b
   \bi\s+(?:spent|paid|owe)\b
   \bwhat(?:'s|\s+is)\s+due\b and \bdue\s+this\s+(?:week|month)\b
   \b(?:credit score|cibil|net worth)\b
Do not add bare "transactions", "payments", "upi", "sip" or "mutual fund" without "my/our" or a time word: "explain how UPI works" is a general question.

STEP 4. Run run_tests with paths ["tests/unit/test_lead_money_words.py", "tests/unit/test_lead_is_personal.py", "tests/unit/test_lead.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_lead_money_words.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what _DOMAIN and _PERSONAL did before, in your words>
Change: <what you changed in _DOMAIN and _PERSONAL (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_lead_money_words.py or tests/unit/test_lead_is_personal.py shows it does not>

Files you may touch:
- life_graph/services/lead.py (_DOMAIN and _PERSONAL)
- tests/unit/test_lead_money_words.py (new; created in STEP 1)

Do NOT:
- change is_personal, route(), local_model(), PERSONAL_TOOLS or any other function;
- change life_graph/services/scrub.py;
- remove or loosen any existing alternative in _PERSONAL;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: Questions about the owner's transactions, payments, EMIs, dues and investments are personal — test: tests/unit/test_lead_money_words.py::test_money_questions_are_personal
AC-2: General questions that only mention money topics stay general — test: tests/unit/test_lead_money_words.py::test_general_money_questions_stay_general
AC-3: Existing routing is unchanged — test: tests/unit/test_lead_is_personal.py::test_general_questions_stay_general
**Design:** Widen the _DOMAIN alternation and add five alternatives to _PERSONAL; no code outside the two regexes changes.
**Tasks:**
1. Create tests/unit/test_lead_money_words.py exactly as given, then extend _DOMAIN and _PERSONAL in lead.py until it and the existing routing tests pass (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes (Claude)

- The direction of the change is safe: it only moves requests from cloud to local. Check that it
  does not route ordinary code work to the weaker local model. "write a function that sums
  transactions" must stay general.
- Run `tests/unit/test_lead.py` too. It exercises `route()` end to end.
