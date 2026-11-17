"""Memory services: what is kept, how it is found, and how it is checked.

- retrieval: memories that answer a question (the relevance judge)
- context: matching memories put in front of Jarvis before it answers
- recall: proactive, push-based recall
- associations, links: links between memories
- tiers: warm and cold memory
- check, page: the owner keeps, drops or fixes what Jarvis noted
- sources: where a memory came from, in words the owner reads
- capture_yield: how much of what was captured became memory
- metamemory: the system's knowledge of its own gaps
- micro_consolidation: post-session cleanup

Grouped here 2026-11-17; they were flat modules in life_graph/services/.
Each old module (services/memory_retrieval.py and the rest) is an alias
of the new module -- the same module object -- for code on other branches.
Nothing is imported here, so importing one submodule loads only that one.
"""
