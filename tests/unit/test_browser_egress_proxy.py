"""The sandboxed browser's way out is pinned, or there is no way out.

``services/destination_validator.py`` decides whether a URL names somewhere a
browser errand may be sent, and its own docstring says what it cannot close:
it resolves the name, the browser resolves the name again, and a zone that
answers differently the second time has not been stopped by anything. These
tests are about ``services/browser_egress_proxy.py``, which closes that window
by making the decision where the connection is made and then connecting to the
**address** rather than the name.

The adversarial claims under test, each in the negative, because a proxy is
only worth having for what it refuses:

* loopback, RFC1918, link-local, carrier-NAT, reserved, documentation,
  benchmarking, multicast, broadcast and the unspecified address are refused —
  in every spelling a resolver would accept, including the IPv6 forms that
  carry an IPv4 address inside them;
* the cloud metadata endpoints are refused, which is the single most valuable
  thing an SSRF reaches;
* ``CONNECT`` is not a general-purpose TCP relay: 22, 25, 3306, 5432, 6379 and
  the sandbox browser's own 9222 are not web ports;
* an errand's origin fence applies to every request the *browser* makes, not
  only to the destinations the plan named;
* a refusal connects to nothing. Every denial test asserts the connector was
  never called, which is a stronger claim than "the client got a 403" — a
  proxy that opened the socket and then refused would have already made the
  request;
* the address is resolved **once** and the socket goes to that address, so a
  resolver that changes its answer cannot move an established connection;
* a resolver answering with one public and one private address is a rebinding
  setup and the whole answer is refused, not filtered down to the public one;
* and the shipped compose stack does not hand the workspace container the
  browser's unauthenticated control endpoint.

No network: the resolver is a dict, the upstream is an in-process server on the
loopback, and the connector is a seam that records which address it was asked
for. Nothing here resolves a real name or opens a real egress connection.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from life_graph.services import browser_egress_proxy as ep
from life_graph.services import browser_sandbox_driver as bsd
from life_graph.services.browser_egress_proxy import BrowserEgressProxy, EgressDeniedError
from life_graph.services.dev.sandbox import SandboxUnavailableError

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A public address, used as "the answer a resolver gives for a real site".
#: Nothing ever connects to it: the connector seam is what opens sockets, and
#: in these tests it opens them to an in-process server on the loopback.
PUBLIC_IP = "93.184.216.34"
SECOND_PUBLIC_IP = "93.184.216.35"


# ── seams ────────────────────────────────────────────────────────────────


class Resolver:
    """Name resolution as a dict, with an optional change of mind.

    *answers* maps a host to a list of answers: the first call gets the first
    answer, the second the second, and so on, with the last repeating. That is
    how a rebinding resolver behaves, and it is the only way to test that this
    proxy asks once.
    """

    def __init__(self, answers: dict[str, list[list[str]]] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, host: str, port: int) -> list[str]:
        self.calls.append((host, port))
        try:
            sequence = self.answers[host]
        except KeyError:
            raise socket.gaierror(socket.EAI_NONAME, f"no address for {host}") from None
        index = min(sum(1 for c in self.calls if c[0] == host) - 1, len(sequence) - 1)
        return list(sequence[index])


class NeverResolver:
    """A resolver that fails the test if it is asked anything.

    Used where the refusal must happen *before* a lookup: a DNS query is an
    outbound signal to whoever runs that zone, and a destination that was never
    going to be allowed should not tell them it was considered.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, host: str, port: int) -> list[str]:
        self.calls.append((host, port))
        raise AssertionError(f"the proxy resolved {host} for a destination it had to refuse")


class Connector:
    """Records the address it was asked to connect to, and connects locally.

    *upstream_port* is an in-process server on the loopback. The proxy asks for
    a public address (which is what the resolver answered); this connector
    notes that and then wires the tunnel to the local server, so the test can
    assert the pin *and* exchange real bytes. ``None`` means "no upstream
    exists", which is what every denial test wants: if the proxy ever called
    it, ``calls`` is not empty and the test says so.
    """

    def __init__(self, upstream_port: int | None = None, fail: BaseException | None = None) -> None:
        self.upstream_port = upstream_port
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    @property
    def ips(self) -> list[str]:
        return [c["ip"] for c in self.calls]

    async def __call__(
        self, *, ip: str, port: int, server_hostname: str, timeout: float
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        self.calls.append(
            {"ip": ip, "port": port, "server_hostname": server_hostname, "timeout": timeout}
        )
        if self.fail is not None:
            raise self.fail
        if self.upstream_port is None:
            raise OSError("no upstream in this test")
        return await asyncio.open_connection("127.0.0.1", self.upstream_port)


async def echo_server() -> tuple[asyncio.AbstractServer, int]:
    """A loopback server that answers ``echo:<what it was sent>``."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(b"echo:" + data)
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, int(server.sockets[0].getsockname()[1])


async def ask(
    proxy: BrowserEgressProxy, request: bytes, *, read: int = 0
) -> tuple[bytes, asyncio.StreamReader, asyncio.StreamWriter]:
    """Send *request* to the running proxy and read back its status line."""
    host, port = proxy._host, proxy._port  # noqa: SLF001 - the bound address
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(request)
    await writer.drain()
    status = await asyncio.wait_for(reader.readline(), timeout=5)
    body = b""
    if read:
        body = await asyncio.wait_for(reader.read(read), timeout=5)
    return status + body, reader, writer


async def connect_through(proxy: BrowserEgressProxy, authority: str) -> bytes:
    """``CONNECT <authority>`` and the status line that came back."""
    request = f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n".encode("latin-1")
    status, _, writer = await ask(proxy, request)
    with contextlib.suppress(Exception):
        writer.close()
        await writer.wait_closed()
    return status


def running(**kwargs: Any) -> BrowserEgressProxy:
    """A proxy with test seams and a short timeout."""
    kwargs.setdefault("resolver", NeverResolver())
    kwargs.setdefault("connector", Connector())
    kwargs.setdefault("timeout", 2.0)
    return BrowserEgressProxy(**kwargs)


def assert_forbidden(status: bytes) -> None:
    assert status.startswith(b"HTTP/1.1 403 Forbidden"), status[:80]


# ── loopback and the names that mean it ──────────────────────────────────


async def test_proxy_blocks_loopback_connect():
    """``127.0.0.1`` and ``localhost`` are the browser reaching back inside.

    Both are refused, and — the part that matters — neither produced a
    connection attempt or a DNS query. ``localhost`` is refused by name
    (RFC 6761 reserves it for the loopback), so a resolver that answered it
    with a public address would never be asked.
    """
    connector = Connector()
    resolver = NeverResolver()
    async with running(connector=connector, resolver=resolver) as proxy:
        assert_forbidden(await connect_through(proxy, "127.0.0.1:80"))
        assert_forbidden(await connect_through(proxy, "localhost:8080"))
    assert connector.calls == [], "the proxy opened a socket for a refused destination"
    assert resolver.calls == [], "the proxy resolved a name it had already refused"
    assert [d.reason for d in proxy.denials] == [
        "the destination is a loopback address (127.0.0.1)",
        "localhost is a local or metadata name",
    ]


async def test_proxy_blocks_loopback_in_every_spelling():
    """Dotted quad, bare decimal, octal, hex, IPv6 and 6to4 all mean 127.0.0.1.

    A connection goes to the address a spelling encodes, not to the spelling,
    so each of these is parsed as the address it is. This is the classic
    SSRF-filter bypass list; the proxy inherits the handling from
    ``destination_validator.parse_host_address`` rather than keeping a second
    copy of it.
    """
    connector = Connector()
    async with running(connector=connector) as proxy:
        for authority in (
            "127.0.0.1:443",
            "127.1:443",
            "2130706433:443",  # bare decimal
            "0x7f.1:443",  # hex
            "0177.0.0.1:443",  # octal
            "[::1]:443",
            "[2002:7f00:1::]:443",  # 6to4 wrapping the loopback
            "[64:ff9b::7f00:1]:443",  # NAT64 wrapping the loopback
            "0.0.0.0:443",  # the unspecified address
            "[::]:443",
        ):
            assert_forbidden(await connect_through(proxy, authority))
    assert connector.calls == []


async def test_proxy_blocks_cloud_metadata():
    """The metadata endpoint, by address and by name.

    ``169.254.169.254`` is link-local *and* named outright, so the audit line
    says "a cloud metadata address" rather than an incidental "link-local".
    ``metadata.google.internal`` is refused by name — and by the
    ``.internal`` suffix even if it were renamed.
    """
    connector = Connector()
    resolver = NeverResolver()
    async with running(connector=connector, resolver=resolver) as proxy:
        assert_forbidden(await connect_through(proxy, "169.254.169.254:80"))
        assert_forbidden(await connect_through(proxy, "metadata.google.internal:80"))
        assert_forbidden(await connect_through(proxy, "169.254.170.2:80"))  # ECS task metadata
        assert_forbidden(await connect_through(proxy, "100.100.100.200:80"))  # Alibaba
        assert_forbidden(await connect_through(proxy, "192.0.0.192:80"))  # Oracle
        assert_forbidden(await connect_through(proxy, "[fd00:ec2::254]:80"))  # IMDS over IPv6
    assert connector.calls == []
    assert resolver.calls == []
    assert "metadata" in proxy.denials[0].reason


async def test_proxy_blocks_private_networks():
    """RFC1918, and every other range a browser errand has no business in."""
    connector = Connector()
    async with running(connector=connector) as proxy:
        for authority in (
            "10.0.0.1:443",
            "192.168.1.1:443",
            "172.16.0.1:443",
            "169.254.1.1:443",  # link-local
            "[fe80::1]:443",  # IPv6 link-local
            "[fc00::1]:443",  # IPv6 unique-local
            "100.64.0.1:443",  # carrier-grade NAT, where a tailnet lives
            "224.0.0.1:443",  # multicast
            "[ff02::1]:443",  # IPv6 multicast
            "255.255.255.255:443",  # broadcast
            "192.0.2.1:443",  # documentation
            "198.51.100.1:443",
            "203.0.113.1:443",
            "198.18.0.1:443",  # benchmarking
            "240.0.0.1:443",  # reserved
        ):
            assert_forbidden(await connect_through(proxy, authority))
    assert connector.calls == []
    assert len(proxy.denials) == 15


async def test_proxy_blocks_ipv4_mapped_ipv6():
    """``::ffff:127.0.0.1`` is the loopback wearing an IPv6 hat.

    A packet to the wrapper arrives at the wrapped address, so the wrapper is
    judged as what it wraps. Tested for the loopback and for RFC1918, because
    the mapping trick works for every blocked range.
    """
    connector = Connector()
    async with running(connector=connector) as proxy:
        assert_forbidden(await connect_through(proxy, "[::ffff:127.0.0.1]:80"))
        assert_forbidden(await connect_through(proxy, "[::ffff:7f00:1]:80"))
        assert_forbidden(await connect_through(proxy, "[::ffff:10.0.0.1]:443"))
        assert_forbidden(await connect_through(proxy, "[::ffff:169.254.169.254]:80"))
    assert connector.calls == []
    assert all(
        "loopback" in d.reason or "private" in d.reason or "metadata" in d.reason
        for d in proxy.denials
    ), [d.reason for d in proxy.denials]


# ── CONNECT is not a TCP relay ───────────────────────────────────────────


async def test_proxy_blocks_dangerous_ports():
    """A ``CONNECT`` to 22 is not a web request, whoever the host is.

    The port is checked first, before the host is even parsed and certainly
    before it is resolved — so an attacker cannot use the proxy as a port
    scanner, and cannot use a refused request to make this host look up a
    name of their choosing. 9222 is on the list because that is the sandbox
    browser's own control port.
    """
    connector = Connector()
    resolver = NeverResolver()
    async with running(connector=connector, resolver=resolver) as proxy:
        for authority in (
            "example.com:22",
            "example.com:25",
            "example.com:5432",
            "example.com:3306",
            "example.com:6379",
            "example.com:9222",
            "example.com:11211",
            "example.com:1",
            "example.com:65535",
        ):
            assert_forbidden(await connect_through(proxy, authority))
    assert connector.calls == []
    assert resolver.calls == [], "a refused port still caused a DNS query"
    assert proxy.denials[0].reason == "port 22 is not a permitted web port"


async def test_proxy_permits_only_the_web_ports():
    """The allowed set is exactly the four, and it is a list not a blocklist."""
    assert ep.DEFAULT_ALLOWED_PORTS == (80, 443, 8080, 8443)
    assert 9222 not in ep.DEFAULT_ALLOWED_PORTS


async def test_proxy_refuses_a_connect_with_no_port():
    """``CONNECT example.com`` names no port, and one is not invented.

    There is no scheme in an authority-form request to take a default from, so
    guessing would mean choosing a port the client never asked for.
    """
    async with running() as proxy:
        assert_forbidden(await connect_through(proxy, "example.com"))
        assert_forbidden(await connect_through(proxy, "example.com:"))
        assert_forbidden(await connect_through(proxy, "example.com:https"))
        assert_forbidden(await connect_through(proxy, "::1:443"))  # unbracketed IPv6
    assert len(proxy.denials) == 4


async def test_proxy_refuses_schemes_that_are_not_http():
    """``file:``, ``gopher:`` and friends, on the absolute-form path."""
    connector = Connector()
    async with running(connector=connector) as proxy:
        for target in ("file:///etc/passwd", "gopher://example.com:80/x", "ftp://example.com:80/"):
            request = f"GET {target} HTTP/1.1\r\nHost: example.com\r\n\r\n".encode("latin-1")
            status, _, writer = await ask(proxy, request)
            assert_forbidden(status)
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
    assert connector.calls == []


async def test_proxy_refuses_an_origin_form_request():
    """``GET /path`` treats the proxy as the origin server. It is not one.

    The destination would have to come from a ``Host`` header, and on this
    path that header is written by a page the owner did not write. A 400, and
    no guess.
    """
    async with running() as proxy:
        request = b"GET /secret HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n\r\n"
        status, _, writer = await ask(proxy, request)
        assert status.startswith(b"HTTP/1.1 400"), status[:80]
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()


async def test_proxy_refuses_a_malformed_or_oversized_head():
    async with running() as proxy:
        for request in (b"not a request at all\r\n\r\n", b"CONNECT\r\n\r\n", b"GET\r\n\r\n"):
            status, _, writer = await ask(proxy, request)
            assert status.startswith(b"HTTP/1.1 400"), status[:80]
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
        # A head that never ends: the cap is what stops the proxy holding it.
        reader, writer = await asyncio.open_connection(proxy._host, proxy._port)  # noqa: SLF001
        writer.write(b"CONNECT example.com:443 HTTP/1.1\r\nX: " + b"a" * (ep.MAX_HEAD_BYTES + 10))
        with contextlib.suppress(Exception):
            await writer.drain()
        status = await asyncio.wait_for(reader.readline(), timeout=5)
        assert status.startswith(b"HTTP/1.1 400"), status[:80]
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()


# ── the errand's fence ───────────────────────────────────────────────────


async def test_proxy_enforces_allowed_origins():
    """The errand's fence applies at the socket, not just to the plan.

    An errand approved for ``https://bank.com`` is approved for that, so a
    page that redirects it to ``evil.com`` is stopped here — the proxy sees
    the redirect hop as its own request, which is precisely what the
    application-level check never gets to see.
    """
    resolver = Resolver({"bank.com": [[PUBLIC_IP]], "evil.com": [[PUBLIC_IP]]})
    connector = Connector()
    async with running(
        allowed_origins=["https://bank.com"], resolver=resolver, connector=connector
    ) as proxy:
        assert_forbidden(await connect_through(proxy, "evil.com:443"))
        assert resolver.calls == [], "a fenced-out host was still resolved"
        assert connector.calls == []

        # And the approved one is permitted: it resolved, it was pinned, and
        # the connection was attempted against the pinned address.
        status = await connect_through(proxy, "bank.com:443")
        assert not status.startswith(b"HTTP/1.1 403"), status[:80]
        assert resolver.calls == [("bank.com", 443)]
        assert connector.ips == [PUBLIC_IP]
    assert [d.requested for d in proxy.denials] == ["evil.com:443"]
    assert proxy.decisions[-1].allowed is True
    assert proxy.decisions[-1].target is not None
    assert proxy.decisions[-1].target.origin == "https://bank.com"


async def test_the_fence_does_not_widen_by_accident():
    """A fence is a narrowing, and every way of getting it wrong narrows more.

    ``https://bank.com`` is not permission to reach ``bank.com`` on 8443, nor
    ``notbank.com``, nor ``bank.com.evil.io``, nor ``bank.com`` over plain
    http. A sub-domain needs an explicit ``*.``.
    """
    hosts = {
        "bank.com": [[PUBLIC_IP]],
        "notbank.com": [[PUBLIC_IP]],
        "bank.com.evil.io": [[PUBLIC_IP]],
        "www.bank.com": [[PUBLIC_IP]],
    }
    connector = Connector()
    async with running(
        allowed_origins=["https://bank.com"], resolver=Resolver(hosts), connector=connector
    ) as proxy:
        for authority in (
            "bank.com:8443",
            "bank.com:80",
            "notbank.com:443",
            "bank.com.evil.io:443",
            "www.bank.com:443",
        ):
            assert_forbidden(await connect_through(proxy, authority))
    assert connector.calls == []


async def test_a_wildcard_fence_covers_sub_domains_and_nothing_else():
    connector = Connector()
    async with running(
        allowed_origins=["https://*.bank.com"],
        resolver=Resolver({"www.bank.com": [[PUBLIC_IP]], "bank.com.evil.io": [[PUBLIC_IP]]}),
        connector=connector,
    ) as proxy:
        assert not (await connect_through(proxy, "www.bank.com:443")).startswith(b"HTTP/1.1 403")
        assert_forbidden(await connect_through(proxy, "bank.com.evil.io:443"))
    assert connector.ips == [PUBLIC_IP]


async def test_an_unreadable_fence_entry_is_dropped_not_widened():
    """A typo in a fence makes the fence narrower, never absent.

    The alternative — an unparseable entry read as "anything" — would turn a
    mistake in the owner's approval into unrestricted egress.
    """
    rules = ep.parse_origin_rules(["https://bank.com", "", "   ", "javascript:alert(1)", "://x"])
    assert len(rules) == 1
    assert rules[0].host == "bank.com"
    # And an entry nobody can read does not make an empty (unfenced) proxy:
    proxy = running(allowed_origins=["javascript:alert(1)"])
    assert proxy.allowed_origins == ()


async def test_no_fence_still_refuses_everything_internal():
    """An unfenced proxy is not an open one.

    With no ``allowed_origins`` the port, scheme and address rules are the only
    ones left — and they are the ones that stop SSRF. A fence narrows further;
    it is not what makes the proxy safe.
    """
    connector = Connector()
    async with running(connector=connector) as proxy:
        assert proxy.allowed_origins == ()
        assert_forbidden(await connect_through(proxy, "127.0.0.1:80"))
        assert_forbidden(await connect_through(proxy, "169.254.169.254:80"))
        assert_forbidden(await connect_through(proxy, "10.0.0.1:8080"))
    assert connector.calls == []


# ── the pin ──────────────────────────────────────────────────────────────


async def test_proxy_pins_ip_against_dns_rebinding():
    """Resolved once, connected to the address — so there is no second answer.

    Three claims in one, and they are the point of the module:

    1. the socket is opened to the *address*, never to the name, so the
       browser's own lookup never happens and cannot be poisoned;
    2. one request causes exactly one lookup;
    3. a resolver that changes its mind to a private address on the next
       request is refused on that next request — the pin is per connection,
       not a cache that goes stale in the unsafe direction.
    """
    resolver = Resolver({"rebind.test": [[PUBLIC_IP], ["127.0.0.1"], [PUBLIC_IP]]})
    connector = Connector()
    async with running(resolver=resolver, connector=connector) as proxy:
        first = await connect_through(proxy, "rebind.test:443")
        assert not first.startswith(b"HTTP/1.1 403"), first[:80]
        assert connector.calls == [
            {
                "ip": PUBLIC_IP,
                "port": 443,
                "server_hostname": "rebind.test",
                "timeout": 2.0,
            }
        ], "the connection did not go to the address that was checked"
        assert resolver.calls == [("rebind.test", 443)], "the name was resolved more than once"

        # The zone now answers with the loopback. The next request is refused,
        # and still nothing was connected to.
        assert_forbidden(await connect_through(proxy, "rebind.test:443"))
        assert len(connector.calls) == 1

        # And it recovers when the zone is honest again: a denial is not a
        # permanent block, it is a judgement on one answer.
        assert not (await connect_through(proxy, "rebind.test:443")).startswith(b"HTTP/1.1 403")
    assert connector.ips == [PUBLIC_IP, PUBLIC_IP]
    assert [d.reason for d in proxy.denials] == ["rebind.test resolves to a loopback address"]


async def test_every_resolved_address_must_be_permitted():
    """One public and one private answer is a rebinding setup, not a choice.

    Which address a connection would pick is the resolver's business and the
    kernel's, so the whole answer is refused rather than filtered down to the
    public one.
    """
    resolver = Resolver(
        {
            "split.test": [[PUBLIC_IP, "127.0.0.1"]],
            "split6.test": [[PUBLIC_IP, "::1"]],
            "meta.test": [[PUBLIC_IP, "169.254.169.254"]],
            "clean.test": [[PUBLIC_IP, SECOND_PUBLIC_IP]],
        }
    )
    connector = Connector()
    async with running(resolver=resolver, connector=connector) as proxy:
        assert_forbidden(await connect_through(proxy, "split.test:443"))
        assert_forbidden(await connect_through(proxy, "split6.test:443"))
        assert_forbidden(await connect_through(proxy, "meta.test:443"))
        assert connector.calls == []
        # All public: permitted, and every address is on the record so an audit
        # can see the rule was applied rather than just the one that was used.
        assert not (await connect_through(proxy, "clean.test:443")).startswith(b"HTTP/1.1 403")
    assert connector.ips == [PUBLIC_IP]
    assert proxy.decisions[-1].target is not None
    assert proxy.decisions[-1].target.resolved == (PUBLIC_IP, SECOND_PUBLIC_IP)


async def test_a_name_that_does_not_resolve_is_refused_not_retried():
    connector = Connector()
    async with running(resolver=Resolver({}), connector=connector) as proxy:
        assert_forbidden(await connect_through(proxy, "nowhere.invalid:443"))
        assert_forbidden(await connect_through(proxy, "empty.test:443"))
    assert connector.calls == []
    assert all("does not resolve" in d.reason for d in proxy.denials)


async def test_a_resolver_that_hangs_is_a_refusal():
    """A lookup that never answers does not hold the errand open forever."""

    async def hangs(host: str, port: int) -> list[str]:
        await asyncio.sleep(30)
        raise AssertionError("the proxy waited out a hung resolver")

    connector = Connector()
    async with running(resolver=hangs, connector=connector, timeout=0.2) as proxy:
        assert_forbidden(await connect_through(proxy, "slow.test:443"))
    assert connector.calls == []
    assert "did not resolve within" in proxy.denials[0].reason


async def test_an_address_literal_is_its_own_pin():
    """A permitted address literal needs no lookup, and gets none."""
    resolver = NeverResolver()
    connector = Connector()
    async with running(resolver=resolver, connector=connector) as proxy:
        assert not (await connect_through(proxy, f"{PUBLIC_IP}:443")).startswith(b"HTTP/1.1 403")
    assert resolver.calls == []
    assert connector.ips == [PUBLIC_IP]


async def test_authorize_is_usable_on_its_own():
    """The decision is a function, so it can be asserted without a socket."""
    proxy = running(resolver=Resolver({"ok.test": [[PUBLIC_IP]]}))
    pinned = await proxy.authorize("https", "ok.test:443")
    assert (pinned.host, pinned.port, pinned.ip) == ("ok.test", 443, PUBLIC_IP)
    assert pinned.origin == "https://ok.test"
    with pytest.raises(EgressDeniedError):
        await proxy.authorize("https", "127.0.0.1:443")
    with pytest.raises(EgressDeniedError):
        await proxy.authorize("https", "ok.test:22")


# ── a tunnel that works ──────────────────────────────────────────────────


async def test_proxy_successful_tunnel():
    """A permitted ``CONNECT`` tunnels bytes both ways, unaltered.

    The upstream is an in-process echo server; the connector reports that the
    proxy asked for the *pinned public address* and then wires the tunnel to
    it. What travels through is not inspected and not modified — this proxy
    authorises where a connection goes, and the browser's TLS session stays
    its own (nothing here terminates TLS).
    """
    server, upstream_port = await echo_server()
    resolver = Resolver({"site.test": [[PUBLIC_IP]]})
    connector = Connector(upstream_port=upstream_port)
    try:
        async with running(resolver=resolver, connector=connector) as proxy:
            request = b"CONNECT site.test:443 HTTP/1.1\r\nHost: site.test:443\r\n\r\n"
            status, reader, writer = await ask(proxy, request)
            assert status == b"HTTP/1.1 200 Connection Established\r\n"
            assert await asyncio.wait_for(reader.readline(), 5) == b"\r\n"  # end of the head

            writer.write(b"hello upstream\n")
            await writer.drain()
            assert await asyncio.wait_for(reader.read(21), 5) == b"echo:hello upstream\n"

            # Both directions, more than once: a tunnel, not a single exchange.
            writer.write(b"again\n")
            await writer.drain()
            assert await asyncio.wait_for(reader.read(12), 5) == b"echo:again\n"
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
        assert connector.ips == [PUBLIC_IP]
        assert connector.calls[0]["server_hostname"] == "site.test"
        assert proxy.denials == ()
    finally:
        server.close()
        await server.wait_closed()


async def test_a_plain_http_request_is_forwarded_rewritten():
    """Absolute-form ``GET http://host/path`` goes upstream in origin form.

    Three rewrites are asserted, and each one is a control:

    * the target becomes a path, because that is what an origin server reads;
    * ``Host`` is the authority that was *authorised*, so the destination
      cannot be told it is somebody else;
    * ``Connection: close`` is forced and ``Proxy-Authorization`` is dropped.
      The forced close is the control that matters: without it a client could
      send a *second* request, to a different host, on a connection this proxy
      has already finished authorising.
    """
    heads: list[bytes] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await reader.readuntil(b"\r\n\r\n")
        heads.append(head)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nhi")
        with contextlib.suppress(Exception):
            await writer.drain()
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    upstream_port = int(server.sockets[0].getsockname()[1])
    resolver = Resolver({"site.test": [[PUBLIC_IP]]})
    connector = Connector(upstream_port=upstream_port)
    try:
        async with running(resolver=resolver, connector=connector) as proxy:
            request = (
                b"GET http://site.test/a/b?c=d HTTP/1.1\r\n"
                b"Host: site.test\r\n"
                b"Proxy-Authorization: Basic c2VjcmV0\r\n"
                b"Proxy-Connection: keep-alive\r\n"
                b"Connection: keep-alive\r\n"
                b"User-Agent: test\r\n\r\n"
            )
            status, _, writer = await ask(proxy, request)
            assert status.startswith(b"HTTP/1.1 200 OK"), status[:80]
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()

    assert len(heads) == 1
    head = heads[0].decode()
    assert head.startswith("GET /a/b?c=d HTTP/1.1\r\n")
    assert "Host: site.test\r\n" in head
    assert "Connection: close\r\n" in head
    assert "Proxy-Authorization" not in head, "a hop credential was forwarded to the destination"
    assert "Proxy-Connection" not in head
    assert "User-Agent: test\r\n" in head
    assert connector.ips == [PUBLIC_IP]


async def test_an_unreachable_upstream_is_a_502_not_a_403():
    """A permitted destination that will not answer is a different failure.

    Worth separating: 403 means "the owner's policy refused this" and 502
    means "the site is down". Conflating them would make a denied-egress alert
    fire on a flaky site, and an outage look like an attack.
    """
    connector = Connector(fail=OSError("connection refused"))
    async with running(resolver=Resolver({"down.test": [[PUBLIC_IP]]}), connector=connector) as p:
        status = await connect_through(p, "down.test:443")
        assert status.startswith(b"HTTP/1.1 502"), status[:80]
    assert connector.ips == [PUBLIC_IP]
    assert p.denials == ()


# ── lifecycle ────────────────────────────────────────────────────────────


async def test_the_proxy_binds_the_loopback_on_an_ephemeral_port():
    """Bound to ``127.0.0.1`` by default: a proxy on ``0.0.0.0`` is an open relay."""
    proxy = running()
    host, port = await proxy.start()
    try:
        assert host == "127.0.0.1"
        assert port > 0
        assert proxy.url == f"http://127.0.0.1:{port}"
        assert proxy.is_running
        assert await proxy.start() == (host, port), "start twice must not rebind"
    finally:
        await proxy.stop()
    assert not proxy.is_running


async def test_there_is_no_url_before_the_proxy_is_listening():
    """A blank url would be handed to ``new_context`` and mean "no proxy".

    That is the one failure the module exists to prevent, so asking for a url
    the proxy does not have raises instead of answering ``""``.
    """
    proxy = running()
    with pytest.raises(RuntimeError):
        _ = proxy.url


async def test_stop_tears_down_an_open_tunnel():
    """A tunnel that outlives the errand is a way out that outlives the errand."""
    server, upstream_port = await echo_server()
    connector = Connector(upstream_port=upstream_port)
    proxy = running(resolver=Resolver({"site.test": [[PUBLIC_IP]]}), connector=connector)
    await proxy.start()
    try:
        request = b"CONNECT site.test:443 HTTP/1.1\r\nHost: site.test:443\r\n\r\n"
        status, reader, writer = await ask(proxy, request)
        assert status.startswith(b"HTTP/1.1 200")
        assert await asyncio.wait_for(reader.readline(), 5) == b"\r\n"  # end of the head
        await asyncio.sleep(0)  # let the handler settle into the relay
        await proxy.stop()
        # The client's half of the tunnel is gone: a read returns EOF rather
        # than hanging or continuing to relay.
        assert await asyncio.wait_for(reader.read(16), timeout=5) == b""
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()
        assert await asyncio.wait_for(reader.read(1), timeout=5) == b""
    finally:
        await proxy.stop()  # idempotent
        server.close()
        await server.wait_closed()


async def test_the_tunnel_ceiling_is_a_503_not_an_unbounded_queue():
    """A page that opens thousands of sockets exhausts its own limit."""
    server, upstream_port = await echo_server()
    connector = Connector(upstream_port=upstream_port)
    proxy = running(
        resolver=Resolver({"site.test": [[PUBLIC_IP]]}), connector=connector, max_tunnels=1
    )
    await proxy.start()
    held: list[Any] = []
    try:
        request = b"CONNECT site.test:443 HTTP/1.1\r\nHost: site.test:443\r\n\r\n"
        status, reader, writer = await ask(proxy, request)
        held.append(writer)
        assert status.startswith(b"HTTP/1.1 200")
        await asyncio.sleep(0.05)
        status2, _, writer2 = await ask(proxy, request)
        held.append(writer2)
        assert status2.startswith(b"HTTP/1.1 503"), status2[:80]
    finally:
        for w in held:
            with contextlib.suppress(Exception):
                w.close()
        await proxy.stop()
        server.close()
        await server.wait_closed()


async def test_denials_are_recorded_but_bounded():
    """The audit list is for an alert and a test, not a log that grows forever."""
    connector = Connector()
    async with running(connector=connector) as proxy:
        for _ in range(3):
            assert_forbidden(await connect_through(proxy, "127.0.0.1:80"))
        assert len(proxy.denials) == 3
        assert all(d.method == "CONNECT" and d.requested == "127.0.0.1:80" for d in proxy.denials)
        # The cap is enforced on the list itself, without needing 300 sockets.
        for i in range(ep._MAX_RECORDED + 50):  # noqa: SLF001
            proxy._record(  # noqa: SLF001
                ep.EgressDecision(allowed=False, method="CONNECT", requested=f"h{i}:443")
            )
        assert len(proxy.decisions) == ep._MAX_RECORDED  # noqa: SLF001


# ── the driver in front of it ────────────────────────────────────────────


class ProxyRecordingTransport:
    """Records the ``proxy_url`` the driver hands to ``new_context``."""

    def __init__(self) -> None:
        self.opened: list[dict[str, Any]] = []

    async def open_session(self, **kwargs: Any) -> Any:
        self.opened.append(kwargs)
        return FakeSession()

    @property
    def proxy_urls(self) -> list[str]:
        return [o.get("proxy_url", "<missing>") for o in self.opened]


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def goto(self, url: str) -> None: ...
    async def fill(self, field: str, value: str) -> None: ...
    async def click(self, selector: str) -> None: ...

    async def text(self) -> str:
        return "page"

    async def origin(self) -> str:
        return "https://bank.com"

    async def close(self) -> None:
        self.closed = True


#: The control channel's path token, as a correctly configured deployment
#: has it: the browser server was started with `--path /<token>` and the
#: application knows the same value, so the endpoint below carries it.
#: tests/unit/test_isolated_browser_driver.py is where the *absence* of it is
#: tested; here it is simply part of a working configuration.
CONTROL_TOKEN = "Oq2tVYbW0yvQcAzpHmJrE4kLsXTd8gNu"
ENDPOINT = f"ws://browser:9222/{CONTROL_TOKEN}"


@pytest.fixture(autouse=True)
def _egress_settings(monkeypatch):
    """Enforcement on and no deployment proxy: the ephemeral-proxy default."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "browser_sandbox_egress_proxy_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_enforce_egress_proxy", True, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_mode", "isolated", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_url", ENDPOINT, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_ws_url", "", raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_token", CONTROL_TOKEN, raising=False)
    monkeypatch.setattr(settings, "browser_sandbox_require_token", True, raising=False)
    return settings


def isolated(transport: Any, **kwargs: Any) -> bsd.IsolatedBrowserDriver:
    kwargs.setdefault("tenant_id", "t1")
    kwargs.setdefault("errand_id", "errand_abc")
    kwargs.setdefault("endpoint_url", ENDPOINT)
    kwargs.setdefault("timeout_seconds", 2.0)
    return bsd.IsolatedBrowserDriver(transport=transport, **kwargs)


async def test_the_driver_puts_an_ephemeral_proxy_in_front_of_every_session():
    """``new_context`` gets a ``proxy``, and it is a proxy that is listening.

    This is the integration claim: without it the module above is a proxy
    nothing uses. The url the transport receives is asserted to be the one the
    driver's own proxy is bound to.
    """
    transport = ProxyRecordingTransport()
    driver = isolated(transport, allowed_origins=["https://bank.com"])
    try:
        await driver.navigate("https://bank.com/login")
        proxy = driver.egress_proxy
        assert proxy is not None and proxy.is_running
        assert transport.proxy_urls == [proxy.url]
        assert transport.proxy_urls[0].startswith("http://127.0.0.1:")
        assert proxy.allowed_origins == ("https://bank.com",)
        # One proxy for the errand, not one per step.
        await driver.read_page()
        assert transport.proxy_urls == [proxy.url]
    finally:
        await driver.close()
    assert not proxy.is_running, "the proxy outlived the errand"
    assert driver.egress_proxy is None


async def test_the_driver_stops_its_proxy_even_when_cleanup_fails():
    """A session that will not close is exactly when a stray listener matters."""

    class StubbornSession(FakeSession):
        async def close(self) -> None:
            raise RuntimeError("the context would not go away")

    class StubbornTransport(ProxyRecordingTransport):
        async def open_session(self, **kwargs: Any) -> Any:
            self.opened.append(kwargs)
            return StubbornSession()

    driver = isolated(StubbornTransport())
    await driver.navigate("https://bank.com/login")
    proxy = driver.egress_proxy
    assert proxy is not None and proxy.is_running
    with pytest.raises(SandboxUnavailableError):
        await driver.close()
    assert not proxy.is_running


async def test_the_driver_uses_a_configured_proxy_and_mints_nothing():
    """A deployment-run proxy is used as-is, and its lifecycle is not ours."""
    transport = ProxyRecordingTransport()
    driver = isolated(transport, proxy_url="http://egress.internal:3128")
    try:
        await driver.navigate("https://bank.com/login")
        assert transport.proxy_urls == ["http://egress.internal:3128"]
        assert driver.egress_proxy is None, "a proxy was minted on top of the configured one"
        assert driver.egress_proxy_url == "http://egress.internal:3128"
    finally:
        await driver.close()


async def test_a_configured_proxy_comes_from_settings_too(_egress_settings, monkeypatch):
    monkeypatch.setattr(
        _egress_settings, "browser_sandbox_egress_proxy_url", "http://egress:3128", raising=False
    )
    assert bsd.configured_egress_proxy_url() == "http://egress:3128"
    transport = ProxyRecordingTransport()
    driver = isolated(transport)
    try:
        await driver.navigate("https://bank.com/login")
        assert transport.proxy_urls == ["http://egress:3128"]
    finally:
        await driver.close()


async def test_an_unusable_configured_proxy_does_not_mean_go_direct(_egress_settings, monkeypatch):
    """A mistyped proxy address falls back to the *enforced* path, not to none.

    Reading "not a usable URL" as "no proxy needed" would turn a typo into
    unrestricted browser egress.
    """
    for bad in ("not-a-url", "ws://egress:3128", "http://", "   "):
        monkeypatch.setattr(
            _egress_settings, "browser_sandbox_egress_proxy_url", bad, raising=False
        )
        assert bsd.configured_egress_proxy_url() == "", bad
    monkeypatch.setattr(
        _egress_settings, "browser_sandbox_egress_proxy_url", "not-a-url", raising=False
    )
    transport = ProxyRecordingTransport()
    driver = isolated(transport)
    try:
        await driver.navigate("https://bank.com/login")
        assert driver.egress_proxy is not None, "an unusable setting left the browser unproxied"
        assert transport.proxy_urls == [driver.egress_proxy.url]
    finally:
        await driver.close()


async def test_the_errand_refuses_to_run_when_no_proxy_can_be_started():
    """Enforcement on and no proxy is a closed failure, not a direct browser."""

    def will_not_start(**kwargs: Any) -> Any:
        raise OSError("address already in use")

    transport = ProxyRecordingTransport()
    driver = isolated(transport, proxy_factory=will_not_start)
    try:
        with pytest.raises(SandboxUnavailableError) as caught:
            await driver.navigate("https://bank.com/login")
        assert "egress proxy" in str(caught.value)
        assert transport.opened == [], "a session was opened without a proxy in front of it"
    finally:
        await driver.close()


async def test_a_proxy_that_hangs_on_start_is_also_a_refusal():
    class Hangs:
        def __init__(self, **kwargs: Any) -> None:
            self.is_running = False

        async def start(self) -> tuple[str, int]:
            await asyncio.sleep(30)
            raise AssertionError("the driver waited out a hung proxy")

        async def stop(self) -> None: ...

    transport = ProxyRecordingTransport()
    driver = isolated(transport, proxy_factory=Hangs, timeout_seconds=0.2)
    try:
        with pytest.raises(SandboxUnavailableError):
            await driver.navigate("https://bank.com/login")
        assert transport.opened == []
    finally:
        await driver.close()


async def test_enforcement_can_be_turned_off_only_deliberately(_egress_settings, monkeypatch):
    """Off means off — and the log says the browser is going direct.

    The setting exists for a deployment that enforces egress at the network
    layer instead. It defaults to on, it is on when the setting is missing
    entirely, and turning it off is visible in the record of the errand.
    """
    assert bsd.egress_proxy_enforced() is True
    monkeypatch.delattr(_egress_settings, "browser_sandbox_enforce_egress_proxy", raising=False)
    assert bsd.egress_proxy_enforced() is True, "a missing setting must still enforce"
    monkeypatch.setattr(
        _egress_settings, "browser_sandbox_enforce_egress_proxy", False, raising=False
    )
    assert bsd.egress_proxy_enforced() is False

    transport = ProxyRecordingTransport()
    driver = isolated(transport)
    try:
        assert driver.egress_enforced is False
        await driver.navigate("https://bank.com/login")
        assert transport.proxy_urls == [""]
        assert driver.egress_proxy is None
    finally:
        await driver.close()


async def test_a_transport_that_cannot_honour_the_proxy_fails_closed():
    """An old transport with no ``proxy_url`` parameter does not get a session.

    A ``TypeError`` from the call is a failure to establish a *contained*
    browser, and every one of those is one ``SandboxUnavailableError``. The
    alternative — dropping the argument when the transport will not take it —
    would silently open an unproxied session.
    """

    class OldTransport:
        def __init__(self) -> None:
            self.attempts = 0

        async def open_session(
            self, *, endpoint_url: str, tenant_id: str, errand_id: str, timeout: float
        ) -> Any:
            self.attempts += 1
            return FakeSession()

    transport = OldTransport()
    driver = isolated(transport)
    try:
        with pytest.raises(SandboxUnavailableError):
            await driver.navigate("https://bank.com/login")
        assert transport.attempts == 0
    finally:
        await driver.close()


async def test_the_errand_fence_reaches_the_proxy(monkeypatch):
    """``get_driver`` hands the plan's fence to the proxy in front of the session.

    The fence can only narrow, which is why it is safe to take from the plan —
    and taking it is what makes the origin check apply to every redirect hop
    and sub-resource rather than only to the urls the plan named.
    """
    from life_graph.tools import errand

    monkeypatch.setattr(errand, "_driver_override", None, raising=False)
    driver = errand.get_driver(
        errand_id="errand_1", tenant_id="t1", allowed_origins=["https://bank.com", "*.bank.com"]
    )
    assert isinstance(driver, bsd.IsolatedBrowserDriver)
    try:
        assert driver._allowed_origins == ("https://bank.com", "*.bank.com")  # noqa: SLF001
        proxy = BrowserEgressProxy(allowed_origins=driver._allowed_origins)  # noqa: SLF001
        assert proxy.allowed_origins == ("https://bank.com", "*://*.bank.com")
    finally:
        await driver.close()


# ── running it as a service ─────────────────────────────────────────────
# The ephemeral proxy the driver mints binds the application's loopback, and a
# container on an `internal: true` bridge cannot reach the application's
# loopback. The deployed stack therefore runs this module as its own process
# (`python -m life_graph.services.browser_egress_proxy`), which is what the
# `egress` service in compose.sandbox.yaml does.


def _args(argv: list[str]) -> Any:
    return ep._build_parser().parse_args(argv)  # noqa: SLF001


def test_the_entrypoint_defaults_to_the_loopback_and_the_proxy_port():
    """A default that binds every interface would be an open relay by typo."""
    args = _args([])
    assert args.host == "127.0.0.1"
    assert args.port == ep.DEFAULT_LISTEN_PORT
    proxy = ep.proxy_from_args(args)
    assert proxy.is_running is False
    # No fence by default: the errand's own is per-errand, and the address,
    # port and scheme rules are the ones that stop SSRF.
    assert proxy.allowed_origins == ()
    assert proxy._allowed_ports == frozenset(ep.DEFAULT_ALLOWED_PORTS)  # noqa: SLF001


def test_the_entrypoint_takes_the_host_port_fence_and_ports_it_is_given():
    args = _args(
        [
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--allowed-origin",
            "https://bank.com",
            "--allowed-origin",
            "*.bank.com",
            "--allowed-port",
            "443",
            "--max-tunnels",
            "8",
            "--timeout",
            "5",
        ]
    )
    proxy = ep.proxy_from_args(args)

    assert proxy._bind_host == "0.0.0.0" and proxy._bind_port == 8080  # noqa: SLF001
    assert proxy.allowed_origins == ("https://bank.com", "*://*.bank.com")
    # Narrowing the port list is safe and is honoured exactly: 80 is no
    # longer permitted because the deployment said 443 only.
    assert proxy._allowed_ports == frozenset({443})  # noqa: SLF001
    assert proxy._max_tunnels == 8  # noqa: SLF001


def test_the_entrypoint_reads_its_configuration_from_the_environment(monkeypatch):
    """So the compose service is configured without rewriting its command.

    The names are deliberately unprefixed: a ``LIFE_GRAPH_*`` variable is
    application configuration and ``services/dev/sandbox.py`` refuses to pass any
    of it into a sandbox container.
    """
    monkeypatch.setenv(ep.ENV_HOST, "0.0.0.0")
    monkeypatch.setenv(ep.ENV_PORT, "9999")
    monkeypatch.setenv(ep.ENV_ORIGINS, "https://a.test, https://b.test")
    monkeypatch.setenv(ep.ENV_PORTS, "443,8443")

    proxy = ep.proxy_from_args(_args([]))

    assert proxy._bind_host == "0.0.0.0" and proxy._bind_port == 9999  # noqa: SLF001
    assert proxy.allowed_origins == ("https://a.test", "https://b.test")
    assert proxy._allowed_ports == frozenset({443, 8443})  # noqa: SLF001

    # A flag still wins over the environment.
    assert ep.proxy_from_args(_args(["--port", "7000"]))._bind_port == 7000  # noqa: SLF001
    assert not ep.proxy_from_args(_args(["--allowed-origin", "https://c.test"])).allowed_origins[1:]


async def test_the_service_serves_until_it_is_asked_to_stop():
    """``serve_forever`` listens, then tears everything down on SIGTERM.

    SIGTERM is how a container runtime asks (``docker compose down``). The
    assertion that matters is the one after: the listener is *gone*, because a
    proxy that outlived the stack would be a way out that outlived it.
    """
    proxy = BrowserEgressProxy(host="127.0.0.1", port=0)
    task = asyncio.create_task(ep.serve_forever(proxy))
    for _ in range(100):
        if proxy.is_running:
            break
        await asyncio.sleep(0.01)
    assert proxy.is_running, "the service never started listening"
    host, port = proxy._host, proxy._port  # noqa: SLF001

    os.kill(os.getpid(), signal.SIGTERM)
    assert await asyncio.wait_for(task, timeout=5) == 0
    assert not proxy.is_running
    with pytest.raises(OSError):
        socket.create_connection((host, port), timeout=1).close()


async def test_a_service_on_a_real_interface_says_so(caplog):
    """Binding more than the loopback is an open relay, and it is logged.

    The container has to do it — a container is reached on its bridge address,
    not on its loopback — and what contains it is the bridge having no other
    member and no gateway, not the bind. Something that is only safe because
    of the network around it should be visible in the log of the process that
    did it.
    """
    proxy = BrowserEgressProxy(host="0.0.0.0", port=0)  # noqa: S104
    with caplog.at_level(logging.WARNING, logger=ep.logger.name):
        task = asyncio.create_task(ep.serve_forever(proxy))
        for _ in range(100):
            if proxy.is_running:
                break
            await asyncio.sleep(0.01)
        assert proxy.is_running
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=5)

    assert "relay" in caplog.text


def test_the_module_runs_as_a_process_and_refuses_the_same_destinations():
    """The real entrypoint, in a real process, over a real socket.

    ``python -m life_graph.services.browser_egress_proxy`` is what the compose
    service runs, so this test is the one that proves the deployed shape of
    the proxy enforces the policy rather than only the in-process one. The
    destinations are the three that matter most: the cloud metadata endpoint,
    the loopback (where the application's own postgres and redis answer) and a
    non-web port — in this case 9222, the sandbox browser's own control
    channel, which an errand reaching would be the browser driving itself.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "life_graph.services.browser_egress_proxy", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        host, port = _wait_for_listener(proc)
        for authority in (
            "169.254.169.254:80",
            "127.0.0.1:80",
            "metadata.google.internal:80",
            "browser:9222",
            "10.0.0.5:443",
            "[::1]:443",
        ):
            with contextlib.closing(socket.create_connection((host, port), timeout=5)) as sock:
                sock.sendall(f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n".encode())
                answer = sock.recv(64)
            assert answer.startswith(b"HTTP/1.1 403"), f"{authority} was not refused: {answer!r}"

        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0, "the service did not shut down cleanly"
    finally:
        if proc.poll() is None:  # pragma: no cover - only on a failed assertion
            proc.kill()
            proc.wait(timeout=10)


def _wait_for_listener(proc: subprocess.Popen, timeout: float = 30.0) -> tuple[str, int]:
    """``(host, port)`` the subprocess reported, read from its own log line.

    Parsed rather than guessed: picking a free port and hoping nothing else
    takes it is how a test suite becomes flaky, and ``--port 0`` means the
    process is the only one that knows the answer.
    """
    pattern = re.compile(r"serving on ([0-9a-fA-F:.]+):(\d+)")
    deadline = time.monotonic() + timeout
    assert proc.stdout is not None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        found = pattern.search(line)
        if found:
            return found.group(1), int(found.group(2))
    raise AssertionError("the egress proxy service never reported a listening address")


def test_the_deployed_proxy_url_is_the_one_the_driver_would_point_at(monkeypatch):
    """The compose service, the setting and the driver agree on one address.

    ``http://egress:8080`` is a name that only resolves on the egress bridge,
    which is the point: the proxy is reachable from the browser container and
    from nowhere else.
    """
    from life_graph.config import settings
    from life_graph.services.dev import sandbox as sb

    url = f"http://{sb.EGRESS_SERVICE}:{sb.EGRESS_PROXY_PORT}"
    monkeypatch.setattr(settings, "browser_sandbox_egress_proxy_url", url, raising=False)
    assert bsd.configured_egress_proxy_url() == url
    assert sb.EGRESS_PROXY_PORT == ep.DEFAULT_LISTEN_PORT

    compose = yaml.safe_load((REPO_ROOT / "compose.sandbox.yaml").read_text())
    egress = compose["services"][sb.EGRESS_SERVICE]
    assert egress["expose"] == [str(sb.EGRESS_PROXY_PORT)]


def test_the_shared_service_carries_no_per_errand_fence_and_that_is_recorded():
    """A limitation, written as a test so it cannot be forgotten.

    A long-lived shared proxy does not know which errand a connection belongs
    to, so it cannot apply that errand's approved origins; only a static
    ``--allowed-origin`` fence or none. What it *does* apply to every request
    is the part that stops SSRF, rebinding and metadata access. The errand's
    own fence stays with the application-level check in ``tools/errand.py``
    and with the ephemeral per-errand proxy. ``docs/AI_WORK_ORDER.md`` §10
    records this as an open gap; this test fails if someone later believes the
    deployed proxy is narrowing by errand when it is not.
    """
    proxy = ep.proxy_from_args(_args([]))
    assert proxy.allowed_origins == ()
    assert proxy._tenant_id == "" and proxy._errand_id == ""  # noqa: SLF001


# ── the compose stack ────────────────────────────────────────────────────


def test_workspace_cannot_access_browser_ws_in_compose():
    """The workspace is not told where the browser's control endpoint is.

    Playwright's browser-server websocket is unauthenticated, so that endpoint
    is not a location — it is a remote-code-execution handle on a browser that
    may be holding the owner's logged-in banking session. The workspace runs
    errand work nobody vetted (``docs/AI_WORK_ORDER.md`` §3: "do not expose an
    unauthenticated browser debugging/WebSocket endpoint to workspace code").

    An absence is checked four ways, because a renamed variable pointing at
    the same place would pass the first: the variable is gone, no value in the
    workspace's environment names the browser or its port, ``browser`` still
    only ``expose``s 9222 — on an internal bridge, on no host interface — and
    the workspace is on no bridge the browser is on, so the endpoint is not
    merely un-named to it but unroutable from it. The guessable-address gap
    this test used to record is closed twice over now: by that network split
    and by the path token the control channel requires
    (``browser_sandbox_require_token``, tested in
    tests/unit/test_isolated_browser_driver.py).
    """
    compose = yaml.safe_load((REPO_ROOT / "compose.sandbox.yaml").read_text())
    workspace = compose["services"]["workspace"]
    env = workspace.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env if "=" in item)

    assert "SANDBOX_BROWSER_WS_URL" not in env
    for key, value in env.items():
        text = str(value)
        assert "9222" not in text, f"workspace {key} names the browser port"
        assert "browser" not in text.lower(), f"workspace {key} names the browser"
        assert "ws://" not in text.lower(), f"workspace {key} carries a websocket url"

    browser = compose["services"]["browser"]
    assert browser["expose"] == ["9222"]
    assert "ports" not in browser, "the browser control endpoint is published to the host"

    nets = compose["networks"]
    browser_nets = {str(nets[n].get("name") or n) for n in browser["networks"]}
    workspace_nets = {str(nets[n].get("name") or n) for n in workspace["networks"]}
    assert not browser_nets & workspace_nets, "the workspace shares a bridge with the browser"
    # Every bridge the browser is on is internal: its only way out is the
    # proxy, which is a different container on a different network.
    for name in browser["networks"]:
        assert nets[name]["internal"] is True, f"the browser is on {name}, which has a gateway"
