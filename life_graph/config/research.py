"""Web search and research: the advisor, research jobs, the tech watch.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from pydantic import BaseModel


class ResearchSettings(BaseModel):
    """Web search and research: the advisor, research jobs, the tech watch."""

    # ── Personal AI: Advisor ──────────────────────────────────
    advisor_models: str = "openrouter/openai/gpt-4o-mini,openrouter/deepseek/deepseek-chat,openrouter/meta-llama/llama-3.1-8b-instruct"
    advisor_timeout_seconds: int = 10
    advisor_max_cost_per_query: float = 0.01

    # ── Personal AI: Research ────────────────────────────
    research_stale_days: int = 30
    research_max_per_run: int = 5
    research_monthly_budget_usd: float = 0.60
    research_confidence_threshold: float = 0.7

    # ── Tavily (web search tool) ──────────────────────
    tavily_api_key: str = ""  # Set LIFE_GRAPH_TAVILY_API_KEY
    # auto = SearXNG if searxng_url is set, then Tavily if keyed, then the
    # keyless DuckDuckGo HTML endpoint. Or name one: searxng|tavily|duckduckgo.
    web_search_provider: str = "auto"
    searxng_url: str = ""  # e.g. http://localhost:8888 (JSON format enabled)
    web_search_max_results: int = 6
    # Hosts agent fetches may reach even though they resolve to a private
    # address (services/safe_fetch.py). Comma-separated host names.
    fetch_allow_hosts: str = ""
    # Personas whose answers must cite URLs a tool returned in the same run
    # (services/sources.py). Comma-separated persona names.
    require_sources_personas: str = "scout,rex"

    # ── Research jobs and the tech watch (was under Agent Drivers) ──
    # Jobs 6 and 10 (services/web_research.py, docs/specs/research-and-tech-watch.md).
    research_max_pages: int = 5  # result pages read for one question
    research_page_chars: int = 8_000  # text kept per page (all go to one worker)
    # Free cloud models to try first for research workers (comma-separated);
    # only reorders the free cloud list (services/workers.envelope_models).
    research_models: str = ""
    # Tech watch: tenants it runs for (comma-separated; empty = off) and the
    # topics, as JSON: topic name -> list of search queries, or -> {"queries":
    # [...], "kind": "model" | "tool", "max_memory_gb": N} to have findings of
    # another kind, or needing more memory, dropped in code ("{month}" becomes
    # e.g. "October 2026", see services/web_research.dated_queries).
    # "ideas": true makes it a feature-watch topic: results are taken a query
    # at a time (at most 2 pages per site) and each finding is assessed against
    # what Life Graph does (services/feature_ideas.py).
    tech_watch_tenants: str = ""
    tech_watch_topics: str = (
        '{"Open models that fit 16 GB": {"kind": "model", "max_memory_gb": 16, "queries": ['
        '"new open weight model Ollama {month}", '
        '"new small open source LLM release {month}"]}, '
        '"AI coding agents": {"kind": "tool", "queries": ['
        '"AI coding agent new release {month}", '
        '"coding agent CLI new version {month}"]}}'
    )
    tech_watch_max_pages: int = 6  # new pages read per topic per day
    tech_watch_digest_per_topic: int = 6  # findings per topic in the Monday brief

    @property
    def research_models_list(self) -> list[str]:
        """Parse the research workers' preferred free models."""
        return [m.strip() for m in self.research_models.split(",") if m.strip()]

    @property
    def tech_watch_tenants_list(self) -> list[str]:
        """Parse the tenants the tech watch runs for."""
        return [t.strip() for t in self.tech_watch_tenants.split(",") if t.strip()]

    @property
    def tech_watch_topics_map(self) -> dict[str, list[str]]:
        """Parse the tech-watch topics (name -> queries); a bad value means none."""
        return {name: spec["queries"] for name, spec in self.tech_watch_topic_specs.items()}

    @property
    def tech_watch_topic_specs(self) -> dict[str, dict]:
        """Each topic's queries and rules: {"queries", "kind", "max_memory_gb", "ideas"}."""
        import json

        try:
            raw = json.loads(self.tech_watch_topics or "{}")
        except ValueError:
            return {}
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict] = {}
        for name, value in raw.items():
            spec = value if isinstance(value, dict) else {"queries": value}
            queries = spec.get("queries")
            if not str(name).strip() or not isinstance(queries, list):
                continue
            kind = spec.get("kind") if spec.get("kind") in ("model", "tool") else None
            try:
                limit = float(spec["max_memory_gb"]) if spec.get("max_memory_gb") else None
            except (TypeError, ValueError):
                limit = None
            out[str(name).strip()[:120]] = {
                "queries": [str(q).strip() for q in queries if str(q).strip()],
                "kind": kind,
                "max_memory_gb": limit,
                "ideas": spec.get("ideas") is True,
            }
        return out
