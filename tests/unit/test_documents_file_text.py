import pytest

from life_graph.services.documents import file_text


class DummyClient:
    pass


class DummyDoc:
    def __init__(self, tenant_id, source, fields):
        self.tenant_id = tenant_id
        self.source = source
        self.fields = fields


@pytest.mark.asyncio
async def test_file_text_default_source_and_extract_called(monkeypatch):
    # Arrange
    captured = {}

    async def fake_extract(text, *, client=None, now=None):
        captured["text"] = text
        captured["client"] = client
        return {"kind": "credit_card", "title": "Test"}

    async def fake_create(session, tenant_id, fields, source="api"):
        captured["create_args"] = (tenant_id, fields, source)
        return DummyDoc(tenant_id, source, fields)

    monkeypatch.setattr("life_graph.services.documents.extract", fake_extract)
    monkeypatch.setattr("life_graph.services.documents.create", fake_create)

    # Act
    doc = await file_text(
        session=None,
        tenant_id="tenant1",
        text="sample text",
        client=DummyClient(),
    )

    # Assert
    assert captured["text"] == "sample text"
    assert isinstance(captured["client"], DummyClient)
    assert captured["create_args"] == (
        "tenant1",
        {"kind": "credit_card", "title": "Test"},
        "api",
    )
    assert isinstance(doc, DummyDoc)
    assert doc.tenant_id == "tenant1"
    assert doc.source == "api"
    assert doc.fields == {"kind": "credit_card", "title": "Test"}


@pytest.mark.asyncio
async def test_file_text_overrides_non_empty(monkeypatch):
    # Arrange
    async def fake_extract(text, *, client=None, now=None):
        return {"kind": "credit_card"}

    async def fake_create(session, tenant_id, fields, source="api"):
        return DummyDoc(tenant_id, source, fields)

    monkeypatch.setattr("life_graph.services.documents.extract", fake_extract)
    monkeypatch.setattr("life_graph.services.documents.create", fake_create)

    # Act
    doc = await file_text(
        session=None,
        tenant_id="tenant2",
        text="text",
        overrides={"title": "New Title", "notes": None, "issuer": ""},
    )

    # Assert
    assert doc.fields == {"kind": "credit_card", "title": "New Title"}


@pytest.mark.asyncio
async def test_file_text_custom_source(monkeypatch):
    # Arrange
    async def fake_extract(text, *, client=None, now=None):
        return {"kind": "credit_card"}

    async def fake_create(session, tenant_id, fields, source="api"):
        return DummyDoc(tenant_id, source, fields)

    monkeypatch.setattr("life_graph.services.documents.extract", fake_extract)
    monkeypatch.setattr("life_graph.services.documents.create", fake_create)

    # Act
    doc = await file_text(
        session=None,
        tenant_id="tenant3",
        text="text",
        source="telegram",
    )

    # Assert
    assert doc.source == "telegram"
