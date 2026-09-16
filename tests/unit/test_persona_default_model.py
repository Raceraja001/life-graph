"""Personas must default to the configured model, never a hardcoded id.

Every persona — seeded builtin and user-created — was inserted with a literal
``gemini/gemini-2.5-flash``, a model that 404s for new API keys (see
test_config_model_defaults.py). So a freshly seeded tenant got 13 personas that
could not answer, and on a local-model deployment none of them could ever work.
The orchestrator already falls back to ``settings.agent_llm_model`` when a
persona carries no model, so that is the one default the two should share.
"""

from __future__ import annotations

import pathlib

from life_graph.api.kernel import PersonaCreate
from life_graph.config import settings

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_persona_create_defaults_to_configured_model():
    persona = PersonaCreate(name="analyst", system_prompt="You analyse things.")
    assert persona.model == settings.agent_llm_model


def test_explicit_model_still_wins():
    persona = PersonaCreate(
        name="analyst", system_prompt="You analyse things.", model="ollama_chat/qwen3:4b"
    )
    assert persona.model == "ollama_chat/qwen3:4b"


def test_no_hardcoded_model_ids_in_persona_creation_paths():
    for relative in ("life_graph/kernel/personas.py", "life_graph/api/kernel.py"):
        source = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "gemini/gemini-2.5-flash" not in source, (
            f"{relative} hardcodes a model id; use settings.agent_llm_model so the "
            "deployment's configured model (cloud or local) is what personas get"
        )
