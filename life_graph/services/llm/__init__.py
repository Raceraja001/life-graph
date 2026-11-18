"""Language-model services: which model answers, and whether it is healthy.

- client: the LM Studio + OpenRouter hybrid client (was llm_client)
- resilient: ordered free-model failover with cooldowns (was resilient_llm)
- health: a fail-open record of free-LLM backend health (was llm_health)
- offers: free LLM offers found, evaluated, offered for adoption (was llm_offers)
- model_catalog, model_eval: the OpenRouter catalog; evaluating a model first
- local_runtime, local_model_registry: how local Ollama models are held and measured
- claude_cli_reply: one-shot replies through the Claude CLI
- compute_router: where a queued coding task runs (local GPU or free cloud)

Not to be confused with life_graph.llm (context management, model routing).

Grouped here 2026-11-18; they were flat modules in life_graph/services/.
Each old module is an alias of the new one -- the same module object --
for code on other branches. Nothing is imported here, so importing one
submodule loads only that one.
"""
