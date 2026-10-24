# 10: Tech watch, model sizes in T, M, NxB and E-numbers

| | |
|---|---|
| Theme | D. Research and pipeline |
| Engine | `code-fixer-local`, `spec_first=True` |
| Depends on | none |
| Review | gates |
| Size | ~15 lines in `worker_templates.py`, one new test file |

## Why

The weekly tech watch (Job 10) keeps only open models that fit the 16 GB GPU. When a page does
not state the memory, `services/worker_templates.py::estimated_memory_gb` estimates it from the
parameter count in the title. It only understands "NNB". So a 1-trillion-parameter model has an
unknown size, and unknown is kept, so it is listed as fitting 16 GB. Reproduced on 6459f6b:

```
"Kimi K2 1T"    -> None   (kept as "fits")
"Mixtral 8x7B"  -> None
"Gemma 3n E4B"  -> None
"SmolLM 360M"   -> None
```

## Instruction

<!-- instruction:start -->
Tech watch: estimated_memory_gb must read trillions, millions, NxB mixtures and E-numbers

Read first:
- life_graph/services/worker_templates.py: _GB_PER_BILLION_Q4, _PARAMS, estimated_memory_gb and validate_finding (lines 247-312).

Change (life_graph/services/worker_templates.py, _PARAMS and estimated_memory_gb only, plus at most one new pattern):
1. "NxMB" (e.g. "8x7B", "8 x 22B") counts as N*M billion. Remove such matches from the text before step 2, so their M is not counted again on its own.
2. A single count is a number followed by B (billion), T (trillion = 1000 B) or M (million = 0.001 B), case-insensitive, with an optional space. As now, it must not follow a letter, digit or "." directly, except an optional "E"/"e" prefix ("E4B" counts as 4 B).
3. Take the largest count, times _GB_PER_BILLION_Q4, rounded to 1 decimal, as now. None when there is no count.

Cases (copy exactly). estimated_memory_gb(title) ==:
- "Kimi K2 1T" -> 600.0
- "Kimi K2 1.04T" -> 624.0
- "Mixtral 8x7B" -> 33.6
- "Mixtral 8x22B" -> 105.6
- "Gemma 3n E4B" -> 2.4
- "SmolLM 360M" -> 0.2
- "Qwen3-235B-A22B" -> 141.0
- "Qwen3 30B-A3B" -> 18.0
- "Qwen3-Coder-480B-A35B" -> 288.0
- "gpt-oss-20b" -> 12.0
- "Heron 480B" -> 288.0
- "Phi-4 mini 3.8B" -> 2.3
- "Llama 3.1 8B Instruct" -> 4.8
- "GPT-4 Turbo" -> None
- "no count here" -> None
- "" -> None
- None -> None
And through validate_finding, with today=date(2026, 10, 24), sources={"https://example.com/k2"}, max_memory_gb=16:
- {"title": "Kimi K2 1T open weights", "source": "https://example.com/k2", "published_on": "2026-10-20"} -> None (too big)
- {"title": "Qwen3 8B update", "source": "https://example.com/k2", "published_on": "2026-10-20"} -> a dict whose "title" is "Qwen3 8B update"

Files you may touch:
- life_graph/services/worker_templates.py (_PARAMS, estimated_memory_gb, one new pattern)
- tests/unit/test_estimated_memory_gb.py (new)

Do NOT:
- change validate_finding, validate_offer, topic_reader or the templates;
- change _GB_PER_BILLION_Q4;
- edit tests/unit/test_workers_and_offers.py or any other existing test.

## Spec
**Requirements:**
AC-1: Titles with B, T, M, NxB and E-prefixed counts give the stated estimates; titles without a count give None — test: tests/unit/test_estimated_memory_gb.py::test_estimated_memory_gb
AC-2: A trillion-parameter model is dropped from a 16 GB topic, and a small model is kept — test: tests/unit/test_estimated_memory_gb.py::test_validate_finding_uses_the_estimate
**Design:** One pattern for NxMB, one for single counts with a unit; collect counts in billions, take the max.
**Tasks:**
1. Extend the count patterns and estimated_memory_gb, and add tests/unit/test_estimated_memory_gb.py with the cases above (AC-1, AC-2)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes

- An 8x7B mixture is really ~47 B, not 56 B. The estimate errs high on purpose, which keeps a
  model from being wrongly listed as fitting.
