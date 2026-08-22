"""The OpenAPI schema must build.

``app.openapi()`` is the only thing that forces FastAPI to resolve every route
handler's annotations at runtime (via ``get_type_hints``) and to build a
Pydantic schema for each model. Nothing else in the suite does — routes are
exercised through the ASGI transport, which uses already-built validators.

This matters because flake8-type-checking (TC) is now enabled. TC moves
imports into ``if TYPE_CHECKING:`` blocks, which is safe for ordinary type
annotations and unsafe for anything FastAPI or Pydantic resolves at runtime.
Applying it to route-defining modules raised:

    PydanticUserError: `TypeAdapter[Annotated[ForwardRef('AutoFixRequest'),
    ...]]` is not fully defined

so those modules are exempt in pyproject.toml. This test is what makes that
exemption enforceable: move a name a route needs into TYPE_CHECKING and the
build fails here rather than at the first request in production.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def spec() -> dict:
    from life_graph.main import app

    return app.openapi()


def test_openapi_schema_builds(spec):
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"]


def test_all_routes_present(spec):
    """A route whose annotations fail to resolve is dropped or raises."""
    paths = spec["paths"]
    assert len(paths) >= 200, f"expected the full route table, got {len(paths)}"

    methods = {"get", "post", "put", "patch", "delete"}
    operations = sum(len(methods & set(v)) for v in paths.values())
    assert operations >= 240, f"expected ~242 operations, got {operations}"


def test_component_schemas_resolved(spec):
    """Every model referenced by a route resolved to a real schema."""
    schemas = spec.get("components", {}).get("schemas", {})
    assert len(schemas) >= 95, f"expected ~99 component schemas, got {len(schemas)}"

    unresolved = [name for name, s in schemas.items() if not isinstance(s, dict)]
    assert not unresolved, f"unresolved component schemas: {unresolved}"


def test_no_forward_refs_leaked_into_the_spec(spec):
    """A ForwardRef reaching the spec means a name never resolved."""
    import json

    dumped = json.dumps(spec)
    assert "ForwardRef" not in dumped
    assert "is not fully defined" not in dumped


def test_health_documents_the_startup_section(spec):
    """/health reports startup subsystems; the example must say so."""
    example = spec["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"][
        "example"
    ]
    assert "startup" in example["checks"]
    assert "failed" in example["checks"]["startup"]
