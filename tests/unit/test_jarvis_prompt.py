from life_graph.kernel.personas import _BUILTIN_PERSONAS


def _jarvis():
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == "jarvis")


def test_jarvis_prompt_discourages_redundant_delegation():
    sp = _jarvis()["system_prompt"].lower()
    assert "at most once" in sp or "do not delegate to the same" in sp
    assert "named" in sp  # must honor roles the user named


def test_jarvis_still_only_delegates():
    assert _jarvis()["allowed_tools"] == ["delegate_to_persona"]
