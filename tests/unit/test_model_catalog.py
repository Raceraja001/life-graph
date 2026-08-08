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
                "architecture": {"modality": "text->text"},
            },
            {
                "id": "openai/gpt-5",
                "name": "GPT-5",
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                "architecture": {"modality": "text->text"},
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
        "data": [
            {
                "id": "a/b",
                "name": "A B",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"modality": "text->text"},
            }
        ]
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
        "data": [
            {
                "id": "a/b",
                "name": "A B",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"modality": "text->text"},
            }
        ]
    }
    first = await model_catalog.get_model_catalog()

    cached_at, _, ttl = model_catalog._CACHE[model_catalog._CACHE_KEY]
    model_catalog._CACHE[model_catalog._CACHE_KEY] = (
        cached_at - ttl - 1,
        first,
        ttl,
    )
    _FakeAsyncClient.raise_on_get = True

    models = await model_catalog.get_model_catalog()

    assert models == first


@pytest.mark.asyncio
async def test_failure_caches_fallback_to_avoid_repeated_timeout():
    """Finding 2: a failure should be negative-cached briefly so a second
    request during the same outage doesn't pay another full HTTP timeout."""
    _FakeAsyncClient.raise_on_get = True

    first = await model_catalog.get_model_catalog()
    assert _FakeAsyncClient.last_request is not None
    _FakeAsyncClient.last_request = None

    second = await model_catalog.get_model_catalog()
    assert _FakeAsyncClient.last_request is None
    assert second == first == model_catalog.FALLBACK_MODELS


@pytest.mark.asyncio
async def test_failure_cache_does_not_clobber_fresh_good_cache():
    """A failure must not shorten the TTL of a still-fresh successful cache
    entry — the top-of-function freshness check returns early before the
    failure path can ever run, so a fresh cache is untouched by a failing
    concurrent/subsequent call once repopulated with real data."""
    _FakeAsyncClient.body = {
        "data": [
            {
                "id": "a/b",
                "name": "A B",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"modality": "text->text"},
            }
        ]
    }
    first = await model_catalog.get_model_catalog()
    _, _, ttl = model_catalog._CACHE[model_catalog._CACHE_KEY]
    assert ttl == model_catalog._TTL_SECONDS

    # A subsequent call within the fresh TTL window must be a pure cache hit
    # and must not touch the network, even though raise_on_get is now True.
    _FakeAsyncClient.raise_on_get = True
    _FakeAsyncClient.last_request = None
    second = await model_catalog.get_model_catalog()

    assert _FakeAsyncClient.last_request is None
    assert second == first
    _, _, ttl_after = model_catalog._CACHE[model_catalog._CACHE_KEY]
    assert ttl_after == model_catalog._TTL_SECONDS


@pytest.mark.asyncio
async def test_malformed_item_missing_id_is_skipped_not_fatal():
    """Finding 1: an entry missing the required 'id' key must not crash the
    whole catalog build — it's skipped, and the call still succeeds (rather
    than raising) by falling through to the Gemini carryover entries."""
    _FakeAsyncClient.body = {"data": [{"name": "no id field"}]}

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "gemini/gemini-3.6-flash" in ids
    assert not any(m["id"].startswith("openrouter/") for m in models)


@pytest.mark.asyncio
async def test_malformed_response_shape_falls_back_to_fallback_models():
    """Finding 1: if the response body is malformed in a way that breaks
    the model-building step itself (here: 'data' is not iterable of dicts),
    get_model_catalog() must degrade to FALLBACK_MODELS instead of raising."""
    _FakeAsyncClient.body = {"data": 42}

    models = await model_catalog.get_model_catalog()

    assert models == model_catalog.FALLBACK_MODELS


@pytest.mark.asyncio
async def test_non_text_output_model_is_excluded():
    """Finding 3: models that don't declare a text-producing modality (e.g.
    image/audio output) must not be selectable in the persona picker."""
    _FakeAsyncClient.body = {
        "data": [
            {
                "id": "openai/gpt-5.4",
                "name": "GPT-5.4",
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                "architecture": {"modality": "text->text"},
            },
            {
                "id": "openai/gpt-5.4-image-2",
                "name": "GPT-5.4 Image",
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                "architecture": {"modality": "text->image"},
            },
        ]
    }

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "openrouter/openai/gpt-5.4" in ids
    assert "openrouter/openai/gpt-5.4-image-2" not in ids


@pytest.mark.asyncio
async def test_model_missing_architecture_field_is_excluded():
    """Finding 3 edge case: no architecture/modality info at all is treated
    conservatively as non-text and excluded."""
    _FakeAsyncClient.body = {
        "data": [
            {
                "id": "vendor/mystery-model",
                "name": "Mystery Model",
                "pricing": {"prompt": "0", "completion": "0"},
            }
        ]
    }

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "openrouter/vendor/mystery-model" not in ids


@pytest.mark.asyncio
async def test_claude_cli_entry_always_present_on_success():
    _FakeAsyncClient.body = {"data": []}

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "claude-cli" in ids
