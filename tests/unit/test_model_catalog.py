import pytest

from life_graph.services import model_catalog


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class _FakeAsyncClient:
    last_request: dict | None = None
    body: dict = {"data": []}
    raise_on_get: bool = False

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        _FakeAsyncClient.last_request = {"url": url}
        if _FakeAsyncClient.raise_on_get:
            raise RuntimeError("network down")
        return _FakeResponse(_FakeAsyncClient.body)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    model_catalog._CACHE.clear()
    _FakeAsyncClient.body = {"data": []}
    _FakeAsyncClient.raise_on_get = False
    _FakeAsyncClient.last_request = None
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    yield


@pytest.mark.asyncio
async def test_classifies_free_and_paid_from_pricing():
    _FakeAsyncClient.body = {
        "data": [
            {
                "id": "nvidia/nemotron-3-super-120b-a12b:free",
                "name": "Nemotron 3 Super",
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "openai/gpt-5",
                "name": "GPT-5",
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            },
        ]
    }

    models = await model_catalog.get_model_catalog()

    free = next(m for m in models if m["id"] == "openrouter/nvidia/nemotron-3-super-120b-a12b:free")
    paid = next(m for m in models if m["id"] == "openrouter/openai/gpt-5")
    assert free["is_free"] is True
    assert paid["is_free"] is False


@pytest.mark.asyncio
async def test_gemini_fallback_entries_always_present_on_success():
    _FakeAsyncClient.body = {"data": []}

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "gemini/gemini-3.6-flash" in ids
    assert "gemini/gemini-3.5-flash-lite" in ids


@pytest.mark.asyncio
async def test_cache_hit_avoids_second_http_call():
    _FakeAsyncClient.body = {
        "data": [{"id": "a/b", "name": "A B", "pricing": {"prompt": "0", "completion": "0"}}]
    }

    await model_catalog.get_model_catalog()
    assert _FakeAsyncClient.last_request is not None
    _FakeAsyncClient.last_request = None

    await model_catalog.get_model_catalog()
    assert _FakeAsyncClient.last_request is None


@pytest.mark.asyncio
async def test_failure_with_no_prior_cache_returns_fallback():
    _FakeAsyncClient.raise_on_get = True

    models = await model_catalog.get_model_catalog()

    assert models == model_catalog.FALLBACK_MODELS


@pytest.mark.asyncio
async def test_failure_with_prior_cache_returns_stale_cache():
    _FakeAsyncClient.body = {
        "data": [{"id": "a/b", "name": "A B", "pricing": {"prompt": "0", "completion": "0"}}]
    }
    first = await model_catalog.get_model_catalog()

    cached_at, _ = model_catalog._CACHE[model_catalog._CACHE_KEY]
    model_catalog._CACHE[model_catalog._CACHE_KEY] = (
        cached_at - model_catalog._TTL_SECONDS - 1,
        first,
    )
    _FakeAsyncClient.raise_on_get = True

    models = await model_catalog.get_model_catalog()

    assert models == first
