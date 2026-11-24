"""The vault: a handle must be worthless anywhere the owner did not allow.

The service's whole value is that ``vault://…`` can travel through plans,
tool calls and logs safely, so these tests check the properties that make that
true rather than the happy path alone: the ciphertext does not contain the
plaintext, metadata has no route to it, a wrong origin is refused *before* a
one-use secret is spent, a spent secret stays spent, and a row that belongs to
another tenant neither resolves nor decrypts.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Update

from life_graph.models.vault import VaultSecret
from life_graph.services import vault
from tests.unit.fakes import FakeResult, FakeSession, sql

TENANT = "t1"
OTHER = "t2"
KEY = base64.urlsafe_b64encode(b"k" * 32).decode()


@pytest.fixture(autouse=True)
def _fixed_key(monkeypatch):
    """A known key, so nothing reads or writes the developer's key file."""
    monkeypatch.setattr(vault.settings, "vault_key", KEY, raising=False)
    monkeypatch.delenv("LIFE_GRAPH_VAULT_KEY", raising=False)
    vault.reset_key_cache()
    yield
    vault.reset_key_cache()


def make_row(
    value: str = "hunter2",
    origins: list[str] | None = None,
    one_use: bool = False,
    tenant_id: str = TENANT,
    handle: str = "h4ndl3",
) -> VaultSecret:
    """A stored secret, as ``store`` would have left it."""
    return VaultSecret(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        handle=handle,
        label="HDFC net banking",
        secret_type="password",
        allowed_origins=origins if origins is not None else ["https://netbanking.hdfcbank.com"],
        encrypted_value=vault.encrypt(tenant_id, handle, value),
        one_use=one_use,
        use_count=0,
        created_at=datetime.now(UTC),
    )


# ── Storing ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_encrypts_and_returns_an_opaque_handle():
    session = FakeSession()
    row = await vault.store(
        session, TENANT, "HDFC net banking", "hunter2", ["netbanking.hdfcbank.com"]
    )

    assert session.added == [row]
    assert b"hunter2" not in row.encrypted_value
    assert "hunter2" not in repr(row)
    assert vault.handle_uri(row).startswith("vault://")
    assert row.handle not in ("HDFC net banking", "hunter2")
    # A bare host is stored as an https origin.
    assert row.allowed_origins == ["https://netbanking.hdfcbank.com"]


@pytest.mark.asyncio
async def test_two_secrets_never_share_a_handle_or_a_ciphertext():
    session = FakeSession()
    a = await vault.store(session, TENANT, "a", "same-value", ["bank.com"])
    b = await vault.store(session, TENANT, "b", "same-value", ["bank.com"])

    assert a.handle != b.handle
    # Same plaintext, different nonce and different handle in the AAD.
    assert a.encrypted_value != b.encrypted_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"label": "", "value": "x", "allowed_origins": ["a.com"]}, "no label"),
        ({"label": "l", "value": "", "allowed_origins": ["a.com"]}, "no value"),
        ({"label": "l", "value": "x", "allowed_origins": []}, "no origin"),
        ({"label": "l", "value": "x", "allowed_origins": ["  "]}, "blank origin"),
        ({"label": "l", "value": "x", "allowed_origins": ["*"]}, "anywhere"),
        (
            {"label": "l", "value": "x", "allowed_origins": ["a.com"], "secret_type": "nonsense"},
            "unknown type",
        ),
    ],
)
async def test_store_refuses_a_secret_that_could_go_anywhere(kwargs, why):
    session = FakeSession()
    with pytest.raises(vault.VaultError):
        await vault.store(session, TENANT, **kwargs)
    assert session.added == [], why


# ── Metadata never carries the value ───────────────────


def test_metadata_has_no_path_to_the_plaintext():
    row = make_row(value="hunter2")
    data = vault.to_dict(row)

    rendered = json.dumps(data)
    assert "hunter2" not in rendered
    assert "value" not in data
    assert "encrypted_value" not in data
    assert data["handle"] == "vault://h4ndl3"
    assert data["label"] == "HDFC net banking"
    assert data["one_use"] is False
    assert data["spent"] is False


def test_metadata_marks_a_spent_one_use_secret():
    row = make_row(one_use=True)
    row.used_at = datetime.now(UTC)
    assert vault.to_dict(row)["spent"] is True


# ── Origins ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://bank.com", "https://bank.com"),
        ("HTTPS://Bank.com/", "https://bank.com"),
        ("https://bank.com/login?next=/x", "https://bank.com"),
        ("bank.com", "https://bank.com"),  # a bare host is never assumed plaintext
        ("http://localhost:3000", "http://localhost:3000"),
        ("", ""),
        ("   ", ""),
        # A default port is not part of the origin; any other port is.
        ("https://bank.com:443", "https://bank.com"),
        ("http://bank.com:80", "http://bank.com"),
        ("https://bank.com:8443", "https://bank.com:8443"),
        ("bank.com:8443", "https://bank.com:8443"),  # a bare host with a port
        ("localhost:3000", "https://localhost:3000"),
        ("//bank.com", "https://bank.com"),  # protocol-relative
        # One place, one spelling: the DNS root dot, the case and the port all go.
        ("https://BANK.com.:443/login", "https://bank.com"),
        # Addresses are canonicalised too, so the spellings a resolver accepts
        # do not read as three different hosts.
        ("https://0x7f.1", "https://127.0.0.1"),
        ("https://2130706433", "https://127.0.0.1"),
        ("https://[0:0:0:0:0:0:0:1]:8080", "https://[::1]:8080"),
        ("https://bänk.com", "https://xn--bnk-qla.com"),  # IDNA, not two hosts
    ],
)
def test_origin_normalisation(raw, expected):
    assert vault.normalize_origin(raw) == expected


@pytest.mark.parametrize(
    ("allowed", "target", "ok"),
    [
        (["https://bank.com"], "https://bank.com/login", True),
        (["bank.com"], "https://bank.com", True),
        (["bank.com"], "http://bank.com", False),  # https unless http was asked for
        (["http://localhost:3000"], "http://localhost:3000", True),
        (["*.bank.com"], "https://login.bank.com", True),
        (["*.bank.com"], "https://bank.com", True),
        (["*.bank.com"], "https://a.b.bank.com", True),  # any depth
        (["*.bank.com"], "https://bank.com.evil.io", False),
        (["*.bank.com"], "https://notbank.com", False),
        # The dot is a boundary, not a character that happens to be in there.
        (["*.bank.com"], "https://evilbank.com", False),
        (["*.bank.com"], "https://xbank.com", False),
        (["*.bank.com"], "https://.bank.com", False),  # not a host at all
        (["*.bank.com"], "http://login.bank.com", False),  # https unless asked
        (["http://*.bank.com"], "http://login.bank.com", True),
        # A pattern's port is part of it, on both sides.
        (["https://*.bank.com:8443"], "https://login.bank.com:8443", True),
        (["https://*.bank.com:8443"], "https://login.bank.com", False),
        (["https://*.bank.com:8443"], "http://login.bank.com:8443", False),
        (["https://*.bank.com"], "https://login.bank.com:8443", False),
        (["https://bank.com"], "https://bank.com:443", True),  # the default port
        (["https://bank.com:443"], "https://bank.com", True),
        # One entry out of several is enough, and a bad one is not fatal.
        (["evil.io", "*.bank.com"], "https://login.bank.com", True),
        (["https://bank.com/login", "https://bank.com"], "https://bank.com", True),
        (["https://bank.com"], "https://bank.com:8443", False),  # a port is part of an origin
        (["https://bank.com"], "https://evil.io", False),
        ([], "https://bank.com", False),
        (None, "https://bank.com", False),
        (["https://bank.com"], "", False),
    ],
)
def test_which_origins_a_secret_may_go_to(allowed, target, ok):
    assert vault.origin_allowed(allowed, target) is ok


# ── Origins that are not origins ───────────────────────
#
# Every one of these reads as a familiar site to a person and means something
# else to a parser, which is exactly the shape of the attack the vault exists
# to stop: a handle is safe to hand around only because the origin check
# cannot be talked around.


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        ("https://user:pass@bank.com", "userinfo: the host is bank.com, the credentials are not"),
        ("https://bank.com@evil.io", "reads as the bank, resolves evil.io"),
        ("https://bank.com\\@evil.io", "a browser reads the backslash as a slash"),
        ("file:///etc/passwd", "not a web origin"),
        ("data:text/html,<h1>bank</h1>", "a document, not a place"),
        ("javascript:alert(1)", "code, not a place"),
        ("ftp://bank.com", "not a scheme a password is typed into"),
        ("vault://h4ndl3", "a handle is not an origin"),
        ("https://bank.com:99999", "not a port"),
        ("https://bank.com:0", "not a port"),
        ("https://bank.com:https", "not a port"),
        ("https://bank .com", "a space means the authority never ended where it reads"),
        ("https://bank .com", "a line separator in the host"),
        ("https://bank.com\x00.evil.io", "a NUL byte truncates differently in every parser"),
        ("https://", "no host"),
        ("https:bank.com", "no authority"),
        ("https://bank..com", "an empty label"),
        ("https://*.bank.com", "a wildcard is the owner's to write, not a page's to claim"),
        ("https://" + "x" * 300 + ".com", "longer than any origin"),
    ],
)
def test_a_malformed_origin_is_refused_rather_than_guessed_at(raw, why):
    with pytest.raises(vault.MalformedOriginError):
        vault.normalize_origin(raw)
    # And it matches nothing, by any route: the bool-returning door fails closed
    # rather than passing the refusal to a caller who might not catch it.
    assert vault.origin_allowed(["https://bank.com", "*.bank.com"], raw) is False


@pytest.mark.parametrize(
    "raw",
    [
        "https://bank.com/login",
        "https://bank.com?next=/x",
        "https://bank.com/#@evil.io",  # the deceptive one: reads as evil.io's page
        "https://evil.io/https://bank.com",
    ],
)
def test_an_allowed_origin_may_not_carry_a_path(raw):
    """A path on an entry promises path scoping the vault does not do.

    For a *page's* origin the same path is stripped — that is the shape a
    browser reports — so the two readings are separate arguments.
    """
    with pytest.raises(vault.MalformedOriginError):
        vault.normalize_origin(raw, origin_only=True)
    assert "/" not in vault.normalize_origin(raw).removeprefix("https://")


def test_a_deceptive_path_is_read_as_the_host_it_really_names():
    """``https://evil.io/https://bank.com`` is evil.io. Nothing else."""
    assert vault.normalize_origin("https://evil.io/https://bank.com") == "https://evil.io"
    assert vault.origin_allowed(["https://bank.com"], "https://evil.io/https://bank.com") is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry",
    ["https://user@bank.com", "file:///etc/passwd", "bank.com:99999", "https://bank.com/login"],
)
async def test_store_refuses_an_origin_that_is_not_one(entry):
    session = FakeSession()
    with pytest.raises(vault.MalformedOriginError):
        await vault.store(session, TENANT, "l", "hunter2", [entry])
    assert session.added == []
    # A VaultError too, so the API's one handler still answers 400 for it.
    assert issubclass(vault.MalformedOriginError, vault.VaultError)


@pytest.mark.asyncio
async def test_a_wildcard_entry_is_stored_the_way_a_match_reads_it():
    session = FakeSession()
    row = await vault.store(session, TENANT, "l", "hunter2", ["*.BANK.com", "*.bank.com"])

    assert row.allowed_origins == ["https://*.bank.com"]  # canonical, de-duplicated
    assert vault.origin_allowed(row.allowed_origins, "https://login.bank.com") is True
    assert vault.origin_allowed(row.allowed_origins, "https://notbank.com") is False


def test_a_stored_entry_that_is_no_longer_an_origin_allows_nothing():
    """Defence in depth: entries are validated at store, and again at match.

    A row written by an older build, by hand or by a migration is not trusted
    to be well-formed; an entry that does not parse is skipped, not guessed at.
    """
    assert vault.origin_allowed(["https://bank.com@evil.io"], "https://evil.io") is False
    assert vault.origin_allowed(["*"], "https://bank.com") is False
    assert vault.origin_allowed(["https://*"], "https://bank.com") is False
    assert vault.origin_allowed([""], "https://bank.com") is False


# ── Resolving ──────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("handle", ["vault://h4ndl3", "h4ndl3", "  vault://h4ndl3  "])
async def test_resolve_returns_the_plaintext_for_an_allowed_origin(handle):
    row = make_row(value="hunter2")
    session = FakeSession(row)

    value = await vault.resolve_for_origin(
        session, TENANT, handle, "https://netbanking.hdfcbank.com/login"
    )

    assert value == "hunter2"
    assert row.use_count == 1
    assert row.last_used_origin == "https://netbanking.hdfcbank.com"
    assert row.used_at is not None
    # The lookup is tenant-scoped, not handle-only.
    assert "tenant_id" in sql(session.statements[0])
    assert f"'{TENANT}'" in sql(session.statements[0])


@pytest.mark.asyncio
async def test_a_wrong_origin_gets_nothing_and_spends_nothing():
    row = make_row(value="hunter2", one_use=True)
    session = FakeSession(row)

    with pytest.raises(vault.OriginNotAllowedError):
        await vault.resolve_for_origin(session, TENANT, "vault://h4ndl3", "https://evil.io")

    # The whole point: a mis-sent one-use secret must still be usable later.
    assert row.used_at is None
    assert row.use_count == 0
    value = await vault.resolve_for_origin(
        session, TENANT, "vault://h4ndl3", "https://netbanking.hdfcbank.com"
    )
    assert value == "hunter2"


@pytest.mark.asyncio
async def test_a_one_use_secret_is_spent_once():
    row = make_row(value="123456", origins=["https://bank.com"], one_use=True)
    session = FakeSession(row)

    assert await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com") == "123456"
    with pytest.raises(vault.SecretSpentError):
        await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")
    assert row.use_count == 1


@pytest.mark.asyncio
async def test_a_reusable_secret_counts_uses_instead():
    row = make_row(value="hunter2", origins=["https://bank.com"])
    session = FakeSession(row)

    for _ in range(3):
        assert await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")
    assert row.use_count == 3


@pytest.mark.asyncio
async def test_an_unknown_handle_resolves_to_nothing():
    session = FakeSession(None)
    with pytest.raises(vault.SecretNotFoundError):
        await vault.resolve_for_origin(session, TENANT, "vault://nope", "https://bank.com")


@pytest.mark.asyncio
@pytest.mark.parametrize("handle", ["", "vault://", "   ", "vault://" + "x" * 200])
async def test_a_malformed_handle_resolves_to_nothing(handle):
    session = FakeSession(make_row())
    with pytest.raises(vault.SecretNotFoundError):
        await vault.resolve_for_origin(session, TENANT, handle, "https://bank.com")


@pytest.mark.asyncio
async def test_no_target_origin_is_refused_rather_than_waved_through():
    session = FakeSession(make_row())
    with pytest.raises(vault.OriginNotAllowedError):
        await vault.resolve_for_origin(session, TENANT, "vault://h4ndl3", "")


@pytest.mark.asyncio
async def test_a_revoked_secret_resolves_to_nothing():
    row = make_row()
    row.revoked_at = datetime.now(UTC)
    session = FakeSession(row)
    with pytest.raises(vault.SecretNotFoundError):
        await vault.resolve_for_origin(
            session, TENANT, "vault://h4ndl3", "https://netbanking.hdfcbank.com"
        )


# ── Spending a one-use secret exactly once ─────────────
#
# The Python-level ``row.used_at is not None`` check is the cheap half. Two
# requests that both read the row before either wrote it both pass that check,
# so what actually decides the winner is the conditional UPDATE: the claim and
# the test of whether it is still claimable are one statement. These tests
# exercise the half that matters, which means the fake has to behave like a
# database rather than like a dict.


class RacingSession:
    """A session that lets two resolves interleave, and claims like Postgres.

    ``execute`` suspends at every statement, so two tasks genuinely read the
    row before either updates it — the race a dict-backed fake cannot produce.
    The UPDATE then lands once: a statement carrying ``used_at IS NULL``
    affects no rows if the secret has already been claimed, exactly as the
    real ``WHERE`` clause would.
    """

    def __init__(self, row: VaultSecret):
        self._row = row
        self._claimed = row.used_at is not None
        self.claims = 0
        self.statements: list[object] = []

    async def execute(self, stmt, *_a, **_k) -> FakeResult:
        self.statements.append(stmt)
        await asyncio.sleep(0)  # the point: the other task runs here
        if not isinstance(stmt, Update):
            return FakeResult([self._row])
        if "used_at IS NULL" in sql(stmt) and self._claimed:
            return FakeResult([], rowcount=0)  # somebody else got there first
        self._claimed = True
        self.claims += 1
        return FakeResult([], rowcount=1)

    async def flush(self) -> None:
        pass


@pytest.mark.asyncio
async def test_two_racing_resolves_spend_a_one_use_secret_exactly_once():
    row = make_row(value="123456", origins=["https://bank.com"], one_use=True)
    session = RacingSession(row)

    results = await asyncio.gather(
        vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com"),
        vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com"),
        return_exceptions=True,
    )

    values = [r for r in results if isinstance(r, str)]
    refusals = [r for r in results if isinstance(r, Exception)]
    assert values == ["123456"], "the OTP came back twice"
    assert [type(r) for r in refusals] == [vault.SecretSpentError]
    assert session.claims == 1
    # And the row says it went once, to the one origin.
    assert row.use_count == 1
    assert row.used_at is not None
    assert row.last_used_origin == "https://bank.com"


@pytest.mark.asyncio
async def test_a_third_resolve_after_the_race_is_still_refused():
    row = make_row(value="123456", origins=["https://bank.com"], one_use=True)
    session = RacingSession(row)

    await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")
    with pytest.raises(vault.SecretSpentError):
        await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")
    assert session.claims == 1


@pytest.mark.asyncio
async def test_the_claim_is_one_conditional_statement_not_a_read_then_a_write():
    """The property the concurrency rests on, asserted on the SQL itself."""
    row = make_row(value="123456", origins=["https://bank.com"], one_use=True)
    session = FakeSession(row)

    await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")

    select_sql, update_sql = (sql(stmt) for stmt in session.statements[:2])
    assert "FOR UPDATE" in select_sql  # the lock serialises the ordinary case
    assert update_sql.startswith("UPDATE vault_secrets")
    assert "used_at IS NULL" in update_sql  # …and this still holds if it does not
    assert "use_count + 1" in update_sql  # counted in the database, not in Python
    assert f"tenant_id = '{TENANT}'" in update_sql
    assert "revoked_at IS NULL" in update_sql


@pytest.mark.asyncio
async def test_a_reusable_secret_is_claimed_without_the_one_use_guard():
    row = make_row(value="hunter2", origins=["https://bank.com"])
    session = FakeSession(row)

    await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")

    update_sql = sql(session.statements[1])
    assert "used_at IS NULL" not in update_sql
    assert "use_count + 1" in update_sql


@pytest.mark.asyncio
async def test_a_secret_claimed_by_another_request_is_spent_not_served():
    """The row read clean, the claim found nothing: another request won."""
    row = make_row(value="123456", origins=["https://bank.com"], one_use=True)
    session = FakeSession(row, FakeResult([], rowcount=0))

    with pytest.raises(vault.SecretSpentError):
        await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")


@pytest.mark.asyncio
async def test_a_secret_revoked_between_the_read_and_the_claim_is_not_found():
    row = make_row(value="hunter2", origins=["https://bank.com"])
    session = FakeSession(row, FakeResult([], rowcount=0))

    with pytest.raises(vault.SecretNotFoundError):
        await vault.resolve_for_origin(session, TENANT, "h4ndl3", "https://bank.com")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("row_kwargs", "origin", "expected"),
    [
        ({}, "https://evil.io", vault.OriginNotAllowedError),
        ({"tenant_id": OTHER}, "https://bank.com", vault.SecretNotFoundError),
    ],
)
async def test_nothing_is_decrypted_until_the_origin_and_the_claim_are_settled(
    monkeypatch, row_kwargs, origin, expected
):
    """A refused resolve must never have held the plaintext in the first place."""
    calls: list[tuple] = []

    def spy(tenant_id, handle, blob):
        calls.append((tenant_id, handle))
        return "hunter2"

    monkeypatch.setattr(vault, "decrypt", spy)
    row = make_row(value="hunter2", origins=["https://bank.com"], one_use=True, **row_kwargs)
    session = FakeSession(row)

    with pytest.raises(expected):
        await vault.resolve_for_origin(session, TENANT, "h4ndl3", origin)
    assert calls == []

    # On the way through, it is called once — after the claim.
    await vault.resolve_for_origin(session, row.tenant_id, "h4ndl3", "https://bank.com")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_a_malformed_target_origin_is_refused_before_anything_is_read():
    session = FakeSession(make_row())
    with pytest.raises(vault.MalformedOriginError):
        await vault.resolve_for_origin(
            session, TENANT, "vault://h4ndl3", "https://bank.com@evil.io"
        )
    assert session.statements == []


# ── Plaintext does not leak, by any route ──────────────


@pytest.mark.asyncio
async def test_no_refusal_or_success_ever_mentions_the_plaintext(caplog):
    """Every path through the service, checked for the one string that matters.

    A secret that shows up in an exception message reaches a traceback, a log
    line, an error response and the agent's own transcript — which is the
    whole thing the vault is for.
    """
    caplog.set_level(logging.DEBUG)
    secret = "c0rrect-horse-battery-staple"
    seen: list[str] = []

    async def attempt(coro):
        try:
            seen.append(repr(await coro))
        except Exception as exc:  # noqa: BLE001 — the message is what is under test
            seen.append(f"{exc!r} {exc!s}")
            cause = exc.__cause__
            while cause is not None:
                seen.append(f"{cause!r} {cause!s}")
                cause = cause.__cause__

    # Stored, listed, revoked, resolved, refused, spent, cross-tenant, tampered.
    store_session = FakeSession()
    stored = await vault.store(store_session, TENANT, "HDFC net banking", secret, ["bank.com"])
    seen += [repr(stored), repr(vault.to_dict(stored)), json.dumps(vault.to_dict(stored))]
    await attempt(vault.resolve_for_origin(FakeSession(stored), TENANT, stored.handle, "bank.com"))
    await attempt(
        vault.resolve_for_origin(FakeSession(stored), TENANT, stored.handle, "https://evil.io")
    )
    await attempt(vault.resolve_for_origin(FakeSession(stored), OTHER, stored.handle, "bank.com"))

    one_use = make_row(value=secret, origins=["https://bank.com"], one_use=True)
    one_use.used_at = datetime.now(UTC)
    await attempt(vault.resolve_for_origin(FakeSession(one_use), TENANT, "h4ndl3", "bank.com"))

    tampered = make_row(value=secret)
    # Flip a bit rather than set a value: the tag is random, so overwriting its
    # last byte with 0 left it unchanged 1 run in 256 and the "tampered" blob
    # decrypted (CI #859).
    tampered.encrypted_value = tampered.encrypted_value[:-1] + bytes(
        [tampered.encrypted_value[-1] ^ 0x01]
    )
    await attempt(
        vault.resolve_for_origin(FakeSession(tampered), TENANT, "h4ndl3", "netbanking.hdfcbank.com")
    )
    # A blob that authenticates and then decrypts to bytes that are not text:
    # the UnicodeDecodeError quotes the byte it tripped on, and that byte is
    # plaintext, so it must not be chained onto the refusal.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = b"n" * 12
    not_text = nonce + AESGCM(vault._key()).encrypt(nonce, b"\xff\xfe", vault._aad(TENANT, "h"))
    with pytest.raises(vault.SecretNotFoundError) as refused:
        vault.decrypt(TENANT, "h", not_text)
    assert refused.value.__cause__ is None
    seen.append(f"{refused.value!r} {refused.value!s}")

    # The one place the plaintext is allowed is the return value of a resolve.
    assert seen[3] == repr(secret), "the allowed resolve should have returned it"
    for text in seen[:3] + seen[4:]:
        assert secret not in text, text
    assert secret not in caplog.text
    assert "HDFC net banking" in caplog.text  # the label is what a log line names


def test_a_revoked_secret_is_gone_rather_than_flagged():
    row = make_row(value="hunter2")
    row.revoked_at = datetime.now(UTC)
    row.encrypted_value = b""

    with pytest.raises(vault.SecretNotFoundError):
        vault.decrypt(TENANT, row.handle, row.encrypted_value)
    assert "hunter2" not in repr(row)
    assert "hunter2" not in json.dumps(vault.to_dict(row))


# ── Tenant isolation ───────────────────────────────────


@pytest.mark.asyncio
async def test_holding_another_tenants_handle_is_not_enough_to_resolve_it():
    """The handle is the whole of what leaks; it is not the whole of what is checked.

    Tenant B stores a secret, tenant A learns its handle — from a shared log,
    a copied plan, a guess. A's resolve is scoped to A, so the row is not
    found; and even handed the row, the ciphertext is bound to B, so there is
    nothing in it for A.
    """
    store_session = FakeSession()
    theirs = await vault.store(store_session, OTHER, "their bank", "hunter2", ["bank.com"])

    # A's query names A's tenant, so B's row is simply not there.
    session = FakeSession(None)
    with pytest.raises(vault.SecretNotFoundError):
        await vault.resolve_for_origin(session, TENANT, theirs.handle, "https://bank.com")
    assert f"'{TENANT}'" in sql(session.statements[0])
    assert f"'{OTHER}'" not in sql(session.statements[0])
    # And the ciphertext itself is B's: the AAD is the tenant.
    with pytest.raises(vault.SecretNotFoundError):
        vault.decrypt(TENANT, theirs.handle, theirs.encrypted_value)
    assert vault.decrypt(OTHER, theirs.handle, theirs.encrypted_value) == "hunter2"


@pytest.mark.asyncio
async def test_another_tenants_row_never_resolves_even_if_the_query_returns_it():
    """Defence in depth: the tenant is in the WHERE clause *and* re-checked."""
    row = make_row(tenant_id=OTHER)
    session = FakeSession(row)

    with pytest.raises(vault.SecretNotFoundError):
        await vault.resolve_for_origin(
            session, TENANT, "vault://h4ndl3", "https://netbanking.hdfcbank.com"
        )
    assert row.used_at is None


def test_ciphertext_is_bound_to_its_tenant_and_handle():
    blob = vault.encrypt(TENANT, "h4ndl3", "hunter2")

    assert vault.decrypt(TENANT, "h4ndl3", blob) == "hunter2"
    for tenant_id, handle in ((OTHER, "h4ndl3"), (TENANT, "other-handle")):
        with pytest.raises(vault.SecretNotFoundError):
            vault.decrypt(tenant_id, handle, blob)


def test_a_blank_or_truncated_ciphertext_is_not_found_rather_than_crashing():
    for blob in (b"", b"short", vault.encrypt(TENANT, "h4ndl3", "x")[:10]):
        with pytest.raises(vault.SecretNotFoundError):
            vault.decrypt(TENANT, "h4ndl3", blob)


@pytest.mark.asyncio
async def test_get_refuses_another_tenants_id():
    row = make_row(tenant_id=OTHER)
    session = FakeSession(objects={(VaultSecret, row.id): row})

    assert await vault.get(session, OTHER, row.id) is row
    with pytest.raises(vault.SecretNotFoundError):
        await vault.get(session, TENANT, row.id)


@pytest.mark.asyncio
async def test_get_on_a_missing_id_is_not_found():
    session = FakeSession()
    with pytest.raises(vault.SecretNotFoundError):
        await vault.get(session, TENANT, uuid.uuid4())


# ── Listing and revoking ───────────────────────────────


@pytest.mark.asyncio
async def test_list_filters_by_tenant_and_hides_revoked_by_default():
    rows = [make_row(), make_row(handle="other")]
    session = FakeSession(rows)

    assert await vault.list_secrets(session, TENANT) == rows
    text = sql(session.statements[0])
    assert f"'{TENANT}'" in text
    assert "revoked_at IS NULL" in text

    await vault.list_secrets(session, TENANT, include_revoked=True)
    assert "revoked_at IS NULL" not in sql(session.statements[1])


@pytest.mark.asyncio
async def test_revoking_destroys_the_ciphertext_and_keeps_the_row():
    row = make_row()
    session = FakeSession(objects={(VaultSecret, row.id): row})

    revoked = await vault.revoke(session, TENANT, row.id)

    assert revoked is row
    assert row.revoked_at is not None
    assert row.encrypted_value == b""  # not recoverable from a later backup
    assert vault.to_dict(row)["revoked_at"] is not None


@pytest.mark.asyncio
async def test_revoking_twice_keeps_the_first_time():
    row = make_row()
    session = FakeSession(objects={(VaultSecret, row.id): row})

    first = (await vault.revoke(session, TENANT, row.id)).revoked_at
    assert (await vault.revoke(session, TENANT, row.id)).revoked_at == first


@pytest.mark.asyncio
async def test_revoking_another_tenants_secret_is_not_found():
    row = make_row(tenant_id=OTHER)
    session = FakeSession(objects={(VaultSecret, row.id): row})

    with pytest.raises(vault.SecretNotFoundError):
        await vault.revoke(session, TENANT, row.id)
    assert row.revoked_at is None
    assert row.encrypted_value != b""


# ── Key handling ───────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        base64.urlsafe_b64encode(b"k" * 32).decode(),
        base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("="),  # pasted unpadded
        (b"k" * 32).hex(),
    ],
)
def test_a_key_may_be_base64_or_hex(monkeypatch, raw):
    monkeypatch.setattr(vault.settings, "vault_key", raw, raising=False)
    vault.reset_key_cache()
    assert vault._key() == b"k" * 32


@pytest.mark.parametrize("raw", ["too-short", base64.urlsafe_b64encode(b"k" * 16).decode()])
def test_a_key_of_the_wrong_size_is_refused_loudly(monkeypatch, raw):
    monkeypatch.setattr(vault.settings, "vault_key", raw, raising=False)
    vault.reset_key_cache()
    with pytest.raises(vault.VaultKeyMissingError):
        vault._key()


def test_a_self_host_with_no_key_generates_one_once(monkeypatch, tmp_path):
    key_file = tmp_path / "nested" / "vault.key"
    monkeypatch.setattr(vault.settings, "vault_key", "", raising=False)
    monkeypatch.setattr(vault.settings, "vault_key_file", str(key_file), raising=False)
    vault.reset_key_cache()

    generated = vault._key()
    assert len(generated) == 32
    assert key_file.stat().st_mode & 0o777 == 0o600

    # Read back, not regenerated: a restart must still decrypt yesterday's secrets.
    vault.reset_key_cache()
    assert vault._key() == generated


def test_the_env_var_is_enough_without_the_setting(monkeypatch):
    monkeypatch.setattr(vault.settings, "vault_key", "", raising=False)
    monkeypatch.setenv("LIFE_GRAPH_VAULT_KEY", base64.urlsafe_b64encode(b"z" * 32).decode())
    vault.reset_key_cache()
    assert vault._key() == b"z" * 32
