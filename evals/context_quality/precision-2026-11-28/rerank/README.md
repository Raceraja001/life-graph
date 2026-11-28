# Reranker check (2026-11-28)

- candidates_B_C.json: eval run `--arms bge-m3 --experiments B,C` (all 45, no cut) from master c7084395.
- rr_score.py: rescoring with BAAI/bge-reranker-v2-m3 (local, offline) and the cut policies; synthetic dataset only.
- results.json: output. Run: `HF_HUB_OFFLINE=1 python -I rr_score.py ../.. candidates_B_C.json results.json`.

Summary and decision: docs/design/adr-m8-context-reranker.md and the audit §5.1.
