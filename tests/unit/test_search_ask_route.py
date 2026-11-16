"""POST /search/ask must be served by ask_brain.

From #226 (2026-11-14) until #241 two helper functions sat between the
``@router.post("/ask")`` decorator and ``ask_brain``. The decorator then
registered ``summarize_cross_domain(memories: list)`` as the endpoint: every
ask -- the MCP ``ask`` tool included -- got a 422 "Input should be a valid
list", and nothing but an integration test that CI was skipping noticed.

These read the search router itself: main.py mounts its routers at startup,
so ``app.routes`` is still empty when a unit test imports the app.
"""

from fastapi.routing import APIRoute


def _routes() -> list[APIRoute]:
    from life_graph.api.search import router

    return [r for r in router.routes if isinstance(r, APIRoute)]


def _post_route(path: str) -> APIRoute:
    matches = [r for r in _routes() if r.path == path and "POST" in r.methods]
    assert len(matches) == 1, [m.endpoint.__name__ for m in matches]
    return matches[0]


def test_ask_is_served_by_ask_brain():
    assert _post_route("/search/ask").endpoint.__name__ == "ask_brain"


def test_ask_takes_a_question_object_not_a_list():
    body = _post_route("/search/ask").body_field
    assert body is not None
    assert "question" in body.field_info.annotation.model_fields


def test_the_helpers_are_not_routes():
    endpoints = {r.endpoint.__name__ for r in _routes()}
    assert not endpoints & {
        "summarize_cross_domain",
        "detect_challenge_prompts",
        "detect_knowledge_gaps",
    }
