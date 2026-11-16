"""The errand's browser lives in the sandbox, or the errand does not run.

``tools/errand.py`` used to hand :class:`~life_graph.services.browser_errand.BrowserDriver`
duty to the bridged Playwright MCP server, which drives *whatever browser that
server happens to own* — in practice one on the host, beside the application's
own credentials. The isolation chassis for errands already existed next to it
(``compose.sandbox.yaml``, ``Dockerfile.browser``, ``services/sandbox.py``): a
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
  :class:`~life_graph.services.sandbox.SandboxUnavailableError`, which is a
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

**What this slice is not.** The default-deny egress proxy, the authenticated
control channel in front of the browser-server websocket, and network-layer
destination pinning are the remaining parts of §3 of ``docs/AI_WORK_ORDER.md``.
Until they are deployed, this driver's isolation is process/container
isolation plus the application-level destination validator — not yet an
egress-enforced boundary. Nothing here should be read as a claim that it is.
Two consequences worth stating plainly: the browser-server websocket is still
unauthenticated on the internal network, so nothing other than this
application should be attached to that network; and with ``internal: true``
and no proxy the container has no route to any real site, so an errand's
navigation fails at the network. Both are closed failures, which is the right
direction, but neither is the finished control.
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
from life_graph.services.sandbox import BROWSER_WS_PORT, SandboxUnavailableError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Awaitable, Callable

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


class BrowserRuntimeUnusableError(RuntimeError):
    """The browser runtime answered, but not with a usable browser session.

    *status* carries the HTTP status when the websocket handshake was refused
    with one (a 502 from a proxy in front of a browser that is not up, say).
    :class:`IsolatedBrowserDriver` turns every one of these into
    :class:`~life_graph.services.sandbox.SandboxUnavailableError`; the separate
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
        self, *, endpoint_url: str, tenant_id: str, errand_id: str, timeout: float
    ) -> IsolatedBrowserSession:
        """A fresh isolated session on *endpoint_url*, scoped to this errand.

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
        self, *, endpoint_url: str, tenant_id: str, errand_id: str, timeout: float
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
            browser = await pw.chromium.connect(endpoint_url, timeout=timeout * 1000)
            context = await browser.new_context(
                # No storage_state: a fresh context starts with no cookies and
                # no localStorage, which is the point. Downloads are refused
                # rather than written anywhere the next errand could read.
                accept_downloads=False,
            )
            context.set_default_timeout(timeout * 1000)
            page = await context.new_page()
        except Exception:
            with contextlib.suppress(Exception):
                await manager.__aexit__(None, None, None)
            raise
        logger.info(
            "isolated browser session opened tenant=%s errand=%s endpoint=%s",
            tenant_id,
            errand_id,
            redacted(endpoint_url),
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


def browser_sandbox_available() -> bool:
    """True when an isolated browser runtime is configured for this process.

    Configuration, not reachability: whether the endpoint actually answers is
    decided by connecting to it, and that answer is a
    :class:`~life_graph.services.sandbox.SandboxUnavailableError` at the moment
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
      :class:`~life_graph.services.sandbox.SandboxUnavailableError` from
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
    ) -> None:
        self._tenant_id = str(tenant_id or "").strip()
        self._errand_id = str(errand_id or "").strip()
        if not self._tenant_id or not self._errand_id:
            # Not a SandboxUnavailableError: the sandbox is fine, the caller
            # asked for a session that could not be scoped to anything.
            raise ValueError("an isolated browser session needs both a tenant_id and an errand_id")
        endpoint = str(endpoint_url or "").strip() or configured_endpoint()
        if endpoint_url:
            # An explicitly passed endpoint goes through the same normalisation
            # and the same refusal as a configured one.
            parts = urlsplit(endpoint)
            if (parts.scheme or "").lower() not in _ENDPOINT_SCHEMES or not parts.netloc:
                raise SandboxUnavailableError(
                    f"{SANDBOX_OFFLINE} (endpoint {redacted(endpoint)} is not a ws/http URL)"
                )
            if (parts.scheme or "").lower() in ("http", "https"):
                endpoint = parts._replace(
                    scheme="wss" if parts.scheme.lower() == "https" else "ws"
                ).geturl()
        if not endpoint:
            raise SandboxUnavailableError(SANDBOX_OFFLINE)
        self._endpoint = endpoint
        self._transport: IsolatedBrowserTransport = transport or PlaywrightServerTransport()
        self._timeout = float(timeout_seconds) if timeout_seconds else sandbox_timeout()
        self._session: IsolatedBrowserSession | None = None
        self._closed = False
        #: Set when the runtime stopped being usable part-way through. Separate
        #: from ``_closed`` so the reason a later step is refused is the honest
        #: one.
        self._lost = False

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
        :class:`~life_graph.services.sandbox.SandboxUnavailableError` for the
        caller to log and report.
        """
        session, self._session = self._session, None
        was_open = not self._closed
        self._closed = True
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

    async def _open(self) -> IsolatedBrowserSession:
        """Connect, or refuse. Every failure here is one closed failure."""
        try:
            session = await asyncio.wait_for(
                self._transport.open_session(
                    endpoint_url=self._endpoint,
                    tenant_id=self._tenant_id,
                    errand_id=self._errand_id,
                    timeout=self._timeout,
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
                exc,
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
                exc,
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
    "BrowserRuntimeUnusableError",
    "IsolatedBrowserDriver",
    "IsolatedBrowserSession",
    "IsolatedBrowserTransport",
    "PlaywrightServerTransport",
    "browser_sandbox_available",
    "configured_endpoint",
    "redacted",
    "sandbox_mode",
    "sandbox_timeout",
]
