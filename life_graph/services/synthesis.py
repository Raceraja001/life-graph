"""Search synthesis — generate natural language answers from memory search results.

Takes a user question + retrieved memories and produces a coherent,
cited answer using the local LLM via LM Studio.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from life_graph.config import settings
from life_graph.services.llm_client import LMStudioClient

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[Memory\s+(\d+)\]")


def parse_citations(answer: str, memory_ids: list[str]) -> list[str]:
    """Extract [Memory N] tags from an answer and map them to memory ids.

    N is 1-based and aligns with the order memories were given to the model.
    Out-of-range tags are dropped; ids are returned in first-appearance order,
    deduplicated.
    """
    seen: list[str] = []
    for match in _CITATION_RE.finditer(answer):
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(memory_ids):
            mid = memory_ids[idx]
            if mid not in seen:
                seen.append(mid)
    return seen


def renumber_citations(answer: str, memory_ids: list[str]) -> tuple[str, list[str]]:
    """Rewrite an answer's [Memory K] tags (K 1-based against `memory_ids`,
    the order memories were given to the model) into sequential [Memory J]
    tags matching first-appearance order, and return
    ``(renumbered_answer, ordered_unique_ids)``.

    This is what makes the citation contract 1:1: after renumbering,
    ``[Memory J]`` in the returned answer always refers to
    ``ordered_unique_ids[J-1]`` — no gaps, no dedup mismatches. Without this,
    an answer citing "[Memory 1] ... [Memory 3]" over a 3-memory context
    would carry a *2*-element ids list (deduped, first-appearance order),
    but the raw "[Memory 3]" token stored in the answer text has no matching
    index in that 2-element list.

    Two different K's that resolve to the same memory get the same J.
    K's that don't resolve to any memory (out of range) are stripped —
    a dead citation token is worse than a plain sentence.
    """
    ordered_ids = parse_citations(answer, memory_ids)
    id_to_j = {mid: i + 1 for i, mid in enumerate(ordered_ids)}

    def _replace(match: re.Match[str]) -> str:
        idx = int(match.group(1)) - 1
        mid = memory_ids[idx] if 0 <= idx < len(memory_ids) else None
        j = id_to_j.get(mid) if mid is not None else None
        return f"[Memory {j}]" if j is not None else ""

    renumbered = _CITATION_RE.sub(_replace, answer)
    # Stripped tokens can leave doubled spaces behind (e.g. "Y  Z") — tidy up.
    renumbered = re.sub(r"[ \t]{2,}", " ", renumbered)
    return renumbered, ordered_ids


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
7. When a fact comes from a memory, cite it inline as [Memory N] using that memory's number from the context. Only cite memories you actually used; never invent a number.
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
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate a synthesized answer from memories.

        Args:
            question: The user's natural language question.
            memories: List of memory dicts from search results.
            model: Override the default synthesis model.
            history: Prior chat turns as {"role", "content"} dicts, oldest
                first. Only the last 6 are included in the prompt.

        Returns:
            Dict with 'answer', 'source_count', 'model', and 'citations'.
        """
        if not memories:
            return {
                "answer": "I don't have any memories related to your question.",
                "source_count": 0,
                "model": None,
                "citations": [],
            }

        # Drop memories with no usable id BEFORE numbering — cited_memory_ids
        # is a Postgres UUID array column, so a blank id can never be a valid
        # citation. Filtering here (rather than post-hoc on the returned
        # citations list) keeps the answer's [Memory J] tokens and the
        # returned ids in lockstep: such a memory never gets a number in the
        # first place, so it can never be cited.
        memories = [mem for mem in memories if mem.get("id")]
        if not memories:
            return {
                "answer": "I don't have any memories related to your question.",
                "source_count": 0,
                "model": None,
                "citations": [],
            }

        # Format memories as context
        memory_ids = [str(mem.get("id", "")) for mem in memories]
        context_parts = []
        for i, mem in enumerate(memories, 1):
            content = mem.get("content") or ""
            tags = ", ".join(mem.get("tags") or [])
            importance = mem.get("importance") or 0
            created = mem.get("created_at") or "unknown"
            context_parts.append(
                f"[Memory {i}] (tags: {tags}, importance: {importance:.1f}, date: {created})\n{content}"
            )

        context_block = "\n\n".join(context_parts)

        messages = [{"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-6:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"## Memories from my brain:\n\n{context_block}\n\n"
                    f"---\n\n"
                    f"## My question:\n{question}"
                ),
            }
        )

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

        # Renumber [Memory K] tags to a gap-free 1..M sequence matching
        # `citations`, so `answer`'s [Memory J] <-> citations[J-1] always
        # holds for callers (e.g. the chat citation chips). The rule-based
        # fallback never emits [Memory N] tags, so `citations` is naturally
        # [] and `answer` passes through unchanged on that path.
        answer, citations = renumber_citations(answer, memory_ids)

        return {
            "answer": answer,
            "source_count": len(memories),
            "model": model_used,
            "citations": citations,
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
