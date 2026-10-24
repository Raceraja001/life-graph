# 09: Sourced answers, ignore tracking parameters

| | |
|---|---|
| Theme | D. Research and pipeline |
| Engine | `code-fixer-local`, `spec_first=True` |
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

Read first:
- life_graph/services/sources.py: normalise, urls_in and check (lines 45-72).
- tests/unit/test_sources_normalise.py and tests/unit/test_sources_check_findings.py (must keep passing unchanged).

Change (life_graph/services/sources.py, normalise only, plus one module-level constant):
1. Split the query on "&". Drop empty pieces, and drop every piece whose name (the part before "=", lower-cased) starts with "utm_" or is one of: fbclid, gclid, dclid, msclkid, mc_cid, mc_eid, igshid, ref_src, si, _hsenc, _hsmi, spm.
2. Sort the remaining pieces as plain strings and join them with "&". Do not decode or re-encode them: "a%20b" stays "a%20b".
3. Return host+path as now, plus "?" and the joined query only when something is left.
Keep "ref" (GitHub uses ?ref=main for a branch) and blank values ("q=").

Cases (copy exactly). normalise(url) ==:
- "https://example.com/a?utm_source=x&id=2" -> "example.com/a?id=2"
- "https://example.com/a?b=1&a=2" -> "example.com/a?a=2&b=1"
- "https://example.com/a?utm_source=x&utm_medium=y" -> "example.com/a"
- "https://example.com/a?UTM_Source=x" -> "example.com/a"
- "https://example.com/a?fbclid=abc#top" -> "example.com/a"
- "https://github.com/o/r?ref=main" -> "github.com/o/r?ref=main"
- "https://example.com/a?q=" -> "example.com/a?q="
- "https://example.com/path?x=1&y=2#frag" -> "example.com/path?x=1&y=2"
- "https://example.com/a%20b" -> "example.com/a%20b"
Also:
- urls_in("see https://x.com/a?utm_source=t and https://x.com/a") returns exactly one URL.
- check("Read https://example.com/post?utm_source=news", ["https://example.com/post"]) has verified == ["https://example.com/post?utm_source=news"] and unsourced_urls == [].

Files you may touch:
- life_graph/services/sources.py (normalise and one new constant)
- tests/unit/test_sources_tracking_params.py (new)

Do NOT:
- change check, annotate, urls_in or the notes text;
- change life_graph/services/web_pages.py or worker_templates.py (they call normalise and get the fix for free);
- edit any existing test file.

## Spec
**Requirements:**
AC-1: Tracking parameters are ignored, case-insensitively, and other parameters are kept — test: tests/unit/test_sources_tracking_params.py::test_tracking_params_are_ignored
AC-2: Query parameter order does not matter — test: tests/unit/test_sources_tracking_params.py::test_query_order_does_not_matter
AC-3: A citation with tracking parameters counts as fetched — test: tests/unit/test_sources_tracking_params.py::test_check_verifies_a_tracked_link
AC-4: Existing normalisation is unchanged — test: tests/unit/test_sources_normalise.py::test_normalise_query_and_fragment
**Design:** Filter and sort the raw query pieces inside normalise; no URL re-encoding.
**Tasks:**
1. Add the tracking-parameter set and the filter/sort to normalise, with tests/unit/test_sources_tracking_params.py holding every case above (AC-1, AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->
