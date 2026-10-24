# 04: Jarvis routing, money questions are personal

| | |
|---|---|
| Theme | B. Privacy and routing |
| Engine | `code-fixer-local`, `spec_first=True` |
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

Read first:
- life_graph/services/lead.py: _DOMAIN, _PERSONAL and is_personal (lines 60-120).
- tests/unit/test_lead_is_personal.py (must keep passing unchanged).

Change (life_graph/services/lead.py, the _DOMAIN string and the _PERSONAL regex only):
1. Add to _DOMAIN (the words that are personal after "my/our/mine"): transactions?, txns?, payments?, upi, emis?, dues, portfolio, investments?, savings, stocks, shares, mutual funds?, sips?, rent, net worth, credit score, cibil.
2. Add these alternatives to _PERSONAL (personal without "my"):
   - a time word, then at most one more word, then a money noun: \b(?:last|this|past|recent)\s+(?:\S+\s+)?(?:transactions?|txns?|payments?|spending|expenses)\b
   - EMI phrases: \bemis?\s+(?:due|of|for|this|next)\b and \bnext\s+emi\b
   - the owner's own money acts: \bi\s+(?:spent|paid|owe)\b
   - dues: \bwhat(?:'s|\s+is)\s+due\b and \bdue\s+this\s+(?:week|month)\b
   - \b(?:credit score|cibil|net worth)\b
Do not add bare "transactions", "payments", "upi", "sip" or "mutual fund" without "my/our" or a time word. "explain how UPI works" is a general question.

Cases (copy exactly):
is_personal(text) is not None for each of:
- "show last week's transactions"
- "list my upi payments"
- "when is the EMI due"
- "what's due this week"
- "how much do I owe"
- "how is my mutual fund doing"
- "my portfolio is down?"
- "I paid the plumber 500, note it"
- "check my cibil score"
- "recent payments please"
- "what's my net worth"
is_personal(text) is None for each of:
- "What is the capital of France?"
- "how do I reverse a list in Python"
- "explain how UPI works in India"
- "write a function that sums transactions"
- "what is a SIP in investing"
- "compare mutual funds and ETFs"
- "explain transformers"
- "how do payments gateways work"

Files you may touch:
- life_graph/services/lead.py (_DOMAIN and _PERSONAL only)
- tests/unit/test_lead_money_words.py (new)

Do NOT:
- change route(), local_model(), PERSONAL_TOOLS or any other function;
- change life_graph/services/scrub.py;
- remove or loosen any existing alternative in _PERSONAL;
- edit tests/unit/test_lead_is_personal.py, tests/unit/test_lead.py or any other existing test.

## Spec
**Requirements:**
AC-1: Questions about the owner's transactions, payments, EMIs, dues and investments are personal — test: tests/unit/test_lead_money_words.py::test_money_questions_are_personal
AC-2: General questions that only mention money topics stay general — test: tests/unit/test_lead_money_words.py::test_general_money_questions_stay_general
AC-3: Existing routing is unchanged — test: tests/unit/test_lead_is_personal.py::test_general_questions_stay_general
**Design:** Widen the _DOMAIN alternation and add five alternatives to _PERSONAL; no code outside the two regexes changes.
**Tasks:**
1. Extend _DOMAIN and _PERSONAL in lead.py and add tests/unit/test_lead_money_words.py with both case lists (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes (Claude)

- The direction of the change is safe: it only moves requests from cloud to local. Check that it
  does not route ordinary code work to the weaker local model. "write a function that sums
  transactions" must stay general.
- Run `tests/unit/test_lead.py` too. It exercises `route()` end to end.
