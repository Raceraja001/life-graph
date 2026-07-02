# Agent Guidelines

## About the Developer
- Solo developer, values self-hosted solutions and cost efficiency
- Prefers Python (FastAPI) for backend, Next.js for frontend
- Uses Windows, deploys on self-hosted VPS
- Wants to own their toolchain — no vendor lock-in

## Current Project: Life Graph
We are building a brain-inspired, self-hosted personal memory system + AI coding team that:
- Remembers the developer's preferences, coding style, and past decisions permanently
- Uses LiteLLM to route tasks to cheap vs expensive models (saves 60-70% on API costs)
- Is based on a fork of OpenHands + CrewAI multi-agent orchestration
- Uses PostgreSQL (pgvector + Apache AGE) as unified database — NOT ChromaDB
- Minimizes LLM dependency — 85% of operations use rule-based/local models (spaCy, sentence-transformers)
- See KNOWLEDGE.md for full context, decisions, and design rationale

## Rules
- Always read KNOWLEDGE.md at the start of a session for context
- Never ask the developer to re-explain preferences already documented
- Prefer practical solutions over theoretical discussions
- Ask for approval before starting implementation plans
- When building memory features, prefer rule-based/local approaches over LLM calls
- Keep schemas flexible — no hardcoded enums for types or domains
