"""The vault: a handle must be worthless anywhere the owner did not allow.

The service's whole value is that ``vault://…`` can travel through plans,
tool calls and logs safely, so these tests check the properties that make that
true rather than the happy path alone: the ciphertext does not contain the
plaintext, metadata has no route to it, a wrong origin is refused *before* a
one-use secret is spent, a spent secret stays spent, and a row that belongs to
another tenant neither resolves nor decrypts.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

import pytest

from life_graph.models.vault import VaultSecret
from life_graph.services import vault
from tests.unit.fakes import FakeSession, sql

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
        (["*.bank.com"], "https://bank.com.evil.io", False),
        (["*.bank.com"], "https://notbank.com", False),
        (["https://bank.com"], "https://bank.com:8443", False),  # a port is part of an origin
        (["https://bank.com"], "https://evil.io", False),
        ([], "https://bank.com", False),
        (None, "https://bank.com", False),
        (["https://bank.com"], "", False),
    ],
)
def test_which_origins_a_secret_may_go_to(allowed, target, ok):
    assert vault.origin_allowed(allowed, target) is ok


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


# ── Tenant isolation ───────────────────────────────────


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
