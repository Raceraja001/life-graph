import pytest

from life_graph.services.web_pages import SEEN_TTL, mark_seen


class FakeRedis:
    def __init__(self, raise_on_sadd: bool = False):
        self.sadd_calls = []
        self.expire_calls = []
        self.raise_on_sadd = raise_on_sadd

    async def sadd(self, key: str, *urls: str):
        if self.raise_on_sadd:
            raise Exception("sadd failure")
        self.sadd_calls.append((key, list(urls)))

    async def expire(self, key: str, ttl: int):
        self.expire_calls.append((key, ttl))


@pytest.mark.asyncio
async def test_mark_seen_noop_if_no_redis():
    await mark_seen(None, "test-key", ["https://example.com"])


@pytest.mark.asyncio
async def test_mark_seen_noop_if_no_urls():
    fake = FakeRedis()
    await mark_seen(fake, "test-key", [])
    assert not fake.sadd_calls
    assert not fake.expire_calls


@pytest.mark.asyncio
async def test_mark_seen_success_calls():
    fake = FakeRedis()
    urls = ["https://a.com", "https://b.com"]
    await mark_seen(fake, "test-key", urls)
    assert fake.sadd_calls == [("test-key", urls)]
    assert fake.expire_calls == [("test-key", SEEN_TTL)]


@pytest.mark.asyncio
async def test_mark_seen_exception_swallow():
    fake = FakeRedis(raise_on_sadd=True)
    # Should not raise
    await mark_seen(fake, "test-key", ["https://x.com"])
    # No expire should have been called
    assert not fake.expire_calls
