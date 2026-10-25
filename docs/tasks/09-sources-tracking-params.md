# 09: Sourced answers, ignore tracking parameters

| | |
|---|---|
| Theme | D. Research and pipeline |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | none |
| Review | gates |
| Size | ~10 lines in `sources.py`, one new test file |

## Why

`services/sources.py::check` marks a research answer *unverified* when it cites a URL that no
search or fetch returned during the run. URLs are compared after `normalise()`. On 6459f6b,
`normalise` keeps `utm_*`, `fbclid` and similar tracking parameters, and it keeps the
parameters in their original order. So a model that cites the clean link of a page it fetched
with tracking parameters, or the other way round, is flagged as unsourced. The topic reader's
`validate_finding` and `web_pages` dedupe on the same key, so both also treat one page as two.

```
normalise("https://example.com/a?utm_source=x&id=2") -> "example.com/a?utm_source=x&id=2"
normalise("https://example.com/a?id=2")              -> "example.com/a?id=2"
normalise("https://example.com/a?b=1&a=2")           -> "example.com/a?b=1&a=2"
```

## Instruction

<!-- instruction:start -->
Sources: normalise must drop tracking query parameters and sort the rest

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_sources_tracking_params.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_sources_tracking_params.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_sources_tracking_params.py =====
import pytest

from life_graph.services.sources import check, normalise, urls_in


@pytest.mark.parametrize(
    ("url", "key"),
    [
        ("https://example.com/a?utm_source=x&id=2", "example.com/a?id=2"),
        ("https://example.com/a?utm_source=x&utm_medium=y", "example.com/a"),
        ("https://example.com/a?UTM_Source=x", "example.com/a"),
        ("https://example.com/a?fbclid=abc#top", "example.com/a"),
        ("https://github.com/o/r?ref=main", "github.com/o/r?ref=main"),
        ("https://example.com/a?q=", "example.com/a?q="),
        ("https://example.com/path?x=1&y=2#frag", "example.com/path?x=1&y=2"),
        ("https://example.com/a%20b", "example.com/a%20b"),
    ],
)
def test_tracking_params_are_ignored(url, key):
    assert normalise(url) == key


def test_query_order_does_not_matter():
    assert normalise("https://example.com/a?b=1&a=2") == "example.com/a?a=2&b=1"
    assert normalise("https://example.com/a?a=2&b=1") == "example.com/a?a=2&b=1"
    assert urls_in("see https://x.com/a?utm_source=t and https://x.com/a") == [
        "https://x.com/a?utm_source=t"
    ]


def test_check_verifies_a_tracked_link():
    outcome = check("Read https://example.com/post?utm_source=news", ["https://example.com/post"])
    assert outcome["verified"] == ["https://example.com/post?utm_source=news"]
    assert outcome["unsourced_urls"] == []
===== end of tests/unit/test_sources_tracking_params.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_sources_tracking_params.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/sources.py (normalise) that makes those cases pass. Read the code first.
1. Add one module-level frozenset of tracking names: fbclid, gclid, dclid, msclkid, mc_cid, mc_eid, igshid, ref_src, si, _hsenc, _hsmi, spm.
2. In normalise, split parts.query on "&". Drop empty pieces and every piece whose name (before "=", lower-cased) starts with "utm_" or is in the set.
3. Sort the remaining pieces as plain strings and join them with "&". Do not decode or re-encode: "a%20b" stays "a%20b".
4. Return host+path as now, plus "?" and the joined query only when something is left. Keep "ref" (GitHub's ?ref=main) and blank values ("q=").
Leave the imports at the top of the file as they are (settings is used by required_for).

STEP 4. Run run_tests with paths ["tests/unit/test_sources_tracking_params.py", "tests/unit/test_sources_normalise.py", "tests/unit/test_sources_check_findings.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_sources_tracking_params.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what normalise did before, in your words>
Change: <what you changed in normalise (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_sources_tracking_params.py or tests/unit/test_sources_normalise.py shows it does not>

Files you may touch:
- life_graph/services/sources.py (normalise)
- tests/unit/test_sources_tracking_params.py (new; created in STEP 1)

Do NOT:
- change check, annotate, urls_in or the notes text;
- change web_pages.py or worker_templates.py (they call normalise and get the fix for free);
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: Tracking parameters are ignored, case-insensitively, and other parameters are kept — test: tests/unit/test_sources_tracking_params.py::test_tracking_params_are_ignored
AC-2: Query parameter order does not matter — test: tests/unit/test_sources_tracking_params.py::test_query_order_does_not_matter
AC-3: A citation with tracking parameters counts as fetched — test: tests/unit/test_sources_tracking_params.py::test_check_verifies_a_tracked_link
AC-4: Existing normalisation is unchanged — test: tests/unit/test_sources_normalise.py::test_normalise_query_and_fragment
**Design:** Filter and sort the raw query pieces inside normalise; no URL re-encoding.
**Tasks:**
1. Create tests/unit/test_sources_tracking_params.py exactly as given, then add the tracking set and the filter/sort to normalise until it and the existing sources tests pass (AC-1, AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->
