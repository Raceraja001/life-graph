"""One tap, one action, once.

A capability used to say "the owner approved a click on this bank, some time
in the next half hour". That is a narrower mandate than an action type alone,
and still not what the owner was shown: the card named one errand, one step of
it, one button and one value, and the capability authorised any step of any
run that happened to be a click on that site. Nor was it spent by being used,
so the same approval could be redeemed twice — or by two workers at once.

So a capability is now bound to the whole identity of the approved action
(``autonomy/approvals/capability.py``):

* ``errand_id`` — the run the owner saw the plan of;
* ``step_index`` — its position in that run, so a re-ordered plan is not it;
* ``target_selector`` — the element, from the engine's own reading of the step;
* ``parameters_hash`` — a digest of the whole action, so an edited value is a
  different action (``browser_errand.canonical_parameters_hash``);

and it is ``one_use``: :meth:`CapabilityStore.consume` spends it in one atomic
step, so a replay and a race both lose.

These tests cover the semantics in memory and then the same semantics in
Postgres, because the durable store is the one that has to hold across
workers — a lock in one process is not an answer to two of them.

The Postgres half needs the ``capabilities`` table (migration 059). Where it
is unreachable those tests say so rather than passing quietly; every property
they check is also checked against the in-process store, which always runs.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from life_graph.autonomy.approvals import capability as cap
from life_graph.autonomy.approvals.capability import CapabilityStore
from life_graph.services import browser_errand as be
from life_graph.services import vault

TENANT = "t1"
OTHER_TENANT = "t2"
BANK = "https://netbanking.hdfcbank.com"
EVIL = "https://evil.io"
ERRAND = "errand_0123456789abcdef"
SELECTOR = "#confirm-transfer"

#: Enough threads to lose a race that is only guarded by a lock, and all of
#: them released at once by a barrier.
RACERS = 16


# ── A browser that is not a browser ──────────────────────────────────────


class FakeBrowser:
    """A :class:`~life_graph.services.browser_errand.BrowserDriver` in a dict."""

    def __init__(self, origin: str = BANK, page: str = "Welcome back.") -> None:
        self.origin = origin
        self.page = page
        self.calls: list[tuple] = []

    async def navigate(self, url: str) -> None:
        self.calls.append(("navigate", url))
        self.origin = vault.normalize_origin(url)

    async def fill_field(self, field: str, value: str) -> None:
        self.calls.append(("fill_field", field))

    async def click(self, selector: str) -> None:
        self.calls.append(("click", selector))

    async def read_page(self) -> str:
        self.calls.append(("read_page",))
        return self.page

    async def current_origin(self) -> str:
        return self.origin

    @property
    def kinds(self) -> list[str]:
        return [c[0] for c in self.calls]


# ── Fixtures ─────────────────────────────────────────────────────────────


def _click_step(selector: str = SELECTOR) -> be.BrowserStep:
    return be.BrowserStep(be.CLICK, selector=selector)


def _bound(store: CapabilityStore, step: be.BrowserStep | None = None, **overrides):
    """A capability bound to one exact click, as tapping Approve mints one."""
    step = step or _click_step()
    params = {
        "tenant_id": TENANT,
        "action_types": ["browser_click", "browser_navigate", "read_page"],
        "target_origins": [BANK],
        "errand_id": ERRAND,
        "approval_id": str(uuid.uuid4()),
        "step_index": 0,
        "target_selector": be.step_target(step),
        "parameters_hash": be.canonical_parameters_hash(step),
        "one_use": True,
    }
    params.update(overrides)
    return store.issue(**params)


def _spend(store: CapabilityStore, capability, step: be.BrowserStep | None = None, **overrides):
    """Present *capability* for the action it was issued for, unless overridden."""
    step = step or _click_step()
    args = {
        "tenant_id": TENANT,
        "errand_id": ERRAND,
        "step_index": 0,
        "target_selector": be.step_target(step),
        "parameters_hash": be.canonical_parameters_hash(step),
    }
    args.update(overrides)
    return store.consume(capability.capability_id, **args)


@pytest.fixture
def store() -> CapabilityStore:
    """A store of its own: module state shared between tests is a flaky test."""
    return CapabilityStore()


# ── What the digest covers ───────────────────────────────────────────────


def test_the_digest_changes_with_every_part_of_the_action():
    """Each field the owner was shown moves the digest. None of them is the value."""
    base = be.BrowserStep(be.CLICK, selector="#pay")
    same = be.BrowserStep(be.CLICK, selector="#pay")
    assert be.canonical_parameters_hash(base) == be.canonical_parameters_hash(same)

    different = [
        be.BrowserStep(be.CLICK, selector="#pay-now"),  # another button
        be.BrowserStep(be.FILL_FIELD, field="#pay"),  # another kind of action
        be.BrowserStep(be.CLICK, selector="#pay", value="1"),  # another value
        be.BrowserStep(be.CLICK, selector="#pay", url=BANK),  # another destination
    ]
    digests = {be.canonical_parameters_hash(s) for s in [base, *different]}
    assert len(digests) == len(different) + 1

    # A digest, not a transcript: nothing typed is recoverable from it.
    typed = be.BrowserStep(be.FILL_FIELD, field="amount", value="250000")
    assert "250000" not in be.canonical_parameters_hash(typed)
    assert len(be.canonical_parameters_hash(typed)) == 64


def test_a_fill_and_a_click_on_the_same_name_are_not_the_same_target():
    """``step_target`` reads whichever field the plan used, and the kind separates them."""
    assert be.step_target(be.BrowserStep(be.CLICK, selector="#go")) == "#go"
    assert be.step_target(be.BrowserStep(be.FILL_FIELD, field="#go")) == "#go"
    assert be.step_target(be.BrowserStep(be.READ_PAGE)) is None
    assert be.canonical_parameters_hash(
        be.BrowserStep(be.CLICK, selector="#go")
    ) != be.canonical_parameters_hash(be.BrowserStep(be.FILL_FIELD, field="#go"))


# ── Every binding is its own refusal ─────────────────────────────────────


def test_the_approved_action_is_what_the_capability_spends_on(store):
    """The baseline the mismatches below are departures from."""
    capability = _bound(store)

    spent, check = _spend(store, capability)

    assert check.ok and check.reason == cap.VALID
    assert spent is not None and spent.consumed_at is not None


@pytest.mark.parametrize(
    ("presented", "reason"),
    [
        ({"errand_id": "errand_a-different-run"}, cap.ERRAND_MISMATCH),
        # A plan whose steps moved after the card was written.
        ({"step_index": 1}, cap.STEP_MISMATCH),
        ({"target_selector": "#transfer-everything"}, cap.SELECTOR_MISMATCH),
        ({"parameters_hash": "0" * 64}, cap.PARAMETERS_MISMATCH),
        ({"tenant_id": OTHER_TENANT}, cap.TENANT_MISMATCH),
        # Not asserting a binding the record carries is a mismatch, not a pass:
        # a caller that cannot say which step it is on may not spend this.
        ({"errand_id": None}, cap.ERRAND_MISMATCH),
        ({"step_index": None}, cap.STEP_MISMATCH),
        ({"target_selector": None}, cap.SELECTOR_MISMATCH),
        ({"parameters_hash": None}, cap.PARAMETERS_MISMATCH),
    ],
)
def test_one_wrong_binding_refuses_and_names_itself(store, presented, reason):
    capability = _bound(store)

    refused, check = _spend(store, capability, **presented)

    assert not check.ok
    assert check.reason == reason
    # And the refusal did not burn the approval: the real step can still run.
    assert store.get(capability.capability_id).consumed_at is None
    if reason != cap.TENANT_MISMATCH:
        assert refused is not None
    assert _spend(store, capability)[1].ok


def test_an_edited_value_invalidates_the_approval(store):
    """What the owner approved was the amount on the card, not the field."""
    approved = be.BrowserStep(be.FILL_FIELD, field="amount", value="500")
    capability = _bound(store, approved, action_types=["browser_fill_field"])
    edited = be.BrowserStep(be.FILL_FIELD, field="amount", value="500000")

    _refused, check = _spend(store, capability, edited)

    assert check.reason == cap.PARAMETERS_MISMATCH


def test_a_forged_handle_spends_nothing(store):
    """The only thing a page can actually do: invent an id."""
    assert _spend(store, _Fake("cap_the-owner-approved-this"))[1].reason == cap.UNKNOWN
    assert store.consume(None, tenant_id=TENANT)[1].reason == cap.UNKNOWN
    assert store.consume("", tenant_id=TENANT)[1].reason == cap.UNKNOWN


class _Fake:
    """Something with a ``capability_id`` that no store ever issued."""

    def __init__(self, capability_id: str) -> None:
        self.capability_id = capability_id


def test_a_revoked_or_expired_capability_fails_closed(store):
    revoked = _bound(store)
    store.revoke(revoked.capability_id)
    assert _spend(store, revoked)[1].reason == cap.REVOKED

    stale = _bound(store, ttl=timedelta(minutes=1), now=datetime.now(UTC) - timedelta(hours=2))
    assert _spend(store, stale)[1].reason == cap.EXPIRED

    # Revocation is checked before consumption, so a kill switch during a run
    # reads as "the owner stopped this" and not as "this was already used".
    live = _bound(store)
    store.revoke(live.capability_id)
    assert _spend(store, live)[1].reason == cap.REVOKED


def test_one_tenants_approval_cannot_be_spent_by_another(store):
    """Even with every other binding right, and even reading it back."""
    capability = _bound(store)

    assert _spend(store, capability, tenant_id=OTHER_TENANT)[1].reason == cap.TENANT_MISMATCH
    assert _spend(store, capability, tenant_id="")[1].reason == cap.TENANT_MISMATCH
    assert store.get(capability.capability_id).consumed_at is None


# ── One use, atomically ──────────────────────────────────────────────────


def test_a_spent_capability_cannot_be_spent_again(store):
    capability = _bound(store)

    first = _spend(store, capability)
    second = _spend(store, capability)

    assert first[1].ok
    assert not second[1].ok
    assert second[1].reason == cap.ALREADY_CONSUMED
    # The record says when, once, and the second attempt did not move it.
    assert second[0].consumed_at == first[0].consumed_at


def test_a_spent_capability_authorises_nothing_further(store):
    """Not only ``consume``: the ordinary check refuses it too."""
    capability = _bound(store)
    _spend(store, capability)

    _cap, check = store.verify(
        capability.capability_id,
        tenant_id=TENANT,
        action_type="browser_click",
        target_origin=BANK,
        errand_id=ERRAND,
        step_index=0,
        target_selector=SELECTOR,
        parameters_hash=be.canonical_parameters_hash(_click_step()),
    )

    assert not check.ok and check.reason == cap.ALREADY_CONSUMED


def test_a_reusable_capability_is_not_spent_by_being_used(store):
    """``one_use=False`` exists so revocation can be tested, and says so."""
    capability = _bound(store, one_use=False)

    assert _spend(store, capability)[1].ok
    assert _spend(store, capability)[1].ok
    assert store.get(capability.capability_id).consumed_at is None


def test_exactly_one_of_sixteen_racing_callers_spends_it(store):
    """A replay is one worker arriving late; a race is two arriving together.

    All sixteen threads are held at a barrier and released into ``consume``
    at once, so the check and the write have to be one step. If they were
    two, more than one caller would see ``consumed_at IS NULL``.
    """
    capability = _bound(store)
    gate = threading.Barrier(RACERS)
    outcomes: list[cap.CapabilityCheck] = []
    lock = threading.Lock()

    def race() -> None:
        gate.wait()
        check = _spend(store, capability)[1]
        with lock:
            outcomes.append(check)

    threads = [threading.Thread(target=race) for _ in range(RACERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(outcomes) == RACERS
    assert sum(1 for o in outcomes if o.ok) == 1
    assert {o.reason for o in outcomes if not o.ok} == {cap.ALREADY_CONSUMED}


# ── Through the engine: the replay a real errand would attempt ───────────


def _errand(
    capability_id: str, *steps: be.BrowserStep, errand_id: str = ERRAND
) -> be.BrowserErrand:
    return be.BrowserErrand(steps=steps, capability_id=capability_id, id=errand_id)


@pytest.mark.asyncio
async def test_an_approved_click_runs_once_and_the_replay_is_refused(store):
    """The whole point, through the executor that performs the click.

    The second run is the same plan, the same errand id and the same handle —
    which is exactly what a model re-calling the tool would send, and exactly
    what an attacker who lifted the handle would send. It does not reach the
    page.
    """
    step = _click_step()
    capability = _bound(store)

    first = await be.run_errand(
        FakeBrowser(), _errand(capability.capability_id, step), tenant_id=TENANT, capabilities=store
    )
    replayed = FakeBrowser()
    second = await be.run_errand(
        replayed, _errand(capability.capability_id, step), tenant_id=TENANT, capabilities=store
    )

    assert first.status == be.DONE
    assert second.status == be.DENIED
    assert second.steps[0].reasons == (cap.ALREADY_CONSUMED,)
    assert replayed.calls == []


@pytest.mark.asyncio
async def test_an_approval_from_one_run_does_not_authorise_another(store):
    """A second plan ending in the same click on the same site is not the same action."""
    step = _click_step()
    capability = _bound(store)
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand(capability.capability_id, step, errand_id="errand_a-second-plan"),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.status == be.DENIED
    assert result.steps[0].reasons == (cap.ERRAND_MISMATCH,)
    assert browser.calls == []
    # Unspent: the run it was approved for can still have it.
    assert store.get(capability.capability_id).consumed_at is None


@pytest.mark.asyncio
async def test_an_approval_does_not_travel_to_a_different_step_of_the_same_run(store):
    """The owner approved step 0. The same button at step 1 is not covered."""
    step = _click_step()
    capability = _bound(store)
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand(capability.capability_id, be.BrowserStep(be.READ_PAGE), step),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.steps[0].status == be.DONE  # read_page needs no mandate
    assert result.steps[1].status == be.DENIED
    assert result.steps[1].reasons == (cap.STEP_MISMATCH,)
    assert "click" not in browser.kinds


@pytest.mark.asyncio
async def test_a_repointed_selector_invalidates_the_approval(store):
    """The card named a button. A plan that now presses a different one is refused."""
    capability = _bound(store, _click_step("#next"))
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand(capability.capability_id, _click_step("#pay-now")),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.status == be.DENIED
    # The selector moves the digest too, so either binding may be the one that
    # names the refusal; both are a refusal of the same substitution.
    assert result.steps[0].reasons[0] in {cap.SELECTOR_MISMATCH, cap.PARAMETERS_MISMATCH}
    assert "click" not in browser.kinds


@pytest.mark.asyncio
async def test_reading_and_navigating_acquire_no_side_effect_authority(store):
    """A read-only errand runs with no capability at all, and spends none.

    The separation requirement: read-only work must not need side-effect
    authority, and must not be a way to get some.
    """
    capability = _bound(store)
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand(
            capability.capability_id,
            be.BrowserStep(be.NAVIGATE, url=f"{BANK}/statements"),
            be.BrowserStep(be.READ_PAGE),
        ),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.status == be.DONE
    assert browser.kinds == ["navigate", "read_page"]
    # Nothing was spent, so the click the owner actually approved still can be.
    assert store.get(capability.capability_id).consumed_at is None
    assert _spend(store, capability)[1].ok

    # And with no handle at all, the same two steps still run.
    plain = FakeBrowser()
    assert (
        await be.run_errand(
            plain,
            be.BrowserErrand(steps=(be.BrowserStep(be.READ_PAGE),), id=ERRAND),
            tenant_id=TENANT,
            capabilities=store,
        )
    ).status == be.DONE
    assert plain.kinds == ["read_page"]


@pytest.mark.asyncio
async def test_a_spent_approval_still_lets_the_errand_read_the_page_it_landed_on(store):
    """Spending the one approval must not break the rest of its own errand.

    Otherwise the useful errand — click Download, then read what came back —
    would fail after doing the irreversible part, which is the worst half to
    succeed at.
    """
    capability = _bound(store)
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand(capability.capability_id, _click_step(), be.BrowserStep(be.READ_PAGE)),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.status == be.DONE
    assert browser.kinds == ["click", "read_page"]


@pytest.mark.asyncio
async def test_the_approval_is_spent_before_the_page_is_touched(store):
    """A step that fails after consuming does not hand the approval back.

    The browser raising is not evidence the click did not land — the request
    may have reached the bank and the response may have been what was lost. So
    the mandate is already spent, and a retry needs the owner again.
    """

    class Breaking(FakeBrowser):
        async def click(self, selector: str) -> None:
            self.calls.append(("click", selector))
            raise RuntimeError("the page went away")

    capability = _bound(store)
    result = await be.run_errand(
        Breaking(),
        _errand(capability.capability_id, _click_step()),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.status == be.FAILED
    assert store.get(capability.capability_id).consumed_at is not None
    assert _spend(store, capability)[1].reason == cap.ALREADY_CONSUMED


@pytest.mark.asyncio
async def test_a_click_the_owner_asked_for_spends_no_capability(store):
    """There is no mandate to consume when the authority is the owner's own request.

    Consuming only happens when the verdict actually rested on a capability
    (``PolicyDecision.capability_id``), so an errand the owner asked for
    directly is not quietly turned into a one-shot — and an unrelated live
    capability of theirs is not spent by it either.
    """
    untouched = _bound(store)
    browser = FakeBrowser()
    result = await be.run_errand(
        browser,
        be.BrowserErrand(
            steps=(_click_step(),),
            owner_request=be.errand_mandate(["browser_click"], [BANK]),
            id=ERRAND,
        ),
        tenant_id=TENANT,
        capabilities=store,
    )

    assert result.status == be.DONE
    assert result.steps[0].reasons == ("owner_asked_for_this_action",)
    assert ("click", SELECTOR) in browser.calls
    assert store.get(untouched.capability_id).consumed_at is None


@pytest.mark.asyncio
async def test_the_consume_gate_refuses_even_when_the_policy_was_fooled(store):
    """The atomic gate is load-bearing on its own, not only as a second opinion.

    The policy check and the consume read the same record, so in ordinary
    running the policy catches a replay first (the test above). This stands in
    a store whose *verify* always says yes — the shape of a checker that was
    somehow talked into an ALLOW — and shows the click still does not happen,
    because what performs the action is the consume and not the verdict.
    """

    class CredulousStore(CapabilityStore):
        def verify(self, capability_id, **kw):  # noqa: ANN001, ANN003
            return self.get(capability_id), cap.CapabilityCheck(True, cap.VALID)

    credulous = CredulousStore()
    capability = _bound(credulous)
    _spend(credulous, capability)  # already redeemed
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand(capability.capability_id, _click_step()),
        tenant_id=TENANT,
        capabilities=credulous,
    )

    assert result.status == be.DENIED
    assert result.steps[0].reasons == (cap.ALREADY_CONSUMED,)
    assert result.steps[0].detail == be.CAPABILITY_NOT_CONSUMED
    assert browser.calls == []


# ── The approval card, and what a tap may widen ──────────────────────────


def _card(**meta):
    """An errand approval card as ``tools/errand.py`` writes one."""
    from types import SimpleNamespace

    from life_graph.tools import errand

    step = _click_step()
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_type=errand.APPROVAL_SOURCE,
        title=f"Approval needed: click on {BANK}",
        created_at=datetime.now(UTC),
        is_read=False,
        extra_metadata={
            "item": errand.APPROVAL_SOURCE,
            "item_id": ERRAND,
            "step_index": 0,
            "action_type": "browser_click",
            "target_origin": BANK,
            "target_selector": be.step_target(step),
            "parameters_hash": be.canonical_parameters_hash(step),
            "goal": "download the statement",
            **meta,
        },
    )


async def _tap(card, action: str) -> str:
    from zoneinfo import ZoneInfo

    from life_graph.services.notifications import actions as na
    from tests.unit.fakes import FakeSession

    return await na.perform(
        FakeSession(), TENANT, card, action, datetime.now(UTC), ZoneInfo("Asia/Kolkata")
    )


@pytest.fixture
def owner_tenant(monkeypatch):
    """The owner's own tenant, and a process store nothing leaks between tests."""
    from life_graph.autonomy.approvals import capability_store
    from life_graph.config import settings
    from life_graph.core.tenant import tenant_scope

    monkeypatch.setattr(settings, "tool_privileged_tenants", TENANT, raising=False)
    capability_store.clear()
    with tenant_scope(TENANT):
        yield capability_store
    capability_store.clear()


@pytest.mark.asyncio
async def test_approving_mints_a_capability_bound_to_that_one_step(owner_tenant):
    """Every binding on the card, and nothing wider."""
    card = _card()

    await _tap(card, "approve")

    capability = owner_tenant.get(card.extra_metadata["capability_id"])
    assert capability is not None
    assert capability.tenant_id == TENANT
    assert capability.errand_id == ERRAND
    assert capability.step_index == 0
    assert capability.target_selector == SELECTOR
    assert capability.parameters_hash == be.canonical_parameters_hash(_click_step())
    assert capability.approval_id == str(card.id)
    assert capability.one_use is True
    assert capability.consumed_at is None
    # Still the narrow action-type and origin scope it always had.
    assert capability.authorizes("browser_click", BANK)
    assert not capability.authorizes("browser_click", EVIL)
    assert not capability.authorizes("browser_fill_secret", BANK)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["item_id", "step_index", "action_type", "target_origin"])
async def test_a_card_that_cannot_name_the_action_is_refused_not_widened(owner_tenant, missing):
    """Tampering with the payload buys a refusal, never a broader mandate.

    A capability with nothing to pin it to one action is not what the card
    described, so the tap mints nothing at all.
    """
    from life_graph.services.notifications import actions as na

    card = _card(**{missing: None})

    with pytest.raises(na.ActionRefusedError):
        await _tap(card, "approve")

    assert "capability_id" not in card.extra_metadata


@pytest.mark.asyncio
async def test_a_tampered_step_index_binds_to_the_tampered_step_and_not_the_real_one(owner_tenant):
    """A payload may lie about which step it is; it cannot lie its way to the step.

    The card is the server's own writing, so this is the shape of an attacker
    who reached the metadata. Claiming step 4 produces a mandate for step 4 —
    which the engine, holding the real step, will not present.
    """
    card = _card(step_index=4)

    await _tap(card, "approve")
    capability = owner_tenant.get(card.extra_metadata["capability_id"])

    assert capability.step_index == 4
    assert _spend(owner_tenant, capability, step_index=0)[1].reason == cap.STEP_MISMATCH
    assert _spend(owner_tenant, capability, step_index=4)[1].ok


# ── The same semantics, in Postgres ──────────────────────────────────────
#
# A lock in one process is not an answer to two of them. These run the
# in-memory properties again against the ``capabilities`` table (migration
# 059), where the deciding is done by one conditional UPDATE … RETURNING.


def _postgres_available() -> bool:
    from life_graph.autonomy.approvals.durable_store import sync_engine

    try:
        with sync_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM capabilities LIMIT 1"))
    except Exception:
        return False
    return True


_POSTGRES_AVAILABLE = _postgres_available()

# CI's integration job sets this when it runs this file against its migrated
# test database. There a missing table is a broken setup, not a reason to
# skip, and a skip would report the Postgres half as green without running it.
if not _POSTGRES_AVAILABLE and os.environ.get("LIFE_GRAPH_REQUIRE_POSTGRES_TESTS") == "1":
    raise RuntimeError(
        "LIFE_GRAPH_REQUIRE_POSTGRES_TESTS=1 but the capabilities table is not "
        "reachable; run the migrations (python -m alembic upgrade head) first"
    )

requires_postgres = pytest.mark.skipif(
    not _POSTGRES_AVAILABLE,
    reason=(
        "needs the capabilities table from migration 059 "
        "(python -m alembic upgrade head). The same properties are checked "
        "against the in-process store above, which always runs."
    ),
)

#: A tenant of this test file's own, so a run never touches real rows and the
#: cleanup below can be a tenant-scoped DELETE rather than a TRUNCATE.
DB_TENANT = f"t_capbind_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def durable():
    """A :class:`CapabilityStore` writing through to Postgres.

    Its own engine with room for :data:`RACERS` connections, because the
    concurrency test below really does want sixteen at once rather than
    sixteen queued behind a pool of two.
    """
    from sqlalchemy import create_engine

    from life_graph.autonomy.approvals.durable_store import DurableCapabilityStore
    from life_graph.config import settings, sqlalchemy_sync_url

    # The same driver-naming the app's own sync_engine() uses: on SQLAlchemy
    # 2.1 a bare postgresql:// URL means psycopg (v3), which is not installed.
    # Unnoticed until CI first ran these tests against a real database.
    engine = create_engine(
        sqlalchemy_sync_url(settings.database_url_sync),
        pool_size=RACERS + 4,
        max_overflow=4,
        future=True,
    )

    def wipe() -> None:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM capabilities WHERE tenant_id = :t"), {"t": DB_TENANT})

    wipe()
    store = CapabilityStore(durable=DurableCapabilityStore(engine))
    try:
        yield store
    finally:
        wipe()
        engine.dispose()


def _db_bound(store: CapabilityStore, step: be.BrowserStep | None = None, **overrides):
    overrides.setdefault("tenant_id", DB_TENANT)
    return _bound(store, step, **overrides)


def _db_spend(store: CapabilityStore, capability, step=None, **overrides):
    overrides.setdefault("tenant_id", DB_TENANT)
    return _spend(store, capability, step, **overrides)


@requires_postgres
def test_a_durable_capability_survives_the_store_that_issued_it(durable):
    """Restart persistence: a new store object finds the same record.

    This is what the in-memory store could not do, and why the approval queue
    needed a table: the API process mints the mandate when the owner taps
    Approve, and an ARQ worker is the one that resumes the errand.
    """
    from life_graph.autonomy.approvals.durable_store import DurableCapabilityStore

    capability = _db_bound(durable)

    # A different store object, standing in for a different worker.
    worker = CapabilityStore(durable=DurableCapabilityStore(durable.durable.engine))
    found = worker.get(capability.capability_id)

    assert found is not None
    assert found.capability_id == capability.capability_id
    assert found.tenant_id == DB_TENANT
    assert found.errand_id == ERRAND
    assert found.step_index == 0
    assert found.target_selector == SELECTOR
    assert found.parameters_hash == capability.parameters_hash
    assert found.action_types == capability.action_types
    assert found.target_origins == capability.target_origins
    assert found.one_use is True
    assert found.consumed_at is None
    assert found.expires_at == capability.expires_at


@requires_postgres
def test_a_durable_capability_is_spent_once_and_the_other_worker_is_told_why(durable):
    from life_graph.autonomy.approvals.durable_store import DurableCapabilityStore

    capability = _db_bound(durable)
    worker = CapabilityStore(durable=DurableCapabilityStore(durable.durable.engine))

    first = _db_spend(durable, capability)
    second = _db_spend(worker, capability)

    assert first[1].ok
    assert second[1].reason == cap.ALREADY_CONSUMED
    assert second[0].consumed_at == first[0].consumed_at


@requires_postgres
@pytest.mark.parametrize(
    ("presented", "reason"),
    [
        ({"errand_id": "errand_a-different-run"}, cap.ERRAND_MISMATCH),
        ({"step_index": 1}, cap.STEP_MISMATCH),
        ({"target_selector": "#transfer-everything"}, cap.SELECTOR_MISMATCH),
        ({"parameters_hash": "0" * 64}, cap.PARAMETERS_MISMATCH),
        ({"errand_id": None}, cap.ERRAND_MISMATCH),
        ({"step_index": None}, cap.STEP_MISMATCH),
    ],
)
def test_the_durable_bindings_refuse_exactly_as_the_in_memory_ones_do(durable, presented, reason):
    """The UPDATE's WHERE clause and ``check_bindings`` have to agree."""
    capability = _db_bound(durable)

    refused, check = _db_spend(durable, capability, **presented)

    assert not check.ok and check.reason == reason
    assert refused is not None
    assert durable.get(capability.capability_id).consumed_at is None
    assert _db_spend(durable, capability)[1].ok


@requires_postgres
def test_one_tenants_durable_approval_is_invisible_to_another(durable):
    """Tenant-scoped in the statement, not in the caller."""
    capability = _db_bound(durable)

    assert _db_spend(durable, capability, tenant_id=OTHER_TENANT)[1].reason == cap.TENANT_MISMATCH
    assert durable.get(capability.capability_id).consumed_at is None
    # And the row is not reachable by a revoke-all for the other tenant.
    assert durable.revoke_all(tenant_id=OTHER_TENANT) == 0
    assert durable.get(capability.capability_id).revoked is False


@requires_postgres
def test_revoking_and_expiry_fail_closed_in_the_table(durable):
    revoked = _db_bound(durable)
    assert durable.revoke(revoked.capability_id) is True
    # Conditional, so a second kill-switch tap reports one revocation.
    assert durable.revoke(revoked.capability_id) is False
    assert _db_spend(durable, revoked)[1].reason == cap.REVOKED

    stale = _db_bound(durable, ttl=timedelta(minutes=1), now=datetime.now(UTC) - timedelta(hours=2))
    assert _db_spend(durable, stale)[1].reason == cap.EXPIRED

    live = _db_bound(durable, task_id="task-7")
    assert durable.revoke_all(tenant_id=DB_TENANT, task_id="task-7") == 1
    assert _db_spend(durable, live)[1].reason == cap.REVOKED


@requires_postgres
def test_expired_rows_are_purged_without_changing_a_decision(durable):
    stale = _db_bound(durable, ttl=timedelta(minutes=1), now=datetime.now(UTC) - timedelta(hours=2))
    live = _db_bound(durable)

    assert durable.purge_expired() >= 1

    assert durable.get(stale.capability_id) is None
    assert _db_spend(durable, stale)[1].reason == cap.UNKNOWN  # same denial, different reason
    assert durable.get(live.capability_id) is not None


@requires_postgres
def test_exactly_one_of_sixteen_workers_spends_a_durable_capability(durable):
    """Multi-worker consistency, which is the whole reason for the table.

    Sixteen threads, each with its own store object over the same table, all
    released at once. Postgres decides, once: the conditional UPDATE matches a
    row only while ``consumed_at IS NULL``, so fifteen get nothing back.
    """
    from life_graph.autonomy.approvals.durable_store import DurableCapabilityStore

    capability = _db_bound(durable)
    engine = durable.durable.engine
    workers = [CapabilityStore(durable=DurableCapabilityStore(engine)) for _ in range(RACERS)]
    gate = threading.Barrier(RACERS)
    outcomes: list[cap.CapabilityCheck] = []
    lock = threading.Lock()

    def race(worker: CapabilityStore) -> None:
        gate.wait()
        check = _db_spend(worker, capability)[1]
        with lock:
            outcomes.append(check)

    threads = [threading.Thread(target=race, args=(w,)) for w in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert len(outcomes) == RACERS
    assert sum(1 for o in outcomes if o.ok) == 1
    assert {o.reason for o in outcomes if not o.ok} == {cap.ALREADY_CONSUMED}
    assert durable.get(capability.capability_id).consumed_at is not None


@requires_postgres
def test_a_duplicate_capability_id_cannot_be_inserted(durable):
    """The unique index is what makes the consuming UPDATE touch one row."""
    from life_graph.autonomy.approvals.durable_store import StoreUnavailableError

    capability = _db_bound(durable)

    with pytest.raises(StoreUnavailableError):
        durable.durable.insert(capability)


# ── When the table cannot be reached ─────────────────────────────────────


@pytest.fixture
def unreachable():
    """A durable store pointed at a database that is not there."""
    from sqlalchemy import create_engine

    from life_graph.autonomy.approvals.durable_store import DurableCapabilityStore

    engine = create_engine(
        "postgresql+psycopg2://nobody:nobody@127.0.0.1:1/does_not_exist",
        connect_args={"connect_timeout": 1},
        future=True,
    )
    store = CapabilityStore(durable=DurableCapabilityStore(engine))
    try:
        yield store
    finally:
        engine.dispose()


def test_issuing_against_an_unreachable_store_raises_rather_than_pretending(unreachable):
    """An id no worker can resolve would tell the owner their tap worked."""
    from life_graph.autonomy.approvals.durable_store import StoreUnavailableError

    with pytest.raises(StoreUnavailableError):
        _bound(unreachable, tenant_id=DB_TENANT)


def test_reading_and_consuming_against_an_unreachable_store_deny(unreachable):
    """Denials, not exceptions: a blip aborts a step, not a process."""
    assert unreachable.get("cap_whatever") is None

    _cap, check = unreachable.consume(
        "cap_whatever",
        tenant_id=DB_TENANT,
        errand_id=ERRAND,
        step_index=0,
        target_selector=SELECTOR,
        parameters_hash="0" * 64,
    )
    assert not check.ok
    assert check.reason == cap.STORE_UNAVAILABLE
    assert check.reason in cap.CHECK_REASONS


def test_revoking_against_an_unreachable_store_raises_rather_than_reporting_nothing(
    unreachable,
):
    """M1 (audit 2026-11-19): ``revoke`` returned False and ``revoke_all`` 0
    on a database error — the answers for "already revoked" and "nothing was
    live". A kill switch reading those would say it worked while every
    mandate stayed live."""
    from life_graph.autonomy.approvals.durable_store import StoreUnavailableError

    with pytest.raises(StoreUnavailableError):
        unreachable.revoke("cap_whatever")
    with pytest.raises(StoreUnavailableError):
        unreachable.revoke_all(tenant_id=DB_TENANT)
    with pytest.raises(StoreUnavailableError):
        unreachable.revoke_all(tenant_id=DB_TENANT, task_id="task-7")


@pytest.mark.asyncio
async def test_an_errand_is_denied_when_the_authorization_store_is_down(unreachable):
    """Fail closed end to end: no capability resolves, so no click happens."""
    browser = FakeBrowser()

    result = await be.run_errand(
        browser,
        _errand("cap_the-owner-approved-this", _click_step()),
        tenant_id=DB_TENANT,
        capabilities=unreachable,
    )

    assert result.status == be.DENIED
    assert result.steps[0].reasons == (cap.UNKNOWN,)
    assert browser.calls == []


def test_unreadable_standing_rules_are_no_rules_at_all():
    """Absent rules are default-deny, which is the safe reading of an outage."""
    from sqlalchemy import create_engine

    from life_graph.autonomy.approvals.capability import StandingRuleStore
    from life_graph.autonomy.approvals.durable_store import (
        DurableStandingRuleStore,
        StoreUnavailableError,
    )

    engine = create_engine(
        "postgresql+psycopg2://nobody:nobody@127.0.0.1:1/does_not_exist",
        connect_args={"connect_timeout": 1},
        future=True,
    )
    try:
        rules = StandingRuleStore()
        rules.attach_durable(DurableStandingRuleStore(engine))

        assert rules.rules_for(DB_TENANT) == ()
        # Writing is the other way round: a rule the owner set that was not
        # saved has to be reported.
        with pytest.raises(StoreUnavailableError):
            rules.set_rules(DB_TENANT, [be.errand_rule("browser_click", "deny", [BANK])])
    finally:
        engine.dispose()


# ── Durable standing rules ───────────────────────────────────────────────


@pytest.fixture
def durable_rules():
    from life_graph.autonomy.approvals.capability import StandingRuleStore
    from life_graph.autonomy.approvals.durable_store import DurableStandingRuleStore, sync_engine

    store = StandingRuleStore()
    store.attach_durable(DurableStandingRuleStore(sync_engine()))
    store.clear(DB_TENANT)
    try:
        yield store
    finally:
        store.clear(DB_TENANT)


@requires_postgres
def test_standing_rules_persist_per_tenant_and_replace_as_a_set(durable_rules):
    from life_graph.autonomy.approvals.capability import StandingRuleStore
    from life_graph.autonomy.approvals.durable_store import DurableStandingRuleStore, sync_engine

    durable_rules.set_rules(
        DB_TENANT,
        [
            be.errand_rule("browser_click", "deny", [EVIL]),
            be.errand_rule("browser_fill_field", "allow", [BANK]),
        ],
    )

    # Another worker reads the same set.
    worker = StandingRuleStore()
    worker.attach_durable(DurableStandingRuleStore(sync_engine()))
    read = worker.rules_for(DB_TENANT)

    assert {(r.action_type, r.effect) for r in read} == {
        ("browser_click", "deny"),
        ("browser_fill_field", "allow"),
    }
    assert any(r.applies_to("browser_click", EVIL) for r in read)
    assert not any(r.applies_to("browser_click", BANK) for r in read)
    # Another tenant's rules are not this tenant's.
    assert worker.rules_for(OTHER_TENANT) == ()

    # Setting the set replaces it: a rule the owner removed has to actually go.
    durable_rules.set_rules(DB_TENANT, [be.errand_rule("browser_click", "deny", [EVIL])])
    assert len(worker.rules_for(DB_TENANT)) == 1


@requires_postgres
def test_a_rule_over_several_origins_round_trips_as_the_same_rule(durable_rules):
    """One row per origin, because the unique index is on (tenant, action, origin)."""
    durable_rules.set_rules(DB_TENANT, [be.errand_rule("browser_click", "deny", [BANK, EVIL])])

    read = durable_rules.rules_for(DB_TENANT)

    assert len(read) == 2
    assert all(
        r.applies_to("browser_click", o) for r, o in zip(read, sorted([BANK, EVIL]), strict=True)
    )
    assert not any(r.applies_to("browser_click", "https://elsewhere.test") for r in read)


@requires_postgres
def test_a_rule_for_any_origin_round_trips_as_any_origin(durable_rules):
    """NULL is "anywhere" and the empty set is nowhere; they must not be confused."""
    from life_graph.autonomy.approvals import StandingRule

    durable_rules.set_rules(
        DB_TENANT, [StandingRule(action_type="browser_click", effect="deny", origins=None)]
    )

    [read] = durable_rules.rules_for(DB_TENANT)

    # An *empty* origins set is StandingRule's own spelling of "anywhere";
    # reading NULL back as "no origins" dropped the row entirely, which is how
    # the owner's broadest rule became the one that did not persist.
    assert read.origins == frozenset()
    assert read.applies_to("browser_click", BANK)
    assert read.applies_to("browser_click", EVIL)


@requires_postgres
def test_the_default_any_origin_rule_round_trips_too(durable_rules):
    """``StandingRule("x")`` leaves origins at its empty default. It must persist."""
    from life_graph.autonomy.approvals import StandingRule

    durable_rules.set_rules(DB_TENANT, [StandingRule("create_reminder")])

    [read] = durable_rules.rules_for(DB_TENANT)

    assert read.action_type == "create_reminder"
    assert read.applies_to("create_reminder", None)


@requires_postgres
def test_a_rule_with_a_ceiling_is_refused_rather_than_stored_without_it(durable_rules):
    """A limit that did not survive a reload would come back as no limit."""
    from life_graph.autonomy.approvals import StandingRule

    with pytest.raises(ValueError, match="max_amount"):
        durable_rules.set_rules(DB_TENANT, [StandingRule("transfer_money", max_amount=1000.0)])

    assert durable_rules.rules_for(DB_TENANT) == ()


# ── That the application actually uses it ────────────────────────────────


@requires_postgres
def test_attaching_makes_the_process_wide_stores_durable():
    """The process stores every caller already imports become the table's.

    Nothing else in the codebase changes to get durability: the objects keep
    their identity, so ``from ... import capability_store`` is still the right
    import and still the right store.
    """
    from life_graph.autonomy.approvals.capability import capability_store, standing_rule_store
    from life_graph.autonomy.approvals.durable_store import (
        DurableCapabilityStore,
        DurableStandingRuleStore,
        attach_durable_stores,
        detach_durable_stores,
    )

    assert capability_store.durable is None  # conftest keeps the suite in memory

    attach_durable_stores()
    try:
        assert isinstance(capability_store.durable, DurableCapabilityStore)
        assert isinstance(standing_rule_store._durable, DurableStandingRuleStore)

        issued = _db_bound(capability_store)
        # Resolvable from a store object that has never seen it: the point.
        other = CapabilityStore(durable=DurableCapabilityStore())
        assert other.get(issued.capability_id) is not None
        assert _db_spend(other, issued)[1].ok
        assert _db_spend(capability_store, issued)[1].reason == cap.ALREADY_CONSUMED
    finally:
        capability_store.revoke_all(tenant_id=DB_TENANT)
        detach_durable_stores()

    assert capability_store.durable is None


def test_the_application_startup_attaches_the_durable_stores():
    """The wiring claim, read off the startup it is claimed about.

    ``docs/AI_WORK_ORDER.md`` distinguishes "implemented" from "integrated",
    so this asserts the real startup path reaches ``attach_durable_stores``
    behind ``settings.durable_authorization`` rather than trusting a comment.
    """
    import inspect

    from life_graph import main
    from life_graph.config import settings

    # _start_extended_domains runs the _EXTENDED_STARTUP steps in order
    # (split per domain, audit M15); read every step it runs.
    src = "\n".join(inspect.getsource(step) for step in main._EXTENDED_STARTUP)

    assert "settings.durable_authorization" in src
    assert "attach_durable_stores()" in src
    # On by default: an in-memory mandate is invisible to every other worker.
    assert settings.model_fields["durable_authorization"].default is True
