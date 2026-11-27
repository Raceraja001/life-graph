"""Agent accounts (Phase 3b part 1): catalog, identity, pool, env, homes, service, hook.

No database: the service is driven with tests/unit/fakes.FakeSession, the
vault with a stand-in, and the hook with a session factory over FakeSession.
"""

from __future__ import annotations

import os
import stat
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.drivers import accounts_hook, cli_run
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.models.agent_accounts import AgentAccount
from life_graph.services.agent_accounts import env as account_env
from life_graph.services.agent_accounts import homes, identity, pool, service
from life_graph.services.agent_accounts.catalog import (
    AccountError,
    allowed_env_names,
    check_driver_kind,
    clean_name,
    clean_properties,
)
from tests.unit.fakes import FakeSession, sql

NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


def _acct(name="a", *, priority=100, enabled=True, cooldown=None, age=0, driver="codex", **kw):
    row = AgentAccount(
        id=kw.pop("id", uuid.uuid4()),
        tenant_id=kw.pop("tenant_id", "t1"),
        driver=driver,
        name=name,
        kind=kw.pop("kind", "subscription"),
        enabled=enabled,
        priority=priority,
        cooldown_until=cooldown,
        properties=kw.pop("properties", {}),
        created_at=NOW - timedelta(days=age),
        updated_at=NOW,
        **kw,
    )
    return row


@pytest.fixture
def home_root(tmp_path, monkeypatch):
    root = tmp_path / "homes"
    monkeypatch.setattr(settings, "driver_accounts_home_root", str(root))
    return root


# ── Catalog ──────────────────────────────────────────────────


def test_driver_kind_rules():
    check_driver_kind("claude_code", "vertex")
    check_driver_kind("codex", "api_key")
    with pytest.raises(AccountError, match="not 'vertex'"):
        check_driver_kind("codex", "vertex")
    with pytest.raises(AccountError, match="not supported yet"):
        check_driver_kind("opencode", "subscription")
    with pytest.raises(AccountError, match="unknown driver"):
        check_driver_kind("aider", "subscription")


def test_names_and_properties_are_validated():
    assert clean_name("  Claude ·  work Max ") == "Claude · work Max"
    with pytest.raises(AccountError):
        clean_name("x" * 61)
    with pytest.raises(AccountError):
        clean_name("evil; rm -rf /")
    assert clean_properties("gemini", "vertex", {"project": "my-proj-1", "region": "us-east5"}) == {
        "project": "my-proj-1",
        "region": "us-east5",
    }
    with pytest.raises(AccountError, match="project"):
        clean_properties("gemini", "vertex", {"region": "us-east5"})
    # Unknown keys are dropped, not stored.
    assert clean_properties("codex", "subscription", {"LD_PRELOAD": "/x.so"}) == {}


# ── Identity ─────────────────────────────────────────────────


def test_identity_is_masked_and_hashed_never_kept_raw():
    assert identity.mask("Rajasekar@Gmail.com") == "ra***@g***.com"
    assert identity.mask("acme-org") == "ac***"
    key = b"k" * 32
    one = identity.identity_hash("t1", "codex", " rajasekar@gmail.com", key)
    assert one == identity.identity_hash("t1", "codex", "RAJASEKAR@gmail.com ", key)
    assert one != identity.identity_hash("t2", "codex", "rajasekar@gmail.com", key)
    assert one != identity.identity_hash("t1", "codex", "rajasekar@gmail.com", b"x" * 32)
    assert "rajasekar" not in one and len(one) == 64


# ── Pool ─────────────────────────────────────────────────────


def test_pick_takes_the_first_enabled_account_not_cooling():
    a = _acct("a", priority=10)
    b = _acct("b", priority=20)
    off = _acct("off", priority=1, enabled=False)
    assert pool.pick([b, off, a], NOW).account is a
    a.cooldown_until = NOW + timedelta(minutes=5)
    assert pool.pick([b, off, a], NOW).account is b
    # A cooldown that has ended no longer counts.
    a.cooldown_until = NOW - timedelta(seconds=1)
    assert pool.pick([b, a], NOW).account is a


def test_pick_ties_break_on_age_then_name():
    old = _acct("z-old", age=3)
    new = _acct("a-new", age=1)
    assert pool.ordered([new, old]) == [old, new]


def test_pick_with_everything_cooling_says_when_to_retry():
    a = _acct("a", cooldown=NOW + timedelta(hours=2))
    b = _acct("b", cooldown=NOW + timedelta(minutes=30))
    picked = pool.pick([a, b], NOW)
    assert picked.state == "cooling" and picked.retry_at == NOW + timedelta(minutes=30)


def test_no_enabled_account_means_the_default_login():
    assert pool.pick([], NOW).state == "none"
    assert pool.pick([_acct(enabled=False)], NOW).state == "none"


def test_next_after_a_rate_limit_skips_the_current_account():
    a, b = _acct("a", priority=1), _acct("b", priority=2)
    assert pool.next_after([a, b], a.id, NOW).account is b
    assert pool.next_after([a], a.id, NOW).state == "none"


def test_cooldown_uses_the_cli_reset_else_the_default():
    soon = {"kind": "rate_limited", "resets_at": "2026-11-27T11:05:00Z"}
    assert pool.cooldown_until(soon, NOW) == datetime(2026, 11, 27, 11, 5, tzinfo=UTC)
    assert pool.cooldown_until(
        {"kind": "rate_limited"}, NOW, default_minutes=15
    ) == NOW + timedelta(minutes=15)
    past = {"kind": "rate_limited", "resets_at": "2026-11-26T00:00:00Z"}
    assert pool.cooldown_until(past, NOW, default_minutes=15) == NOW + timedelta(minutes=15)
    absurd = {"kind": "rate_limited", "resets_at": "2027-06-01T00:00:00Z"}
    assert pool.cooldown_until(absurd, NOW, default_minutes=15) == NOW + timedelta(minutes=15)
    assert pool.cooldown_until({"kind": "auth"}, NOW) is None
    assert pool.cooldown_until(None, NOW) is None


def test_reorder_rewrites_priorities_and_rejects_unknown_ids():
    a, b, c = _acct("a", priority=1), _acct("b", priority=2), _acct("c", priority=3)
    assert pool.reorder([a, b, c], [c.id]) == {c.id: 10, a.id: 20, b.id: 30}
    with pytest.raises(ValueError, match="unknown"):
        pool.reorder([a], [uuid.uuid4()])
    with pytest.raises(ValueError, match="twice"):
        pool.reorder([a], [a.id, a.id])


# ── Environment ──────────────────────────────────────────────


def test_subscription_env_sets_the_home_and_strips_every_key():
    built = account_env.build_account_env("codex", "subscription", home="/h/codex/1")
    base = {"PATH": "/bin", "OPENAI_API_KEY": "sk-x", "CODEX_API_KEY": "sk-y", "CODEX_HOME": "/old"}
    env = built.apply(base)
    assert env == {"PATH": "/bin", "CODEX_HOME": "/h/codex/1"}
    assert built.names() == ["CODEX_HOME"]


def test_api_key_env_per_driver():
    for driver, var, home_var in (
        ("claude_code", "ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR"),
        ("codex", "CODEX_API_KEY", "CODEX_HOME"),
        ("gemini", "GEMINI_API_KEY", "GEMINI_CLI_HOME"),
    ):
        built = account_env.build_account_env(driver, "api_key", home="/h", api_key="sk-secret")
        env = built.apply({"PATH": "/bin"})
        assert env[var] == "sk-secret" and env[home_var] == "/h"
        assert set(built.overlay) <= allowed_env_names(driver, "api_key")
        assert "sk-secret" not in repr(built)  # the overlay is kept out of reprs
    with pytest.raises(AccountError, match="no key"):
        account_env.build_account_env("codex", "api_key", home="/h", api_key=None)


def test_vertex_env_and_its_allowlist():
    built = account_env.build_account_env(
        "claude_code", "vertex", home="/h", properties={"project": "p-12345", "region": "us-east5"}
    )
    assert built.overlay == {
        "CLAUDE_CONFIG_DIR": "/h",
        "CLAUDE_CODE_USE_VERTEX": "1",
        "ANTHROPIC_VERTEX_PROJECT_ID": "p-12345",
        "CLOUD_ML_REGION": "us-east5",
    }
    env = built.apply({"ANTHROPIC_API_KEY": "sk-stray"})
    assert "ANTHROPIC_API_KEY" not in env
    with pytest.raises(AccountError, match="Vertex"):
        account_env.build_account_env("codex", "vertex", home="/h", properties={})


def test_home_is_required_for_a_cli_with_a_home_variable():
    with pytest.raises(AccountError, match="home"):
        account_env.build_account_env("gemini", "subscription", home=None)


# ── Homes ────────────────────────────────────────────────────


def test_homes_are_private_and_stay_under_the_root(home_root, tmp_path):
    aid = uuid.uuid4()
    home = homes.ensure_home("t1", "codex", aid)
    assert home == home_root.resolve() / "t1" / "codex" / str(aid)
    for path in (home, home.parent, home.parent.parent):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    assert homes.checked_home(str(home)) == home

    outside = tmp_path / "elsewhere"
    outside.mkdir(mode=0o700)
    with pytest.raises(homes.HomeError, match="outside"):
        homes.checked_home(str(outside))
    with pytest.raises(homes.HomeError, match="outside"):
        homes.checked_home(str(home / ".." / ".." / ".." / ".."))
    link = home_root / "t1" / "codex" / "link"
    link.symlink_to(outside)
    with pytest.raises(homes.HomeError, match="symlink"):
        homes.checked_home(str(link))
    os.chmod(home, 0o755)
    with pytest.raises(homes.HomeError, match="readable"):
        homes.checked_home(str(home))
    with pytest.raises(homes.HomeError):
        homes.home_path("../t1", "codex", aid)


def test_remove_home_only_removes_a_checked_home(home_root, tmp_path):
    home = homes.ensure_home("t1", "gemini", uuid.uuid4())
    assert homes.remove_home(str(home)) is True and not home.exists()
    victim = tmp_path / "victim"
    victim.mkdir(mode=0o700)
    assert homes.remove_home(str(victim)) is False and victim.exists()


# ── Service ──────────────────────────────────────────────────


def test_to_dict_never_carries_a_secret_a_ref_a_path_or_the_hash():
    secret_ref = uuid.uuid4()
    row = _acct(
        "c",
        kind="api_key",
        secret_ref=secret_ref,
        secret_set_at=NOW,
        home_dir="/very/private/home",
        identity_masked="ra***@g***.com",
        identity_hash="f" * 64,
    )
    data = service.to_dict(row, now=NOW)
    flat = repr(data)
    assert data["has_secret"] is True and data["has_home"] is True
    assert data["identity"] == "ra***@g***.com"
    for leak in (str(secret_ref), "/very/private/home", "f" * 64, "secret_ref", "home_dir"):
        assert leak not in flat
    row.cooldown_until = NOW + timedelta(minutes=3)
    assert service.to_dict(row, now=NOW)["status"] == "cooling_down"
    assert service.home_info(row)["env"] == {"CODEX_HOME": "/very/private/home"}


async def test_create_account_makes_a_private_home_and_keeps_identity_masked(
    home_root, monkeypatch
):
    monkeypatch.setattr(identity, "identity_hash", lambda t, d, v, key=None: "h" * 64)
    session = FakeSession(None)  # no name or identity clash
    row = await service.create_account(
        session,
        "t1",
        driver="claude_code",
        name="Claude · work",
        kind="subscription",
        identity_value="raja@example.com",
    )
    assert session.added == [row]
    assert row.identity_masked == "ra***@e***.com" and row.identity_hash == "h" * 64
    assert "raja@example.com" not in repr(vars(row))
    assert Path(row.home_dir).is_dir() and stat.S_IMODE(Path(row.home_dir).stat().st_mode) == 0o700
    rendered = [sql(s) for s in session.statements]
    assert all("tenant_id = 't1'" in s for s in rendered)


async def test_create_refuses_a_duplicate_name(home_root):
    session = FakeSession(uuid.uuid4())  # the name query finds a row
    with pytest.raises(service.AccountConflictError):
        await service.create_account(session, "t1", driver="codex", name="dup", kind="subscription")
    assert session.added == []


async def test_get_account_is_tenant_scoped():
    session = FakeSession(None)
    with pytest.raises(service.AccountNotFoundError):
        await service.get_account(session, "t1", uuid.uuid4())
    assert "tenant_id = 't1'" in sql(session.statements[0])
    with pytest.raises(service.AccountNotFoundError):
        await service.get_account(FakeSession(None), "t1", "not-a-uuid")
    other = _acct(tenant_id="t2")
    with pytest.raises(service.AccountNotFoundError):
        await service.get_account(FakeSession(other), "t1", other.id)


class _FakeVault:
    """The vault API the service uses, in memory."""

    VaultError = type("VaultError", (Exception,), {})
    SecretNotFoundError = type("SecretNotFoundError", (VaultError,), {})

    def __init__(self):
        self.rows: dict = {}
        self.revoked: list = []
        self.resolved: list = []

    async def store(self, session, tenant_id, label, value, allowed_origins, secret_type):
        row = SimpleNamespace(id=uuid.uuid4(), handle=uuid.uuid4().hex, value=value)
        row.origins, row.tenant = allowed_origins, tenant_id
        self.rows[row.id] = row
        return row

    async def revoke(self, session, tenant_id, secret_id):
        self.revoked.append(secret_id)

    async def get(self, session, tenant_id, secret_id):
        if secret_id not in self.rows or secret_id in self.revoked:
            raise self.SecretNotFoundError
        return self.rows[secret_id]

    def handle_uri(self, row):
        return f"vault://{row.handle}"

    async def resolve_for_origin(self, session, tenant_id, handle, origin):
        row = next(r for r in self.rows.values() if f"vault://{r.handle}" == handle)
        if origin not in row.origins:
            raise self.VaultError("origin")
        self.resolved.append(origin)
        return row.value


@pytest.fixture
def fake_vault(monkeypatch):
    vault = _FakeVault()
    monkeypatch.setattr(service, "vault", vault)
    return vault


async def test_set_secret_goes_to_the_vault_only_and_revokes_the_old_one(fake_vault):
    row = _acct("k", kind="api_key", driver="codex")
    session = FakeSession(row)
    await service.set_secret(session, "t1", row.id, "sk-first-key")
    first = row.secret_ref
    await service.set_secret(session, "t1", row.id, "sk-second-key")
    assert fake_vault.revoked == [first] and row.secret_ref != first
    assert fake_vault.rows[row.secret_ref].origins == ["https://api.openai.com"]
    data = service.to_dict(row, now=NOW)
    assert "sk-second-key" not in repr(data) and "sk-second-key" not in repr(vars(row))
    with pytest.raises(AccountError, match="one line"):
        await service.set_secret(session, "t1", row.id, "two words")


async def test_set_secret_is_refused_for_a_subscription(fake_vault):
    row = _acct("s", kind="subscription")
    with pytest.raises(AccountError, match="takes no secret"):
        await service.set_secret(FakeSession(row), "t1", row.id, "sk-x")
    assert fake_vault.rows == {}


async def test_account_env_resolves_the_key_for_its_provider_origin(fake_vault, home_root):
    row = _acct("k", kind="api_key", driver="gemini")
    row.home_dir = str(homes.ensure_home("t1", "gemini", row.id))
    await service.set_secret(FakeSession(row), "t1", row.id, "AIza-test-key")
    built = await service.account_env(FakeSession(row), "t1", row)
    assert built.overlay["GEMINI_API_KEY"] == "AIza-test-key"
    assert fake_vault.resolved == ["https://generativelanguage.googleapis.com"]
    fake_vault.revoked.append(row.secret_ref)
    with pytest.raises(AccountError, match="revoked"):
        await service.account_env(FakeSession(row), "t1", row)


def test_apply_outcome_sets_cooldown_on_a_rate_limit_only():
    row = _acct("a")
    until = service.apply_outcome(
        row,
        success=False,
        failure={"kind": "rate_limited", "resets_at": "2026-11-27T10:00:00Z", "message": "429"},
        now=NOW,
        default_cooldown_minutes=15,
    )
    assert until == row.cooldown_until == datetime(2026, 11, 27, 10, 0, tzinfo=UTC)
    assert row.last_error.startswith("rate limited")
    other = _acct("b")
    assert (
        service.apply_outcome(
            other,
            success=False,
            failure={"kind": "auth", "hint": "run `codex login`"},
            now=NOW,
            default_cooldown_minutes=15,
        )
        is None
    )
    assert other.cooldown_until is None and "codex login" in other.last_error
    service.apply_outcome(other, success=True, failure=None, now=NOW, default_cooldown_minutes=15)
    assert other.last_error is None and other.last_used_at == NOW


async def test_pool_order_validates_ids():
    a, b = _acct("a", priority=1), _acct("b", priority=2)
    rows = await service.set_pool_order(FakeSession([a, b]), "t1", "codex", [str(b.id)])
    assert [r.name for r in rows] == ["b", "a"]
    with pytest.raises(AccountError):
        await service.set_pool_order(FakeSession([a]), "t1", "codex", [str(uuid.uuid4())])
    with pytest.raises(AccountError):
        await service.set_pool_order(FakeSession([a]), "t1", "codex", ["nope"])


# ── The driver hook ──────────────────────────────────────────


class _Factory:
    """``async with factory() as s`` -> a fresh FakeSession over the same rows."""

    def __init__(self, *results, fail: bool = False):
        self.results, self.fail = results, fail
        self.sessions: list[FakeSession] = []

    def __call__(self):
        if self.fail:
            raise RuntimeError("database down")
        session = FakeSession(*self.results)
        self.sessions.append(session)
        return session


@pytest.fixture
def accounts_on(monkeypatch):
    monkeypatch.setattr(settings, "driver_accounts_enabled", True)
    yield
    accounts_hook.configure(None)


async def test_hook_does_nothing_when_accounts_are_off(monkeypatch):
    monkeypatch.setattr(settings, "driver_accounts_enabled", False)
    factory = _Factory(fail=True)
    accounts_hook.configure(factory)
    try:
        lease = await accounts_hook.acquire("codex", "t1")
    finally:
        accounts_hook.configure(None)
    assert lease.refusal is None and not lease.active
    assert lease.apply({"A": "1"}) == {"A": "1"}


async def test_hook_with_no_account_runs_on_the_default_login(accounts_on):
    accounts_hook.configure(_Factory([]))
    lease = await accounts_hook.acquire("codex", "t1")
    assert lease.refusal is None and not lease.active


async def test_hook_fails_closed_when_the_pool_cannot_be_read(accounts_on):
    accounts_hook.configure(_Factory(fail=True))
    lease = await accounts_hook.acquire("codex", "t1")
    assert lease.refusal.metadata["exit_status"] == "account_unavailable"
    assert lease.refusal.success is False


async def test_hook_refuses_as_rate_limited_when_every_account_cools(accounts_on):
    rows = [_acct("a", cooldown=NOW + timedelta(hours=1))]
    accounts_hook.configure(_Factory(rows))
    lease = await accounts_hook.acquire("codex", "t1", now=NOW)
    failure = lease.refusal.metadata["failure"]
    assert failure["kind"] == "rate_limited" and failure["resets_at"] == "2026-11-27T10:00:00Z"
    assert lease.refusal.metadata["exit_status"] == "rate_limited"


async def test_hook_refuses_an_account_whose_home_is_unsafe(accounts_on, home_root, tmp_path):
    row = _acct("a", home_dir=str(tmp_path))  # outside the root
    accounts_hook.configure(_Factory([row]))
    lease = await accounts_hook.acquire("codex", "t1", now=NOW)
    assert lease.refusal.metadata["exit_status"] == "account_unavailable"
    assert "outside" in row.last_error


async def test_hook_picks_and_releases_with_cooldown_and_next(accounts_on, home_root):
    a = _acct("a", priority=1)
    b = _acct("b", priority=2)
    a.home_dir = str(homes.ensure_home("t1", "codex", a.id))
    accounts_hook.configure(_Factory([a, b]))
    lease = await accounts_hook.acquire("codex", "t1", now=NOW)
    assert lease.active and lease.name == "a"
    assert lease.apply({"OPENAI_API_KEY": "sk-x"}) == {"CODEX_HOME": a.home_dir}

    # release: get_account -> a, list_accounts -> [a, b]
    accounts_hook.configure(_Factory(a, [a, b]))
    result = DriverResult(
        success=False,
        metadata={
            "failure": {"kind": "rate_limited", "resets_at": "2026-11-27T12:00:00Z"},
            "rate_limits": [
                {"slot": "primary", "used_percent": 100.0, "window_minutes": 300,
                 "resets_at": "2026-11-27T12:00:00Z"},
            ],
        },
    )  # fmt: skip
    await accounts_hook.release(lease, result, now=NOW)
    info = result.metadata["account"]
    assert info["name"] == "a" and info["kind"] == "subscription" and info["env"] == ["CODEX_HOME"]
    assert info["cooldown_until"] == "2026-11-27T12:00:00Z"
    assert info["next"] == {"id": str(b.id), "name": "b"}
    assert a.cooldown_until == datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    assert a.home_dir not in repr(result.metadata)
    statements = [sql(s) for s in accounts_hook._sf().sessions[-1].statements]
    assert any("agent_account_limits" in s and "five_hour" in s for s in statements)


async def test_a_pinned_account_must_be_enabled_and_not_cooling(accounts_on):
    row = _acct("a", enabled=False)
    accounts_hook.configure(_Factory(row))
    lease = await accounts_hook.acquire("codex", "t1", account_id=row.id, now=NOW)
    assert lease.refusal.metadata["exit_status"] == "account_unavailable"
    row.enabled, row.cooldown_until = True, NOW + timedelta(minutes=9)
    lease = await accounts_hook.acquire("codex", "t1", account_id=row.id, now=NOW)
    assert lease.refusal.metadata["exit_status"] == "rate_limited"


# ── A real driver run on an account ──────────────────────────


def _recording_cli(tmp_path: Path, events: str) -> Path:
    seen = tmp_path / "seen.json"
    fake = tmp_path / "codex"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "data = {'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'env': dict(os.environ)}\n"
        f"json.dump(data, open({str(seen)!r}, 'w'))\n"
        f"sys.stdout.write({events!r})\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


_CODEX_OK = (
    '{"type":"thread.started","thread_id":"0199c0de-0000-7000-8000-00000000c0de"}\n'
    '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"done"}}\n'
    '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n'
)


async def test_codex_dispatch_runs_in_the_account_home_with_its_key(
    accounts_on, home_root, fake_vault, tmp_path, monkeypatch
):
    import json

    from life_graph.drivers.codex import CodexDriver

    cli_run.clear_probe_cache()
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    monkeypatch.setattr(settings, "driver_host_env_passthrough", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-host-default-key")
    row = _acct("api", kind="api_key")
    row.home_dir = str(homes.ensure_home("t1", "codex", row.id))
    await service.set_secret(FakeSession(row), "t1", row.id, "sk-account-key")
    accounts_hook.configure(_Factory([row]))
    fake = _recording_cli(tmp_path, _CODEX_OK)
    work = tmp_path / "work"
    (work / ".git").mkdir(parents=True)
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code_change", instruction="do it",
        project_context={"path": str(work), "isolation": False},
    )  # fmt: skip

    result = await CodexDriver(binary=str(fake)).dispatch(packet, work)

    seen = json.loads((tmp_path / "seen.json").read_text())
    assert result.success, result.error
    assert seen["env"]["CODEX_HOME"] == row.home_dir
    assert seen["env"]["CODEX_API_KEY"] == "sk-account-key"
    assert "OPENAI_API_KEY" not in seen["env"]  # the host's key never reaches an account run
    assert result.metadata["account"]["name"] == "api"
    assert "sk-account-key" not in repr(result.metadata)


def test_accounts_are_off_by_default():
    from life_graph.config import Settings

    fields = Settings.model_fields
    assert fields["driver_accounts_enabled"].default is False
    assert fields["driver_accounts_codex_probe_enabled"].default is False


async def test_gemini_sign_in_check_follows_the_account_home(tmp_path):
    from life_graph.drivers.gemini import GeminiDriver

    home = tmp_path / "acct"
    (home / ".gemini").mkdir(parents=True)
    (home / ".gemini" / "oauth_creds.json").write_text("{}")
    driver = GeminiDriver()
    assert await driver.login_check("gemini", {"HOME": str(tmp_path / "none")}) is False
    env = {"HOME": str(tmp_path / "none"), "GEMINI_CLI_HOME": str(home)}
    assert await driver.login_check("gemini", env) is True
