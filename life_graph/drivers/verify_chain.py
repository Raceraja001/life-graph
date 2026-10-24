"""Which verifiers a dispatch runs: the default diff-scoped chain, the checks
that are always on, the caller > persona > default precedence, and whether a
dispatch runs only on local models (split out of dispatcher.py, 2026-10-25)."""

from __future__ import annotations

from life_graph.config import settings

# Diff-scoped on purpose: the whole-repo variants lint every file in the
# project, so on any codebase with pre-existing debt they fail on files the
# agent never touched. That is not a verdict on the change — it bounced the
# task once (a wasted frontier call) and then escalated to needs_human, every
# time, forever. A verifier chain judges the diff; a persona may ask for
# something stricter via its own verifier_chain.
#
# no_secrets_in_diff and no_vulnerable_deps_in_diff are in the default
# chain, not opt-in like most other checks — see _ALWAYS_ON_CHECKS below,
# which is what actually guarantees they run even for a persona that picks
# its own chain; listed here too so the default chain reads as complete on
# its own.
DEFAULT_VERIFY_CHAIN = [
    "build_ok_diff",
    "lint_clean_diff",
    "no_secrets_in_diff",
    "no_vulnerable_deps_in_diff",
]

# Appended unconditionally in _with_required_checks, after persona/caller
# resolution — a persona picking its own verifier_chain (personas.py has
# several) opts out of the default chain, but must not thereby opt out of
# these. Unlike required_checks these are not project-configurable: there
# is no legitimate reason for any project to dispatch without them.
#
# no_vulnerable_deps_in_diff self-gates (a real pass, not a no-op) unless
# the diff touches a dependency manifest, so it costs nothing on the
# overwhelming majority of dispatches that never touch one.
#
# no_test_weakening likewise passes at once unless an existing test changed.
_ALWAYS_ON_CHECKS = ("no_secrets_in_diff", "no_vulnerable_deps_in_diff", "no_test_weakening")


_LOCAL_MODEL_PREFIXES = ("ollama/", "ollama_chat/")


def _is_local_model(model: str | None) -> bool:
    return bool(model) and model.lower().startswith(_LOCAL_MODEL_PREFIXES)


def runs_on_local_model(driver_name: str, persona_model: str | None) -> bool:
    """True when every model this dispatch could call runs on this machine.

    The Governor's monthly cap is for paid API spend (the user, 2026-10-18:
    "budget cap only for api"). A local run cannot spend money, but it is
    only local if nothing it may fall back to is a paid model, so the agent
    fallback model and the whole fallback chain must be local too. Decided
    from the models, not cost_per_task(): the local driver reports $0 even
    when its persona model is an API model.
    """
    if driver_name == "cloud":
        # Not local, but just as unable to spend: the cloud driver refuses a
        # model that isn't free and fails over only to free ones
        # (drivers/cloud.py).
        from life_graph.services.compute_router import is_free_cloud_model

        return is_free_cloud_model(persona_model)
    if driver_name == "opencode":
        models = [settings.driver_opencode_model]
    elif driver_name == "local":
        models = [
            persona_model or settings.agent_llm_model,
            settings.agent_fallback_model,
            *settings.llm_fallback_chain_list,
        ]
    else:
        return False  # claude_code and the rest call paid APIs
    return all(_is_local_model(m) for m in models if m)


def _with_required_checks(chain: list[str], project_context: dict) -> list[str]:
    """Append the project's required checks (e.g. tests_pass), plus the
    always-on checks, that *chain* lacks.

    A project can require checks for all of its tasks on top of whatever the
    caller or persona asked for. Read from the registry via the packet's
    project context, never from the worktree the agent controls.
    """
    required = [*(project_context.get("required_checks") or []), *_ALWAYS_ON_CHECKS]
    return [*chain, *(c for c in dict.fromkeys(required) if c not in chain)]


def _resolve_verify_chain(caller_chain: list[str] | None, persona) -> list[str]:
    """Precedence: explicit caller argument > persona's own chain > default."""
    if caller_chain is not None:
        return list(caller_chain)
    persona_chain = getattr(persona, "verifier_chain", None) if persona is not None else None
    if persona_chain:
        return list(persona_chain)
    return list(DEFAULT_VERIFY_CHAIN)
