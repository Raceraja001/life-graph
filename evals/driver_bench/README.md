# Coding-engine benchmark

Run `python scripts/bench_drivers.py --engine … --repeat N`. The tasks are in `../driver_tasks.yaml`. Each task runs on a fresh copy of a fixture app. Pass or fail is decided by a **hidden test** written in afterwards and run in the verifier sandbox, never by the engine's own claims.

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
