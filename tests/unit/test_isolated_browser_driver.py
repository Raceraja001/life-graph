"""An errand's browser is the sandboxed one, or there is no errand.

``tools/errand.py``'s driver seam used to answer with whatever browser the
bridged Playwright MCP server owned — in practice one on the host, beside the
application's credentials. These tests are about the seam after it was joined
to the isolation chassis (``services/browser_sandbox_driver.py``,
``compose.sandbox.yaml``), and specifically about the ways it must *refuse*:

* the sandboxed driver really does present all five driver methods, so the
  engine underneath cannot tell it from the fake the rest of the suite uses;
* every way of not having the contained runtime — unconfigured, unreachable,
  timing out, 5xx, no session — is one ``SandboxUnavailableError``, and no
  step runs;
* with the sandbox down, ``get_driver`` answers ``None`` *even when the MCP
  browser tools are registered and would work*. That is the fallback the work
  order forbids, so it is the test that matters most here;
* the browser context is closed on every exit: done, failed, and paused
  waiting for the owner's tap;
* two tenants and two errands get two sessions, with nothing shared;
* an origin the page did not report cleanly is an error, because that string
  is what a vault secret's origin check is made against.

No Playwright, no docker daemon and no DNS: the transport is a fake, the
session is ``tests.unit.fakes.FakeSession``, and name resolution is a dict.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

import pytest

from life_graph.autonomy.approvals import capability_store
from life_graph.core.tenant import tenant_scope
from life_graph.services import browser_sandbox_driver as bsd
from life_graph.services import destination_validator as dv
from life_graph.services.browser_errand import BrowserDriver
from life_graph.services.browser_sandbox_driver import (
    BrowserRuntimeUnusableError,
    IsolatedBrowserDriver,
)
from life_graph.services.sandbox import SandboxUnavailableError
from life_graph.storage import database
from life_graph.tools import errand
from tests.unit.fakes import FakeSession, session_factory

TENANT = "t1"
OTHER_TENANT = "t2"
BANK = "https://netbanking.hdfcbank.com"
START = f"{BANK}/login"
GOAL = "get this month's statement"
#: The control channel's shared secret: the path Playwright's browser server
#: was started with (`--path /<token>`, Dockerfile.browser) and the only path
#: on which it accepts a websocket upgrade. 32 url-safe characters, as a real
#: one would be — the driver refuses a short one, and a test that used "tok"
#: would be testing a token the application would never accept.
CONTROL_TOKEN = "IQ7naCGt3bRtNcHLIUqJbltB2VIaeDCk"
ENDPOINT = f"ws://browser:9222/{CONTROL_TOKEN}"

FAKE_DNS: dict[str, list[str]] = {"netbanking.hdfcbank.com": ["93.184.216.34"]}


@pytest.fixture(autouse=True)
def _offline_dns(monkeypatch):
    """Name resolution as a dict: these tests never touch a network."""

    def resolve(host: str, port: int) -> list[str]:
        try:
            return list(FAKE_DNS[host])
        except KeyError:
            raise socket.gaierror(socket.EAI_NONAME, f"no address for {host}") from None

    monkeypatch.setattr(dv, "_getaddrinfo", resolve)


@pytest.fixture(autouse=True)
def _sandbox_configured(monkeypatch):
    """An isolated runtime that is configured, a privileged owner tenant, and
    no leftover override on the driver seam."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "tool_privileged_tenants", TENANT, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_mode", "isolated", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_url", ENDPOINT, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_timeout_seconds", 5, raising=False)
    # A correctly configured deployment now includes an authenticated control
    # channel: the browser container was started with --path /<token> and the
    # application knows the same token. Tests that assert what happens when it
    # is *missing* set it to "" themselves.
    monkeypatch.setattr(settings, "browser_sandbox_token", CONTROL_TOKEN, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_require_token", True, raising=False)
    monkeypatch.delenv(bsd.ENV_ENDPOINT, raising=False)
    monkeypatch.setattr(errand, "_driver_override", None, raising=False)
    capability_store.clear()
    with tenant_scope(TENANT):
        yield
    capability_store.clear()


# ── A sandbox that is not a sandbox ──────────────────────────────────────


class FakeSandboxSession:
    """One session in the fake runtime: its own cookie jar and storage.

    Separate dicts per instance is the whole point — a test asserting that two
    errands do not share state is asserting that they were handed two of
    these, and that each one's jar stayed its own.
    """

    def __init__(self, scope: str, *, origin: str = BANK, page: str = "Closing balance 12,340.00"):
        self.scope = scope
        self.origin_value = origin
        self.page = page
        self.cookies: dict[str, str] = {}
        self.local_storage: dict[str, str] = {}
        self.calls: list[tuple] = []
        self.closed = False
        self.close_fails = False

    async def goto(self, url: str) -> None:
        self.calls.append(("goto", url))
        # A navigation sets a cookie, as a real login page would.
        self.cookies["session"] = f"cookie-for-{self.scope}"
        self.local_storage["last_url"] = url
        self.origin_value = url.split("/")[0] + "//" + url.split("/")[2]

    async def fill(self, field: str, value: str) -> None:
        self.calls.append(("fill", field))

    async def click(self, selector: str) -> None:
        self.calls.append(("click", selector))

    async def text(self) -> str:
        self.calls.append(("text",))
        return self.page

    async def origin(self) -> str:
        return self.origin_value

    async def close(self) -> None:
        self.calls.append(("close",))
        if self.close_fails:
            raise RuntimeError("the context would not go away")
        self.cookies.clear()
        self.local_storage.clear()
        self.closed = True

    @property
    def kinds(self) -> list[str]:
        return [c[0] for c in self.calls]


class FakeTransport:
    """A runtime that answers. Records who asked for what."""

    def __init__(self, *, origin: str = BANK, page: str = "Closing balance 12,340.00"):
        self.opened: list[dict[str, Any]] = []
        self.sessions: list[FakeSandboxSession] = []
        self._origin = origin
        self._page = page

    async def open_session(
        self,
        *,
        endpoint_url: str,
        tenant_id: str,
        errand_id: str,
        timeout: float,
        proxy_url: str = "",
    ) -> FakeSandboxSession:
        self.opened.append(
            {
                "endpoint_url": endpoint_url,
                "tenant_id": tenant_id,
                "errand_id": errand_id,
                "timeout": timeout,
                "proxy_url": proxy_url,
            }
        )
        session = FakeSandboxSession(
            f"{tenant_id}/{errand_id}", origin=self._origin, page=self._page
        )
        self.sessions.append(session)
        return session


class RefusingTransport:
    """A runtime that is not there. *failure* is what being not-there looks like."""

    def __init__(self, failure: BaseException | None = None, *, session: Any = ...):
        self.failure = failure
        self.session = session
        self.attempts = 0

    async def open_session(self, **kwargs: Any) -> Any:
        self.attempts += 1
        if self.failure is not None:
            raise self.failure
        if self.session is not ...:
            return self.session
        raise OSError("connection refused")


class HangingTransport:
    """A runtime that accepts the connection and then says nothing."""

    def __init__(self) -> None:
        self.attempts = 0

    async def open_session(self, **kwargs: Any) -> Any:
        self.attempts += 1
        await asyncio.sleep(60)
        raise AssertionError("the driver waited out a hung runtime")


def driver(
    transport: Any,
    *,
    tenant_id: str = TENANT,
    errand_id: str = "errand_abc",
    timeout_seconds: float = 0.2,
) -> IsolatedBrowserDriver:
    return IsolatedBrowserDriver(
        tenant_id=tenant_id,
        errand_id=errand_id,
        endpoint_url=ENDPOINT,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )


# ── The protocol ─────────────────────────────────────────────────────────


def test_driver_implements_browser_driver_protocol():
    """The engine takes a five-method protocol; the sandboxed driver is one.

    ``BrowserDriver`` is ``runtime_checkable``, so this is a method-presence
    check — which is exactly the claim being made: nothing in the engine, the
    policy or the vault needs to know that this driver's browser is in a
    container.
    """
    isolated = driver(FakeTransport())

    assert isinstance(isolated, BrowserDriver)
    for method in ("navigate", "fill_field", "click", "read_page", "current_origin"):
        assert callable(getattr(isolated, method))
    # Lifecycle is this driver's own addition: it owns a context, so it can
    # be asked to give it back, and it works as a context manager.
    assert callable(isolated.close)
    assert hasattr(isolated, "__aenter__") and hasattr(isolated, "__aexit__")


async def test_the_context_manager_closes_the_session():
    transport = FakeTransport()
    async with driver(transport) as isolated:
        await isolated.navigate(START)
        assert isolated.is_open

    assert transport.sessions[0].closed is True
    assert not isolated.is_open


# ── Fail closed: no runtime means no errand ──────────────────────────────


@pytest.mark.parametrize(
    "failure",
    [
        OSError("connection refused"),
        ConnectionRefusedError("nothing listening on 9222"),
        BrowserRuntimeUnusableError("bad gateway", status=502),
        BrowserRuntimeUnusableError("service unavailable", status=503),
        RuntimeError("the browser server closed the websocket"),
    ],
    ids=["unreachable", "refused", "http_502", "http_503", "unusable"],
)
async def test_driver_fails_closed_when_sandbox_offline(failure):
    """Unreachable, refused, 5xx or unusable: one closed failure, nothing run."""
    transport = RefusingTransport(failure)
    isolated = driver(transport)

    with pytest.raises(SandboxUnavailableError):
        await isolated.navigate(START)

    assert transport.attempts == 1
    assert not isolated.is_open
    # And every other step refuses too, rather than retrying into a runtime
    # that has already said no.
    for call in (
        isolated.read_page(),
        isolated.current_origin(),
        isolated.click("e1"),
        isolated.fill_field("e1", "value"),
    ):
        with pytest.raises(SandboxUnavailableError):
            await call


async def test_a_connection_that_times_out_is_a_closed_failure():
    transport = HangingTransport()
    isolated = driver(transport, timeout_seconds=0.05)

    with pytest.raises(SandboxUnavailableError) as caught:
        await isolated.read_page()

    assert "within" in str(caught.value)
    assert transport.attempts == 1


async def test_a_runtime_that_returns_no_session_is_a_closed_failure():
    isolated = driver(RefusingTransport(session=None))

    with pytest.raises(SandboxUnavailableError):
        await isolated.navigate(START)


def test_an_unconfigured_runtime_cannot_even_be_constructed(monkeypatch):
    """No endpoint, no driver: the refusal is at construction, not at step 3."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.delenv(bsd.ENV_ENDPOINT, raising=False)

    assert bsd.browser_sandbox_available() is False
    with pytest.raises(SandboxUnavailableError):
        IsolatedBrowserDriver(tenant_id=TENANT, errand_id="errand_abc")


@pytest.mark.parametrize(
    "endpoint",
    ["file:///etc/passwd", "javascript:alert(1)", "not-a-url", "ws://", "://browser:9222"],
)
def test_an_endpoint_that_is_not_a_browser_runtime_is_refused(endpoint):
    with pytest.raises(SandboxUnavailableError):
        IsolatedBrowserDriver(
            tenant_id=TENANT,
            errand_id="errand_abc",
            endpoint_url=endpoint,
            transport=FakeTransport(),
        )


async def test_a_session_lost_mid_errand_refuses_the_rest_of_it():
    """The runtime dying after step one does not leave the errand running.

    An errand that carried on against a page nobody can describe is the
    failure mode this is here to prevent: the session is marked lost and every
    later step is a closed failure.
    """

    class DyingSession(FakeSandboxSession):
        async def click(self, selector: str) -> None:
            raise ConnectionResetError("the browser went away")

    class DyingTransport(FakeTransport):
        async def open_session(self, **kwargs: Any) -> FakeSandboxSession:
            await super().open_session(**kwargs)
            session = DyingSession(f"{kwargs['tenant_id']}/{kwargs['errand_id']}")
            self.sessions[-1] = session
            return session

    transport = DyingTransport()
    isolated = driver(transport)
    await isolated.navigate(START)

    with pytest.raises(SandboxUnavailableError):
        await isolated.click("e1")
    with pytest.raises(SandboxUnavailableError):
        await isolated.read_page()
    assert transport.opened and len(transport.opened) == 1  # no silent reconnect


async def test_a_closed_driver_does_not_quietly_open_a_second_context():
    transport = FakeTransport()
    isolated = driver(transport)
    await isolated.navigate(START)
    await isolated.close()

    with pytest.raises(SandboxUnavailableError):
        await isolated.read_page()
    assert len(transport.opened) == 1


async def test_a_cleanup_that_fails_is_raised_not_swallowed():
    transport = FakeTransport()
    isolated = driver(transport)
    await isolated.navigate(START)
    transport.sessions[0].close_fails = True

    with pytest.raises(SandboxUnavailableError):
        await isolated.close()
    # Closing twice is still safe, and does not try the broken session again.
    await isolated.close()


# ── The seam: never a less contained browser ─────────────────────────────


def test_no_silent_fallback_to_mcp_when_isolated_mode(monkeypatch):
    """The MCP browser is registered and working. It is still not the answer.

    This is the regression test for §3's "do not silently fall back to a less
    isolated local/MCP driver": with the contained runtime unconfigured,
    ``get_driver`` has to answer ``None`` even though an MCP browser is right
    there and would have run the errand.
    """
    from life_graph.config import settings
    from life_graph.tools.registry import registry

    monkeypatch.setattr(settings, "browser_sandbox_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.delenv(bsd.ENV_ENDPOINT, raising=False)
    monkeypatch.setitem(registry._tools, f"{errand.MCP_PREFIX}browser_navigate", object())

    assert errand.browser_available() is True  # the bridge really is up
    assert errand.get_driver(errand_id="errand_abc", tenant_id=TENANT) is None


def test_the_mcp_driver_is_never_what_the_seam_returns(monkeypatch):
    """Configured or not, up or down, the answer is the sandbox or nothing."""
    from life_graph.config import settings
    from life_graph.tools.registry import registry

    monkeypatch.setitem(registry._tools, f"{errand.MCP_PREFIX}browser_navigate", object())

    for url, mode in (
        (ENDPOINT, "isolated"),
        ("", "isolated"),
        (ENDPOINT, "disabled"),
        (ENDPOINT, "mock"),
        (ENDPOINT, "something-nobody-implemented"),
    ):
        monkeypatch.setattr(settings, "browser_sandbox_url", url, raising=False)
        monkeypatch.setattr(settings, "browser_sandbox_mode", mode, raising=False)
        got = errand.get_driver(errand_id="errand_abc", tenant_id=TENANT)
        assert not isinstance(got, errand.MCPBrowserDriver)
        if (url, mode) == (ENDPOINT, "isolated"):
            assert isinstance(got, IsolatedBrowserDriver)
        else:
            assert got is None


def test_a_disabled_or_unknown_mode_runs_no_errands(monkeypatch):
    from life_graph.config import settings

    for mode in ("disabled", "", "ISOLATED-ish", "mcp"):
        monkeypatch.setattr(settings, "browser_sandbox_mode", mode, raising=False)
        assert errand.get_driver(errand_id="errand_abc", tenant_id=TENANT) is None


def test_the_seam_refuses_a_session_it_cannot_scope(monkeypatch):
    """No tenant or no errand id is no session: an unscoped context would be
    one that two errands could share."""
    assert errand.get_driver(errand_id=None, tenant_id=TENANT) is None
    assert errand.get_driver(errand_id="errand_abc", tenant_id=None) is None
    assert errand.get_driver(errand_id="   ", tenant_id="  ") is None

    with pytest.raises(ValueError):
        IsolatedBrowserDriver(tenant_id="", errand_id="errand_abc", endpoint_url=ENDPOINT)
    with pytest.raises(ValueError):
        IsolatedBrowserDriver(tenant_id=TENANT, errand_id="", endpoint_url=ENDPOINT)


def test_the_seam_builds_a_sandboxed_driver_scoped_to_this_run():
    got = errand.get_driver(errand_id="errand_abc", tenant_id=TENANT)

    assert isinstance(got, IsolatedBrowserDriver)
    assert got.session_scope == f"{TENANT}/errand_abc"
    assert got.endpoint == "ws://browser:9222"


def test_an_explicit_override_wins_and_is_the_only_way_in(monkeypatch):
    sentinel = FakeTransport()
    monkeypatch.setattr(errand, "_driver_override", sentinel, raising=False)

    assert errand.get_driver() is sentinel

    errand.set_driver_override(None)
    assert errand.get_driver() is None


# ── Where the runtime is ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("ws://browser:9222/", "ws://browser:9222/"),
        ("http://browser:9222/", "ws://browser:9222/"),
        ("https://browser:9222/", "wss://browser:9222/"),
        ("ws://browser", f"ws://browser:{bsd.BROWSER_WS_PORT}"),
        ("  ws://browser:9222/  ", "ws://browser:9222/"),
        ("", ""),
        ("file:///tmp/x", ""),
        ("browser:9222", ""),
    ],
)
def test_the_endpoint_is_read_as_a_websocket_or_not_at_all(monkeypatch, configured, expected):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", configured, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.delenv(bsd.ENV_ENDPOINT, raising=False)

    assert bsd.configured_endpoint() == expected


def test_the_environment_variable_is_the_last_resort(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.setenv(bsd.ENV_ENDPOINT, "ws://browser:9222/")

    assert bsd.configured_endpoint() == "ws://browser:9222/"

    # An explicit ws override wins over both.
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "ws://broker:7000/", raising=False)
    assert bsd.configured_endpoint() == "ws://broker:7000/"


def test_the_endpoint_is_never_reported_with_its_credentials_on_it():
    """A control endpoint is remote code execution on the browser. If a
    deployment puts a token in its path, that token does not get copied into
    every log line and error message."""
    isolated = IsolatedBrowserDriver(
        tenant_id=TENANT,
        errand_id="errand_abc",
        endpoint_url="ws://broker:7000/session/super-secret-token",
        transport=FakeTransport(),
    )

    assert isolated.endpoint == "ws://broker:7000"
    assert "super-secret-token" not in isolated.endpoint
    assert "super-secret-token" not in repr(isolated)
    assert bsd.redacted("ws://u:p@broker:7000/t") == "ws://broker:7000"


# ── The control channel is authenticated ─────────────────────────────────
# Playwright's browser server with no --path accepts any connection that can
# reach the port, and that connection can open any page and read any cookie
# the browser holds. The sandbox browser is therefore started with
# `--path /<token>` and answers 404 on every other path, which makes the token
# in the endpoint URL the credential for the control channel
# (docs/AI_WORK_ORDER.md §3, "separate authenticated control channel").


def test_the_token_fills_a_blank_path_and_reaches_the_transport(monkeypatch):
    """The endpoint the driver connects to carries the path, not just the port.

    A token nobody puts in the URL is a token the browser server never sees,
    so this asserts the whole way through: the setting, the composed endpoint
    and the string the transport is actually handed.
    """
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", "ws://browser:9222/", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_token", CONTROL_TOKEN, raising=False)

    assert bsd.control_endpoint() == f"ws://browser:9222/{CONTROL_TOKEN}"
    assert bsd.control_token() == CONTROL_TOKEN

    isolated = IsolatedBrowserDriver(
        tenant_id=TENANT, errand_id="errand_tok", transport=FakeTransport()
    )
    assert isolated._endpoint == f"ws://browser:9222/{CONTROL_TOKEN}"  # noqa: SLF001


async def test_the_token_is_the_endpoint_the_connection_is_made_to(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", "ws://browser:9222/", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_token", CONTROL_TOKEN, raising=False)
    transport = FakeTransport()
    isolated = IsolatedBrowserDriver(
        tenant_id=TENANT, errand_id="errand_tok", transport=transport, timeout_seconds=0.5
    )
    try:
        await isolated.read_page()
    finally:
        await isolated.close()

    assert transport.opened[0]["endpoint_url"] == f"ws://browser:9222/{CONTROL_TOKEN}"


@pytest.mark.parametrize(
    ("configured_url", "token"),
    [
        ("ws://browser:9222/", ""),
        ("ws://browser:9222", ""),
        # A query is not a path: Playwright compares --path against the
        # request path, so ?token=... would never match and must not be
        # mistaken for a credential that was supplied.
        (f"ws://browser:9222/?token={'x' * 32}", ""),
        # Too short to be a credential, in the URL and in the setting.
        ("ws://browser:9222/browser", ""),
        ("ws://browser:9222/", "short"),
        # Long enough, but spelled with characters the server would never
        # match byte for byte.
        ("ws://browser:9222/", "token with spaces and %% signs!!"),
    ],
    ids=[
        "no-path",
        "no-path-no-slash",
        "query-not-path",
        "short-path",
        "short-token",
        "unmatchable",
    ],
)
def test_an_unauthenticated_control_channel_refuses_the_errand(monkeypatch, configured_url, token):
    """No usable token, no browser. The refusal is at construction.

    Every one of these is a control channel that anything able to reach port
    9222 could drive, so each is a ``SandboxUnavailableError`` rather than a
    session — and ``get_driver`` answers ``None``, which is what makes the
    errand stop instead of looking for a less contained browser.
    """
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", configured_url, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_token", token, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_require_token", True, raising=False)

    with pytest.raises(SandboxUnavailableError) as caught:
        IsolatedBrowserDriver(tenant_id=TENANT, errand_id="errand_abc", transport=FakeTransport())
    assert "token" in str(caught.value).lower()
    assert errand.get_driver(errand_id="errand_abc", tenant_id=TENANT) is None


def test_an_explicitly_passed_endpoint_is_held_to_the_same_requirement(monkeypatch):
    """A caller that hands in an endpoint does not get to skip the token.

    ``control_endpoint`` is the one place that decides, so the argument path
    and the settings path cannot drift apart — which they would if the check
    lived next to the setting.
    """
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_token", "", raising=False)

    with pytest.raises(SandboxUnavailableError):
        IsolatedBrowserDriver(
            tenant_id=TENANT,
            errand_id="errand_abc",
            endpoint_url="ws://broker:7000/",
            transport=FakeTransport(),
        )
    # With a usable one in the url itself, the same call is fine.
    isolated = IsolatedBrowserDriver(
        tenant_id=TENANT,
        errand_id="errand_abc",
        endpoint_url=f"ws://broker:7000/{CONTROL_TOKEN}",
        transport=FakeTransport(),
    )
    assert isolated._endpoint.endswith(CONTROL_TOKEN)  # noqa: SLF001


def test_a_path_the_endpoint_already_carries_wins_over_the_setting(monkeypatch):
    """A broker in front of the browser may need a path of its own.

    The more specific value wins, and neither comes from model output: both
    are owner configuration, so this is a precedence rule and not a trust
    decision.
    """
    from life_graph.config import settings

    monkeypatch.setattr(
        settings, "browser_sandbox_url", "ws://broker:7000/session/qSHZ3n0bFvQdXg0u", raising=False
    )
    monkeypatch.setattr(settings, "browser_sandbox_token", CONTROL_TOKEN, raising=False)

    assert bsd.control_endpoint() == "ws://broker:7000/session/qSHZ3n0bFvQdXg0u"


def test_the_requirement_is_only_turned_off_deliberately_and_loudly(monkeypatch, caplog):
    """Off is for a deployment that authenticates the channel somewhere else.

    It is still not quiet: an unauthenticated control endpoint is written
    into the log, because somebody reading the record of an errand should be
    able to see that this was the configuration it ran under.
    """
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_url", "ws://browser:9222/", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_token", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_require_token", False, raising=False)

    with caplog.at_level(logging.WARNING, logger=bsd.logger.name):
        isolated = IsolatedBrowserDriver(
            tenant_id=TENANT, errand_id="errand_abc", transport=FakeTransport()
        )

    assert isolated._endpoint == "ws://browser:9222/"  # noqa: SLF001
    assert "not authenticated" in caplog.text or "reachable by anything" in caplog.text


def test_a_missing_setting_reads_as_required(monkeypatch):
    """A deployment that predates this slice gets the requirement, not an
    open browser-control port."""
    from life_graph.config import settings

    monkeypatch.delattr(settings, "browser_sandbox_require_token", raising=False)
    assert bsd.control_token_required() is True
    monkeypatch.setattr(settings, "browser_sandbox_require_token", "off", raising=False)
    assert bsd.control_token_required() is False


async def test_the_token_never_reaches_a_log_or_an_error(monkeypatch, caplog):
    """The credential does not travel with the complaint about it.

    Playwright quotes the endpoint it was handed ("connect ws://host/<token>"),
    and that text ends up in a log line and in the error the owner is shown.
    Both go through ``scrubbed`` first, so this asserts the whole surface: the
    exception, the log, ``repr`` and the driver's own ``endpoint`` property.
    """
    leak = f"connect ECONNREFUSED ws://browser:9222/{CONTROL_TOKEN} failed"
    isolated = driver(RefusingTransport(RuntimeError(leak)))

    with caplog.at_level(logging.DEBUG), pytest.raises(SandboxUnavailableError) as caught:
        await isolated.navigate(START)

    assert CONTROL_TOKEN not in str(caught.value)
    assert CONTROL_TOKEN not in caplog.text
    assert CONTROL_TOKEN not in repr(isolated)
    assert isolated.endpoint == "ws://browser:9222"
    assert (
        bsd.scrubbed(leak, ENDPOINT) == "connect ECONNREFUSED ws://browser:9222/<redacted> failed"
    )


async def test_a_refused_handshake_is_an_unusable_runtime(monkeypatch, caplog):
    """404 on the websocket upgrade is what a wrong token looks like.

    The path-scoped browser server answers every path but its own that way,
    so this is the shape of an unauthorised control-channel attempt arriving
    back at the driver: one closed failure, nothing retried, no fallback.
    """
    refusal = BrowserRuntimeUnusableError(
        f"the browser control endpoint refused the handshake"
        f" (Error: Unexpected server response: 404 at ws://browser:9222/{CONTROL_TOKEN})",
        status=404,
    )
    transport = RefusingTransport(refusal)
    isolated = driver(transport)

    with caplog.at_level(logging.DEBUG), pytest.raises(SandboxUnavailableError) as caught:
        await isolated.navigate(START)

    assert transport.attempts == 1
    assert "404" in str(caught.value)
    assert CONTROL_TOKEN not in str(caught.value)
    assert CONTROL_TOKEN not in caplog.text


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Error: Unexpected server response: 404", 404),
        ("websocket handshake failed with status code 401", 401),
        ("browserType.connect: status: 403 forbidden", 403),
        ("connect ECONNREFUSED 172.19.0.3:9222", None),
        ("", None),
    ],
)
def test_the_handshake_status_is_read_out_of_the_client_message(message, expected):
    """Playwright reports a refused upgrade as prose, not as a field."""
    assert bsd._handshake_status(message) == expected  # noqa: SLF001


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (f"ws://browser:9222/{CONTROL_TOKEN}", CONTROL_TOKEN),
        ("ws://browser:9222/a/b", "a/b"),
        ("ws://browser:9222/", ""),
        ("ws://browser:9222", ""),
        ("ws://browser:9222/t?x=1", ""),
        ("ws://browser:9222/t#frag", ""),
        ("", ""),
    ],
)
def test_the_path_a_endpoint_carries_is_read_exactly(endpoint, expected):
    assert bsd.endpoint_token(endpoint) == expected


def test_a_token_that_is_set_but_unusable_is_not_quietly_used(monkeypatch, caplog):
    """A mistyped token falls back to the refusal, never to an open channel.

    And the value does not appear in the warning: it is a credential even
    when it is a broken one, and the log is the wrong place to publish an
    almost-correct password.
    """
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_token", "tok", raising=False)
    with caplog.at_level(logging.WARNING, logger=bsd.logger.name):
        assert bsd.control_token() == ""
    assert "not usable" in caplog.text
    assert "tok" not in caplog.text.replace("token", "").replace("Token", "")


# ── Where the browser actually is ────────────────────────────────────────


async def test_current_origin_validation():
    """A page that will not say where it is cleanly is an error, not a guess.

    This string is what a ``vault://`` secret's origin check is made against,
    so a blank answer (which would normalise to a blank origin and compare
    equal to nothing) and a mangled one are both refused outright.
    """
    for bad in ("", "   ", "about:blank", "null", "not-an-origin", "javascript:alert(1)"):
        transport = FakeTransport(origin=bad)
        isolated = driver(transport)
        with pytest.raises(RuntimeError) as caught:
            await isolated.current_origin()
        assert not isinstance(caught.value, SandboxUnavailableError)
        # The page's own text is not in the message: it is untrusted content.
        if bad.strip():
            assert bad not in str(caught.value)

    # An origin with something else stapled to it is refused too: a prefix
    # match would let a page choose which origin the secret is checked for.
    transport = FakeTransport(origin=f"{BANK} and also https://evil.io")
    with pytest.raises(RuntimeError):
        await driver(transport).current_origin()


async def test_a_clean_origin_comes_back_as_it_was_reported():
    for good in (BANK, "http://localhost:3000", "https://[::1]:8443", f"  {BANK}  "):
        isolated = driver(FakeTransport(origin=good))
        assert await isolated.current_origin() == good.strip()


async def test_the_origin_is_read_live_every_time():
    """Never remembered: a driver that answered with the origin it *expected*
    would defeat the vault's origin check."""
    transport = FakeTransport()
    isolated = driver(transport)
    await isolated.navigate(START)
    assert await isolated.current_origin() == BANK

    transport.sessions[0].origin_value = "https://evil.io"
    assert await isolated.current_origin() == "https://evil.io"


# ── Two errands, two tenants, nothing shared ─────────────────────────────


async def test_tenant_and_errand_isolation():
    """Each errand gets its own session, named after it, and keeps it to itself."""
    transport = FakeTransport()
    first = driver(transport, tenant_id=TENANT, errand_id="errand_one")
    second = driver(transport, tenant_id=TENANT, errand_id="errand_two")
    third = driver(transport, tenant_id=OTHER_TENANT, errand_id="errand_one")

    for isolated in (first, second, third):
        await isolated.navigate(START)

    # Three sessions, each told exactly whose it is.
    assert [(o["tenant_id"], o["errand_id"]) for o in transport.opened] == [
        (TENANT, "errand_one"),
        (TENANT, "errand_two"),
        (OTHER_TENANT, "errand_one"),
    ]
    assert len({id(s) for s in transport.sessions}) == 3
    assert {d.session_scope for d in (first, second, third)} == {
        f"{TENANT}/errand_one",
        f"{TENANT}/errand_two",
        f"{OTHER_TENANT}/errand_one",
    }

    # Same tenant, different errand: no shared cookie jar or localStorage.
    jars = [s.cookies["session"] for s in transport.sessions]
    assert len(set(jars)) == 3
    assert transport.sessions[0].cookies != transport.sessions[1].cookies
    assert transport.sessions[0].local_storage is not transport.sessions[1].local_storage

    # And closing one leaves the others alone.
    await first.close()
    assert transport.sessions[0].cookies == {}
    assert transport.sessions[1].cookies != {}
    assert transport.sessions[2].cookies != {}


async def test_one_errand_opens_exactly_one_session():
    transport = FakeTransport()
    isolated = driver(transport)

    await isolated.navigate(START)
    await isolated.read_page()
    await isolated.current_origin()

    assert len(transport.opened) == 1
    assert transport.opened[0]["endpoint_url"] == ENDPOINT
    assert transport.sessions[0].kinds == ["goto", "text"]


# ── Through the real tool ────────────────────────────────────────────────


async def run_tool(
    monkeypatch,
    *,
    steps: list[dict] | None,
    transport: Any = None,
    session: FakeSession | None = None,
    allowed_origins: list[str] | None = None,
) -> tuple[dict, Any, FakeSession]:
    """``run_browser_errand`` with a sandboxed driver over a fake runtime.

    The seam is overridden with a real :class:`IsolatedBrowserDriver` — not a
    fake driver — so what is exercised is the production path: the engine, the
    policy, the vault origin check and this driver's own fail-closed
    behaviour, with only the container swapped out.
    """
    transport = transport if transport is not None else FakeTransport()
    session = session if session is not None else FakeSession()
    isolated = IsolatedBrowserDriver(
        tenant_id=TENANT,
        errand_id="errand_tool",
        endpoint_url=ENDPOINT,
        transport=transport,
        timeout_seconds=5,
    )
    monkeypatch.setattr(errand, "_driver_override", isolated, raising=False)
    monkeypatch.setattr(database, "async_session", session_factory(session))
    out = await errand.run_browser_errand(
        goal=GOAL,
        start_url=START,
        steps=steps,
        allowed_origins=[BANK] if allowed_origins is None else allowed_origins,
    )
    return json.loads(out), isolated, session


async def test_run_browser_errand_end_to_end_with_isolated_driver(monkeypatch):
    """A read-only errand runs in the sandbox and comes back fenced."""
    from life_graph.core.trust import UNTRUSTED_PREAMBLE

    transport = FakeTransport()
    out, isolated, session = await run_tool(
        monkeypatch, steps=[{"kind": "read_page"}], transport=transport
    )

    assert out["status"] == "done"
    assert out["steps_completed"] == 2
    assert "12,340.00" in out["extracted_data"]
    assert UNTRUSTED_PREAMBLE in out["extracted_data"]
    assert "cleanup_failed" not in out
    # It really went through the isolated runtime: one session, on the
    # sandbox endpoint, driven by the engine.
    assert [o["endpoint_url"] for o in transport.opened] == [ENDPOINT]
    assert transport.sessions[0].kinds[:2] == ["goto", "text"]
    assert session.added == []


async def test_errand_context_cleanup_on_completion_and_error(monkeypatch):
    """Done, paused, and blown up: the context is closed on all three.

    A paused errand is over as far as this process is concerned — resuming is
    a new tool call with a new session — so there is no exit on which the
    browser context outlives the errand.
    """
    # 1. Finished.
    transport = FakeTransport()
    out, isolated, _ = await run_tool(
        monkeypatch, steps=[{"kind": "read_page"}], transport=transport
    )
    assert out["status"] == "done"
    assert transport.sessions[0].closed is True
    assert not isolated.is_open

    # 2. Paused for the owner's tap — a fill_field needs approval.
    transport = FakeTransport()
    session = FakeSession()
    out, isolated, session = await run_tool(
        monkeypatch,
        steps=[{"kind": "fill_field", "field": "e7", "value": "raja@example.com"}],
        transport=transport,
        session=session,
    )
    assert out["status"] == "needs_approval"
    assert len(session.added) == 1  # the card went to the phone
    assert transport.sessions[0].closed is True
    assert not isolated.is_open

    # 3. Blown up: the engine raised part-way through.
    class ExplodingSession(FakeSandboxSession):
        async def text(self) -> str:
            raise ValueError("the engine fell over")

    class ExplodingTransport(FakeTransport):
        async def open_session(self, **kwargs: Any) -> FakeSandboxSession:
            await super().open_session(**kwargs)
            session = ExplodingSession(f"{kwargs['tenant_id']}/{kwargs['errand_id']}")
            self.sessions[-1] = session
            return session

    transport = ExplodingTransport()
    out, isolated, _ = await run_tool(
        monkeypatch, steps=[{"kind": "read_page"}], transport=transport
    )
    assert out["status"] == "failed"
    assert "ValueError" in out["error"]
    assert transport.sessions[0].closed is True
    assert not isolated.is_open


async def test_a_cleanup_failure_is_reported_on_the_reply(monkeypatch):
    """Cookies that outlive the errand are the isolation failing, so the reply
    says so rather than the log keeping it to itself."""

    class StickySession(FakeSandboxSession):
        async def close(self) -> None:
            raise RuntimeError("the context would not go away")

    class StickyTransport(FakeTransport):
        async def open_session(self, **kwargs: Any) -> FakeSandboxSession:
            await super().open_session(**kwargs)
            session = StickySession(f"{kwargs['tenant_id']}/{kwargs['errand_id']}")
            self.sessions[-1] = session
            return session

    out, _, _ = await run_tool(
        monkeypatch, steps=[{"kind": "read_page"}], transport=StickyTransport()
    )

    assert out["status"] == "done"
    assert out["cleanup_failed"] is True


async def test_the_tool_refuses_the_errand_when_the_sandbox_is_offline(monkeypatch):
    """No contained browser, no errand — and the reply says which it was."""
    from life_graph.config import settings
    from life_graph.tools.registry import registry

    monkeypatch.setattr(settings, "browser_sandbox_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.delenv(bsd.ENV_ENDPOINT, raising=False)
    # The MCP browser is up. It is still not used.
    monkeypatch.setitem(registry._tools, f"{errand.MCP_PREFIX}browser_navigate", object())
    session = FakeSession()
    monkeypatch.setattr(database, "async_session", session_factory(session))

    out = json.loads(
        await errand.run_browser_errand(
            goal=GOAL, start_url=START, steps=[{"kind": "read_page"}], allowed_origins=[BANK]
        )
    )

    assert out["status"] == "failed"
    assert out["reason"] == errand.SANDBOX_UNAVAILABLE
    assert out["message"] == errand.NO_BROWSER
    assert "isolated browser container must be running" in out["message"]
    # Nothing ran, and nothing was written.
    assert session.added == []


async def test_the_tool_reports_a_runtime_that_will_not_answer(monkeypatch):
    """The endpoint is configured but the container is down: a failed errand
    whose first step never happened, not a fallback to something else."""
    transport = RefusingTransport(OSError("connection refused"))
    out, isolated, _ = await run_tool(
        monkeypatch, steps=[{"kind": "read_page"}], transport=transport
    )

    assert out["status"] == "failed"
    # The first step is a navigate, and the engine asks the driver where it is
    # before it sends it anywhere: the refusal lands on step 0, before any
    # navigation happened.
    assert out["step"] == 0
    assert "Isolated browser sandbox is offline" in out["error"]
    assert transport.attempts == 1
    assert not isolated.is_open


async def test_a_vault_fill_is_still_refused_without_the_owners_tap(monkeypatch):
    """The isolation change did not widen anything: an outward step with no
    mandate behind it is still denied and still becomes a question."""
    transport = FakeTransport()
    out, _, session = await run_tool(
        monkeypatch,
        steps=[{"kind": "fill_field", "field": "e7", "value": "bank/password", "is_secret": True}],
        transport=transport,
    )

    assert out["status"] == "needs_approval"
    assert len(session.added) == 1  # the owner is asked, on their phone
    # Nothing was typed into the page, and no secret was resolved for it: the
    # session only ever navigated, and was then closed.
    assert transport.sessions[0].kinds == ["goto", "close"]
