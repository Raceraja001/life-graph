"""Search synthesis — generate natural language answers from memory search results.

Takes a user question + retrieved memories and produces a coherent,
cited answer using the local LLM via LM Studio.
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.services.llm_client import LMStudioClient
from life_graph.config import settings

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a personal memory assistant. The user has a brain (memory system)
that stores facts, preferences, decisions, and experiences.

Given a question and a set of relevant memories from the brain,
synthesize a clear, natural answer. Follow these rules:

1. Answer ONLY based on the provided memories. Do not hallucinate.
2. If memories don't cover the question, say "I don't have enough memories about this."
3. Reference specific memories naturally (e.g., "You mentioned that...", "Based on your experience with...").
4. Be concise but thorough.
5. If there are contradictions in memories, point them out.
6. Use a warm, assistant-like tone — you're helping the user understand their own knowledge.
"""


class SynthesisService:
    """Generate natural language answers from search results.
    
    Combines retrieved memories with an LLM to produce
    human-readable answers to questions about the user's knowledge.
    """

    def __init__(self, client: LMStudioClient | None = None) -> None:
        self._client = client or LMStudioClient()

    async def synthesize(
        self,
        question: str,
        memories: list[dict[str, Any]],
        *,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generate a synthesized answer from memories.
        
        Args:
            question: The user's natural language question.
            memories: List of memory dicts from search results.
            model: Override the default synthesis model.
            
        Returns:
            Dict with 'answer', 'source_count', and 'model' used.
        """
        if not memories:
            return {
                "answer": "I don't have any memories related to your question.",
                "source_count": 0,
                "model": None,
            }

        # Format memories as context
        context_parts = []
        for i, mem in enumerate(memories, 1):
            content = mem.get("content", "")
            tags = ", ".join(mem.get("tags", []))
            importance = mem.get("importance", 0)
            created = mem.get("created_at", "unknown")
            context_parts.append(
                f"[Memory {i}] (tags: {tags}, importance: {importance:.1f}, date: {created})\n{content}"
            )
        
        context_block = "\n\n".join(context_parts)

        messages = [
            {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"## Memories from my brain:\n\n{context_block}\n\n"
                    f"---\n\n"
                    f"## My question:\n{question}"
                ),
            },
        ]

        # Let the LLM client pick the right model (cloud vs local)
        answer = await self._client.chat(
            messages=messages,
            model=model,  # None = client picks based on hybrid mode
            temperature=0.3,
            max_tokens=1024,
        )

        model_used = model or (
            settings.openrouter_model if settings.use_hybrid_llm
            else settings.lm_synthesis_model
        )

        # Fallback: if LLM is unavailable, build a rule-based answer
        if not answer or not answer.strip():
            logger.warning("LLM unavailable — using rule-based synthesis")
            answer = self._rule_based_answer(question, memories)
            model_used = "rule-based"

        return {
            "answer": answer,
            "source_count": len(memories),
            "model": model_used,
        }

    @staticmethod
    def _rule_based_answer(question: str, memories: list[dict[str, Any]]) -> str:
        """Build a simple answer from memories without LLM."""
        if not memories:
            return "I don't have any memories related to your question."

        parts = [f"Based on {len(memories)} memory/memories in your brain:\n"]
        for i, mem in enumerate(memories[:5], 1):
            content = mem.get("content", "")
            tags = mem.get("tags", [])
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            parts.append(f"  {i}. {content}{tag_str}")

        if len(memories) > 5:
            parts.append(f"\n  ...and {len(memories) - 5} more related memories.")

        return "\n".join(parts)
