"""Application configuration using Pydantic Settings.

``Settings`` is one class made of per-domain parts (life_graph/config/<domain>.py),
split 2026-11-18 without renaming anything: every field is still
``settings.<name>`` and still read from ``LIFE_GRAPH_<NAME>``. A new setting goes
in the part for its domain; a derived value that reads several domains goes
here on ``Settings``.

Supports multi-tenant SaaS mode with service-to-service auth,
Redis, rate limiting, and environment profiles.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings

from life_graph.config.agents import AgentSettings
from life_graph.config.assistant import AssistantSettings
from life_graph.config.browser import BrowserSettings
from life_graph.config.core import CoreSettings
from life_graph.config.drivers import DriverSettings
from life_graph.config.llm import LLMSettings
from life_graph.config.memory import MemorySettings
from life_graph.config.research import ResearchSettings
from life_graph.config.storage import StorageSettings


class Settings(
    BrowserSettings,
    AssistantSettings,
    AgentSettings,
    DriverSettings,
    ResearchSettings,
    LLMSettings,
    MemorySettings,
    StorageSettings,
    CoreSettings,
    BaseSettings,
):
    """Life Graph application settings.

    All settings can be overridden via environment variables
    prefixed with LIFE_GRAPH_ (e.g., LIFE_GRAPH_DATABASE_URL).
    """

    model_config = {
        "env_prefix": "LIFE_GRAPH_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()


def sqlalchemy_sync_url(url: str) -> str:
    """*url* with the psycopg2 driver named, for a synchronous SQLAlchemy engine.

    SQLAlchemy 2.1 changed what a bare ``postgresql://`` URL means: its
    default driver went from psycopg2 to psycopg (v3). We depend on
    psycopg2-binary, so a fresh install (CI) failed migrations with "No module
    named 'psycopg'" while older local installs worked. Naming the driver
    makes the URL mean the same thing on every SQLAlchemy version. Only for
    SQLAlchemy: plain ``psycopg2.connect`` still wants the bare scheme.
    """
    for bare in ("postgresql://", "postgres://"):
        if url.startswith(bare):
            return "postgresql+psycopg2://" + url[len(bare) :]
    return url
