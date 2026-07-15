"""Ingress + propagation tests for trust tiers.

Covers the capture-spine tier derivation and the guarantee that a client
cannot self-assert a memory's trust tier through the public creation schema.
"""

from __future__ import annotations

import pytest

from life_graph.core.trust import TrustTier
from life_graph.models.schemas import MemoryCreate
from life_graph.services.capture import CaptureService

# ── Bypass closed: trust_tier is not a client-settable memory field ───

def test_memory_create_has_no_client_trust_tier_field():
    """Clients must not be able to self-assert a trusted tier on POST /memories."""
    assert "trust_tier" not in MemoryCreate.model_fields
    # Extra fields are ignored/forbidden — asserting one is silently dropped.
    payload = MemoryCreate(content="x", trust_tier="self")  # type: ignore[call-arg]
    assert not hasattr(payload, "trust_tier")


# ── Capture ingress tier derivation ───────────────────────────────────

class _FakeResult:
    def scalars(self):
        return self

    def first(self):
        return None  # no duplicate


class _FakeSession:
    """Minimal async session stand-in for CaptureService.ingest."""

    def __init__(self):
        self.added = []

    async def execute(self, *_a, **_k):
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.parametrize(
    "surface,expected",
    [
        ("cli", TrustTier.SELF.value),
        ("watcher", TrustTier.EXTERNAL.value),
        ("whatsapp", TrustTier.HOSTILE_POSSIBLE.value),
        ("totally_unknown", TrustTier.EXTERNAL.value),  # default-deny
    ],
)
async def test_ingest_derives_tier_from_surface(surface, expected):
    svc = CaptureService(_FakeSession(), event_bus=None)
    event = await svc.ingest(tenant_id="t1", surface=surface, content="hello")
    assert event.trust_tier == expected


async def test_ingest_explicit_tier_overrides_surface():
    svc = CaptureService(_FakeSession(), event_bus=None)
    # A trusted-looking surface, but caller pins it hostile (e.g. raw web body).
    event = await svc.ingest(
        tenant_id="t1", surface="cli", content="scraped",
        trust_tier=TrustTier.HOSTILE_POSSIBLE,
    )
    assert event.trust_tier == TrustTier.HOSTILE_POSSIBLE.value
