"""The sandboxed browser's only way out, and it pins where that is.

``services/destination_validator.py`` already decides whether a URL names
somewhere a browser errand may be sent, and ``tools/errand.py`` asks it before
any driver sees a destination. That check is necessary and it is not
sufficient, for a reason its own docstring states: it resolves the name, and
then the browser resolves the name *again* when it connects. A DNS server that
answers ``93.184.216.34`` to the application and ``127.0.0.1`` to Chromium a
moment later has not been stopped by anything — the classic time-of-check /
time-of-use gap, which goes by DNS rebinding when the second answer is the
attack. The same gap opens on every redirect, every sub-resource, every
``fetch()`` a page's own script makes: the application validated *one* URL, and
a page makes as many requests as it likes.

This module closes it by moving the decision to the place the connection is
actually made. :class:`BrowserEgressProxy` is a forward proxy the sandboxed
browser is pointed at (``new_context(proxy={"server": ...})``), and it is the
enforcement point rather than a second opinion:

* it sees **every** request the browser makes — the first navigation, each
  redirect hop, every image, XHR and websocket — because a browser configured
  with a proxy sends them all through it;
* it judges the destination with
  :func:`~life_graph.services.destination_validator.split_destination` and
  :func:`~life_graph.services.destination_validator.address_refusal`, so the
  rules here are the *same* rules, not a second set that can drift: loopback,
  private, link-local, carrier-NAT, reserved, documentation, benchmarking,
  multicast, broadcast and the unspecified address, the cloud metadata
  addresses by name, and the IPv6 spellings that carry an IPv4 address inside
  them (``::ffff:127.0.0.1``, NAT64, 6to4);
* it resolves the name **once**, requires *every* address it resolved to to be
  permitted, and then opens the TCP connection **to that address**, never to
  the name. The browser's second lookup never happens, so there is no second
  answer to poison. That pin is the whole point of this module;
* only web ports (:data:`DEFAULT_ALLOWED_PORTS`) and only ``http``/``https``:
  a ``CONNECT`` to 22, 25, 3306, 5432, 6379 or 9222 is not a web request, and
  ``CONNECT`` is otherwise a general-purpose TCP relay;
* with an origin allowlist it enforces the errand's fence here too, so a page
  that redirects an approved errand somewhere else is stopped at the socket
  rather than trusted to report where it went.

Everything that is not plainly permitted gets ``HTTP/1.1 403 Forbidden`` and
the connection is closed **without the upstream connection being opened at
all**. There is no error path that reaches the destination anyway.

**What this does not do, stated plainly.**

*It does not terminate TLS.* A ``CONNECT`` tunnel relays bytes, so the
browser's TLS session is with the real site and the certificate and SNI are the
browser's own. That is deliberate: a proxy holding a forged CA to read an
errand's traffic would be a second place the owner's banking session exists in
cleartext. The consequence is that inside an established tunnel this module
sees ciphertext — it authorises *where* a connection goes, not what travels
through it. Response-size and content limits belong to the browser and the
errand engine, not here.

*It is not, by itself, default-deny.* A proxy only constrains a browser that
cannot route around it. That property comes from the network: the sandbox's
``internal: true`` bridge gives the browser container no gateway, so the proxy
is its only path off the bridge. Pointing a browser with a working default
route at this proxy would leave ``--proxy-bypass-list``, WebRTC, DNS and plain
mis-configuration as ways out. Proxy *and* no route; neither alone.

*Reachability is a deployment question.* An in-process ephemeral proxy bound
to ``127.0.0.1`` is reachable from the application and from this test suite,
and **not** from a container on an internal-only bridge. A compose deployment
wants the proxy as its own service attached to both the internal bridge and an
egress network, with ``LIFE_GRAPH_BROWSER_SANDBOX_EGRESS_PROXY_URL`` pointing
at it. ``docs/AI_WORK_ORDER.md`` §10 records that this part is not yet
operationally verified.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import ipaddress
import logging
import os
import signal
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from life_graph.services.destination_validator import (
    DestinationRefusedError,
    address_refusal,
    split_destination,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Awaitable, Callable, Iterable, Sequence

logger = logging.getLogger(__name__)

#: Ports a browser errand may be sent to. A list, not a blocklist: the reason
#: ``CONNECT host:22`` is refused is that 22 is not on here, so a port nobody
#: thought about is refused by default rather than allowed by oversight.
#: 8080/8443 are included because self-hosted sites and staging environments
#: really do answer there; 9222 is deliberately absent — that is the sandbox
#: browser's own control port, and an errand reaching it would be the browser
#: driving itself.
DEFAULT_ALLOWED_PORTS: tuple[int, ...] = (80, 443, 8080, 8443)

#: Which scheme a port implies, for a ``CONNECT`` (which carries only an
#: authority, never a scheme). Used to decide what an origin allowlist entry
#: is being compared against.
_PORT_SCHEME: dict[int, str] = {80: "http", 8080: "http", 443: "https", 8443: "https"}

#: Schemes this proxy will forward. The same two the destination validator
#: allows: no ``file:``, ``data:``, ``ftp:`` or ``javascript:``.
ALLOWED_SCHEMES: tuple[str, ...] = ("http", "https")

#: Longest request head (request line plus headers) this proxy will read. A
#: client that sends more than this before ``\r\n\r\n`` is not making a web
#: request; the cap is what stops it from making the proxy hold the bytes.
MAX_HEAD_BYTES = 64 * 1024

#: Relay chunk size. Big enough that a page download is not syscall-bound.
_RELAY_CHUNK = 64 * 1024

#: How many tunnels one proxy will hold open at once. A page opens several
#: connections, so this is not 1 per errand; it is a ceiling, so a page that
#: opens thousands exhausts its own limit instead of the host's descriptors.
DEFAULT_MAX_TUNNELS = 64

#: How many decisions are kept for inspection. Bounded: a long errand against
#: a busy page makes hundreds, and this list exists for tests and for an audit
#: line, not as a log.
_MAX_RECORDED = 256

#: The refusal, byte for byte. No body and no detail: the client here is a
#: browser rendering a page the owner did not write, and *why* a destination
#: was refused is for the owner's audit trail, not for the page to read.
FORBIDDEN_RESPONSE = b"HTTP/1.1 403 Forbidden\r\n\r\n"
BAD_REQUEST_RESPONSE = b"HTTP/1.1 400 Bad Request\r\n\r\n"
BUSY_RESPONSE = b"HTTP/1.1 503 Service Unavailable\r\n\r\n"
GATEWAY_RESPONSE = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
TUNNEL_ESTABLISHED = b"HTTP/1.1 200 Connection Established\r\n\r\n"

#: Headers that are between a client and *this* proxy and must not be passed
#: on. ``Proxy-Authorization`` especially: it is a credential for the hop, and
#: forwarding it would hand it to the destination.
_HOP_BY_HOP = frozenset({"proxy-connection", "proxy-authorization", "keep-alive", "upgrade"})


class EgressDeniedError(Exception):
    """This destination is not one the sandboxed browser may reach.

    *reason* is a short machine-ish phrase for the audit record; the client is
    told nothing but ``403``.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class PinnedTarget:
    """A destination that passed every check, and the address it is pinned to.

    *ip* is what the socket connects to. *host* is carried alongside it for the
    ``Host`` header and for the audit record — it is never resolved a second
    time, which is the property that makes rebinding impossible here.
    """

    scheme: str
    host: str
    port: int
    ip: str
    #: Every address the name resolved to, all of which were permitted. Kept so
    #: an audit record can show that the all-addresses rule was applied rather
    #: than just the one that was used.
    resolved: tuple[str, ...] = ()

    @property
    def origin(self) -> str:
        """``scheme://host[:port]``, default port omitted."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        default = 443 if self.scheme == "https" else 80
        port = "" if self.port == default else f":{self.port}"
        return f"{self.scheme}://{host}{port}"


@dataclass(frozen=True, slots=True)
class EgressDecision:
    """One authorisation decision, for the audit trail and for tests."""

    allowed: bool
    method: str
    #: The authority as the client asked for it, bounded. Untrusted text.
    requested: str
    reason: str = ""
    target: PinnedTarget | None = None


@dataclass(slots=True)
class _OriginRule:
    """One entry of an origin allowlist, parsed once."""

    host: str
    #: ``None`` when the entry named no scheme, which then matches either.
    scheme: str | None
    #: ``None`` when the entry named no port, which then matches the scheme's
    #: default only — an allowlisted ``https://bank.com`` is not permission to
    #: reach ``bank.com:8443``.
    port: int | None
    wildcard: bool = False

    def matches(self, scheme: str, host: str, port: int) -> bool:
        if self.scheme is not None and self.scheme != scheme:
            return False
        want_port = self.port if self.port is not None else (443 if scheme == "https" else 80)
        if want_port != port:
            return False
        if self.wildcard:
            return host == self.host or host.endswith(f".{self.host}")
        return host == self.host


def parse_origin_rules(origins: Iterable[str] | None) -> tuple[_OriginRule, ...]:
    """An allowlist as rules. Unreadable entries are dropped, loudly.

    Accepts ``https://bank.com``, ``bank.com``, ``https://*.bank.com`` and an
    explicit port. A bare host matches either scheme on that scheme's default
    port, which is what the errand tool's own fence (``tools/errand.py``'s
    ``_fenced``) means by a host entry.

    An entry that cannot be read is *dropped*, never widened to "anything":
    a typo in a fence must make the fence narrower, not absent.
    """
    rules: list[_OriginRule] = []
    for raw in origins or ():
        text = str(raw or "").strip().lower().rstrip("/")
        if not text:
            continue
        scheme: str | None = None
        if "://" in text:
            parts = urlsplit(text)
            scheme = (parts.scheme or "").lower()
            if scheme not in ALLOWED_SCHEMES:
                logger.warning("egress allowlist entry has an unusable scheme; dropped")
                continue
            try:
                host, port = parts.hostname or "", parts.port
            except ValueError:
                logger.warning("egress allowlist entry has an unusable port; dropped")
                continue
        else:
            authority = text
            port = None
            if authority.count(":") == 1:
                authority, _, port_text = authority.partition(":")
                try:
                    port = int(port_text)
                except ValueError:
                    logger.warning("egress allowlist entry has an unusable port; dropped")
                    continue
            host = authority
        host = (host or "").strip().rstrip(".")
        wildcard = host.startswith("*.")
        if wildcard:
            host = host[2:]
        if not host:
            logger.warning("egress allowlist entry has no host; dropped")
            continue
        if port is not None and not 0 < port < 65536:
            logger.warning("egress allowlist entry has an out-of-range port; dropped")
            continue
        rules.append(_OriginRule(host=host, scheme=scheme, port=port, wildcard=wildcard))
    return tuple(rules)


async def _default_resolver(host: str, port: int) -> list[str]:
    """Every address *host* resolves to, without blocking the event loop.

    The loop's own ``getaddrinfo`` runs the lookup in a thread, so this is the
    one piece of I/O in the authorisation path and it is still async. It is a
    module-level function and the proxy takes it as a seam, so the suite can
    exercise every rule — including a resolver that *changes its answer* —
    without a network.
    """
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    out: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in out:
            out.append(str(address))
    return out


async def _default_connector(
    *, ip: str, port: int, server_hostname: str, timeout: float
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """A TCP connection **to an address**, never to a name.

    ``host=ip`` is the pin: ``asyncio.open_connection`` will not consult a
    resolver for something that already parses as an address, so there is no
    second lookup for a rebinding answer to win.

    *server_hostname* is accepted and deliberately unused. It is the name this
    connection is for, and it would be the TLS SNI if anything here terminated
    TLS — nothing does, by design (see the module docstring), so the browser's
    own handshake carries its own SNI end to end. The parameter stays in the
    seam's signature so a deployment that *does* want a terminating proxy has
    somewhere to put it, and so what is and is not happening is written down.
    """
    return await asyncio.wait_for(asyncio.open_connection(host=ip, port=port), timeout)


class BrowserEgressProxy:
    """A forward proxy that only lets the sandboxed browser reach vetted places.

    ::

        async with BrowserEgressProxy(allowed_origins=errand.allowed_origins) as proxy:
            ...  # browser context created with proxy={"server": proxy.url}

    Args:
        allowed_origins: The errand's fence. Empty or ``None`` means no origin
            fence — the port, scheme and address rules still apply, and they
            are the ones that stop SSRF. A fence narrows further, to the
            origins the owner approved.
        host: Interface to bind. ``127.0.0.1`` by default, because a proxy on
            ``0.0.0.0`` is an open relay for anything that can reach the host.
        port: ``0`` for an ephemeral port, which is what a per-errand proxy
            wants: nothing else knows the number.
        allowed_ports: Overridable for a deployment whose sites answer
            elsewhere. Narrowing it is safe; widening it is a decision.
        resolver: ``async (host, port) -> [address]``. The seam that makes
            rebinding testable.
        connector: ``async (*, ip, port, server_hostname, timeout) ->
            (reader, writer)``. The seam that lets a test observe **which
            address** was connected to, which is the claim this module makes.
        timeout: Ceiling on reading a request head and on the upstream
            connect. Not a ceiling on an established tunnel — a download is
            allowed to take longer than a handshake.
        idle_timeout: How long an established tunnel may be silent before it
            is closed. ``None`` leaves it to the browser and the engine.
    """

    def __init__(
        self,
        *,
        allowed_origins: Iterable[str] | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
        allowed_ports: Iterable[int] = DEFAULT_ALLOWED_PORTS,
        resolver: Callable[[str, int], Awaitable[list[str]]] | None = None,
        connector: Any | None = None,
        timeout: float = 30.0,
        idle_timeout: float | None = None,
        max_tunnels: int = DEFAULT_MAX_TUNNELS,
        tenant_id: str = "",
        errand_id: str = "",
    ) -> None:
        self._rules = parse_origin_rules(allowed_origins)
        self._bind_host = host
        self._bind_port = port
        self._allowed_ports = frozenset(int(p) for p in allowed_ports)
        self._resolve = resolver or _default_resolver
        self._connect = connector or _default_connector
        self._timeout = float(timeout) if timeout and timeout > 0 else 30.0
        self._idle_timeout = idle_timeout
        self._max_tunnels = max(1, int(max_tunnels))
        self._tenant_id = str(tenant_id or "")
        self._errand_id = str(errand_id or "")
        self._server: asyncio.AbstractServer | None = None
        self._host = ""
        self._port = 0
        #: Live connection handlers, so :meth:`stop` can actually stop them
        #: rather than leaving a tunnel open past the errand that opened it.
        self._tunnels: set[asyncio.Task[None]] = set()
        self._decisions: list[EgressDecision] = []

    # ── what happened ────────────────────────────────────────────────────

    @property
    def decisions(self) -> tuple[EgressDecision, ...]:
        """Every authorisation decision this proxy made, newest last."""
        return tuple(self._decisions)

    @property
    def denials(self) -> tuple[EgressDecision, ...]:
        """Just the refusals — what an alert on denied egress would watch."""
        return tuple(d for d in self._decisions if not d.allowed)

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        """The fence as it was parsed, for the audit record."""
        return tuple(
            f"{r.scheme or '*'}://{'*.' if r.wildcard else ''}{r.host}"
            + (f":{r.port}" if r.port else "")
            for r in self._rules
        )

    def _record(self, decision: EgressDecision) -> EgressDecision:
        self._decisions.append(decision)
        if len(self._decisions) > _MAX_RECORDED:
            del self._decisions[: len(self._decisions) - _MAX_RECORDED]
        return decision

    # ── lifecycle ────────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        """``http://host:port`` — what goes in Playwright's ``proxy.server``.

        Raises:
            RuntimeError: the proxy is not listening, so there is no url. A
                blank string here would be handed to ``new_context`` and
                quietly mean "no proxy", which is the one failure this whole
                module exists to prevent.
        """
        if self._server is None:
            raise RuntimeError("the egress proxy is not running, so it has no url")
        host = f"[{self._host}]" if ":" in self._host else self._host
        return f"http://{host}:{self._port}"

    @property
    def is_running(self) -> bool:
        return self._server is not None

    async def start(self) -> tuple[str, int]:
        """Listen, and return the ``(host, port)`` actually bound."""
        if self._server is not None:
            return (self._host, self._port)
        server = await asyncio.start_server(
            self._handle, host=self._bind_host, port=self._bind_port
        )
        sockets = server.sockets or ()
        if not sockets:  # pragma: no cover - a bound server always has one
            server.close()
            raise RuntimeError("the egress proxy bound no socket")
        bound = sockets[0].getsockname()
        self._server = server
        self._host, self._port = str(bound[0]), int(bound[1])
        logger.info(
            "browser egress proxy listening on %s:%s tenant=%s errand=%s fence=%s",
            self._host,
            self._port,
            self._tenant_id or "-",
            self._errand_id or "-",
            ",".join(self.allowed_origins) or "none",
        )
        return (self._host, self._port)

    async def stop(self) -> None:
        """Stop listening and tear down every tunnel still open.

        Idempotent. A tunnel that outlives the errand that opened it is a hole
        in the containment, so this cancels them rather than waiting.
        """
        server, self._server = self._server, None
        if server is not None:
            # Stop accepting first, so a request that arrives during teardown
            # is not authorised by a proxy that is going away.
            server.close()
        # Then the live tunnels, and *before* ``wait_closed``: since 3.12 that
        # waits for every handler to finish, and a handler relaying an open
        # tunnel does not finish until one side hangs up — which is the client
        # we are trying to disconnect. Cancel, then wait.
        tunnels, self._tunnels = set(self._tunnels), set()
        for task in tunnels:
            task.cancel()
        if tunnels:
            await asyncio.gather(*tunnels, return_exceptions=True)
        if server is not None:
            with contextlib.suppress(Exception):
                await server.wait_closed()
            logger.info(
                "browser egress proxy stopped (%d allowed, %d denied)",
                len(self._decisions) - len(self.denials),
                len(self.denials),
            )

    async def __aenter__(self) -> BrowserEgressProxy:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()

    # ── the decision ─────────────────────────────────────────────────────

    async def authorize(self, scheme: str, authority: str) -> PinnedTarget:
        """*authority* as a :class:`PinnedTarget`, or :class:`EgressDeniedError`.

        The order matters and is cheapest-and-most-decisive first: a
        destination that was never going to be allowed must not cause a DNS
        query, because a query is itself an outbound signal to whoever runs
        that zone.

        1. the authority parses, and names a port on :data:`DEFAULT_ALLOWED_PORTS`;
        2. the destination validator's structural rules — scheme, userinfo,
           control characters, ``localhost``/``*.internal``/metadata names, and
           an address literal in *any* spelling (dotted quad, bare decimal,
           octal, hex, IPv6, IPv4-mapped, NAT64, 6to4) judged as the address it
           encodes;
        3. the origin fence, if there is one;
        4. resolution — once — and then **every** address it returned must be
           permitted. Not the first: a name answering with one public and one
           private address is a rebinding setup, and which one a connection
           would pick is not ours to assume.

        The address that comes back is what the socket must use.
        """
        # A ``CONNECT`` authority must name its port — there is no scheme to
        # take a default from, and inventing one would mean choosing a port the
        # client never asked for. An absolute-form request *does* have a
        # scheme, so ``http://site.test/`` means 80 the way it does everywhere.
        default_port = None
        if scheme:
            default_port = 443 if scheme.lower() == "https" else 80
        host, port = _split_authority(authority, default_port=default_port)
        if port not in self._allowed_ports:
            raise EgressDeniedError(f"port {port} is not a permitted web port")
        scheme = (scheme or _PORT_SCHEME.get(port) or "https").lower()
        if scheme not in ALLOWED_SCHEMES:
            raise EgressDeniedError(f"scheme {scheme[:12]!r} is not http or https")

        shown = f"[{host}]" if ":" in host and not host.startswith("[") else host
        try:
            destination = split_destination(
                f"{scheme}://{shown}:{port}/", allowed_schemes=ALLOWED_SCHEMES
            )
        except DestinationRefusedError as exc:
            raise EgressDeniedError(str(exc)) from None

        host = destination.hostname
        if self._rules and not any(r.matches(scheme, host, port) for r in self._rules):
            raise EgressDeniedError(f"{host[:60]} is not inside the approved origins")

        if destination.address is not None:
            # An address literal: already judged above by the validator, and
            # there is nothing to resolve. It *is* the pin.
            return PinnedTarget(
                scheme=scheme,
                host=host,
                port=port,
                ip=destination.address.compressed,
                resolved=(destination.address.compressed,),
            )

        try:
            addresses = await asyncio.wait_for(self._resolve(host, port), self._timeout)
        except TimeoutError:
            raise EgressDeniedError(
                f"{host[:60]} did not resolve within {self._timeout:g}s"
            ) from None
        except OSError:
            raise EgressDeniedError(f"{host[:60]} does not resolve") from None
        if not addresses:
            raise EgressDeniedError(f"{host[:60]} does not resolve")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(str(address).split("%", 1)[0])
            except ValueError:
                raise EgressDeniedError(
                    f"{host[:60]} resolves to something that is not an address"
                ) from None
            refusal = address_refusal(ip)
            if refusal:
                raise EgressDeniedError(f"{host[:60]} resolves to {refusal}")
        return PinnedTarget(
            scheme=scheme,
            host=host,
            port=port,
            ip=str(addresses[0]).split("%", 1)[0],
            resolved=tuple(str(a) for a in addresses),
        )

    # ── serving ──────────────────────────────────────────────────────────

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """One client connection: authorise it, or refuse it and hang up."""
        task = asyncio.current_task()
        if task is not None:
            if len(self._tunnels) >= self._max_tunnels:
                await _respond(writer, BUSY_RESPONSE)
                return
            self._tunnels.add(task)
        try:
            await self._serve(reader, writer)
        except (ConnectionError, OSError):
            # The client or the destination went away mid-relay. Nothing to
            # say to a socket that is already gone.
            pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("egress proxy connection failed: %s: %s", type(exc).__name__, exc)
        finally:
            if task is not None:
                self._tunnels.discard(task)
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head, leftover = await asyncio.wait_for(_read_head(reader), self._timeout)
        except (TimeoutError, ValueError):
            await _respond(writer, BAD_REQUEST_RESPONSE)
            return
        if not head:
            return  # a connection that said nothing; nothing to refuse

        try:
            method, target, version, headers = _parse_head(head)
        except ValueError:
            await _respond(writer, BAD_REQUEST_RESPONSE)
            return

        if method == "CONNECT":
            scheme, authority, path = "", target, ""
        else:
            parts = urlsplit(target)
            scheme = (parts.scheme or "").lower()
            if scheme and scheme not in ALLOWED_SCHEMES:
                # ``file:``, ``gopher:``, ``ftp:``… A policy refusal rather
                # than a parse failure, and checked before the authority is
                # looked at: ``file:///etc/passwd`` has no authority at all,
                # and answering it with "malformed" would leave the one thing
                # worth recording — that something asked for a local file —
                # out of the audit trail.
                self._record(
                    EgressDecision(
                        allowed=False,
                        method=method,
                        requested=target[:120],
                        reason=f"scheme {scheme[:12]!r} is not http or https",
                    )
                )
                await _respond(writer, FORBIDDEN_RESPONSE)
                return
            if not scheme or not parts.netloc:
                # Origin-form: the client is talking to this proxy as if it
                # were the origin server. It is not one, and guessing the
                # destination from a Host header a page controls is not a
                # decision this module will make.
                await _respond(writer, BAD_REQUEST_RESPONSE)
                return
            authority = parts.netloc
            path = parts.path or "/"
            if parts.query:
                path = f"{path}?{parts.query}"

        try:
            pinned = await self.authorize(scheme, authority)
        except EgressDeniedError as denied:
            self._record(
                EgressDecision(
                    allowed=False,
                    method=method,
                    requested=str(authority)[:120],
                    reason=denied.reason,
                )
            )
            logger.warning(
                "egress denied tenant=%s errand=%s %s %s: %s",
                self._tenant_id or "-",
                self._errand_id or "-",
                method,
                str(authority)[:120],
                denied.reason,
            )
            # Nothing upstream has been opened at this point, and nothing will
            # be: the refusal is the end of this connection.
            await _respond(writer, FORBIDDEN_RESPONSE)
            return

        self._record(
            EgressDecision(
                allowed=True, method=method, requested=str(authority)[:120], target=pinned
            )
        )
        try:
            up_reader, up_writer = await self._connect(
                ip=pinned.ip,
                port=pinned.port,
                server_hostname=pinned.host,
                timeout=self._timeout,
            )
        except (TimeoutError, OSError) as exc:
            logger.info(
                "egress upstream %s (pinned %s) unreachable: %s",
                pinned.origin,
                pinned.ip,
                type(exc).__name__,
            )
            await _respond(writer, GATEWAY_RESPONSE)
            return

        try:
            if method == "CONNECT":
                await _respond(writer, TUNNEL_ESTABLISHED, close=False)
                if leftover:
                    up_writer.write(leftover)
                    await up_writer.drain()
            else:
                up_writer.write(_forward_head(method, path, version, headers, pinned))
                if leftover:
                    up_writer.write(leftover)
                await up_writer.drain()
            await self._relay(reader, writer, up_reader, up_writer)
        finally:
            with contextlib.suppress(Exception):
                up_writer.close()
                await up_writer.wait_closed()

    async def _relay(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        up_reader: asyncio.StreamReader,
        up_writer: asyncio.StreamWriter,
    ) -> None:
        """Copy bytes both ways until either side is done.

        What travels through an established tunnel is not inspected — it is
        the browser's TLS session (see the module docstring). The decision was
        made before this function was reached, and nothing here can widen it.
        """
        pumps = [
            asyncio.create_task(_pump(client_reader, up_writer)),
            asyncio.create_task(_pump(up_reader, client_writer)),
        ]
        try:
            if self._idle_timeout:
                await asyncio.wait_for(
                    asyncio.gather(*pumps, return_exceptions=True), self._idle_timeout
                )
            else:
                await asyncio.gather(*pumps, return_exceptions=True)
        except TimeoutError:
            pass
        finally:
            for pump in pumps:
                pump.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)


# ── small pieces, module level so a test can use them directly ──────────


def _split_authority(authority: str, *, default_port: int | None = None) -> tuple[str, int]:
    """``host:port`` (or ``[v6]:port``) as its parts.

    *default_port* is the scheme's port, for a request that had a scheme. With
    ``None`` — which is every ``CONNECT``, since an authority-form target
    carries no scheme — a missing port is a refusal rather than a guess: there
    is nothing to take a default from, and choosing one would mean sending the
    client somewhere it never asked to go.
    """
    text = str(authority or "").strip()
    if not text:
        raise EgressDeniedError("the request named no destination")
    if text.startswith("["):
        close = text.find("]")
        if close < 1:
            raise EgressDeniedError("the destination authority is malformed")
        host, rest = text[1:close], text[close + 1 :]
        if rest and not rest.startswith(":"):
            raise EgressDeniedError("the destination authority is malformed")
        port_text = rest[1:] if rest else ""
    elif text.count(":") > 1:
        # An unbracketed IPv6 literal. Ambiguous with host:port, so refused
        # rather than guessed at.
        raise EgressDeniedError("the destination authority is malformed")
    else:
        host, _, port_text = text.partition(":")
    host = host.strip()
    if not host:
        raise EgressDeniedError("the request named no host")
    if not port_text:
        if default_port is None:
            raise EgressDeniedError("the request named no port")
        return host, default_port
    try:
        port = int(port_text)
    except ValueError:
        raise EgressDeniedError("the destination port is not a number") from None
    if not 0 < port < 65536:
        raise EgressDeniedError("the destination port is out of range")
    return host, port


async def _read_head(reader: asyncio.StreamReader) -> tuple[bytes, bytes]:
    """``(head, bytes that came after it)``, read up to :data:`MAX_HEAD_BYTES`.

    Returning the leftover matters: a client may pipeline the start of its
    payload behind the head, and dropping those bytes would corrupt the very
    first request of every tunnel.
    """
    buffer = bytearray()
    while True:
        chunk = await reader.read(_RELAY_CHUNK)
        if not chunk:
            if not buffer:
                return (b"", b"")
            raise ValueError("the request head never ended")
        buffer += chunk
        end = buffer.find(b"\r\n\r\n")
        if end >= 0:
            return (bytes(buffer[:end]), bytes(buffer[end + 4 :]))
        if len(buffer) > MAX_HEAD_BYTES:
            raise ValueError("the request head is too long")


def _parse_head(head: bytes) -> tuple[str, str, str, list[tuple[str, str]]]:
    """``(method, target, version, headers)`` from a request head."""
    try:
        text = head.decode("latin-1")
    except UnicodeDecodeError:  # pragma: no cover - latin-1 decodes anything
        raise ValueError("the request head is not text") from None
    lines = text.split("\r\n")
    bits = lines[0].split()
    if len(bits) != 3:
        raise ValueError("the request line is malformed")
    method, target, version = bits[0].upper(), bits[1], bits[2]
    if not version.upper().startswith("HTTP/"):
        raise ValueError("the request line names no HTTP version")
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep:
            raise ValueError("a header line is malformed")
        headers.append((name.strip(), value.strip()))
    return method, target, version, headers


def _forward_head(
    method: str,
    path: str,
    version: str,
    headers: list[tuple[str, str]],
    pinned: PinnedTarget,
) -> bytes:
    """The request to send upstream: origin-form, and one request only.

    Two deliberate rewrites:

    * ``Host`` is replaced with the authority that was *authorised*, so the
      destination cannot be told it is someone else;
    * ``Connection: close`` is forced. That is not politeness — without it the
      client could send a *second* request on the same connection, to a
      different host, and this proxy has already stopped parsing. One
      authorisation, one request.
    """
    host = f"[{pinned.host}]" if ":" in pinned.host else pinned.host
    default = 443 if pinned.scheme == "https" else 80
    authority = host if pinned.port == default else f"{host}:{pinned.port}"
    out = [f"{method} {path} {version}", f"Host: {authority}"]
    for name, value in headers:
        lowered = name.lower()
        if lowered in _HOP_BY_HOP or lowered in ("host", "connection"):
            continue
        out.append(f"{name}: {value}")
    out.append("Connection: close")
    return ("\r\n".join(out) + "\r\n\r\n").encode("latin-1")


async def _respond(writer: asyncio.StreamWriter, body: bytes, *, close: bool = True) -> None:
    """Write a bare status line and (usually) hang up."""
    with contextlib.suppress(Exception):
        writer.write(body)
        await writer.drain()
    if close:
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()


async def _pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Copy one direction until EOF, then half-close so the peer sees it."""
    try:
        while True:
            chunk = await reader.read(_RELAY_CHUNK)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        with contextlib.suppress(Exception):
            if writer.can_write_eof():
                writer.write_eof()


# ── running it as a service ─────────────────────────────────────
# ``python -m life_graph.services.browser_egress_proxy --host 0.0.0.0 --port 8080``
#
# The in-process proxy :class:`IsolatedBrowserDriver` mints is reachable from
# the application and from the test suite, and *not* from a container on an
# ``internal: true`` bridge — a loopback listener is not on that bridge. The
# browser container therefore needs the proxy as a peer, which is what this
# entrypoint is for: it is the command the ``egress`` service in
# ``compose.sandbox.yaml`` runs, on the bridge the browser can reach and on
# the one network in that stack with a route out.
#
# Two differences from the ephemeral proxy, both deliberate and both worth
# knowing:
#
# * it binds a real interface, so it is only safe where nothing else can reach
#   it. The default is still the loopback and ``--host`` is what widens it;
# * it is long-lived and shared, so it carries **no per-errand origin fence**
#   unless ``--allowed-origin`` gives it a static one. The address, port and
#   scheme rules — the ones that stop SSRF, rebinding and metadata access —
#   apply to every request either way. The errand's own fence stays with the
#   application-level check in ``tools/errand.py``, which sees navigations but
#   not sub-resources; a fence that follows the errand through a shared proxy
#   needs the proxy to know which errand a connection belongs to, and nothing
#   here claims to do that yet.

#: Environment variables the entrypoint reads, so the compose service can be
#: configured without rewriting its command. Deliberately unprefixed: a
#: ``LIFE_GRAPH_*`` variable is application configuration and
#: ``services/dev/sandbox.py`` refuses to pass any of it into a sandbox container.
ENV_HOST = "SANDBOX_EGRESS_HOST"
ENV_PORT = "SANDBOX_EGRESS_PORT"
ENV_ORIGINS = "SANDBOX_EGRESS_ALLOWED_ORIGINS"
ENV_PORTS = "SANDBOX_EGRESS_ALLOWED_PORTS"

#: The port the compose service listens on. Not 3128 or 8888: nothing should
#: recognise this as a proxy by its port number, and 9222 is taken by the
#: browser's own control channel.
DEFAULT_LISTEN_PORT = 8080


def _csv(raw: str | None) -> list[str]:
    """``"a, b ,,c"`` -> ``["a", "b", "c"]``."""
    return [part.strip() for part in str(raw or "").replace(";", ",").split(",") if part.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m life_graph.services.browser_egress_proxy",
        description=(
            "The sandboxed browser's only way out: a forward proxy that judges every"
            " destination and connects to the address it resolved, not to the name."
        ),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get(ENV_HOST, "127.0.0.1"),
        help=(
            "interface to bind (default 127.0.0.1). 0.0.0.0 is what a container on an"
            " internal-only bridge needs, and is an open relay to anything that can reach"
            " it — safe only because that bridge has no gateway."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get(ENV_PORT) or DEFAULT_LISTEN_PORT),
        help=f"port to listen on (default {DEFAULT_LISTEN_PORT}); 0 picks an ephemeral one",
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=None,
        metavar="ORIGIN",
        help=(
            "a static origin fence, repeatable ('https://site.test', '*.site.test')."
            " Omitted means no origin fence: the address, port and scheme rules still"
            " apply and are the ones that stop SSRF."
        ),
    )
    parser.add_argument(
        "--allowed-port",
        action="append",
        type=int,
        default=None,
        metavar="PORT",
        help=(
            "override the permitted destination ports (default"
            f" {', '.join(str(p) for p in DEFAULT_ALLOWED_PORTS)}). Narrowing is safe;"
            " widening is a decision."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="ceiling on reading a request head and on the upstream connect (seconds)",
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help="close an established tunnel after this long with no traffic (seconds)",
    )
    parser.add_argument(
        "--max-tunnels",
        type=int,
        default=DEFAULT_MAX_TUNNELS,
        help=f"how many connections may be open at once (default {DEFAULT_MAX_TUNNELS})",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("SANDBOX_EGRESS_LOG_LEVEL", "INFO"),
        help="python logging level (default INFO). Denials are logged at WARNING.",
    )
    return parser


def proxy_from_args(args: argparse.Namespace) -> BrowserEgressProxy:
    """The proxy *args* asks for. Separate from :func:`main` so a test can
    inspect the configuration without binding a socket or running a loop."""
    origins = (
        args.allowed_origin
        if args.allowed_origin is not None
        else _csv(os.environ.get(ENV_ORIGINS))
    )
    ports: Iterable[int]
    if args.allowed_port:
        ports = tuple(args.allowed_port)
    else:
        from_env = [int(p) for p in _csv(os.environ.get(ENV_PORTS)) if p.isdigit()]
        ports = tuple(from_env) or DEFAULT_ALLOWED_PORTS
    return BrowserEgressProxy(
        allowed_origins=origins,
        host=str(args.host),
        port=int(args.port),
        allowed_ports=ports,
        timeout=float(args.timeout),
        idle_timeout=args.idle_timeout,
        max_tunnels=int(args.max_tunnels),
    )


async def serve_forever(proxy: BrowserEgressProxy) -> int:
    """Run *proxy* until the process is asked to stop, then stop it cleanly.

    SIGTERM is how a container runtime asks (``docker compose down``,
    ``docker stop``), and SIGINT is how a terminal does. Both land on the same
    path: stop accepting, cancel the live tunnels, log what was denied. A
    tunnel that outlived the proxy would be a way out that outlived it.
    """
    loop = asyncio.get_running_loop()
    stopping: asyncio.Future[str] = loop.create_future()

    def _ask_to_stop(name: str) -> None:
        if not stopping.done():
            stopping.set_result(name)

    for signame in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, signame, None)
        if sig is None:  # pragma: no cover - every platform we run on has both
            continue
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, _ask_to_stop, signame)

    host, port = await proxy.start()
    if not ipaddress.ip_address(host).is_loopback:
        logger.warning(
            "browser egress proxy is bound to %s:%s, which anything that can reach this"
            " interface may use as a relay. That is only contained because the bridge it"
            " is on has no other members and no gateway.",
            host,
            port,
        )
    logger.info(
        "browser egress proxy serving on %s:%s (fence: %s, ports: %s)",
        host,
        port,
        ", ".join(proxy.allowed_origins) or "none — address and port rules only",
        ", ".join(str(p) for p in sorted(proxy._allowed_ports)),  # noqa: SLF001
    )
    try:
        reason = await stopping
        logger.info("browser egress proxy stopping on %s", reason)
    except asyncio.CancelledError:
        logger.info("browser egress proxy stopping on cancellation")
        raise
    finally:
        await proxy.stop()
        for decision in proxy.denials[-20:]:
            logger.info(
                "denied egress: %s %s: %s", decision.method, decision.requested, decision.reason
            )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m life_graph.services.browser_egress_proxy``."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=str(args.log_level).upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    proxy = proxy_from_args(args)
    try:
        return asyncio.run(serve_forever(proxy))
    except KeyboardInterrupt:  # pragma: no cover - a terminal, not a test
        return 0
    except OSError as exc:
        # Almost always "address already in use" or a bind to an interface the
        # container does not have. A proxy that did not bind is a browser with
        # no way out, which is a failure worth a non-zero exit so the
        # container runtime reports it rather than restarting into silence.
        logger.error("browser egress proxy could not listen: %s: %s", type(exc).__name__, exc)
        return 1


__all__ = [
    "ALLOWED_SCHEMES",
    "DEFAULT_LISTEN_PORT",
    "ENV_HOST",
    "ENV_ORIGINS",
    "ENV_PORT",
    "ENV_PORTS",
    "BAD_REQUEST_RESPONSE",
    "DEFAULT_ALLOWED_PORTS",
    "DEFAULT_MAX_TUNNELS",
    "FORBIDDEN_RESPONSE",
    "MAX_HEAD_BYTES",
    "TUNNEL_ESTABLISHED",
    "BrowserEgressProxy",
    "EgressDecision",
    "EgressDeniedError",
    "PinnedTarget",
    "main",
    "parse_origin_rules",
    "proxy_from_args",
    "serve_forever",
]


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
