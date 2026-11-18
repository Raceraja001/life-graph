# Coding-engine benchmark

Run `python scripts/bench_drivers.py --engine … --repeat N`. The tasks are in `../driver_tasks.yaml`. Each task runs on a fresh copy of a fixture app. Pass or fail is decided by a **hidden test** written in afterwards and run in the verifier sandbox, never by the engine's own claims.

## 2026-11-18: 10 tasks in 5 categories; claude_code in the task runtime (`20261118T120452Z.json`, `20261118T121045Z.json`)

Work order Stage 5 (`docs/work-orders/secure-execution-runtime.md`).

**Setup:**
- 4 new tasks: `py-bugfix` (two bugs, the tests already failing), `py-refactor` (a rename
  across app and tests, plus an alias), `py-multifile` (a store method and an HTTP route) and
  `py-validate` (edge cases).
- Each new hidden test was checked to FAIL on the starting repo and PASS on a reference fix
  before any engine ran.
- New measurements: the project's own checks (`build_ok_diff` + `tests_pass`) compared with
  the hidden test, runtime duration, peak container CPU and memory, and cost.
- Git SHA and image tags are recorded in each JSON file.
- RTX 5080, WSL2, Docker 29.7.2. Images: driver `life-graph-claude-driver:wo-test`, verifiers
  `life-graph-verifier:wo-test` / `:node-wo-test`. These are test tags built from this branch's
  Dockerfiles.

| Engine | Passed | Own checks agree with hidden test | False positives | Avg s | Cost* | Peak container RAM / CPU |
|---|---|---|---|---|---|---|
| claude_code, task runtime | **10/10**† | 10/10 | 0 | 20 | $0.66 / 10 runs | 173 MiB / 60 % |
| local + `ollama_chat/gpt-oss:20b` (no container) | 9/10 | 10/10 | 0 | 27 | $0 | n/a (in-process) |

| Category | claude_code | gpt-oss:20b |
|---|---|---|
| feature (6) | 6/6 | 6/6 |
| bugfix | 1/1† (and 2/2 on rerun) | 0/1 (and 0/2 on rerun) |
| refactor | 1/1 | 1/1 |
| multi_file | 1/1 | 1/1 |
| edge_cases | 1/1 | 1/1 |

\* What the CLI reports. It runs on the OAuth subscription, not the API budget.

† The first run's `py-bugfix` failed after 7 s with "stream ended without a result" and an
incomplete teardown. That run overlapped `scripts/runtime_reliability.py`, whose workers'
startup sweep removed the benchmark's runtime: the benchmark ran under the same instance
label and had no task row, so its runtime looked orphaned. Scripts now run under their own
instance label. Rerun alone, it passed 2/2 (`20261118T121045Z.json`).

**Findings:**
- **Both engines are reliable on single-file features, refactors and multi-file changes.**
  The gap is the two-bug fix. gpt-oss:20b failed it 3 times out of 3: once with no net change,
  and twice with a shallow copy that the hidden test rejects. Claude Code fixed both bugs every
  time it ran unhindered.
- **The project's own verifier chain never passed wrong work:** 0 false positives in 14 runs.
  On this task set, the checks the dispatcher runs before landing agree with the hidden ground
  truth.
- **Overhead of the task runtime:** about 3 s startup (network, proxy and container; see the
  probe results). The agent container peaks at 173–226 MiB and ~60 % of one CPU against
  4g / 4 CPU limits.
- **Coverage is still small:** 10 tasks, 2 fixture apps, 1 repeat (2 for the bugfix). Treat it
  as a regression baseline, not a capability claim.

## 2026-10-19: free cloud models, 6 tasks × 1 (`20261019T154737Z.json`)

The `cloud` engine is the cloud driver (`drivers/cloud.py`) that `code-fixer-cloud` runs on
while the GPU is busy with speech: OpenRouter `:free` models, failover only to other free models.

| Engine | Passed | Honest* | Avg s | Edits ok / refused |
|---|---|---|---|---|
| cloud + `openrouter/cohere/north-mini-code:free` | **6/6** | 2/6 | **60** | 15 / 0 |
| cloud + `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | **6/6** | 3/6 | 203 | 11 / 3 |

**Findings:**
- **Both wrote correct code on every task.** The low honesty is the driver's verdict, not the
  code: after a correct edit the models kept re-reading or re-checking until loop detection
  stopped them (6 runs "stuck"), or they ran out of rounds (1). One run hit "All models are
  currently unavailable" (free-tier rate limits).
- **North Mini Code is the default** (`dev_cloud_models` order): 5–25 s when it ends cleanly
  and no refused edits. Nemotron is slower (1–5 min per task) and is second.
- `poolside/laguna-s-2.1:free` returned 429 from its provider during setup, so it was not run.

## 2026-10-15: 6 tasks × 2 repeats, RTX 5080 16 GB (`20261015T104039Z.json`)

| Engine | Passed | Honest* | Avg s | Edits ok / refused |
|---|---|---|---|---|
| OpenCode + `ollama/qwen3-coder:30b` | **12/12** | 12/12 | 30 | 12 / 0 |
| local + `ollama_chat/gpt-oss:20b` | **11/12** | 11/12 | **7** | 12 / 1 |
| local + `ollama_chat/qwen3:14b` | 8/12 | 9/12 | 119 | 19 / 41 |
| local + `ollama_chat/qwen2.5-coder:14b` | 0/12 | 12/12 | 4 | 0 / 0 |

\* Honest means the driver's own verdict agreed with the hidden test.

**Findings:**
- **OpenCode with qwen3-coder:30b is the most reliable free engine.** The model does not fit the GPU (18 GB), but OpenCode ran it without stalling WSL.
- **gpt-oss:20b on the local driver fits the GPU, is 17× faster than qwen3:14b, and nearly matches OpenCode.** It is the best default for the local driver.
- **qwen3:14b struggles to reproduce exact text.** 41 of its 60 edits were refused, even with tiered matching; it is the weakest usable choice.
- **qwen2.5-coder:14b made no real tool calls through Ollama.** The driver reported all 12 runs as `no_action`; before 2026-10-15 they would have counted as successes.
