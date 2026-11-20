"""The errand's browser lives in the sandbox, or the errand does not run.

``tools/errand.py`` used to hand :class:`~life_graph.services.browser_errand.BrowserDriver`
duty to the bridged Playwright MCP server, which drives *whatever browser that
server happens to own* — in practice one on the host, beside the application's
own credentials. The isolation chassis for errands already existed next to it
(``compose.sandbox.yaml``, ``Dockerfile.browser``, ``services/dev/sandbox.py``): a
non-root headless Chromium with a read-only root filesystem, every capability
dropped, tmpfs-only writable space and an ``internal: true`` network, driven
from outside over Playwright's own browser-server websocket. The two were never
joined up, so the chassis was a chassis and the real errand path was not
isolated at all.

This module is the join. :class:`IsolatedBrowserDriver` is the five-method
driver protocol over **that endpoint and no other**:

* it connects only to the configured browser-runtime endpoint
  (``LIFE_GRAPH_BROWSER_SANDBOX_URL``), never to a host browser;
* every way of not having that runtime — unset, malformed, unreachable,
  timing out, answering 5xx, dying mid-errand — is one
  :class:`~life_graph.services.dev.sandbox.SandboxUnavailableError`, which is a
  refusal to act rather than a reason to try something less contained;
* a session is opened per ``(tenant_id, errand_id)`` pair and closed with the
  errand, so two errands — and two tenants — never see each other's cookies,
  ``localStorage`` or history;
* :meth:`IsolatedBrowserDriver.current_origin` is read from the live page and
  validated, because that string is what a vault secret's origin check is made
  against; an unreadable answer is an error, never a guess.

The runtime is reached through an injectable
:class:`IsolatedBrowserTransport`, which is what makes the fail-closed
behaviour testable: the suite passes a transport that refuses to connect, or
one that answers, and needs neither Playwright nor a docker daemon.
:class:`PlaywrightServerTransport` is the real one and is the only place in
Life Graph that imports Playwright.

**What is supported, and what is deliberately not.** The five driver methods
are: ``navigate``, ``read_page`` (the body text), ``fill_field``, ``click`` and
``current_origin``. Deliberately unavailable, rather than half-working:
*downloads* (the context is created with ``accept_downloads=False`` — a file an
errand pulled down needs a policed destination, and there is not one yet),
*uploads*, *arbitrary script evaluation* (nothing here evaluates a string the
model wrote; ``current_origin`` runs one fixed expression this module owns),
and *any reuse of a session across errands*. ``read_page`` is the whole body,
not an accessibility snapshot, so element names are CSS selectors here rather
than the ``e12`` refs the bridged MCP driver used.

**Egress.** Every session this driver opens is created with an egress proxy in
front of it (``services/browser_egress_proxy.py``), passed to Playwright as
``new_context(proxy={"server": ...})`` so Chromium sends navigations,
redirects, sub-resources and XHR through it. The proxy judges each destination
with the same rules as ``services/destination_validator.py`` and then connects
to the **address it resolved**, which is what closes the DNS-rebinding window
the application-level check cannot: that check resolves a name and the browser
resolves it again, and a zone answering differently the second time wins that
race. Either a deployment runs the proxy
(``LIFE_GRAPH_BROWSER_SANDBOX_EGRESS_PROXY_URL``) or this driver mints an
ephemeral one per errand, fenced to that errand's approved origins and stopped
with it. With ``browser_sandbox_enforce_egress_proxy`` on — the default — a
proxy that cannot be started is a ``SandboxUnavailableError`` and the errand
does not run.

**The control channel is authenticated.** The sandbox browser server is
started with ``--path /<token>`` (``Dockerfile.browser``,
``SANDBOX_BROWSER_PATH``), so it answers the websocket upgrade on that one
path and refuses every other with a 404. :func:`control_endpoint` is the only
place that decides what this driver may connect to: it takes the path an
endpoint already carries, or fills a blank one from
``LIFE_GRAPH_BROWSER_SANDBOX_TOKEN``, and with
``browser_sandbox_require_token`` on — the default — an endpoint with no
usable token is a ``SandboxUnavailableError`` before a socket is opened. The
token is a credential, so it never reaches a log: every endpoint we format
goes through :func:`redacted`, and every message a client library hands back
goes through :func:`scrubbed`, because Playwright quotes the URL it was given.

**What is still not done.** Operational verification. No deployment has yet
run a browser errand through the proxy to a real site, so the path token, the
proxy and the network topology are joined up in configuration and in tests
rather than in evidence from a running stack. The compose file now ships the
proxy as its own ``egress`` service on a bridge the browser can reach — an
ephemeral proxy bound to the application's loopback is *not* reachable from a
container on an ``internal: true`` bridge, which is why the service exists —
but ``docs/AI_WORK_ORDER.md`` §10 is the record of what has and has not been
observed, and nothing here should be read as a claim beyond it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from urllib.parse import urlsplit

from life_graph.config import settings
from life_graph.services.browser_egress_proxy import BrowserEgressProxy
from life_graph.services.dev.sandbox import BROWSER_WS_PORT, SandboxUnavailableError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Awaitable, Callable, Iterable

logger = logging.getLogger(__name__)

#: The endpoint is read from settings (``LIFE_GRAPH_BROWSER_SANDBOX_URL`` /
#: ``LIFE_GRAPH_BROWSER_SANDBOX_WS_URL`` via the app's env prefix). This name is
#: consulted directly as a last resort so a container started with the variable
#: set works even where the settings object was built before it existed.
ENV_ENDPOINT = "LIFE_GRAPH_BROWSER_SANDBOX_URL"

#: ``browser_sandbox_mode``. "isolated" is the only mode that produces a
#: browser; everything else is "no browser", which is a closed failure.
MODE_ISOLATED = "isolated"
MODE_DISABLED = "disabled"
MODE_MOCK = "mock"
MODES = (MODE_ISOLATED, MODE_DISABLED, MODE_MOCK)

#: Schemes a browser-runtime endpoint may use. ``ws``/``wss`` is Playwright's
#: browser-server protocol; ``http``/``https`` is accepted because that is how
#: the endpoint is usually written down, and is normalised to ``ws`` below.
_ENDPOINT_SCHEMES = ("ws", "wss", "http", "https")

#: An origin as the page itself reports it. Deliberately a ``fullmatch``: this
#: string decides which origin a password is checked against, so anything we
#: cannot read cleanly and completely is an error, not a prefix to salvage.
#: The twin of ``tools/errand.py``'s ``_ORIGIN``, which searches instead
#: because an MCP reply arrives wrapped in a tool's prose.
_ORIGIN = re.compile(r"https?://[A-Za-z0-9._~%:\[\]-]+")

#: What the model (and so the owner) is told when there is no isolated runtime.
#: It says what is missing and what would fix it, and offers no second option,
#: because there is deliberately no less-contained browser to fall back to.
SANDBOX_OFFLINE = (
    "Isolated browser sandbox is offline or not configured. To run browser"
    " errands securely, the isolated browser container must be running."
)

#: Schemes an egress proxy may be addressed by. Playwright accepts all of
#: these in ``proxy.server``; ``BrowserEgressProxy`` itself speaks the first.
_PROXY_SCHEMES = ("http", "https", "socks5")

#: Shortest control-channel path token this module will accept. The token is
#: the only thing standing between a process that can reach port 9222 and a
#: browser it can drive, so a short one is not authentication: 16 characters
#: of ``secrets.token_urlsafe`` output is ~96 bits. Enforced, rather than
#: documented, because a deployment that set ``--path /browser`` would
#: otherwise believe it had a credential.
MIN_CONTROL_TOKEN_LENGTH = 16

#: What a control-channel path may be made of. No query, no fragment, no
#: whitespace, no control characters, no percent-escapes to unpick — the path
#: is compared byte for byte by the browser server, and a token that needs
#: encoding is a token that will not match.
_CONTROL_PATH = re.compile(r"[A-Za-z0-9._~/-]+")

#: Said when the control channel would be unauthenticated. Playwright's
#: browser server without ``--path`` accepts any connection that reaches the
#: port, and that connection can open any page and read any cookie the browser
#: holds, so this is a refusal rather than a warning.
CONTROL_CHANNEL_UNAUTHENTICATED = (
    "The isolated browser control channel is not authenticated: the endpoint"
    " carries no path token, so the errand will not run. Set"
    " LIFE_GRAPH_BROWSER_SANDBOX_TOKEN to the same value the browser container"
    " was started with (SANDBOX_BROWSER_PATH)."
)

#: Said when there *is* a path but it is not a credential — too short, or
#: spelled with characters the browser server would never match.
CONTROL_TOKEN_UNUSABLE = (
    "The isolated browser control channel's path token is not usable as a"
    f" credential (at least {MIN_CONTROL_TOKEN_LENGTH} characters of"
    " url-safe text), so the errand will not run."
)

#: Said when egress enforcement is on and there is no proxy to enforce it.
#: A browser with no egress control is a browser a page can redirect at the
#: metadata endpoint, so this is a refusal, not a warning.
EGRESS_PROXY_OFFLINE = (
    "The browser egress proxy is unavailable, so the isolated browser has no"
    " policed way out and the errand will not run."
)


class BrowserRuntimeUnusableError(RuntimeError):
    """The browser runtime answered, but not with a usable browser session.

    *status* carries the HTTP status when the websocket handshake was refused
    with one (a 502 from a proxy in front of a browser that is not up, say).
    :class:`IsolatedBrowserDriver` turns every one of these into
    :class:`~life_graph.services.dev.sandbox.SandboxUnavailableError`; the separate
    type exists so a transport can report *why* without each transport
    inventing its own exception.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        self.status = status
        super().__init__(message)


# ── The transport: how the driver reaches the sandboxed browser ──────────


@runtime_checkable
class IsolatedBrowserSession(Protocol):
    """One page in one freshly created, throwaway browser context.

    A session is the unit of isolation: it is opened for exactly one errand,
    it carries that errand's cookies and storage and nothing else, and
    :meth:`close` is what removes them. Implementations are async.
    """

    async def goto(self, url: str) -> None:
        """Navigate the page to *url*."""
        ...

    async def fill(self, field: str, value: str) -> None:
        """Type *value* into the element named by *field*."""
        ...

    async def click(self, selector: str) -> None:
        """Click the element named by *selector*."""
        ...

    async def text(self) -> str:
        """The readable text of the current page."""
        ...

    async def origin(self) -> str:
        """The live ``location.origin`` of the page, unmodified."""
        ...

    async def close(self) -> None:
        """Close the page and context, dropping cookies, storage and downloads."""
        ...


@runtime_checkable
class IsolatedBrowserTransport(Protocol):
    """How :class:`IsolatedBrowserDriver` gets a session out of the runtime.

    One async call, so a test injects a fake and the suite never needs
    Playwright or a container runtime.
    """

    async def open_session(
        self,
        *,
        endpoint_url: str,
        tenant_id: str,
        errand_id: str,
        timeout: float,
        proxy_url: str = "",
    ) -> IsolatedBrowserSession:
        """A fresh isolated session on *endpoint_url*, scoped to this errand.

        *proxy_url* is the egress proxy every request this session makes must
        go through (``services/browser_egress_proxy.py``). A transport that
        cannot honour it must raise rather than open an unproxied session: a
        browser that silently went direct would be the one failure the proxy
        exists to prevent. ``""`` means no proxy, which the driver only ever
        passes when egress enforcement has been deliberately turned off.

        Raises:
            BrowserRuntimeUnusableError: the runtime answered unusably.
            OSError: the runtime could not be reached at all.
        """
        ...


class _PlaywrightSession:
    """A :class:`IsolatedBrowserSession` over a Playwright context and page."""

    def __init__(self, browser: Any, context: Any, page: Any) -> None:
        self._browser = browser
        self._context = context
        self._page = page

    async def goto(self, url: str) -> None:
        await self._page.goto(url)

    async def fill(self, field: str, value: str) -> None:
        # The plaintext is an argument, never logged: Playwright's own client
        # does not log fill values, and nothing here writes one out.
        await self._page.fill(field, value)

    async def click(self, selector: str) -> None:
        await self._page.click(selector)

    async def text(self) -> str:
        return str(await self._page.inner_text("body"))

    async def origin(self) -> str:
        return str(await self._page.evaluate("() => location.origin"))

    async def close(self) -> None:
        """Drop everything this errand accumulated, then let the context go.

        The explicit cookie and storage clear is belt and braces — closing a
        Playwright context already discards its storage, and the container's
        profile is a tmpfs that dies with it. It is here so that a reused
        context (a future pooling change) cannot quietly keep a session alive
        past the errand that opened it.
        """
        with contextlib.suppress(Exception):
            await self._page.evaluate(
                "() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} }"
            )
        with contextlib.suppress(Exception):
            await self._context.clear_cookies()
        with contextlib.suppress(Exception):
            await self._context.clear_permissions()
        # These three are the ones that must work: an un-closed context keeps
        # a profile directory and a renderer alive inside the sandbox.
        await self._page.close()
        await self._context.close()
        await self._browser.close()


#: An HTTP status in a websocket-handshake failure message. Playwright reports
#: a refused upgrade as prose ("Unexpected server response: 404"), so the
#: status is read out of it rather than from a structured field.
_HANDSHAKE_STATUS = re.compile(r"\b(?:response|status(?:\s+code)?)[:\s]+([1-5]\d\d)\b", re.I)


def _handshake_status(message: str) -> int | None:
    """The HTTP status a refused websocket upgrade reported, if it said one."""
    found = _HANDSHAKE_STATUS.search(str(message or ""))
    return int(found.group(1)) if found else None


class PlaywrightServerTransport:
    """Connects to the sandbox browser's Playwright browser-server websocket.

    The only importer of Playwright in Life Graph, and deliberately a lazy
    import: the application does not need the client installed to start, and a
    deployment with no browser sandbox never pays for it.

    Every connection makes a **new context**, never the browser's default one,
    because a default context is shared by everything that connects to the
    server and would hand the next errand the previous errand's cookies.
    """

    async def open_session(
        self,
        *,
        endpoint_url: str,
        tenant_id: str,
        errand_id: str,
        timeout: float,
        proxy_url: str = "",
    ) -> IsolatedBrowserSession:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - depends on the extra
            raise SandboxUnavailableError(
                "the playwright client is not installed, so the isolated browser"
                " runtime cannot be driven"
            ) from exc

        manager = async_playwright()
        pw = await manager.start()
        try:
            try:
                browser = await pw.chromium.connect(endpoint_url, timeout=timeout * 1000)
            except Exception as exc:
                # A path-scoped browser server answers the websocket upgrade
                # with 404 on every path but its own, so this is what an
                # unauthenticated — or wrongly authenticated — control channel
                # looks like from here. It is reported as one unusable runtime
                # with the status attached, and the message is scrubbed first:
                # Playwright quotes the endpoint it was handed, token and all.
                status = _handshake_status(str(exc))
                raise BrowserRuntimeUnusableError(
                    f"the browser control endpoint {redacted(endpoint_url)} refused the"
                    f" handshake ({type(exc).__name__}:"
                    f" {scrubbed(str(exc), endpoint_url)[:200]})",
                    status=status,
                ) from None
            options: dict[str, Any] = {
                # No storage_state: a fresh context starts with no cookies and
                # no localStorage, which is the point. Downloads are refused
                # rather than written anywhere the next errand could read.
                "accept_downloads": False,
            }
            if proxy_url:
                # Per *context*, not per browser: the browser server is shared
                # by whatever connects to it, and a browser-level proxy would
                # be a setting one errand could leave behind for the next.
                # Chromium sends navigations, redirects, sub-resources and XHR
                # through this, which is why the proxy sees every destination
                # rather than only the one the application validated.
                options["proxy"] = {"server": proxy_url}
            context = await browser.new_context(**options)
            context.set_default_timeout(timeout * 1000)
            page = await context.new_page()
        except Exception:
            with contextlib.suppress(Exception):
                await manager.__aexit__(None, None, None)
            raise
        logger.info(
            "isolated browser session opened tenant=%s errand=%s endpoint=%s egress=%s",
            tenant_id,
            errand_id,
            redacted(endpoint_url),
            redacted(proxy_url) if proxy_url else "direct",
        )
        return _PlaywrightSession(_ManagedBrowser(browser, manager), context, page)


class _ManagedBrowser:
    """A connected browser whose ``close`` also stops the Playwright driver."""

    def __init__(self, browser: Any, manager: Any) -> None:
        self._browser = browser
        self._manager = manager

    async def close(self) -> None:
        try:
            await self._browser.close()
        finally:
            with contextlib.suppress(Exception):
                await self._manager.__aexit__(None, None, None)


# ── Where the runtime is, and whether there is one ──────────────────────


def redacted(endpoint: str) -> str:
    """*endpoint* with everything but scheme, host and port removed.

    A browser control endpoint is a remote-code-execution handle, and a
    deployment that puts a token in its path or query would otherwise have
    that token copied into every log line and error message the driver emits.
    """
    try:
        parts = urlsplit(endpoint or "")
    except ValueError:
        return "<unreadable endpoint>"
    if not parts.scheme or not parts.netloc:
        return "<unreadable endpoint>"
    host = parts.hostname or ""
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}"


def scrubbed(text: str, endpoint: str) -> str:
    """*text* with the endpoint's control-channel token taken out of it.

    A client library's error message routinely quotes the URL it was given
    ("connect ws://browser:9222/<token>"), and that message ends up in a log
    line or an exception the owner reads. The token is the credential for a
    remote-code-execution handle on the browser, so it is removed from any
    third-party text before it travels any further. :func:`redacted` does the
    same job for an endpoint we are formatting ourselves.
    """
    out = str(text or "")
    token = endpoint_token(endpoint)
    if token and len(token) >= 4:
        out = out.replace(token, "<redacted>")
    return out


def configured_endpoint() -> str:
    """The browser-runtime endpoint as a websocket URL, or ``""`` when unset.

    Read in the order a deployment would expect to win:
    ``browser_sandbox_ws_url`` (an explicit websocket override),
    ``browser_sandbox_url`` (the usual setting), then the environment variable
    directly, for a process whose settings object predates it.

    An ``http(s)://`` endpoint is normalised to ``ws(s)://``: the sandbox
    speaks Playwright's browser-server protocol over a websocket, and the
    address is routinely written down with the scheme people type.
    """
    raw = ""
    for candidate in (
        getattr(settings, "browser_sandbox_ws_url", "") or "",
        getattr(settings, "browser_sandbox_url", "") or "",
        os.environ.get(ENV_ENDPOINT, "") or "",
    ):
        raw = str(candidate).strip()
        if raw:
            break
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = (parts.scheme or "").lower()
    if scheme not in _ENDPOINT_SCHEMES or not parts.netloc:
        logger.warning(
            "browser sandbox endpoint is not a usable ws/http URL: %s", redacted(raw) or "<blank>"
        )
        return ""
    if scheme in ("http", "https"):
        parts = parts._replace(scheme="wss" if scheme == "https" else "ws")
    if not parts.port:
        # The browser server's port is not a web default; an endpoint written
        # without one means the sandbox's own.
        host = parts.hostname or ""
        host = f"[{host}]" if ":" in host else host
        parts = parts._replace(netloc=f"{host}:{BROWSER_WS_PORT}")
    return parts.geturl()


def control_token_required() -> bool:
    """Whether the control channel must carry a path token. Default **yes**.

    Missing setting reads as required, which is the fail-closed direction: a
    deployment that predates this slice gets the authenticated requirement
    rather than an open browser-control port.
    """
    raw = getattr(settings, "browser_sandbox_require_token", True)
    if isinstance(raw, str):
        return raw.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(raw)


def control_token() -> str:
    """``browser_sandbox_token``, trimmed of its slashes, or ``""``.

    ``""`` means "nothing configured", which with
    :func:`control_token_required` on is a refusal rather than a blank path.
    A value that is set but unusable as a credential is **not** silently
    accepted either: it comes back as ``""`` and is logged without its value,
    so a mistyped or far-too-short token fails the errand closed instead of
    producing a control channel that only looks authenticated.
    """
    raw = str(getattr(settings, "browser_sandbox_token", "") or "").strip().strip("/")
    if not raw:
        return ""
    if not _usable_control_token(raw):
        # Never the value itself: it is a credential, and this line goes to
        # the same log as everything else.
        logger.warning(
            "browser_sandbox_token is not usable as a control-channel credential"
            " (needs at least %d characters of url-safe text); it will not be used",
            MIN_CONTROL_TOKEN_LENGTH,
        )
        return ""
    return raw


def _usable_control_token(path: str) -> bool:
    """Whether *path* is long enough and plain enough to be the credential."""
    text = str(path or "").strip().strip("/")
    if len(text) < MIN_CONTROL_TOKEN_LENGTH:
        return False
    return _CONTROL_PATH.fullmatch(text) is not None


def endpoint_token(endpoint: str) -> str:
    """The path *endpoint* already carries, without its leading slash.

    A query or a fragment is not part of it: Playwright's ``--path`` is
    compared against the request path, so anything after ``?`` would never
    match and must not be mistaken for a credential that was supplied.
    """
    try:
        parts = urlsplit(str(endpoint or ""))
    except ValueError:
        return ""
    if parts.query or parts.fragment:
        return ""
    return (parts.path or "").strip().strip("/")


def control_endpoint(endpoint_url: str | None = None) -> str:
    """The endpoint the driver may actually connect to, token and all.

    This is the authenticated-control-channel requirement of
    ``docs/AI_WORK_ORDER.md`` §3, enforced in one place so that no caller can
    reach the browser-server websocket without it. The browser container is
    started with ``--path /<token>`` (``Dockerfile.browser``,
    ``SANDBOX_BROWSER_PATH``) and refuses the websocket upgrade on every other
    path, so the token in this URL is what the control channel is
    authenticated *with*.

    Resolution order, narrowest first:

    1. *endpoint_url* if given, else :func:`configured_endpoint`;
    2. the path the endpoint already carries wins — a URL written as
       ``ws://browser:9222/<token>`` is more specific than a separate setting,
       and a broker in front of the browser may need a path of its own;
    3. otherwise :func:`control_token` fills the blank path.

    Then the requirement: with :func:`control_token_required` on, an endpoint
    whose final path is empty, too short or not plain url-safe text is a
    :class:`~life_graph.services.dev.sandbox.SandboxUnavailableError`. The errand
    does not run, and it does not run over an unauthenticated channel either.

    Raises:
        SandboxUnavailableError: no endpoint, not a ws/http URL, or no usable
            path token when one is required. The message never contains the
            token — only :func:`redacted` forms of the endpoint appear.
    """
    raw = str(endpoint_url or "").strip()
    if raw:
        parts = urlsplit(raw)
        scheme = (parts.scheme or "").lower()
        if scheme not in _ENDPOINT_SCHEMES or not parts.netloc:
            raise SandboxUnavailableError(
                f"{SANDBOX_OFFLINE} (endpoint {redacted(raw)} is not a ws/http URL)"
            )
        if scheme in ("http", "https"):
            parts = parts._replace(scheme="wss" if scheme == "https" else "ws")
        endpoint = parts.geturl()
    else:
        endpoint = configured_endpoint()
    if not endpoint:
        raise SandboxUnavailableError(SANDBOX_OFFLINE)

    present = endpoint_token(endpoint)
    if not present:
        token = control_token()
        if token:
            parts = urlsplit(endpoint)
            endpoint = parts._replace(path=f"/{token}", query="", fragment="").geturl()
            present = token
    if not control_token_required():
        if not present:
            logger.warning(
                "browser control-channel authentication is off: %s is reachable by anything"
                " that can open the port",
                redacted(endpoint),
            )
        return endpoint
    if not present:
        raise SandboxUnavailableError(f"{CONTROL_CHANNEL_UNAUTHENTICATED} ({redacted(endpoint)})")
    if not _usable_control_token(present):
        raise SandboxUnavailableError(f"{CONTROL_TOKEN_UNUSABLE} ({redacted(endpoint)})")
    return endpoint


def browser_sandbox_available() -> bool:
    """True when an isolated browser runtime is configured for this process.

    Configuration, not reachability: whether the endpoint actually answers is
    decided by connecting to it, and that answer is a
    :class:`~life_graph.services.dev.sandbox.SandboxUnavailableError` at the moment
    an errand needs the browser rather than a cached health bit that could be
    stale in the unsafe direction.
    """
    return bool(configured_endpoint())


def sandbox_mode() -> str:
    """``browser_sandbox_mode``, lowercased. Unknown values read as disabled."""
    mode = str(getattr(settings, "browser_sandbox_mode", "") or "").strip().lower()
    if mode not in MODES:
        if mode:
            logger.warning(
                "unknown browser_sandbox_mode %r: browser errands will not run (known: %s)",
                mode,
                ", ".join(MODES),
            )
        return MODE_DISABLED
    return mode


def egress_proxy_enforced() -> bool:
    """Whether a browser errand may run without a proxy in front of it.

    Defaults to **on** when the setting is missing entirely, which is the
    fail-closed direction: a deployment that predates the setting gets
    enforcement rather than an unpoliced browser.
    """
    raw = getattr(settings, "browser_sandbox_enforce_egress_proxy", True)
    if isinstance(raw, str):
        return raw.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(raw)


def configured_egress_proxy_url() -> str:
    """``browser_sandbox_egress_proxy_url``, normalised, or ``""``.

    ``""`` means "nothing was configured", and the driver answers that by
    minting an ephemeral per-errand proxy of its own. A value that is *set but
    unusable* — no scheme, no host, a scheme Playwright would not accept — is
    also ``""`` here and is logged: a mistyped proxy address must fall back to
    the enforced path, never to going direct.
    """
    raw = str(getattr(settings, "browser_sandbox_egress_proxy_url", "") or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        logger.warning("browser egress proxy url cannot be parsed; it will not be used")
        return ""
    scheme = (parts.scheme or "").lower()
    if scheme not in _PROXY_SCHEMES or not parts.hostname:
        logger.warning(
            "browser egress proxy url is not a usable %s URL: %s",
            "/".join(_PROXY_SCHEMES),
            redacted(raw) or "<blank>",
        )
        return ""
    host = parts.hostname
    host = f"[{host}]" if ":" in host else host
    port = f":{parts.port}" if parts.port else ""
    return f"{scheme}://{host}{port}"


def _normalised_proxy_url(raw: str | None) -> str:
    """An explicitly passed proxy url, normalised like a configured one.

    Unusable reads as ``""`` — not as "go direct": the caller gets the
    enforced path, which either mints a proxy or refuses the errand.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        logger.warning("the egress proxy url passed to the driver cannot be parsed")
        return ""
    scheme = (parts.scheme or "").lower()
    if scheme not in _PROXY_SCHEMES or not parts.hostname:
        logger.warning("the egress proxy url passed to the driver is not usable")
        return ""
    host = parts.hostname
    host = f"[{host}]" if ":" in host else host
    port = f":{parts.port}" if parts.port else ""
    return f"{scheme}://{host}{port}"


def sandbox_timeout() -> float:
    """``browser_sandbox_timeout_seconds``, as a positive float."""
    raw = getattr(settings, "browser_sandbox_timeout_seconds", 30)
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        timeout = 30.0
    return timeout if timeout > 0 else 30.0


# ── The driver ──────────────────────────────────────────────────────────


class IsolatedBrowserDriver:
    """A :class:`~life_graph.services.browser_errand.BrowserDriver` that only
    ever drives the sandboxed browser.

    One instance per errand. *tenant_id* and *errand_id* are not decoration:
    they are the scope of the session this driver opens, they are what the
    transport names the context after, and a driver that cannot say which
    errand it is for is refused outright — an unscoped session is the thing
    this class exists to prevent.

    Nothing is connected in ``__init__`` beyond checking that there is
    something to connect *to*; the session is opened on the first step that
    needs the browser and closed by :meth:`close`. Used as an async context
    manager, that close is automatic::

        async with IsolatedBrowserDriver(tenant_id=t, errand_id=e) as driver:
            await executor.run(errand)

    Fail-closed in every direction:

    * no endpoint configured, or one that is not a usable ws/http URL →
      :class:`~life_graph.services.dev.sandbox.SandboxUnavailableError` from
      ``__init__``, before anything can mistake this driver for a working one;
    * unreachable, timing out, 5xx, or any other failure to establish the
      session → ``SandboxUnavailableError`` from the first step;
    * the runtime dying, or an operation timing out, mid-errand → the session
      is marked lost and every later step raises ``SandboxUnavailableError``
      too, rather than running on in a state nobody can describe;
    * closed, then used again → ``SandboxUnavailableError``, because silently
      opening a second context would resurrect an errand that was over.

    Raises:
        ValueError: *tenant_id* or *errand_id* is blank.
        SandboxUnavailableError: no usable isolated browser endpoint.
    """

    def __init__(
        self,
        *,
        tenant_id: str | None,
        errand_id: str | None,
        endpoint_url: str | None = None,
        transport: IsolatedBrowserTransport | None = None,
        timeout_seconds: float | None = None,
        proxy_url: str | None = None,
        allowed_origins: Iterable[str] | None = None,
        enforce_egress_proxy: bool | None = None,
        proxy_factory: Callable[..., BrowserEgressProxy] | None = None,
    ) -> None:
        self._tenant_id = str(tenant_id or "").strip()
        self._errand_id = str(errand_id or "").strip()
        if not self._tenant_id or not self._errand_id:
            # Not a SandboxUnavailableError: the sandbox is fine, the caller
            # asked for a session that could not be scoped to anything.
            raise ValueError("an isolated browser session needs both a tenant_id and an errand_id")
        # One place decides what this driver may connect to: normalisation,
        # the control-channel path token and the refusal when there is none
        # all live in ``control_endpoint``, so an explicitly passed endpoint
        # is held to exactly the same requirement as a configured one.
        self._endpoint = control_endpoint(endpoint_url)
        self._transport: IsolatedBrowserTransport = transport or PlaywrightServerTransport()
        self._timeout = float(timeout_seconds) if timeout_seconds else sandbox_timeout()
        self._session: IsolatedBrowserSession | None = None
        self._closed = False
        #: Set when the runtime stopped being usable part-way through. Separate
        #: from ``_closed`` so the reason a later step is refused is the honest
        #: one.
        self._lost = False
        # ── egress ───────────────────────────────────────────────────────
        #: A proxy somebody else runs, which this driver only points at. An
        #: explicitly passed url goes through the same normalisation as a
        #: configured one, and an unusable one reads as "none configured" so
        #: the enforced path takes over rather than the browser going direct.
        self._proxy_url = _normalised_proxy_url(proxy_url) or configured_egress_proxy_url()
        self._enforce_proxy = (
            egress_proxy_enforced() if enforce_egress_proxy is None else bool(enforce_egress_proxy)
        )
        #: The errand's fence, handed to an ephemeral proxy so a page that
        #: redirects the errand off the approved origins is stopped at the
        #: socket rather than trusted to say where it went.
        self._allowed_origins = tuple(str(o) for o in (allowed_origins or ()) if str(o).strip())
        self._proxy_factory = proxy_factory or BrowserEgressProxy
        #: The ephemeral proxy *this driver owns* and must therefore stop.
        #: ``None`` when a deployment-run proxy is configured, or when
        #: enforcement is off.
        self._proxy: BrowserEgressProxy | None = None

    # -- identity ---------------------------------------------------------

    @property
    def tenant_id(self) -> str:
        """The tenant this driver's session belongs to."""
        return self._tenant_id

    @property
    def errand_id(self) -> str:
        """The single errand run this driver's session belongs to."""
        return self._errand_id

    @property
    def endpoint(self) -> str:
        """The browser-runtime endpoint, with any credential material removed."""
        return redacted(self._endpoint)

    @property
    def session_scope(self) -> str:
        """``"<tenant>/<errand>"`` — what cookies and storage are keyed to.

        Two drivers never share a scope, which is the property the isolation
        tests assert: a session opened for one errand is not reachable from
        another, and not from another tenant at all.
        """
        return f"{self._tenant_id}/{self._errand_id}"

    @property
    def is_open(self) -> bool:
        """True while a live session exists."""
        return self._session is not None and not self._closed

    @property
    def egress_proxy_url(self) -> str:
        """The proxy this session's requests go through, or ``""``.

        Blank before the session is opened when the proxy is the ephemeral
        one — it has no port until it is listening.
        """
        if self._proxy is not None and self._proxy.is_running:
            return self._proxy.url
        return self._proxy_url

    @property
    def egress_proxy(self) -> BrowserEgressProxy | None:
        """The ephemeral proxy this driver owns, if it minted one.

        ``None`` when a deployment-run proxy is configured — then the denials
        are that proxy's audit trail, not this driver's.
        """
        return self._proxy

    @property
    def egress_enforced(self) -> bool:
        """Whether this driver refuses to open a session without a proxy."""
        return self._enforce_proxy

    # -- lifecycle --------------------------------------------------------

    async def __aenter__(self) -> IsolatedBrowserDriver:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session and remove everything this errand left behind.

        Idempotent, and safe to call on a driver that never opened a session.
        A failure to clean up is **not** swallowed: cookies that outlive the
        errand that set them are the isolation failing, so it comes back as
        :class:`~life_graph.services.dev.sandbox.SandboxUnavailableError` for the
        caller to log and report. The ephemeral egress proxy, if this driver
        minted one, is stopped either way — a listener left running past the
        errand is a way out left running past the errand.
        """
        session, self._session = self._session, None
        was_open = not self._closed
        self._closed = True
        try:
            if session is None:
                return
            try:
                await asyncio.wait_for(session.close(), timeout=self._timeout)
            except Exception as exc:
                logger.warning(
                    "isolated browser session %s could not be cleaned up: %s: %s",
                    self.session_scope,
                    type(exc).__name__,
                    exc,
                )
                raise SandboxUnavailableError(
                    f"the isolated browser session for {self.session_scope} could not be"
                    f" cleaned up ({type(exc).__name__})"
                ) from None
            if was_open:
                logger.info("isolated browser session closed scope=%s", self.session_scope)
        finally:
            # In a ``finally``, and after the session: a listener that outlives
            # the errand is a way out that outlives the errand, and a session
            # that would not close is exactly the case where that matters most.
            await self._stop_proxy()

    # -- the five protocol methods ----------------------------------------

    async def navigate(self, url: str) -> None:
        """Go to *url* in the sandboxed browser."""
        await self._act("navigate", lambda s: s.goto(url))

    async def fill_field(self, field: str, value: str) -> None:
        """Type *value* into *field*. The value is never logged."""
        await self._act("fill a field", lambda s: s.fill(field, value))

    async def click(self, selector: str) -> None:
        """Click *selector*."""
        await self._act("click", lambda s: s.click(selector))

    async def read_page(self) -> str:
        """The readable text of the current page, as untrusted data."""
        out = await self._act("read the page", lambda s: s.text())
        return out if isinstance(out, str) else str(out or "")

    async def current_origin(self) -> str:
        """Where the sandboxed browser **actually is**, as ``scheme://host[:port]``.

        Read live from the page every time, never remembered: this is the
        origin a vault secret is checked against, so a driver that answered
        with the origin it *expected* would defeat that check.

        Raises:
            RuntimeError: the browser reported nothing, or something that is
                not an origin. A blank answer would normalise to a blank
                origin, which compares equal to nothing and would fail an
                origin check for the wrong reason.
            SandboxUnavailableError: the runtime is gone.
        """
        raw = await self._act("read the current origin", lambda s: s.origin())
        text = raw.strip() if isinstance(raw, str) else ""
        found = _ORIGIN.fullmatch(text)
        if found is None:
            # The value itself is not in the message: it came from a page, and
            # a page's text does not belong in a log or an error unfenced.
            raise RuntimeError("the isolated browser did not report a usable origin")
        return found.group(0)

    # -- internals --------------------------------------------------------

    async def _session_or_open(self) -> IsolatedBrowserSession:
        """The live session, opening one on first use. Fails closed."""
        if self._closed:
            raise SandboxUnavailableError(
                f"the isolated browser session for {self.session_scope} is already closed"
            )
        if self._lost:
            raise SandboxUnavailableError(
                f"the isolated browser runtime for {self.session_scope} was lost mid-errand"
            )
        if self._session is None:
            self._session = await self._open()
        return self._session

    async def _egress_proxy_url(self) -> str:
        """The proxy this session must go through, starting one if need be.

        Three cases, and only the third involves this driver owning anything:

        * a deployment configured a proxy — use it, and do not manage its
          lifecycle;
        * enforcement is off — ``""``, said out loud in the log, because a
          browser going direct is a decision somebody made and it should be
          visible in the record of the errand;
        * neither — mint an ephemeral proxy bound to the loopback, scoped to
          this errand and fenced to its approved origins, and stop it in
          :meth:`close`.

        Raises:
            SandboxUnavailableError: enforcement is on and no proxy could be
                started. The errand does not run. A browser with no policed
                way out is the thing this refuses to produce.
        """
        if self._proxy_url:
            return self._proxy_url
        if not self._enforce_proxy:
            logger.warning(
                "browser egress enforcement is off: session %s will reach the network"
                " directly, with only the application-level destination check in front of it",
                self.session_scope,
            )
            return ""
        if self._proxy is not None and self._proxy.is_running:
            return self._proxy.url
        try:
            proxy = self._proxy_factory(
                allowed_origins=self._allowed_origins,
                tenant_id=self._tenant_id,
                errand_id=self._errand_id,
                timeout=self._timeout,
            )
            await asyncio.wait_for(proxy.start(), timeout=self._timeout)
        except Exception as exc:
            logger.warning(
                "no egress proxy for session %s: %s: %s",
                self.session_scope,
                type(exc).__name__,
                exc,
            )
            raise SandboxUnavailableError(
                f"{EGRESS_PROXY_OFFLINE} ({type(exc).__name__})"
            ) from None
        self._proxy = proxy
        logger.info(
            "ephemeral egress proxy for %s listening on %s (fence: %s)",
            self.session_scope,
            proxy.url,
            ", ".join(proxy.allowed_origins) or "public internet only",
        )
        return proxy.url

    async def _stop_proxy(self) -> None:
        """Stop the ephemeral proxy, if this driver minted one. Never raises."""
        proxy, self._proxy = self._proxy, None
        if proxy is None:
            return
        try:
            await asyncio.wait_for(proxy.stop(), timeout=self._timeout)
        except Exception as exc:  # noqa: BLE001 - best-effort: see below
            # The listener is on the loopback and dies with the process; a
            # failure to stop it is worth a line, not a second exception on
            # top of whatever is already being reported.
            logger.warning(
                "the egress proxy for %s would not stop: %s: %s",
                self.session_scope,
                type(exc).__name__,
                exc,
            )
        else:
            if proxy.denials:
                logger.info(
                    "egress proxy for %s denied %d destination(s): %s",
                    self.session_scope,
                    len(proxy.denials),
                    "; ".join(f"{d.requested}: {d.reason}" for d in proxy.denials[:5]),
                )

    async def _open(self) -> IsolatedBrowserSession:
        """Connect, or refuse. Every failure here is one closed failure."""
        proxy_url = await self._egress_proxy_url()
        try:
            session = await asyncio.wait_for(
                self._transport.open_session(
                    endpoint_url=self._endpoint,
                    tenant_id=self._tenant_id,
                    errand_id=self._errand_id,
                    timeout=self._timeout,
                    proxy_url=proxy_url,
                ),
                timeout=self._timeout,
            )
        except SandboxUnavailableError:
            raise
        except TimeoutError:
            raise SandboxUnavailableError(
                f"{SANDBOX_OFFLINE} (no answer from {self.endpoint} within {self._timeout:g}s)"
            ) from None
        except Exception as exc:
            # Deliberately everything: there is no failure to establish a
            # contained browser that should result in anything other than
            # refusing to run the errand. The type is kept, the endpoint is
            # redacted, and the errand stops here.
            status = getattr(exc, "status", None)
            detail = f"{type(exc).__name__}" + (f" {status}" if status else "")
            logger.warning(
                "isolated browser runtime at %s refused a session for %s: %s: %s",
                self.endpoint,
                self.session_scope,
                type(exc).__name__,
                scrubbed(str(exc), self._endpoint),
            )
            raise SandboxUnavailableError(
                f"{SANDBOX_OFFLINE} ({self.endpoint}: {detail})"
            ) from None
        if session is None:
            raise SandboxUnavailableError(
                f"{SANDBOX_OFFLINE} ({self.endpoint} returned no session)"
            )
        return session

    async def _act(
        self, what: str, call: Callable[[IsolatedBrowserSession], Awaitable[Any]]
    ) -> Any:
        """Run one driver call against the live session, or fail closed.

        A timeout or a connection-shaped error here means the contained
        browser stopped being a browser we can describe. Both mark the session
        lost, so the rest of the errand is refused rather than continuing
        against a page nobody knows the state of. *what* is a fixed phrase
        from this module — never a url, a selector or a value.
        """
        session = await self._session_or_open()
        try:
            return await asyncio.wait_for(call(session), timeout=self._timeout)
        except SandboxUnavailableError:
            self._lost = True
            raise
        except TimeoutError:
            self._lost = True
            raise SandboxUnavailableError(
                f"the isolated browser did not finish {what} within {self._timeout:g}s"
            ) from None
        except (ConnectionError, OSError, BrowserRuntimeUnusableError) as exc:
            self._lost = True
            logger.warning(
                "isolated browser session %s lost while trying to %s: %s: %s",
                self.session_scope,
                what,
                type(exc).__name__,
                scrubbed(str(exc), self._endpoint),
            )
            raise SandboxUnavailableError(
                f"the isolated browser runtime was lost while trying to {what}"
                f" ({type(exc).__name__})"
            ) from None

    def __repr__(self) -> str:
        return (
            f"IsolatedBrowserDriver(scope={self.session_scope!r},"
            f" endpoint={self.endpoint!r}, open={self.is_open})"
        )


__all__ = [
    "ENV_ENDPOINT",
    "MODES",
    "MODE_DISABLED",
    "MODE_ISOLATED",
    "MODE_MOCK",
    "SANDBOX_OFFLINE",
    "CONTROL_CHANNEL_UNAUTHENTICATED",
    "CONTROL_TOKEN_UNUSABLE",
    "MIN_CONTROL_TOKEN_LENGTH",
    "BrowserRuntimeUnusableError",
    "IsolatedBrowserDriver",
    "IsolatedBrowserSession",
    "IsolatedBrowserTransport",
    "PlaywrightServerTransport",
    "EGRESS_PROXY_OFFLINE",
    "browser_sandbox_available",
    "configured_egress_proxy_url",
    "configured_endpoint",
    "control_endpoint",
    "control_token",
    "control_token_required",
    "egress_proxy_enforced",
    "endpoint_token",
    "redacted",
    "sandbox_mode",
    "scrubbed",
    "sandbox_timeout",
]
